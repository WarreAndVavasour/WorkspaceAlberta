"""classify_tender: PDF split, Jev pipeline, service wiring. No network.

Every Jev request goes to a deterministic fake that answers by keyword (patched over
``urlopen`` in procurement_core.requirements.jev, so the real request building, retry and
parsing code runs). Supabase Storage is the in-memory fake from test_bid_room_uploads.
Outbound sockets are refused for the whole module.
"""

import asyncio
import contextlib
import io
import json
import logging
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from email.message import Message
from pathlib import Path
from unittest.mock import AsyncMock, patch
from urllib.error import HTTPError

os.environ.setdefault("CANADABUYS_DATA_DIR", tempfile.mkdtemp(prefix="classify-tender-tests-"))
os.environ.setdefault("CANADABUYS_LOAD_ENV_FILE", "0")

import pymupdf  # noqa: E402

from procurement_core import auth, bid_room_uploads as up, service, storage  # noqa: E402
from procurement_core.requirements import NoTextError, child, classify_documents, jev, pipeline, tags  # noqa: E402
from procurement_core.requirements.extract import extract_units  # noqa: E402
from tests.test_bid_room_uploads import ENV, FIXTURE, PDF_NAME, REFERENCE, TENANT, FakeStorage  # noqa: E402

API_KEY = "ts_test_SECRET_KEY_0123456789"

_no_network = None


def setUpModule():
    global _no_network

    def refuse(*_args, **_kwargs):
        raise AssertionError("tests must not open network connections")

    _no_network = [patch.object(socket.socket, "connect", refuse), patch.object(socket, "create_connection", refuse),
                   patch.object(socket, "getaddrinfo", refuse)]
    for item in _no_network:
        item.start()


def tearDownModule():
    for item in _no_network:
        item.stop()


# --------------------------------------------------------------------------- test tender

INSTRUCTIONS = [
    "Proposals must be received before the Closing Time of 2:00 PM Mountain Time on November 14, 2026 "
    "through the Alberta Purchasing Connection portal.",
    "A mandatory site visit will be held on October 28, 2026 at 10:00 AM at the water station. "
    "Proponents who do not attend the site visit will be disqualified.",
    "The evaluation committee will review each proposal against the published criteria and weightings.",
]
BID_FORM = [
    "Legal name of Proponent, business address and GST number: ______________________________",
    "Provide a list of Key Personnel with resumes and years of relevant experience. This information is mandatory.",
    "The sample bonding letter in Appendix F is provided for reference only and is not part of the bid.",
]
CONTRACT = [
    "The Contractor shall provide a schedule of values for progress payments after award of the contract.",
    "The Contractor shall maintain commercial general liability insurance of not less than $5,000,000.",
]
PAGES = [("INSTRUCTIONS TO PROPONENTS", INSTRUCTIONS), ("BID FORM", BID_FORM), ("CONTRACT AGREEMENT", CONTRACT)]


def make_pdf(pages=PAGES, blank_pages: int = 0) -> bytes:
    doc = pymupdf.open()
    for heading, paragraphs in pages:
        page = doc.new_page(width=612, height=792)
        page.insert_text((72, 90), heading, fontsize=16)
        y = 120
        for text in paragraphs:
            page.insert_textbox(pymupdf.Rect(72, y, 540, y + 60), text, fontsize=10)
            y += 90
    for _ in range(blank_pages):
        doc.new_page(width=612, height=792)
    data = doc.tobytes()
    doc.close()
    return data


# --------------------------------------------------------------------------- fake Jev

L0_RULES = [  # (keyword, label, in_bid, mandatory)
    ("Closing Time", "submission_instruction", 0.2, 0.3),
    ("site visit", "attendance", 0.2, 0.9),
    ("Legal name of Proponent", "form_field", 0.9, 0.2),
    ("Key Personnel", "experience_reference", 0.9, 0.8),
    ("reference only", "attach_document", 0.8, 0.1),        # L1 rejects it
    ("schedule of values", "pricing", 0.7, 0.1),             # dropped by the page gate
    ("liability insurance", "compliance_confirm", 0.2, 0.6),  # dropped by the unit gate
]
L1_RULES = [
    ("Closing Time", "closing_deadline"),
    ("site visit", "mandatory_site_visit"),
    ("Legal name", "legal_name_address"),
    ("Key Personnel", "key_personnel"),
    ("reference only", "not_a_bid_requirement"),
    ("schedule of values", "lump_sum"),
]


def choice(options, picked):
    probs = {k: (0.9 if k == picked else 0.1 / max(1, len(options) - 1)) for k in options}
    return {"choice": picked, "probabilities": probs, "confidence": 0.9}


