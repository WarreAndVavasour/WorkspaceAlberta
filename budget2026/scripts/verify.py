"""Check transcribed numbers and editorial facts against the page text they cite.

1. Every fiscal table value must appear in its cited page text.
2. Every chapter's section subtotals must reconcile with its net fiscal impact.
3. Each section's measures (with adjustments) must reconcile with the section subtotal.
4. Every number in a W&V key fact must appear on the cited page (or the next page).
5. Tax table values must appear on pages 392-393.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fiscal_data import TABLES, ECONOMY  # noqa: E402

WORK = Path(sys.argv[1])
SRC = json.loads((WORK / "source.json").read_text(encoding="utf-8"))
P = {p["pdf_page"]: re.sub(r"\s+", " ", p["text"]) for p in SRC["pages"]}
M = json.loads((WORK / "measures.json").read_text(encoding="utf-8"))
T = json.loads((WORK / "tables.json").read_text(encoding="utf-8"))
TAX = json.loads((WORK / "tax.json").read_text(encoding="utf-8"))
problems = []


def fmt(v):
    if v is None:
        return None
    if abs(v) >= 1000:
        return f"{v:,.1f}"
    return f"{v:.1f}"


for t in TABLES + [dict(ECONOMY, id="economy", rows=ECONOMY["rows"])]:
    text = P[t["pdf_page"]]
    for label, vals in t["rows"]:
        for v in vals:
            if v is None:
                continue
            cands = {fmt(v), str(v), f"{v:,}", f"{v:,.0f}" if float(v).is_integer() else fmt(v)}
            if not any(c and c in text for c in cands):
                problems.append(f"fiscal {t['id']} p{t['pdf_page']}: {label} value {v} not found")

for ch, tab in T.items():
    net = next(r for r in tab["rows"] if r["kind"] == "net")
    secs = [r for r in tab["rows"] if r["kind"] in ("section", "chapter_adjustment")]
    if abs(sum(r["total"] or 0 for r in secs) - net["total"]) > 3:
        problems.append(f"chapter {ch}: sections do not reconcile with net {net['total']}")
    current, acc = None, 0.0
    for r in tab["rows"] + [dict(kind="end")]:
        if r["kind"] in ("section", "end", "chapter_adjustment", "net"):
            if current is not None and abs(acc - (current["total"] or 0)) > 3:
                problems.append(f"chapter {ch} section {current.get('code')}: measures {acc:.0f} vs subtotal {current['total']}")
            current, acc = (r if r["kind"] == "section" else None), 0.0
            continue
        if r["kind"] == "measure":
            acc += (r["total"] or 0) + sum(a["total"] or 0 for a in r.get("adjustments", []))

for m in M["measures"]:
    for f in m.get("key_facts", []):
        nums = re.findall(r"\$?\d[\d,.]*", f["text"])
        text = P.get(f["pdf_page"], "") + " " + P.get(f["pdf_page"] + 1, "") + " " + P.get(f["pdf_page"] - 1, "")
        for n in nums:
            n = n.rstrip(".,")
            if n.startswith("$"):
                n = n[1:]
            if n and n not in text and n.replace(",", "") not in text.replace(",", ""):
                problems.append(f"fact on {m['slug']} p{f['pdf_page']}: '{n}' not found in '{f['text'][:60]}'")

tax_text = P[392] + P[393]
for x in TAX:
    for v in [x["total"]] + x["values"]:
        if v is not None and f"{v:,}" not in tax_text:
            problems.append(f"tax {x['title']}: {v} not on pp. 392-393")

print(f"{len(problems)} problem(s)")
for p in problems:
    print(" -", p)
sys.exit(1 if problems else 0)
