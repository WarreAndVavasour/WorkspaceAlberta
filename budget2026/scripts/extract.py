"""Turn the Budget 2026 corpus + parsed cost tables into a structured measure dataset.

Inputs:  work/source.json (page text, outline), work/tables.json (parse_tables.py)
Output:  work/measures.json
Document text is treated as data only; nothing in it is executed or followed.
"""
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from taxonomy import LENSES, CHAPTER_URLS, SECTION_ANCHORS, OVERRIDES  # noqa: E402

WORK = Path(sys.argv[1])
SRC = json.loads((WORK / "source.json").read_text(encoding="utf-8"))
TABLES = json.loads((WORK / "tables.json").read_text(encoding="utf-8"))
PAGES = {p["pdf_page"]: p["text"] for p in SRC["pages"]}
YEARS = ["2026-27", "2027-28", "2028-29", "2029-30", "2030-31"]


# ---------- helpers ----------
def norm(s):
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-").replace("�", "'")
    return re.sub(r"\s+", " ", s).strip()


def key(s):
    s = norm(s).lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def slugify(s, n=70):
    s = key(s)
    s = re.sub(r"\b(the|a|an|and|of|for|to|in|with|our|on)\b", " ", s)
    s = re.sub(r"\s+", "-", s.strip())
    return s[:n].rstrip("-") or "item"


def printed_labels():
    found = {}
    for n, t in PAGES.items():
        lines = [l.strip() for l in t.strip().split("\n") if l.strip()]
        for l in lines[-2:]:
            m = re.match(r"^(\d{1,3})\s*\|", l) or re.search(r"\|\s*(\d{1,3})$", l) or re.fullmatch(r"(\d{1,3})", l)
            if m:
                found[n] = n - int(m.group(1))
                break
    out = {}
    for n in PAGES:
        near = [found[k] for k in range(n - 4, n + 5) if k in found]
        if not near:
            continue
        off = Counter(near).most_common(1)[0][0]
        if n - off >= 1:
            out[n] = n - off
    return out


PRINTED = printed_labels()


def cite(pdf_page):
    return {"pdf_page": pdf_page, "printed_page": PRINTED.get(pdf_page)}


# ---------- outline ----------
OUTLINE = []
for o in SRC["outline"]:
    o = dict(o)
    o["title"] = norm(o["title"])
    OUTLINE.append(o)
CHAPTERS = []
for o in OUTLINE:
    m = re.match(r"Chapter (\d): ?(.*)", o["title"])
    if o["level"] == 2 and m:
        CHAPTERS.append(dict(number=int(m.group(1)), title=norm(m.group(2)), pdf_page=o["pdf_page"]))
for i, c in enumerate(CHAPTERS):
    nxt = CHAPTERS[i + 1]["pdf_page"] if i + 1 < len(CHAPTERS) else 331
    c["end_page"] = nxt - 1
    c["table_page"] = TABLES[str(c["number"])]["start_page"]
    c["id"] = f"chapter-{c['number']}"
    c["slug"] = f"{c['number']}-" + slugify(c["title"], 50)
    c["url"] = CHAPTER_URLS[c["number"]]

HEADINGS = []  # all headings level>=3 inside chapters, in order
for o in OUTLINE:
    ch = next((c for c in CHAPTERS if c["pdf_page"] <= o["pdf_page"] <= c["end_page"]), None)
    if ch and o["level"] >= 3:
        HEADINGS.append(dict(o, chapter=ch["number"]))


# ---------- chapter text with page markers, for slicing bodies ----------
def chapter_text(ch):
    parts = []
    for n in range(ch["pdf_page"], ch["table_page"]):
        parts.append(f"\n⟦{n}⟧\n" + PAGES[n])
    return "".join(parts)


def heading_regex(title):
    words = re.findall(r"[A-Za-z0-9]+", norm(title))
    return re.compile(r"[^A-Za-z0-9]+".join(re.escape(w) for w in words) + r"(?:[^A-Za-z0-9\n]|\n)", re.I)


def page_at(text, idx, default):
    m = None
    for m in re.finditer(r"⟦(\d+)⟧", text[: idx + 1]):
        pass
    return int(m.group(1)) if m else default