def answer(payload: dict) -> dict:
    questions, state = payload["questions"], payload["state"]
    if "response_type" in questions:
        label, in_bid, mandatory = "none", 0.05, 0.05
        for keyword, *rule in L0_RULES:
            if keyword in state["clause"]:
                label, in_bid, mandatory = rule
                break
        answers = {"response_type": choice(questions["response_type"]["criteria"], label),
                   "in_bid": {"noul": in_bid}, "mandatory": {"noul": mandatory}}
    elif "document_part" in questions:
        text = state["page_text"]
        part, bid = ("bid_forms", 0.9) if "Legal name" in text else ("bid_instructions", 0.6) \
            if "Closing Time" in text else ("contract_terms", 0.1)
        answers = {"document_part": choice(questions["document_part"]["criteria"], part), "bid_content": {"noul": bid}}
    else:
        options = questions["sub_tag"]["criteria"]
        picked = next((sub for keyword, sub in L1_RULES if keyword in state["clause"] and sub in options),
                      [k for k in options if k.startswith("other_")][0])
        answers = {"sub_tag": choice(options, picked)}
    return {"answers": answers, "model": "jev-1.13.0", "usage": {"input_tokens": 100}}


class FakeResponse:
    def __init__(self, body: dict):
        self._data = json.dumps(body).encode("utf-8")
        self.headers = Message()

    def read(self, *_args):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


class FakeJev:
    """Stands in for ``urlopen`` inside procurement_core.requirements.jev."""

    def __init__(self, delay=None, fail=None):
        self.lock = threading.Lock()
        self.requests: list[dict] = []
        self.auth_headers: set[str] = set()
        self.delay = delay or (lambda payload: 0)
        self.fail = fail or (lambda payload, n: None)

    def __call__(self, request, timeout=None):
        assert request.full_url == jev.API_URL, request.full_url
        assert request.get_method() == "POST"
        payload = json.loads(request.data)
        with self.lock:
            self.requests.append(payload)
            self.auth_headers.add(request.get_header("Authorization"))
            n = len(self.requests)
        error = self.fail(payload, n)
        if error is not None:
            raise error
        pause = self.delay(payload)
        if pause:
            time.sleep(pause)
        return FakeResponse(answer(payload))


def http_error(code: int, body: bytes = b"", headers: dict | None = None) -> HTTPError:
    message = Message()
    for key, value in (headers or {}).items():
        message[key] = value
    return HTTPError(jev.API_URL, code, "error", message, io.BytesIO(body))


class JevTestCase(unittest.TestCase):
    def setUp(self):
        self.fake = FakeJev()
        self.urlopen = patch.object(jev, "urlopen", self.fake)
        self.urlopen.start()
        self.addCleanup(self.urlopen.stop)
        self.pdf = make_pdf()

    def classify(self, files=None, seconds=60.0, **kwargs):
        return classify_documents(files or [("tender.pdf", self.pdf)], deadline=time.monotonic() + seconds,
                                  api_key=API_KEY, **kwargs)


# --------------------------------------------------------------------------- split

class ExtractTest(unittest.TestCase):
    def test_units_from_bytes_match_the_pipeline_splitter(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "label_requirements", Path(__file__).resolve().parents[1] / "pipelines" / "requirement_classifier" / "label_requirements.py")
        lr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lr)
        pdf = make_pdf()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "t.pdf"
            path.write_bytes(pdf)
            from_path = lr.extract_units(path)
        from_bytes = extract_units(pdf)
        self.assertEqual(from_path, from_bytes)
        units, stats = from_bytes
        self.assertEqual(stats, {"pages": 3, "pages_without_text": 0, "units": len(BID_FORM + INSTRUCTIONS + CONTRACT)})
        self.assertEqual(units[0]["section"], "INSTRUCTIONS TO PROPONENTS")
        self.assertIn("Legal name of Proponent", units[3]["text"])
        self.assertEqual(units[3]["page"], 2)
        self.assertIs(lr.RESPONSE_TYPES, tags.RESPONSE_TYPES)  # one copy

    def test_max_pages_reads_only_the_first_pages(self):
        units, stats = extract_units(make_pdf(), max_pages=1)
        self.assertEqual((stats["pages"], stats["pages_in_file"]), (1, 3))
        self.assertEqual({u["page"] for u in units}, {1})


# --------------------------------------------------------------------------- pipeline

