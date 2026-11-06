"""Tax measures from 'Tax Measures: Supplementary Information', Table 1 (PDF pp. 392-393).

Values transcribed from the table (CAD millions). Positive = revenue decrease (relief for taxpayers);
negative = revenue increase. None = the table's dash: nil, under $500,000, or not determinable.
Then each measure's annex heading is located for a citation and the first 'Budget 2026 proposes' sentence.
"""
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

WORK = Path(sys.argv[1])
SRC = json.loads((WORK / "source.json").read_text(encoding="utf-8"))
PAGES = {p["pdf_page"]: p["text"] for p in SRC["pages"]}
PRINTED = {int(k): v for k, v in json.loads((WORK / "measures.json").read_text(encoding="utf-8"))["printed_pages"].items()}
D = None
ROWS = [
    ("Personal income tax", "2027 Canada Groceries and Essentials Benefit Supplement", [4055, D, D, D, D], 4055, ["households"]),
    ("Personal income tax", "Mineral Exploration Tax Credit and Critical Mineral Exploration Tax Credit", [1, 307, 216, 216, 216], 956, ["energy", "investment"]),
    ("Personal income tax", "Canada Caregiver Credit", [D, 185, 200, 220, 240], 845, ["households"]),
    ("Personal income tax", "Canada Growth Incentive – Capital Gains Exemption", [D, D, D, 80, 485], 565, ["investment", "businesses"]),
    ("Personal income tax", "Canada Growth Incentive – Rollover for Investments in Small Businesses", [D, 35, 35, 40, 40], 150, ["investment", "businesses"]),
    ("Personal income tax", "Instalment Payments for Individuals and Corporations", [D, 25, 115, 125, 130], 395, ["businesses", "households"]),
    ("Personal income tax", "Income Tax Return Filing and Balance-Due Dates for Individuals", [15, 50, 55, 55, 55], 230, ["households"]),
    ("Personal income tax", "Northern Residents Deductions", [D, 21, 26, 26, 26], 99, ["households"]),
    ("Personal income tax", "Expansion of the Intergenerational Farm and Fishing Property Rollover", [D, 15, 15, 15, 20], 65, ["businesses"]),
    ("Personal income tax", "Registered Disability Savings Plan", [1, 5, 8, 10, 15], 39, ["households"]),
    ("Personal income tax", "Moving Expense Deduction", [D, 1, 1, 1, 1], 4, ["households"]),
    ("Personal income tax", "Clergy Residence Deduction", [D, 6, 7, 7, 7], 27, []),
    ("Personal income tax", "Labour Mobility Deduction for Tradespeople", [D, D, D, D, D], D, ["trades"]),
    ("Personal income tax", "Home Accessibility Tax Credit", [D, 1, 1, 1, 1], 4, ["households", "housing", "trades"]),
    ("Personal income tax", "Adoption Expense Tax Credit", [D, D, D, D, D], D, ["households"]),
    ("Personal income tax", "Foreign Income Verification Statement – Form T1135", [D, D, 5, 6, 6], 17, []),
    ("Personal income tax", "Apprentice Vehicle Mechanics’ Tools Deduction", [D, 3, 3, 3, 3], 12, ["trades"]),
    ("Personal income tax", "Medical Expense Tax Credit and Disability Supports Deduction", [D, 1, 2, 2, 2], 7, ["households", "health"]),
    ("Personal income tax", "Deductibility of Expenses Against Commission Income", [D, 1, 1, 1, 1], 4, ["businesses"]),
    ("Personal income tax", "Lump-sum Thresholds for Periodic Payment of Benefits", [D, D, D, D, D], D, ["households"]),
    ("Personal income tax", "Scholarship, Fellowship, and Bursary Income", [D, D, D, D, D], D, ["training"]),
    ("Personal income tax", "Deductibility of Expenses by Employed Artists", [D, D, D, D, D], D, []),
    ("Personal income tax", "Volunteer Firefighters and Search and Rescue Volunteers Tax Credit", [D, D, D, D, D], D, ["households"]),
    ("Personal income tax", "Registered Retirement Savings Plan", [D, D, D, D, D], D, ["households"]),
    ("Personal income tax", "Excess Corporate Holdings Regime for Private Foundations", [D, D, D, D, D], D, []),
    ("Personal income tax", "Objections to Assessments", [D, D, D, D, D], D, []),
    ("Personal income tax", "Disclosure of Tax Debt to Credit Bureaus", [D, D, D, D, D], D, []),
    ("Personal income tax", "Trust Distributions to Non-Residents", [D, D, D, D, D], D, []),
    ("Personal income tax", "Information Sharing – Pension Administrators", [D, D, -10, -10, -10], -30, []),
    ("Personal income tax", "Registered Pension Plans", [D, D, -50, -50, -48], -148, []),
    ("Personal income tax", "Build Canada Workers Benefit", [D, 515, 515, 515, 515], 2060, ["households"]),
    ("Personal income tax", "Less: savings from the phasing out of advance payments", [D, -470, -860, -860, -860], -3050, ["households"]),
    ("Business income tax", "Clean Electricity and Clean Technology Investment Tax Credits", [D, 70, 780, 710, 860], 2420, ["energy", "investment", "businesses"]),
    ("Business income tax", "Scientific Research and Experimental Development Tax Incentive Program", [25, 200, 245, 225, 235], 930, ["businesses", "investment"]),
    ("Business income tax", "Interest Deductibility Limits", [235, 80, 80, 80, 80], 555, ["housing", "investment"]),
    ("Business income tax", "Canadian Journalism Labour Tax Credit", [16, 150, 170, 85, 80], 501, ["businesses"]),
    ("Business income tax", "Taxable Preferred Shares", [1, 25, 25, 20, 20], 91, ["businesses"]),
    ("Business income tax", "Helium Exploration, Development and Resource Expenses", [D, 4, 15, 15, 20], 54, ["energy", "investment"]),
    ("Business income tax", "Corporate Tax Elections", [D, D, D, D, D], D, ["businesses"]),
    ("Business income tax", "Corporate Loss Transfers", [D, D, D, D, D], D, ["businesses"]),
    ("Business income tax", "Administrative Penalties", [D, D, -11, -48, -58], -117, []),
    ("Business income tax", "Less: amounts provisioned in Budget 2025 for future reviews", [D, D, 11, 48, 58], 117, []),
    ("International tax", "Common Reporting Standard", [D, D, D, D, D], D, []),
    ("International tax", "Taxable Canadian Property", [3, 15, 15, 15, 15], 63, []),
    ("Sales and excise tax", "GST/HST Health Measures", [20, 41, 46, 46, 46], 199, ["health"]),
    ("Sales and excise tax", "Pre-approval regime for GST/HST Input Tax Credit Allocation Methods of Financial Institutions", [D, D, D, D, D], D, []),
    ("Sales and excise tax", "Product Descriptions and Regulatory Cross-References in Sales and Excise Tax Rules", [D, D, D, D, D], D, []),
    ("Sales and excise tax", "Cannabis Taxation", [D, D, D, D, D], D, []),
    ("Sales and excise tax", "Spirits Licence Security Requirements", [D, D, D, D, D], D, []),
    ("Sales and excise tax", "Federal Fuel Excise Tax Licensing Framework", [D, 20, D, D, D], 20, ["businesses"]),
    ("Other tax", "Ministerial Delegations", [D, D, D, D, D], D, []),
]