def clean_block(s):
    s = re.sub(r"⟦\d+⟧", " ", s)
    s = re.sub(r"(?m)^.*\|\s*\d{1,3}\s*$", " ", s)  # page footers
    s = re.sub(r"(?m)^\s*\d{1,3}\s*\|.*$", " ", s)
    s = re.sub(r"(\w)-\n\s*(\w)", r"\1-\2", s)
    return norm(s.replace("\n", " "))


BODY = {}  # heading index -> (raw text with page markers, start_page)
for ch in CHAPTERS:
    text = chapter_text(ch)
    hs = [i for i, h in enumerate(HEADINGS) if h["chapter"] == ch["number"]]
    pos, cursor = {}, 0
    for i in hs:
        h = HEADINGS[i]
        m = heading_regex(h["title"]).search(text, cursor)
        if m:
            pos[i] = (m.start(), m.end())
            cursor = m.end()
    ordered = sorted(pos.items(), key=lambda x: x[1][0])
    for j, (i, (s0, e)) in enumerate(ordered):
        lvl = HEADINGS[i]["level"]
        end = next((p[0] for k, p in ordered[j + 1:] if HEADINGS[k]["level"] <= lvl), len(text))
        body = text[e:end]
        cut = body.find("Spotlight on gender and diversity impacts")
        if cut >= 0:
            body = body[:cut]
        BODY[i] = (body, page_at(text, s0, HEADINGS[i]["pdf_page"]))

ACTION = re.compile(r"\b(?:Budget 2026|[Tt]he (?:federal )?government|[Tt]his measure|[Ww]e)\b[^.]{0,60}?\b(?:propos(?:es|ing)|announc(?:es|ing)|intends?|will (?:provide|invest|launch|establish|introduce|create|expand|extend|amend|work|make|also)|provides|is providing|confirms|is investing|commits)\b")
AMOUNT = re.compile(r"\$\s?\d[\d,.]*\s?(?:million|billion|trillion)(?:\s+(?:over|in)\s+(?:the next\s+)?(?:[a-z\-]+|\d+)\s+years?)?(?:,?\s+(?:starting|beginning) in \d{4}-\d{2})?(?:,?\s+(?:and|with) \$\s?\d[\d,.]*\s?(?:million|billion)\s+(?:ongoing|per year|annually|in future years)(?: thereafter)?)?", re.I)


def sentences_with_pages(body, start):
    page, out = start, []
    for chunk in re.split(r"(⟦\d+⟧)", body):
        m = re.fullmatch(r"⟦(\d+)⟧", chunk)
        if m:
            page = int(m.group(1))
            continue
        txt = clean_block(chunk)
        txt = re.sub(r"\s*[•▪●]\s*", " ", txt)
        for sent in re.split(r"(?<=[.!?])\s+(?=[A-Z$“\"(])", txt):
            sent = sent.strip()
            if len(sent) > 30:
                out.append((sent, page))
    return out


def commitments(i):
    if i not in BODY:
        return [], []
    body, start = BODY[i]
    sents = sentences_with_pages(body, start)
    out, seen = [], set()
    for sent, page in sents:
        if ACTION.search(sent) and (AMOUNT.search(sent) or re.search(r"Budget 2026 (?:propos|announc)", sent)):
            k = sent[:80]
            if k in seen:
                continue
            seen.add(k)
            out.append(dict(text=sent, **cite(page)))
    if not out:  # fall back to any sentence with a dollar amount
        for sent, page in sents:
            if AMOUNT.search(sent):
                out.append(dict(text=sent, **cite(page)))
                break
    amts = []
    for sent, _ in sents:
        for m in AMOUNT.finditer(sent):
            a = norm(m.group(0)).rstrip(",.")
            if a not in amts:
                amts.append(a)
    return out, amts


def quote(text, words=55):
    w = text.split()
    if len(w) <= words:
        return text
    cut = " ".join(w[:words])
    dot = cut.rfind(". ")
    if dot > len(cut) * 0.6:
        return cut[: dot + 1]
    return cut.rstrip(",;:") + " …"