class PipelineTest(JevTestCase):
    def test_requirements_tags_gates_and_order(self):
        result = self.classify()
        self.assertEqual(result["status"], "complete", result["warnings"])
        by_tag = {q["tag"]: q for q in result["requirements"]}
        self.assertEqual(set(by_tag), {
            "submission_instruction.closing_deadline", "attendance.mandatory_site_visit",
            "form_field.legal_name_address", "experience_reference.key_personnel",
        })
        # unit gate: compliance_confirm (in_bid 0.2) never reaches L1; attendance and
        # submission_instruction are exempt from the in_bid gate.
        l1_clauses = [r["state"]["clause"] for r in self.fake.requests if "sub_tag" in r["questions"]]
        self.assertFalse(any("liability insurance" in c for c in l1_clauses))
        # page gate: the pricing clause passes the unit gate but sits on a contract page.
        self.assertFalse(any("schedule of values" in c for c in l1_clauses))
        counts = result["counts"]
        self.assertEqual(counts["units_gated"], 6)
        self.assertEqual(counts["units_after_page_gate"], 5)
        self.assertEqual(counts["rejected_by_l1"], 1)
        self.assertEqual(counts["requirements"], 4)
        self.assertEqual(counts["pages_gated"], 2)
        # routing comes from the tag library, mandatory first, then lead time.
        people = by_tag["experience_reference.key_personnel"]
        self.assertTrue(people["mandatory"])
        self.assertEqual((people["connector"], people["lead_time"], people["answer_source"]),
                         ("project_and_people_records", "days", "person_input"))
        self.assertEqual(people["pages"], [{"document": "tender.pdf", "page": 2}])
        self.assertEqual(people["evidence"][0]["page"], 2)
        self.assertEqual([q["id"] for q in result["requirements"]], ["R01", "R02", "R03", "R04"])
        self.assertEqual([q["mandatory"] for q in result["requirements"]], [True, True, False, False])
        self.assertEqual(result["requirements"][0]["tag"], "experience_reference.key_personnel")  # days > minutes
        for q in result["requirements"]:
            for item in q["evidence"]:
                self.assertLessEqual(len(item["text"]), 240)
                self.assertIsInstance(item["page"], int)
        # cost from reported usage tokens
        calls = len(self.fake.requests)
        self.assertEqual(counts["classifier_calls"], calls)
        self.assertEqual(result["cost"]["input_tokens"], 100 * calls)
        self.assertAlmostEqual(result["cost"]["usd"], round(100 * calls / 1e6 * 0.042, 4))
        self.assertEqual(result["model"], "jev-1.13.0")

    def test_requests_use_the_shared_questions(self):
        self.classify()
        l0 = [r for r in self.fake.requests if "response_type" in r["questions"]]
        self.assertEqual(l0[0]["questions"], jev.QUESTIONS)
        self.assertEqual(list(l0[0]["questions"]["response_type"]["criteria"])[-1], "none")
        l1 = [r for r in self.fake.requests if "sub_tag" in r["questions"]]
        self.assertTrue(all(list(r["questions"]["sub_tag"]["criteria"])[-1] == "not_a_bid_requirement" for r in l1))

    def test_reject_option_drops_the_unit(self):
        result = self.classify()
        self.assertFalse(any(q["tag"].startswith("attach_document") for q in result["requirements"]))
        evidence = " ".join(e["text"] for q in result["requirements"] for e in q["evidence"])
        self.assertNotIn("reference only", evidence)

    def test_key_is_sent_only_in_the_header_and_never_output_or_logged(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        root = logging.getLogger()
        root.addHandler(handler)
        old_level = root.level
        root.setLevel(logging.DEBUG)
        stdout, stderr = io.StringIO(), io.StringIO()
        # A non-retried error whose body echoes the key: the warning must carry it redacted.
        self.fake.fail = lambda payload, n: http_error(400, f"echo {API_KEY}".encode()) if n == 1 else None
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = self.classify()
                markdown = pipeline.render_markdown(result, reference="TEST")
        finally:
            root.removeHandler(handler)
            root.setLevel(old_level)
        self.assertEqual(self.fake.auth_headers, {f"Bearer {API_KEY}"})
        self.assertTrue(any("echo [redacted]" in w for w in result["warnings"]), result["warnings"])
        self.assertEqual(result["status"], "partial")
        self.assertFalse(any(API_KEY in json.dumps(r) for r in self.fake.requests))
        for text in (json.dumps(result), markdown, stream.getvalue(), stdout.getvalue(), stderr.getvalue()):
            self.assertNotIn(API_KEY, text)

    def test_deadline_returns_a_labelled_partial_result(self):
        # Clauses on the contract page answer slowly; L0 must stop and leave time for L1.
        self.fake.delay = lambda payload: 2.5 if "Contractor shall" in payload["state"].get("clause", "") else 0
        with patch.object(pipeline, "MIN_L1_SECONDS", 2.0):
            started = time.monotonic()
            result = self.classify(seconds=6.0, concurrency=4)
        self.assertLess(time.monotonic() - started, 6.0)
        self.assertEqual(result["status"], "partial")
        self.assertTrue(any("Time limit reached" in w for w in result["warnings"]), result["warnings"])
        self.assertIn("form_field.legal_name_address", {q["tag"] for q in result["requirements"]})
        self.assertIn("Partial result", pipeline.render_markdown(result))

    def test_page_and_unit_limits_warn(self):
        result = self.classify(max_pages=2)
        self.assertEqual(result["status"], "partial")
        self.assertTrue(any("only the first 2 of 3 pages" in w for w in result["warnings"]))
        self.assertEqual(result["counts"]["pages"], 2)
        result = self.classify(max_units=4)
        self.assertTrue(any("only the first 4 were classified" in w for w in result["warnings"]))
        self.assertEqual(result["counts"]["units"], 4)
        result = self.classify(files=[("a.pdf", self.pdf), ("b.pdf", self.pdf)], max_pages=3)
        self.assertTrue(any("b.pdf: skipped, the 3-page limit" in w for w in result["warnings"]))

    def test_scanned_and_non_pdf_files_are_reported(self):
        scanned = make_pdf(pages=PAGES[:1], blank_pages=3)
        result = self.classify(files=[("scan.pdf", scanned), ("pricing.xlsx", b"PK\x03\x04data")])
        self.assertTrue(any("scan.pdf" in w and "no text layer" in w for w in result["warnings"]))
        self.assertTrue(any("pricing.xlsx: skipped, not a PDF" in w for w in result["warnings"]))
        sent = len(self.fake.requests)
        with self.assertRaises(NoTextError):
            self.classify(files=[("blank.pdf", make_pdf(pages=[], blank_pages=2))])
        self.assertEqual(len(self.fake.requests), sent)  # nothing was sent for a file without text

    def test_multiple_documents_keep_their_own_pages(self):
        result = self.classify(files=[("a.pdf", self.pdf), ("b.pdf", make_pdf(pages=PAGES[1:2]))])
        people = next(q for q in result["requirements"] if q["tag"] == "experience_reference.key_personnel")
        self.assertEqual(people["pages"], [{"document": "a.pdf", "page": 2}, {"document": "b.pdf", "page": 1}])
        self.assertIn("a.pdf p. 2; b.pdf p. 1", pipeline.render_markdown(result))


SLEEP = [sys.executable, "-c", "import sys, time; sys.stdin.buffer.read(); time.sleep(30)"]
EMPTY_RESULT = ('{"units": [], "stats": {"pages": 0, "pages_without_text": 0, "pages_in_file": 0, '
                '"empty_pages": []}}')


class ChildProcessTest(JevTestCase):
    """PDF parsing runs in a separate process with limits, never in the service process."""

    def run_with(self, commands: dict, timeout: float | None = None, **kwargs):
        """Classify, replacing the worker command (and optionally the timeout) for the named files."""
        real = child.extract_in_child
        override = timeout
        names = {}

        def fake_extract(name, data, max_pages, deadline):
            names[threading.get_ident()] = name
            return original_extract(name, data, max_pages, deadline)

        def extract_in_child(data, *, max_pages, timeout):
            name = names[threading.get_ident()]
            if name in commands:
                return real(data, max_pages=max_pages, timeout=override or timeout, command=commands[name])
            return real(data, max_pages=max_pages, timeout=timeout)

        original_extract = pipeline._extract
        with patch.object(pipeline, "_extract", fake_extract), \
                patch.object(child, "extract_in_child", extract_in_child):
            return self.classify(**kwargs)

    def test_happy_path_uses_the_real_worker_not_the_service_process(self):
        units, stats = child.extract_in_child(self.pdf, max_pages=800, timeout=60)
        self.assertEqual((units, stats), extract_units(self.pdf, max_pages=800))
        boom = AssertionError("PDF parsed in the service process")
        with patch("procurement_core.requirements.extract.extract_units", side_effect=boom), \
                patch("procurement_core.requirements.extract._open", side_effect=boom):
            result = self.classify()
        self.assertEqual(result["status"], "complete", result["warnings"])
        self.assertEqual(result["counts"]["requirements"], 4)

    def test_worker_command_is_isolated_and_limited(self):
        command = child.worker_command(800, 42.2)
        self.assertEqual(command[:4], [sys.executable, "-I", "-B", str(child.WORKER)])
        self.assertEqual(command[4:], ["800", "43", str(child.MEMORY_LIMIT_BYTES)])
        self.assertEqual(child.MEMORY_LIMIT_BYTES, 1536 * 1024 * 1024)

    def test_child_env_has_no_secrets(self):
        secrets = {"TYPESAFE_API_KEY": API_KEY, "SUPABASE_SERVICE_ROLE_KEY": "srk", "COHERE_API_KEY": "ck",
                   "E2B_API_KEY": "ek", "PYTHONPATH": "/evil", "HOME": "/root"}
        with patch.dict(os.environ, secrets):
            env = child.child_env()
            self.assertTrue(set(env) <= set(child.ENV_ALLOWLIST), env)
            self.assertNotIn(API_KEY, json.dumps(env))
            # and the process really does not see it
            probe = [sys.executable, "-c",
                     "import os, sys; sys.stdin.buffer.read(); "
                     "sys.exit(5) if any(k in os.environ for k in ('TYPESAFE_API_KEY', 'SUPABASE_SERVICE_ROLE_KEY', "
                     f"'COHERE_API_KEY', 'E2B_API_KEY', 'PYTHONPATH')) else print({EMPTY_RESULT!r})"]
            with patch.object(child.subprocess, "Popen", wraps=child.subprocess.Popen) as popen:
                self.assertEqual(child.extract_in_child(self.pdf, max_pages=1, timeout=30, command=probe)[0], [])
                self.assertEqual(child.extract_in_child(self.pdf, max_pages=1, timeout=30)[1]["pages"], 1)
        for call in popen.call_args_list:
            self.assertEqual(call.kwargs["env"], env)
            self.assertTrue(call.kwargs["start_new_session"])

    def test_timeout_kills_the_process_group_and_skips_only_that_file(self):
        with tempfile.TemporaryDirectory() as folder:
            pidfile = Path(folder) / "grandchild.pid"
            spawn = [sys.executable, "-c",
                     "import subprocess, sys, time; sys.stdin.buffer.read(); "
                     "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
                     f"open({str(pidfile)!r}, 'w').write(str(p.pid)); time.sleep(60)"]
            started = time.monotonic()
            result = self.run_with({"slow.pdf": spawn}, timeout=1.5,
                                   files=[("slow.pdf", self.pdf), ("tender.pdf", self.pdf)])
            self.assertLess(time.monotonic() - started, 15)
            self.assertIn("slow.pdf: skipped, the PDF took too long to read.", result["warnings"])
            self.assertEqual([d["document"] for d in result["documents"]], ["tender.pdf"])
            self.assertEqual(result["counts"]["requirements"], 4)
            grandchild = int(pidfile.read_text())
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:  # gone, or a zombie waiting for init
            try:
                state = Path(f"/proc/{grandchild}/stat").read_text().split(")")[-1].split()[0]
            except (FileNotFoundError, ProcessLookupError):
                break
            if state == "Z":
                break
            time.sleep(0.1)
        else:
            self.fail("the worker's child process survived the timeout")

    def test_crash_garbage_and_worker_errors_are_warnings(self):
        crash = [sys.executable, "-c", "import sys; sys.stdin.buffer.read(); sys.stderr.write('SECRET TRACE'); sys.exit(3)"]
        garbage = [sys.executable, "-c", "import sys; sys.stdin.buffer.read(); print('not json')"]
        wrong = [sys.executable, "-c", "import sys; sys.stdin.buffer.read(); print('{\"units\": 1}')"]
        result = self.run_with({"crash.pdf": crash, "garbage.pdf": garbage, "wrong.pdf": wrong},
                               files=[("crash.pdf", self.pdf), ("garbage.pdf", self.pdf), ("wrong.pdf", self.pdf),
                                      ("broken.pdf", b"%PDF-1.7 this is not really a pdf"), ("tender.pdf", self.pdf)])
        for name in ("crash.pdf", "garbage.pdf", "wrong.pdf", "broken.pdf"):
            self.assertIn(f"{name}: skipped, the PDF could not be read.", result["warnings"])
        self.assertNotIn("SECRET TRACE", json.dumps(result))
        self.assertEqual([d["document"] for d in result["documents"]], ["tender.pdf"])

    def test_worker_sets_cpu_memory_and_file_limits(self):
        import subprocess

        probe = ("import json, resource, runpy, sys; "
                 f"runpy.run_path({str(child.WORKER)!r})['_set_limits'](7, {child.MEMORY_LIMIT_BYTES}); "
                 "print(json.dumps([resource.getrlimit(r) for r in "
                 "(resource.RLIMIT_CPU, resource.RLIMIT_AS, resource.RLIMIT_FSIZE, resource.RLIMIT_CORE)]))")
        out = subprocess.run([sys.executable, "-I", "-B", "-c", probe], capture_output=True, timeout=30,
                             env=child.child_env(), check=True).stdout
        self.assertEqual(json.loads(out), [[7, 7], [child.MEMORY_LIMIT_BYTES] * 2, [0, 0], [0, 0]])

    def test_files_are_parsed_one_at_a_time(self):
        lock, active, peak = threading.Lock(), [0], [0]
        real = child.extract_in_child

        def counting(*args, **kwargs):
            with lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            try:
                time.sleep(0.2)
                return real(*args, **kwargs)
            finally:
                with lock:
                    active[0] -= 1

        with patch.object(child, "extract_in_child", counting):
            result = self.classify(files=[(f"f{i}.pdf", self.pdf) for i in range(5)])
        self.assertEqual(result["counts"]["files_read"], 5)
        self.assertEqual(peak[0], pipeline.PARALLEL_FILES)
        self.assertEqual(pipeline.PARALLEL_FILES, 1)

    def test_global_page_cap_trims_a_later_file(self):
        result = self.classify(files=[("a.pdf", self.pdf), ("b.pdf", self.pdf)], max_pages=4)
        self.assertEqual([d["pages"] for d in result["documents"]], [3, 1])
        self.assertIn("b.pdf: only the first 1 of 3 pages were read (limit 4 pages per request).", result["warnings"])
        self.assertEqual(result["counts"]["pages"], 4)
        b_pages = {loc["page"] for q in result["requirements"] for loc in q["pages"] if loc["document"] == "b.pdf"}
        self.assertEqual(b_pages, {1})


class JevClientTest(JevTestCase):
    def test_retry_after_429_then_success(self):
        self.fake.fail = lambda payload, n: http_error(429, b"slow down", {"retry-after-ms": "1"}) if n == 1 else None
        body, error, attempts = jev.call_jev({"model": "m", "state": {"clause": "x"}, "questions": jev.QUESTIONS},
                                             API_KEY, timeout=5)
        self.assertEqual((error, attempts), ("", 2))
        self.assertIn("answers", body)

    def test_client_error_is_not_retried(self):
        self.fake.fail = lambda payload, n: http_error(400, b"bad request")
        body, error, attempts = jev.call_jev({"model": "m", "state": {}, "questions": jev.QUESTIONS}, API_KEY)
        self.assertIsNone(body)
        self.assertEqual(attempts, 1)
        self.assertTrue(error.startswith("HTTP 400"))

    def test_auth_failure_stops_everything_without_echoing_the_key(self):
        self.fake.fail = lambda payload, n: http_error(401, f"bad key {API_KEY}".encode())
        with self.assertRaises(jev.AuthError) as ctx:
            self.classify()
        self.assertNotIn(API_KEY, str(ctx.exception))

    def test_deadline_bounds_the_request(self):
        body, error, attempts = jev.call_jev({}, API_KEY, deadline=time.monotonic() + 0.5)
        self.assertEqual((body, attempts), (None, 0))
        self.assertEqual(self.fake.requests, [])


# --------------------------------------------------------------------------- service

def run_async(coro):
    return asyncio.run(coro)


class ServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {**ENV, "TYPESAFE_API_KEY": API_KEY})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.storage_fake = FakeStorage()
        storage_patch = patch.object(up, "_storage_request", self.storage_fake)
        storage_patch.start()
        self.addCleanup(storage_patch.stop)
        up._bucket_ready = False
        self.details = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.jev = FakeJev()
        jev_patch = patch.object(jev, "urlopen", self.jev)
        jev_patch.start()
        self.addCleanup(jev_patch.stop)
        details_patch = patch.object(service, "get_alberta_api_details", return_value=self.details)
        self.get_details = details_patch.start()
        self.addCleanup(details_patch.stop)
        self.pdf = make_pdf()

    def run_tool(self, args):
        token = storage.set_tenant(TENANT)
        try:
            return service.classify_tender_artifact(args)
        finally:
            storage.reset_tenant(token)


