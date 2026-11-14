import json, time, requests, collections, datetime as dt

UA = {"User-Agent": "Academic Research jerry.silvon@bbabah.christuniversity.in"}
INC = "SupplierFinanceProgramObligationIncrease"
SET = "SupplierFinanceProgramObligationDecreaseSettlement"

cov = json.load(open("outputs/supplier_finance/tag_coverage.json"))
ciks = [r["cik"] for r in cov if r["has_activity"]]
print(f"firms with >=1 activity element: {len(ciks)}", flush=True)

def annual(units):
    """distinct (start,end) periods of ~annual length"""
    out = {}
    for f in units:
        s, e = f.get("start"), f.get("end")
        if not s or not e:
            continue
        d = (dt.date.fromisoformat(e) - dt.date.fromisoformat(s)).days
        if 340 <= d <= 400:
            out[(s, e)] = f["val"]
    return out

rows, err = [], collections.Counter()
for i, cik in enumerate(ciks):
    try:
        r = requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json",
                         headers=UA, timeout=30)
    except Exception as e:
        err[type(e).__name__] += 1; continue
    time.sleep(0.12)
    if r.status_code != 200:
        err[f"HTTP {r.status_code}"] += 1; continue
    j = r.json(); g = j.get("facts", {}).get("us-gaap", {})
    inc = annual(g.get(INC, {}).get("units", {}).get("USD", []))
    stl = annual(g.get(SET, {}).get("units", {}).get("USD", []))
    both = sorted(set(inc) & set(stl))
    rows.append({"cik": cik, "entity": j.get("entityName", ""),
                 "n_inc": len(inc), "n_set": len(stl),
                 "usable_years": [s[:4] for s, e in both],
                 "n_usable": len(both)})
    if (i + 1) % 50 == 0:
        print(f"  {i+1}/{len(ciks)}", flush=True)

json.dump(rows, open("outputs/supplier_finance/usable_panel.json", "w"), indent=1)
usable = [r for r in rows if r["n_usable"] > 0]
yc = collections.Counter(y for r in rows for y in r["usable_years"])
print(f"\nqueried {len(rows)} | errors {dict(err)}")
print(f"firms with >=1 USABLE annual rollforward (both elements): {len(usable)}")
print(f"usable firm-years by fiscal start year: {dict(sorted(yc.items()))}")
print(f"total usable firm-years: {sum(r['n_usable'] for r in rows)}")
print(f"firms with >=2 usable years: {sum(1 for r in rows if r['n_usable']>=2)}")
print(f"\nasymmetry: firms with settlements but no annual additions: "
      f"{sum(1 for r in rows if r['n_set']>0 and r['n_inc']==0)}")
