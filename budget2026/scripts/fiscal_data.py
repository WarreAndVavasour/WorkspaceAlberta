"""Fiscal tables transcribed from Budget 2026 (billions of dollars unless noted).

Every series records its source table and PDF page. verify.py checks each value against the page text.
Projection years run April to March. 2025-26 is the most recent (preliminary) year.
"""

YEARS6 = ["2025-26", "2026-27", "2027-28", "2028-29", "2029-30", "2030-31"]
YEARS5 = YEARS6[1:]

TABLES = [
    dict(id="table-1", title="Economic and fiscal developments, policy actions, and measures", table="Table 1", pdf_page=104, unit="CAD billions", years=YEARS6,
         note="A negative number implies a deterioration in the budgetary balance (lower revenue or higher expenses).",
         rows=[
             ("Budgetary balance - Spring Economic Update 2026", [-66.9, -65.3, -63.1, -57.7, -56.2, -53.2]),
             ("Economic and fiscal developments since SEU 2026", [27.5, 21.5, 38.3, 32.9, 33.2, 32.4]),
             ("Budgetary balance before policy actions and measures", [-39.3, -43.8, -24.8, -24.8, -23.0, -20.8]),
             ("Policy actions since SEU 2026", [None, -3.2, -3.9, -1.9, -0.1, -0.4]),
             ("1. Canada's Investment Supercycle", [None, -2.0, -11.0, -12.8, -11.7, -14.4]),
             ("2. A more competitive and connected Canadian economy", [None, -2.3, -4.9, -2.6, -3.0, -2.3]),
             ("3. A more affordable life", [None, -8.6, -8.0, -5.1, -4.1, -4.8]),
             ("4. A strong and united Canada", [None, -1.0, -7.5, -8.5, -9.3, -8.3]),
             ("5. A safe and sovereign Canada", [None, -1.0, -1.6, -1.3, -1.5, -1.1]),
             ("6. A more efficient government", [None, -0.3, -0.6, -0.6, -0.8, -0.8]),
             ("Subtotal - Budget 2026 measures", [None, -15.2, -33.8, -30.9, -30.4, -31.8]),
             ("Total - policy actions and Budget 2026 measures", [None, -18.4, -37.7, -32.8, -30.5, -32.1]),
             ("Budgetary balance", [-39.3, -62.3, -62.5, -57.6, -53.4, -52.9]),
             ("Budgetary balance (% of GDP)", [-1.2, -1.8, -1.8, -1.6, -1.4, -1.3]),
             ("Federal debt (% of GDP)", [40.2, 39.9, 40.2, 40.4, 40.3, 40.1]),
         ]),
    dict(id="summary", title="Summary statement of transactions", table="Table A1.8", pdf_page=344, unit="CAD billions", years=YEARS6,
         rows=[
             ("Budgetary revenues", [526.4, 540.3, 564.2, 581.5, 607.7, 629.1]),
             ("Program expenses, excluding net actuarial losses (gains)", [498.5, 542.7, 559.3, 568.3, 586.3, 600.2]),
             ("Public debt charges", [53.5, 60.2, 67.3, 73.8, 78.4, 85.5]),
             ("Total expenses, excluding net actuarial losses (gains)", [552.1, 602.9, 626.6, 642.1, 664.7, 685.7]),
             ("Net actuarial losses (gains)", [13.6, -0.4, 0.2, -3.0, -3.6, -3.7]),
             ("Budgetary balance", [-39.3, -62.3, -62.5, -57.6, -53.4, -52.9]),
             ("Total liabilities", [2318.3, 2484.1, 2671.8, 2855.3, 3003.9, 3151.7]),
             ("Financial assets", [866.6, 945.8, 1035.6, 1123.5, 1179.0, 1234.1]),
             ("Net debt", [1451.8, 1538.3, 1636.3, 1731.8, 1824.9, 1917.6]),
             ("Non-financial assets", [145.7, 171.8, 207.2, 245.2, 284.8, 324.6]),
             ("Federal debt", [1306.1, 1366.5, 1429.0, 1486.6, 1540.1, 1593.0]),
             ("Public debt charges (% of GDP)", [1.6, 1.8, 1.9, 2.0, 2.0, 2.2]),
         ]),
    dict(id="revenues", title="The revenue outlook", table="Table A1.9", pdf_page=345, unit="CAD billions", years=YEARS6,
         rows=[
             ("Personal income tax", [247.7, 258.7, 270.8, 283.7, 297.0, 309.3]),
             ("Corporate income tax", [104.2, 102.7, 97.1, 97.1, 100.6, 100.2]),
             ("Non-resident income tax", [14.5, 14.8, 15.0, 15.3, 15.5, 15.8]),
             ("Goods and Services Tax", [51.8, 51.5, 57.4, 59.4, 62.1, 65.1]),
             ("Customs import duties", [10.3, 11.1, 13.4, 8.1, 8.4, 8.7]),
             ("Other excise taxes/duties", [13.1, 7.7, 12.9, 13.0, 13.0, 13.1]),
             ("Other taxes", [0.0, 2.7, 1.9, 2.1, 2.1, 2.1]),
             ("Employment Insurance premium revenues", [32.5, 34.3, 35.5, 36.7, 38.2, 39.7]),
             ("Enterprise Crown corporations", [13.1, 13.0, 16.0, 20.7, 23.5, 26.1]),
             ("Other programs", [32.9, 37.0, 36.3, 37.4, 39.1, 40.5]),
             ("Net foreign exchange revenues and return on investments", [6.2, 6.9, 7.9, 8.0, 8.2, 8.6]),
             ("Total budgetary revenues", [526.4, 540.3, 564.2, 581.5, 607.7, 629.1]),
         ]),
    dict(id="expenses", title="The expense outlook", table="Table A1.10", pdf_page=350, unit="CAD billions", years=YEARS6,
         rows=[
             ("Old Age Security program", [82.7, 89.4, 95.2, 99.9, 104.8, 109.5]),
             ("Employment Insurance benefits", [28.8, 32.9, 34.3, 32.9, 33.9, 35.0]),
             ("Canada Child Benefit", [30.1, 31.2, 32.3, 33.5, 34.6, 35.7]),
             ("Canada Health Transfer", [54.7, 57.4, 60.3, 62.9, 65.2, 67.7]),
             ("Canada Social Transfer", [17.4, 17.9, 18.5, 19.0, 19.6, 20.2]),
             ("Equalization", [26.2, 27.2, 28.4, 29.6, 30.7, 31.9]),
             ("Territorial Formula Financing", [5.5, 5.8, 6.3, 6.7, 7.0, 7.2]),
             ("Health agreements with provinces and territories", [4.3, 4.3, 4.3, 2.5, 2.5, 2.5]),
             ("Canada-wide early learning and child care", [7.9, 10.3, 11.0, 8.2, 8.5, 8.8]),
             ("Build Communities Strong Fund - Community Stream", [2.5, 2.5, 2.6, 2.6, 2.7, 2.8]),
             ("Other fiscal arrangements", [-7.6, -8.5, -8.6, -9.0, -9.4, -9.8]),
             ("Other transfer payments", [115.0, 122.4, 125.7, 128.6, 129.6, 129.2]),
             ("Other direct program expenses", [131.0, 150.0, 149.1, 150.8, 156.6, 159.5]),
             ("Total program expenses, excluding net actuarial losses (gains)", [498.5, 542.7, 559.3, 568.3, 586.3, 600.2]),
             ("Public debt charges", [53.5, 60.2, 67.3, 73.8, 78.4, 85.5]),
             ("Net actuarial losses (gains)", [13.6, -0.4, 0.2, -3.0, -3.6, -3.7]),
             ("Total expenses", [565.7, 602.6, 626.8, 639.1, 661.1, 682.1]),
         ]),
    dict(id="capital", title="Capital investments", table="Table A1.5", pdf_page=339, unit="CAD billions", years=YEARS6,
         rows=[
             ("Capital investments in Budget 2026", [37.4, 58.8, 73.7, 77.9, 78.0, 78.2]),
             ("Capital investments in Budget 2026 (cash basis)", [60.2, 103.3, 126.0, 131.4, 130.9, 124.7]),
         ]),
    dict(id="operating", title="Day-to-day operating balance", table="Table A1.6", pdf_page=339, unit="CAD billions", years=YEARS6,
         rows=[
             ("Day-to-day operating expenses", [534.6, 553.7, 569.8, 578.2, 598.0, 618.1]),
             ("Capital investments (expenses)", [31.1, 48.8, 57.0, 60.9, 63.1, 64.0]),
             ("Capital investments (forgone revenues)", [6.3, 9.9, 16.8, 16.9, 14.9, 14.2]),
             ("Day-to-day operating balance", [-2.0, -3.5, 11.2, 20.3, 24.6, 25.2]),
         ]),
    dict(id="non-budgetary", title="Non-budgetary transactions and financial requirement", table="Table A1.11", pdf_page=354, unit="CAD billions", years=YEARS6,
         note="Loans, investments and advances (mostly to enterprise Crown corporations such as CMHC, BDC, EDC and Farm Credit Canada) are financed through borrowing but are not budgetary expenses.",
         rows=[
             ("Budgetary balance", [-39.3, -62.3, -62.5, -57.6, -53.4, -52.9]),
             ("Loans, investments and advances - enterprise Crown corporations", [-55.4, -59.1, -66.3, -66.4, -36.3, -32.1]),
             ("Loans, investments and advances - other", [-5.2, -13.4, -7.7, -4.1, -5.2, -9.3]),
             ("Loans, investments and advances - total", [-60.5, -72.5, -74.0, -70.4, -41.6, -41.4]),
             ("Non-financial assets", [-18.5, -26.1, -35.5, -37.9, -39.6, -39.8]),
             ("Total non-budgetary transactions", [-64.5, -87.2, -106.5, -110.4, -85.7, -86.1]),
             ("Financial source (requirement)", [-103.9, -149.5, -169.0, -168.0, -139.1, -139.1]),
         ]),
]

ECONOMY = dict(table="Table A1.12", pdf_page=358, years=["2026", "2027", "2028", "2029", "2030"],
               rows=[("Real GDP growth (%)", [1.0, 1.7, 2.0, 2.0, 1.9]),
                     ("GDP inflation (%)", [4.6, 1.9, 1.6, 1.9, 1.9]),
                     ("Unemployment rate (%)", [6.6, 6.2, 5.9, 5.9, 5.8]),
                     ("Nominal GDP (CAD billions)", [3427, 3552, 3681, 3826, 3975])])


def series(table_id, label):
    t = next(t for t in TABLES if t["id"] == table_id)
    return next(v for k, v in t["rows"] if k == label)