class ServiceTest(ServiceTestCase):
    def test_missing_key_is_a_clear_error_before_any_download(self):
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": ""}), \
                patch.object(service, "load_contracts_for_unified") as contracts, \
                patch.object(service, "_download_public_document") as download, \
                patch.object(up, "load_uploaded_files") as uploads:
            for args in ({"reference": "PW-26-0001"}, {"reference": REFERENCE},
                         {"reference": REFERENCE, "upload_token": up.create_upload_token(REFERENCE, TENANT)}):
                with self.assertRaisesRegex(ValueError, "Requirement classification is not configured on this server."):
                    self.run_tool(args)
            text = run_async(service.call_tool_text("classify_tender", {"reference": REFERENCE}))
        self.assertEqual(text, "Error: Requirement classification is not configured on this server.")
        for mock in (contracts, download, uploads, self.get_details):
            mock.assert_not_called()
        self.assertEqual(self.storage_fake.calls, [])
        self.assertEqual(self.jev.requests, [])

    def test_apc_without_token_returns_the_bid_room_upload_link(self):
        result = self.run_tool({"reference": REFERENCE})
        self.assertTrue(result["upload_required"])
        self.assertTrue(result["upload_url"].startswith("https://wa.example.test/bid-room/upload/wabr1."))
        claims = up.verify_upload_token(result["upload_token"], reference=REFERENCE, tenant=TENANT)
        self.assertEqual(claims["r"], REFERENCE)
        self.assertIn("run `classify_tender` again", result["markdown"])
        self.assertIn("does not delete the uploaded files", result["markdown"])
        self.assertIn(PDF_NAME, result["markdown"])
        self.assertEqual(self.jev.requests, [])

    def test_apc_with_token_classifies_the_uploads_and_keeps_them(self):
        upload_token = up.create_upload_token(REFERENCE, TENANT)
        claims = up.verify_upload_token(upload_token)
        self.storage_fake.put(claims, PDF_NAME, self.pdf)
        self.storage_fake.put(claims, "Pricing.xlsx", b"PK\x03\x04xlsx")
        result = self.run_tool({"reference": REFERENCE, "upload_token": upload_token})
        artifact = result["artifact"]
        self.assertEqual(artifact["reference"], REFERENCE)
        self.assertEqual(artifact["documents"][0]["document"], PDF_NAME)
        self.assertIn("experience_reference.key_personnel", {q["tag"] for q in artifact["requirements"]})
        self.assertTrue(any("Pricing.xlsx: skipped, only PDF files" in w for w in artifact["warnings"]))
        self.assertIn("| R01 |", result["markdown"])
        self.assertIn("verify every requirement", result["markdown"].lower())
        # uploads are kept for process_bid_room
        self.assertEqual(len(self.storage_fake.objects), 2)
        self.assertNotIn("DELETE", {method for method, _path in self.storage_fake.calls})
        self.assertNotIn(API_KEY, json.dumps(result))
        # the same token still works for process_bid_room afterwards
        self.assertEqual(up.verify_upload_token(upload_token, reference=REFERENCE, tenant=TENANT)["r"], REFERENCE)

    def test_token_checks_match_process_bid_room(self):
        other = up.create_upload_token(REFERENCE, "user:someone-else")
        with self.assertRaisesRegex(ValueError, "different account"):
            self.run_tool({"reference": REFERENCE, "upload_token": other})
        wrong_reference = up.create_upload_token("AB-2026-00001", TENANT)
        with self.assertRaisesRegex(ValueError, "not AB-2026-06584"):
            self.run_tool({"reference": REFERENCE, "upload_token": wrong_reference})
        with self.assertRaisesRegex(ValueError, "only to an Alberta APC reference"):
            self.run_tool({"reference": "PW-26-0001", "upload_token": other})
        self.assertEqual(self.jev.requests, [])

    def test_canadabuys_reads_public_pdfs_only(self):
        zipped = io.BytesIO()
        with zipfile.ZipFile(zipped, "w") as archive:
            archive.writestr("annex-a.pdf", make_pdf(pages=PAGES[1:2]))
            archive.writestr("readme.txt", b"hello")
        bodies = {"https://canadabuys.canada.ca/x/rfp-en.pdf": self.pdf,
                  "https://canadabuys.canada.ca/x/annexes.zip": zipped.getvalue()}
        urls = [*bodies, "https://canadabuys.canada.ca/x/pricing.xlsx?download=1"]
        contract = {"referenceNumber-numeroReference": "PW-26-0001"}
        with patch.object(service, "load_contracts_for_unified", return_value=([contract], [])), \
                patch("procurement_core.e2b_bid_room.resolve_canadabuys_attachment_urls", return_value=urls), \
                patch.object(service, "_download_public_document", side_effect=lambda url, timeout: bodies[url]) as dl:
            result = self.run_tool({"reference": "PW-26-0001"})
        self.assertEqual([c.args[0] for c in dl.call_args_list], list(bodies))  # the .xlsx is never fetched
        artifact = result["artifact"]
        self.assertEqual([d["document"] for d in artifact["documents"]], ["rfp-en.pdf", "annex-a.pdf"])
        self.assertTrue(any("pricing.xlsx: skipped" in w for w in artifact["warnings"]))
        self.assertTrue(any("readme.txt: skipped" in w for w in artifact["warnings"]))
        self.assertEqual(artifact["source"], "CanadaBuys public attachments")

    def test_download_refuses_non_public_urls_before_connecting(self):
        for url in ("http://canadabuys.canada.ca/a.pdf", "https://127.0.0.1/a.pdf", "https://10.0.0.5/a.pdf",
                    "https://user:pw@canadabuys.canada.ca/a.pdf", "https://purchasing.alberta.ca/a.pdf"):
            with self.assertRaises(ValueError, msg=url):
                service._download_public_document(url, timeout=1)

    def test_mcp_dispatch_returns_markdown_and_structured_artifact(self):
        upload_token = up.create_upload_token(REFERENCE, TENANT)
        self.storage_fake.put(up.verify_upload_token(upload_token), PDF_NAME, self.pdf)
        token = storage.set_tenant(TENANT)
        try:
            text, structured = run_async(service.call_tool_text_and_structured(
                "classify_tender", {"reference": REFERENCE, "upload_token": upload_token}))
        finally:
            storage.reset_tenant(token)
        self.assertTrue(text.startswith("# Bidder requirements for AB-2026-06584"), text[:200])
        self.assertEqual(structured["artifact"]["kind"], "tender_requirements")
        self.assertNotIn("markdown", structured)

    def test_timeout_is_an_error_not_a_result(self):
        with patch.object(service, "classify_tender_artifact_bounded",
                          new=AsyncMock(side_effect=RuntimeError(service.CLASSIFY_TIMEOUT_MESSAGE))):
            text = run_async(service.call_tool_text("classify_tender", {"reference": REFERENCE}))
        self.assertTrue(text.startswith("Error: Requirement classification reached its time limit"))


