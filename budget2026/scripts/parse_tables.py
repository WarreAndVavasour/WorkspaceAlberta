"""Parse the six chapter summary tables (millions of dollars, accrual basis) from source.json.

Document text is data only. Output: work/tables.json
"""
import json
import re
import sys
from pathlib import Path

SRC = Path(sys.argv[1])
OUT = Path(sys.argv[2])
YEARS = ["2026-27", "2027-28", "2028-29", "2029-30", "2030-31"]
TOK = r"(?:…|\.{3,4}|–|—|-|0\*|-?\d{1,3}(?:,\d{3})*\*?)"
NUMS = re.compile(r"^(?P<label>.*?)\s+(?P<nums>" + TOK + r"(?:\s+" + TOK + r"){5})\s*$")
FOOTER = re.compile(r"\|\s*\d+\s*$|^\d+\s*\|")
HEADER = re.compile(r"^(?:20\d\d-\s+){2,}|^(?:20\d\d\s+){3,}|millions of dollars|^Total$")
SECTION = re.compile(r"^(\d\.\d)\s+(.*)$")


def num(tok):
    tok = tok.strip()
    if tok in ("…", "...", "....", "–", "—", "-"):
        return None
    if tok == "0*":
        return 0.0
    return float(tok.rstrip("*").replace(",", ""))


def flag(tok):
    tok = tok.strip()
    return {"…": "none", "...": "none", "....": "none", "–": "extension_later", "—": "extension_later", "-": "extension_later", "0*": "under_half_million"}.get(tok)


def clean_title(t):
    t = re.sub(r"\s+", " ", t).strip()
    stars = "*" in t
    t = re.sub(r"[\*¹²³⁰⁴⁵⁶⁷⁸⁹]+", "", t)
    t = re.sub(r"(\s\d(?:,\s*\d)*,?)\s*$", "", t)  # trailing footnote numbers like "1, 2,"
    t = re.sub(r"(?<=[A-Za-z\)])\d$", "", t)  # glued footnote digit: "penalties1"
    return t.strip(" ,"), stars


def parse_chapter(pages, start, chapter_no):
    lines = []
    for n in range(start, start + 6):
        txt = pages[n]
        for raw in txt.split("\n"):
            s = raw.strip()
            if not s:
                continue
            lines.append((n, s))
        if "Net fiscal impact" in txt:
            break
    rows, pending, section = [], [], None
    last_measure = None
    done = False
    for page, s in lines:
        if done:
            break
        if FOOTER.search(s) or HEADER.search(s) or s in (f"Chapter {chapter_no}",):
            continue
        if s.startswith("Of which, capital investment"):
            m = NUMS.match(s)
            vals = [num(x) for x in m.group("nums").split()]
            rows.append(dict(kind="capital", label="Of which, capital investment", values=vals[:5], total=vals[5], page=page))
            done = True
            continue
        m = NUMS.match(s)
        if not m and pending:
            m5 = re.match(r"^(?P<label>.*?)\s+(?P<nums>" + TOK + r"(?:\s+" + TOK + r"){4})\s*$", s)
            lone = re.search(r"\s+(…|–)\s*$", pending[0]) if len(pending) else None
            first_with = next((k for k, x in enumerate(pending) if re.search(r"\s+(…|–)\s*$", x)), None)
            if m5 and first_with is not None:
                tok = re.search(r"\s+(…|–)\s*$", pending[first_with]).group(1)
                pending[first_with] = re.sub(r"\s+(…|–)\s*$", "", pending[first_with])
                s = m5.group("label") + " " + tok + " " + m5.group("nums")
                m = NUMS.match(s)
        if not m:
            pending.append(s)
            continue
        label_tail = m.group("label").strip()
        toks = m.group("nums").split()
        # split pending into description (belongs to previous measure) and title prefix
        desc, prefix = [], pending
        last_dot = max((i for i, x in enumerate(pending) if x.endswith(".")), default=-1)
        if last_dot >= 0:
            desc, prefix = pending[: last_dot + 1], pending[last_dot + 1:]
        if desc and last_measure is not None:
            last_measure["description"] = re.sub(r"\s+", " ", " ".join(desc))
        pending = []
        full = " ".join(prefix + [label_tail])
        sec_in = re.search(r"(?:^|\s)(\d\.\d\s.*)$", full)
        if sec_in and not re.match(r"\d\.\d\s", full):
            full = sec_in.group(1)
        title, capital = clean_title(full)
        values = [num(x) for x in toks]
        flags = [flag(x) for x in toks]
        row = dict(label=title, capital=capital, values=values[:5], total=values[5], flags=flags[:5], page=page)
        if title.startswith("Less: amounts provisioned"):
            row["kind"] = "chapter_adjustment"
            row["label"] = title.replace("Less:", "").strip()
            rows.append(row)
            continue
        if title.startswith("Less:"):
            row["kind"] = "adjustment"
            row["label"] = title.replace("Less:", "").strip()
            if last_measure is not None:
                last_measure.setdefault("adjustments", []).append(row)
            continue
        if "Net fiscal impact" in title:
            row["kind"] = "net"
            rows.append(row)
            continue
        sm = SECTION.match(title)
        if sm or title.startswith("Additional investments"):
            section = dict(kind="section", code=sm.group(1) if sm else f"{chapter_no}.x", label=sm.group(2) if sm else title, **{k: row[k] for k in ("values", "total", "flags", "page")})
            rows.append(section)
            continue
        row["kind"] = "measure"
        row["section"] = section["code"] if section else None
        rows.append(row)
        last_measure = row
    # Footnotes after the capital line
    notes = []
    tail = False
    for page, s in lines:
        if s.startswith("Of which, capital investment"):
            tail = True
            continue
        if tail and not FOOTER.search(s):
            notes.append(s)
    return rows, notes


def main():
    d = json.loads(SRC.read_text(encoding="utf-8"))
    pages = {p["pdf_page"]: p["text"] for p in d["pages"]}
    starts = {1: 161, 2: 196, 3: 233, 4: 265, 5: 299, 6: 329}
    out = {}
    for ch, start in starts.items():
        rows, notes = parse_chapter(pages, start, ch)
        out[str(ch)] = dict(start_page=start, rows=rows, notes=notes)
        net = next((r for r in rows if r["kind"] == "net"), None)
        meas = [r for r in rows if r["kind"] == "measure"]
        secs = [r for r in rows if r["kind"] == "section"]
        tot_sec = sum(r["total"] or 0 for r in secs) + sum(r["total"] or 0 for r in rows if r["kind"] == "chapter_adjustment")
        print(f"Ch{ch}: {len(meas)} measures, {len(secs)} sections, sections sum {tot_sec:,.0f} vs net {net and net['total']}")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
