"""Local bid room: review APC documents already downloaded to this machine.

The harness APC connector (``integrations/apc`` in workspacealberta-harness)
signs in through the user's own browser session and saves a posting's files
under ``$WA_APC_HOME/opportunities/<AB-reference>/`` with a ``manifest.json``
receipt (title, path, sha256, bytes, source, retrieved_at per file).

This module reads that receipt, re-verifies every file against its recorded
SHA-256 and size, uploads the verified bytes straight into a fresh E2B sandbox
and runs the *same* processor, coverage rules and Cohere review as the hosted
``process_bid_room``. No public URL is needed and nothing is fetched from APC.

Boundaries:

- Only an APC reference is accepted from a caller; the folder is derived from
  ``WA_APC_HOME`` (or ``--home`` on the CLI). Manifest paths are reduced to
  their file name inside that folder, so a moved or remounted drive still
  works and a crafted manifest cannot point outside the folder.
- ``browser-profile/`` and ``pending.json`` are never read or uploaded.
- This is exposed only by the stdio adapter and this CLI. The hosted HTTP
  server must never read its own filesystem on a caller's behalf.
- Uploading sends the documents to E2B and their contents to Cohere. Check
  the posting's terms before processing confidential material.

CLI::

    python -m procurement_core.local_bid_room AB-2026-06523 \\
        --home /media/ssd/workspacealberta/apc --context "What we do..."
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

REFERENCE_RE = re.compile(r"AB-\d{4}-\d{5,8}")
SANDBOX_LOCAL_DIR = "/tmp/workspacealberta-bid-room/local"
LOCAL_KIND = "apc_local_document"
SUPPORTED_SUFFIXES = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".zip"}
# Magic numbers the connector also checks; re-checked here because the drive
# may have been edited since download.
SIGNATURES = {".pdf": b"%PDF-", ".docx": b"PK", ".xlsx": b"PK", ".zip": b"PK"}


class LocalBidRoomError(ValueError):
    """A local download cannot be processed; no sandbox was started."""


def default_home() -> Path:
    return Path(os.environ.get("WA_APC_HOME", str(Path.home() / ".workspacealberta" / "apc")))


def validate_reference(value: str) -> str:
    value = str(value or "").strip()
    if not REFERENCE_RE.fullmatch(value):
        raise LocalBidRoomError("Expected an APC reference such as AB-2026-06523.")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_local_download(reference: str, home: Path | None = None, *, max_file_bytes: int | None = None) -> dict[str, Any]:
    """Read and verify a connector download. Returns receipt + per-file checks.

    Every manifest entry appears in ``files`` with ``status`` ``verified`` or a
    reason it cannot be used (``missing``, ``size_mismatch``, ``hash_mismatch``,
    ``unsupported_type``, ``bad_signature``, ``too_large``).
    """
    from procurement_core.e2b_bid_room import MAX_FILE_BYTES

    reference = validate_reference(reference)
    limit = MAX_FILE_BYTES if max_file_bytes is None else max_file_bytes
    folder = (Path(home) if home else default_home()).expanduser().resolve() / "opportunities" / reference
    manifest_path = folder / "manifest.json"
    if not manifest_path.is_file():
        raise LocalBidRoomError(
            f"No local download found for {reference} at {folder}. Download it with the APC connector first."
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LocalBidRoomError(f"Could not read {manifest_path}: {exc}") from exc
    if manifest.get("reference") != reference:
        raise LocalBidRoomError(f"{manifest_path} is for {manifest.get('reference')!r}, not {reference}.")
    entries = manifest.get("documents")
    if not isinstance(entries, list):
        raise LocalBidRoomError(f"{manifest_path} has no documents list.")

    files: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries, 1):
        entry = entry if isinstance(entry, dict) else {}
        name = Path(str(entry.get("path") or "")).name
        expected_sha = str(entry.get("sha256") or "").lower()
        record = {
            "title": str(entry.get("title") or name or f"document-{index}"),
            "name": name,
            "path": folder / name if name else None,
            "sha256": expected_sha,
            "bytes": entry.get("bytes"),
            "source": str(entry.get("source") or ""),
            "retrieved_at": str(entry.get("retrieved_at") or ""),
            "status": "verified",
            "error": "",
        }
        files.append(record)
        path = record["path"]
        suffix = Path(name).suffix.lower()
        if not name or not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
            record.update(status="invalid_entry", error="Manifest entry lacks a file name or SHA-256.")
        elif expected_sha in seen:
            record.update(status="duplicate", error="Same file listed twice in the manifest.")
        elif not path.is_file():
            record.update(status="missing", error=f"{name} is not in {folder}.")
        elif suffix not in SUPPORTED_SUFFIXES:
            record.update(status="unsupported_type", error=f"{suffix or 'No extension'} files are not processed.")
        elif path.stat().st_size > limit:
            record.update(status="too_large", error=f"Larger than the {limit} byte bid room limit.")
        elif isinstance(entry.get("bytes"), int) and path.stat().st_size != entry["bytes"]:
            record.update(status="size_mismatch", error="File size differs from the download receipt.")
        elif _sha256_file(path) != expected_sha:
            record.update(status="hash_mismatch", error="File changed since download (SHA-256 differs).")
        else:
            with path.open("rb") as handle:
                prefix = handle.read(8)
            signature = SIGNATURES.get(suffix)
            if signature and not prefix.startswith(signature):
                record.update(status="bad_signature", error=f"Not a valid {suffix} file.")
        seen.add(expected_sha)

    return {
        "reference": reference,
        "folder": folder,
        "complete": manifest.get("complete") is True,
        "expected_documents": manifest.get("expected_documents"),
        "files": files,
    }


def build_local_bid_room_payload(
    download: dict[str, Any],
    profile: dict[str, Any] | None = None,
    *,
    business_context: str = "",
    max_attachments: int = 5,
    details: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[tuple[str, bytes]]]:
    """Return ``(payload, uploads)`` for :func:`run_live_bid_room_process`."""
    from procurement_core.e2b_bid_room import (
        MAX_ATTACHMENTS, build_apc_bid_room_payload, build_process_payload, profile_for_bid_room,
    )
    from procurement_core.apc_documents import apc_document_manifest, apc_posting_url

    reference = download["reference"]
    limit = max(0, min(MAX_ATTACHMENTS, int(max_attachments)))
    warnings: list[str] = []

    if details:
        base = build_apc_bid_room_payload(details, profile or {}, business_context=business_context, max_attachments=0)
        opportunity, documents = base["opportunity"], base["documents"]
        listed = apc_document_manifest(details)
        if download["expected_documents"] is not None and listed and len(listed) != download["expected_documents"]:
            warnings.append(
                f"APC's public metadata lists {len(listed)} document(s) but the local download has "
                f"{download['expected_documents']}. Re-download to pick up amendments."
            )
    else:
        opportunity = {
            "source": "Alberta Purchasing Connection", "reference": reference, "solicitation": "",
            "title": f"APC opportunity {reference}", "buyer": "", "status": "", "closing": "",
            "url": apc_posting_url(reference, os.environ.get("ALBERTA_APC_APP_BASE", "https://purchasing.alberta.ca")),
        }
        documents = []
        warnings.append("Public APC notice details were not loaded; the review uses the downloaded files only.")
    provenance = download.get("provenance") or "local_apc_download"
    opportunity = {**opportunity, "provenance": provenance}
    warnings.extend(download.get("warnings") or [])

    if not download["complete"]:
        warnings.append(
            "The uploaded documents do not cover every file listed on APC; the review is incomplete. "
            "Upload the missing files before relying on it."
            if provenance == "user_upload" else
            "The local APC download is not marked complete; some posting documents may be missing. "
            "Resume the download before relying on this review."
        )

    manifest: list[dict[str, Any]] = []
    attachments: list[dict[str, Any]] = []
    uploads: list[tuple[str, bytes]] = []
    for item in download["files"]:
        suffix = Path(item["name"]).suffix.lower()
        entry = {
            "document_id": f"local:{item['sha256'][:16]}" if item["sha256"] else f"local:{item['name']}",
            "name": item["title"],
            "kind": LOCAL_KIND,
            "version": None,
            "amendment_number": None,
            "expected_bytes": item["bytes"],
            "expected_mime_type": "application/pdf" if suffix == ".pdf" else "",
            "provenance": provenance,
        }
        if item["status"] != "verified":
            entry.update(status=item["status"], error=item["error"])
        elif limit == 0:
            entry.update(status="not_selected", error="Notice-only review explicitly requested.")
        elif len(attachments) >= limit:
            entry.update(status="not_selected", error="Attachment limit excludes this document.")
        else:
            local_name = f"{item['sha256'][:16]}{suffix}"
            entry.update(status="selected")
            attachments.append({**entry, "url": "", "local_name": local_name, "expected_sha256": item["sha256"]})
            data = item["data"] if item.get("data") is not None else item["path"].read_bytes()
            uploads.append((f"{SANDBOX_LOCAL_DIR}/{local_name}", data))
        manifest.append(entry)

    payload = build_process_payload(
        opportunity=opportunity,
        profile=profile_for_bid_room(profile or {}, business_context),
        documents=documents,
        attachments=attachments,
        document_manifest=manifest,
        warnings=warnings,
    )
    return payload, uploads


def process_local_bid_room_artifact(args: dict[str, Any], *, home: Path | None = None) -> dict[str, Any]:
    """Verify a local download, run it in E2B, and return the artifact envelope."""
    from procurement_core.e2b_bid_room import (
        BID_ROOM_WORK_SECONDS, render_bid_room_markdown, run_live_bid_room_process,
    )

    reference = validate_reference(args.get("reference"))
    max_attachments = args.get("max_attachments", 5)
    download = load_local_download(reference, home)
    if max_attachments and not any(item["status"] == "verified" for item in download["files"]):
        problems = "; ".join(f"{item['title']}: {item['status']}" for item in download["files"]) or "no files listed"
        raise LocalBidRoomError(f"No verified local files for {reference} ({problems}). No sandbox was started.")

    details = args.get("details")
    if details is None and args.get("fetch_notice", True):
        try:
            from procurement_core.service import get_alberta_api_details
            details = get_alberta_api_details(reference)
        except Exception:  # Offline or APC unavailable: the files still carry the review.
            details = None

    profile = args.get("profile")
    if profile is None:
        try:
            from procurement_core.service import resolve_profile
            profile = resolve_profile(args) or {}
        except Exception:
            profile = {}
    payload, uploads = build_local_bid_room_payload(
        download, profile,
        business_context=str(args.get("business_context") or "").strip(),
        max_attachments=max_attachments,
        details=details,
    )
    result = run_live_bid_room_process(
        payload, uploads=uploads, deadline=time.monotonic() + BID_ROOM_WORK_SECONDS,
    )
    return {
        "reference": reference,
        "folder": str(download["folder"]),
        "sandbox_id": result.sandbox_id,
        "sandbox_killed": result.killed,
        "artifact": result.artifact,
        "markdown": render_bid_room_markdown(result),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a bid room on APC documents downloaded to this machine.")
    parser.add_argument("reference", help="APC reference, e.g. AB-2026-06523")
    parser.add_argument("--home", help="APC connector folder (default: $WA_APC_HOME or ~/.workspacealberta/apc)")
    parser.add_argument("--context", default="", help="What your business does / bid context")
    parser.add_argument("--max-attachments", type=int, default=5)
    parser.add_argument("--offline-notice", action="store_true", help="Do not fetch public APC notice details")
    parser.add_argument("--check", action="store_true", help="Only verify the local files; start no sandbox")
    parser.add_argument("--json", action="store_true", help="Print the full JSON artifact")
    options = parser.parse_args(argv)
    home = Path(options.home) if options.home else None
    try:
        if options.check:
            download = load_local_download(options.reference, home)
            print(f"{download['reference']} in {download['folder']} (complete: {download['complete']})")
            for item in download["files"]:
                print(f"  {item['status']:<16} {item['title']}  {item['error']}")
            return 0 if any(item["status"] == "verified" for item in download["files"]) else 1
        envelope = process_local_bid_room_artifact({
            "reference": options.reference,
            "business_context": options.context,
            "max_attachments": options.max_attachments,
            "fetch_notice": not options.offline_notice,
        }, home=home)
    except (LocalBidRoomError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if options.json:
        print(json.dumps({k: v for k, v in envelope.items() if k != "markdown"}, indent=2, ensure_ascii=False))
    else:
        print(envelope["markdown"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