class WiringTest(unittest.TestCase):
    def test_pro_gating_matches_process_bid_room(self):
        self.assertIn("classify_tender", auth.PRO_TOOLS)
        self.assertIn("classify_tender", service.TOOL_NAMES)
        env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "k"}
        with patch.dict(os.environ, env, clear=True):
            for name in ("process_bid_room", "classify_tender"):
                with self.assertRaises(auth.GateError) as ctx:
                    auth.check_tool_access(name, None)
                self.assertEqual(ctx.exception.status_code, 401)

    def test_tool_declaration(self):
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mcp-servers" / "canadabuys"))
        from mcp_tools import get_mcp_tools

        tool = {t.name: t for t in get_mcp_tools()}["classify_tender"]
        self.assertEqual(tool.input_schema["required"], ["reference"])
        self.assertEqual(set(tool.input_schema["properties"]), {"reference", "upload_token"})
        self.assertFalse(tool.input_schema["additionalProperties"])
        for phrase in ("TypeSafe AI", "api.typesafe.ai", "upload bucket", "expires", "Pro subscription"):
            self.assertIn(phrase, tool.description)
        wire = tool.model_dump(by_alias=True, exclude_none=True)
        self.assertFalse(wire["annotations"]["readOnlyHint"])
        self.assertEqual(wire["securitySchemes"], [{"type": "oauth2", "scopes": ["pro"]}])

    def test_mcp_handler_returns_markdown_and_structured_content(self):
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mcp-servers" / "canadabuys"))
        import server_http
        from mcp.types import CallToolRequestParams

        envelope = {"artifact": {"kind": "tender_requirements", "status": "partial", "requirements": []},
                    "markdown": "# Bidder requirements\n\n**Partial result.**"}
        with patch("server_http.check_tool_access", return_value=None), \
                patch.object(service, "classify_tender_artifact_bounded", new=AsyncMock(return_value=envelope)):
            result = run_async(server_http.handle_call_tool(None, CallToolRequestParams(
                name="classify_tender", arguments={"reference": "PW-26-0001"})))
        self.assertFalse(result.is_error)
        self.assertEqual(result.content[0].text, envelope["markdown"])
        self.assertEqual(result.structured_content, {"artifact": envelope["artifact"]})

    def test_privacy_page_lists_typesafe(self):
        from procurement_core.public_pages import PRIVACY, SUPPORT

        self.assertIn("TypeSafe AI", PRIVACY)
        self.assertIn("https://typesafe.ai", PRIVACY)
        self.assertIn("classify_tender", PRIVACY)
        self.assertIn("classify_tender", SUPPORT)


if __name__ == "__main__":
    unittest.main()