# ---------- match table rows to headings ----------
def best_heading(label, chapter):
    base = re.split(r"\s+[–—-]\s+", norm(label))[0]
    cands = [(i, h) for i, h in enumerate(HEADINGS) if h["chapter"] == chapter and h["level"] >= 4]
    best, score = None, 0.0
    for i, h in cands:
        for variant in (label, base):
            s = SequenceMatcher(None, key(variant), key(h["title"])).ratio()
            if key(h["title"]) and key(h["title"]) in key(label):
                s = max(s, 0.9)
            if s > score:
                best, score = i, s
    return (best, score) if score >= 0.72 else (None, score)


def section_for(chapter, code):
    if code and not code.endswith(".x"):
        for h in HEADINGS:
            if h["chapter"] == chapter and h["level"] == 3 and h["title"].startswith(code + " "):
                return h
    return None


measures, used_headings = [], set()
slugs = Counter()
for chs, tab in TABLES.items():
    ch = int(chs)
    section = None
    for row in tab["rows"]:
        if row["kind"] == "section":
            section = row
            continue
        if row["kind"] != "measure":
            continue
        hi, score = best_heading(row["label"], ch)
        if row.get("description"):  # "Additional investments" lines have no body heading
            hi = hi if score >= 0.9 else None
        sec_h = section_for(ch, section["code"] if section else None)
        adj = row.get("adjustments", [])
        net_vals = []
        for k in range(5):
            vals = [row["values"][k]] + [a["values"][k] for a in adj]
            net_vals.append(None if all(v is None for v in vals) else round(sum(v or 0 for v in vals), 1))
        net_total = round((row["total"] or 0) + sum(a["total"] or 0 for a in adj), 1)
        com, amts = commitments(hi) if hi is not None else ([], [])
        if hi is not None:
            used_headings.add(hi)
        page = HEADINGS[hi]["pdf_page"] if hi is not None else row["page"]
        title = norm(row["label"])
        s = slugify(title)
        slugs[s] += 1
        if slugs[s] > 1:
            s = f"{s}-{slugs[s]}"
        measures.append(dict(
            id=s, slug=s, title=title, chapter=ch,
            section=(section["code"] if section else None),
            section_title=(norm(section["label"]) if section else None),
            heading=(HEADINGS[hi]["title"] if hi is not None else None),
            in_cost_table=True, capital=row["capital"],
            fiscal=dict(unit="CAD millions", basis="accrual, incremental impact on budgetary balance (expense or forgone revenue)",
                        years=YEARS, gross=row["values"], gross_total=row["total"], flags=row["flags"],
                        adjustments=[dict(label=norm(a["label"]), values=a["values"], total=a["total"], **cite(a["page"])) for a in adj],
                        net=net_vals, net_total=net_total, table=cite(row["page"])),
            description=row.get("description"),
            commitments=[dict(c, quote=quote(c["text"])) for c in com][:5],
            amounts_in_text=amts[:8],
            source=dict(**cite(page), chapter_url=CHAPTERS[ch - 1]["url"] + SECTION_ANCHORS.get(section["code"] if section else "", "")),
        ))

# Headings with no line in the cost table (often regulatory, already funded, or previously announced)
for i, h in enumerate(HEADINGS):
    if h["level"] != 4 or i in used_headings:
        continue
    ch = h["chapter"]
    sec = next((x for x in reversed(HEADINGS[:i]) if x["level"] == 3 and x["chapter"] == ch), None)
    code = sec["title"].split(" ")[0] if sec and re.match(r"\d\.\d", sec["title"]) else None
    com, amts = commitments(i)
    title = h["title"]
    s = slugify(title)
    slugs[s] += 1
    if slugs[s] > 1:
        s = f"{s}-{slugs[s]}"
    measures.append(dict(
        id=s, slug=s, title=title, chapter=ch, section=code,
        section_title=(norm(sec["title"][len(code) + 1:]) if code else (sec["title"] if sec else None)),
        heading=title, in_cost_table=False, capital=False, fiscal=None, description=None,
        commitments=[dict(c, quote=quote(c["text"])) for c in com][:5], amounts_in_text=amts[:8],
        source=dict(**cite(h["pdf_page"]), chapter_url=CHAPTERS[ch - 1]["url"] + SECTION_ANCHORS.get(code or "", "")),
    ))