def norm(s):
    s = s.replace("’", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip()


def key(s):
    return re.sub(r"[^a-z0-9 ]+", " ", norm(s).lower()).strip()


def slugify(s):
    s = key(s)
    s = re.sub(r"\b(the|a|an|and|of|for|to|in|with|our|on)\b", " ", s)
    return re.sub(r"\s+", "-", s.strip())[:70].rstrip("-")


heads = [o for o in SRC["outline"] if 394 <= o["pdf_page"] <= 443 and o["level"] >= 4]
annex_text = "".join(f"\n⟦{n}⟧\n" + PAGES[n] for n in range(394, 444))


def find_heading(name):
    best, score = None, 0
    for h in heads:
        s = SequenceMatcher(None, key(name), key(h["title"])).ratio()
        if s > score:
            best, score = h, s
    return best if score > 0.8 else None


def proposal(h, nxt_title):
    words = re.findall(r"[A-Za-z0-9]+", norm(h["title"]))
    start = annex_text.find(f"\u27e6{h['pdf_page']}\u27e7")
    m = re.compile(r"[^A-Za-z0-9]+".join(map(re.escape, words))).search(annex_text, max(start, 0))
    if not m:
        return None, h["pdf_page"]
    end = len(annex_text)
    if nxt_title:
        w2 = re.findall(r"[A-Za-z0-9]+", norm(nxt_title))
        m2 = re.compile(r"[^A-Za-z0-9]+".join(map(re.escape, w2))).search(annex_text, m.end())
        if m2:
            end = m2.start()
    body = annex_text[m.end():end]
    page = h["pdf_page"]
    for chunk in re.split(r"(⟦\d+⟧)", body):
        mm = re.fullmatch(r"⟦(\d+)⟧", chunk)
        if mm:
            page = int(mm.group(1))
            continue
        txt = norm(re.sub(r"(?m)^.*\|\s*\d{1,3}\s*$", " ", chunk).replace("\n", " "))
        p = re.search(r"Budget 2026 (?:proposes|announces|confirms)[^.]*(?:\.\d[^.]*)*\.", txt)
        if p:
            return p.group(0), page
    return None, h["pdf_page"]


out = []
for cat, name, vals, total, lenses in ROWS:
    item = dict(category=cat, title=name, values=vals, total=total, lenses=lenses,
                table=dict(pdf_page=392 if cat == "Personal income tax" else 393, printed_page=PRINTED.get(392 if cat == "Personal income tax" else 393)))
    if name.startswith("Less:"):
        out[-1]["adjustment"] = item
        continue
    h = find_heading(name)
    if h:
        idx = heads.index(h)
        nxt = next((x["title"] for x in heads[idx + 1:] if x["level"] <= h["level"]), None)
        text, page = proposal(h, nxt)
        item.update(slug=slugify(name), pdf_page=page, printed_page=PRINTED.get(page), proposal=text, heading_page=h["pdf_page"])
    else:
        item.update(slug=slugify(name), pdf_page=None, printed_page=None, proposal=None)
    out.append(item)

(WORK / "tax.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(out), "tax measures;", sum(1 for x in out if x.get("proposal")), "with a proposal sentence;", sum(1 for x in out if x.get("pdf_page")), "located")
for x in out:
    if not x.get("proposal"):
        print("  no proposal:", x["title"])