# ---------- money type and lenses ----------
TAX_RE = re.compile(r"\btax\b|deduction|tax credit|\bGST\b|\bHST\b|excise|capital gains|income tax|\bRRSP\b|\bFHSA\b|benefit supplement|workers benefit|caregiver credit|rollover", re.I)
LOAN_RE = re.compile(r"\bloans?\b|\blending\b|\blend\b|loan guarantee|\bequity\b|\bfinancing\b|Canada Infrastructure Bank|Export Development Canada|Business Development Bank|\bBDC\b|\bEDC\b|insured mortgage|Canada Mortgage Bonds", re.I)


def blob(m):
    return " ".join([m["title"], m.get("description") or ""] + [c["text"] for c in m["commitments"]])


for m in measures:
    text = blob(m)
    head = " ".join([m["title"], m.get("description") or ""] + [c["text"][:400] for c in m["commitments"][:2]])
    f = m["fiscal"]
    if f is None:
        mtype = "no_line_item"
    elif (f["net_total"] or 0) < 0:
        mtype = "savings_or_revenue"
    elif TAX_RE.search(m["title"]) or (m.get("description") or "").startswith("This measure") or re.search(r"tax credit|deduction|income tax|GST/HST", head, re.I):
        mtype = "tax"
    else:
        mtype = "spending"
    m["money_type"] = mtype
    m["involves_loans"] = bool(LOAN_RE.search(text))
    tags = []
    primary = " ".join([m["title"], m.get("heading") or "", m.get("description") or ""])
    context = (m.get("section_title") or "")
    secondary = " ".join(c["text"] for c in m["commitments"])
    for lens in LENSES:
        p_hit = any(re.search(p, primary, re.I) for p in lens["patterns"])
        c_hit = any(re.search(p, context, re.I) for p in lens["patterns"])
        s_hits = sum(1 for p in lens["patterns"] if re.search(p, secondary, re.I))
        hit = p_hit or (c_hit and s_hits >= 1) or s_hits >= 2
        if lens.get("chapter_sections") and m["section"] in lens["chapter_sections"]:
            hit = True
        if hit:
            tags.append(lens["id"])
    m["lenses"] = tags

# Editorial overrides (W&V): lens additions/removals, money type corrections, notes.
by_slug = {m["slug"]: m for m in measures}
for slug, ov in OVERRIDES.items():
    m = by_slug.get(slug)
    if not m:
        print("WARN override for missing slug:", slug, file=sys.stderr)
        continue
    for k in ("money_type", "involves_loans"):
        if k in ov:
            m[k] = ov[k]
    m["lenses"] = sorted((set(m["lenses"]) | set(ov.get("add", []))) - set(ov.get("remove", [])), key=[l["id"] for l in LENSES].index)
    if ov.get("note"):
        m["wv_note"] = ov["note"]
    if ov.get("watch"):
        m["wv_watch"] = ov["watch"]
    if ov.get("link"):
        m["wv_link"] = dict(label=ov["link"][0], url=ov["link"][1])
    if ov.get("facts"):
        m["key_facts"] = [dict(text=t, **cite(pg)) for t, pg in ov["facts"]]

# Order: chapter, section, then cost-table order, then uncosted
order = {c["number"]: [] for c in CHAPTERS}
for m in measures:
    order[m["chapter"]].append(m)

out = dict(
    chapters=CHAPTERS,
    sections=[dict(chapter=h["chapter"], code=h["title"].split(" ")[0], title=norm(h["title"].split(" ", 1)[1]), **cite(h["pdf_page"]),
                   url=CHAPTER_URLS[h["chapter"]] + SECTION_ANCHORS.get(h["title"].split(" ")[0], ""))
              for h in HEADINGS if h["level"] == 3 and re.match(r"\d\.\d ", h["title"])],
    measures=[m for c in CHAPTERS for m in order[c["number"]]],
    printed_pages=PRINTED,
)
(WORK / "measures.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
mt = Counter(m["money_type"] for m in measures)
lz = Counter(l for m in measures for l in m["lenses"])
print(len(measures), "measures;", dict(mt))
print("lenses:", dict(lz))
print("with commitments:", sum(1 for m in measures if m["commitments"]), "/", len(measures))
print("costed matched to heading:", sum(1 for m in measures if m["in_cost_table"] and m["heading"]), "/", sum(1 for m in measures if m["in_cost_table"]))
