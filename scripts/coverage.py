import json, time, requests, collections, sys

UA = {"User-Agent": "Academic Research jerry.silvon@bbabah.christuniversity.in"}
ACT = ["SupplierFinanceProgramObligationIncrease",
       "SupplierFinanceProgramObligationDecreaseSettlement"]
BAL = ["SupplierFinanceProgramObligation", "SupplierFinanceProgramObligationCurrent"]

ciks = sorted({int(c) for h in json.load(open("data/discovery/supplier_finance.json")) for c in h.get("ciks", [])})
print(f"discovered CIKs: {len(ciks)}", flush=True)

rows, err = [], collections.Counter()
for i, cik in enumerate(ciks):
    u = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
    try:
        r = requests.get(u, headers=UA, timeout=30)
    except Exception as e:
        err[type(e).__name__] += 1; continue
    time.sleep(0.12)
    if r.status_code != 200:
        err[f"HTTP {r.status_code}"] += 1; continue
    g = r.json().get("facts", {}).get("us-gaap", {})
    act_periods = set()
    for el in ACT:
        for unit in g.get(el, {}).get("units", {}).values():
            for f in unit:
                if f.get("start") and f.get("end"):
                    act_periods.add((f["start"][:4], f["end"][:10]))
    rows.append({
        "cik": cik,
        "entity": r.json().get("entityName", ""),
        "has_balance": any(el in g for el in BAL),
        "has_activity": any(el in g for el in ACT),
        "activity_years": sorted({p[0] for p in act_periods}),
        "n_activity_periods": len(act_periods),
    })
    if (i + 1) % 100 == 0:
        print(f"  {i+1}/{len(ciks)}  activity so far: {sum(x['has_activity'] for x in rows)}", flush=True)

json.dump(rows, open("outputs/supplier_finance/tag_coverage.json", "w"), indent=1)
nb = sum(r["has_balance"] for r in rows); na = sum(r["has_activity"] for r in rows)
yrs = collections.Counter(y for r in rows for y in r["activity_years"])
print(f"\nqueried {len(rows)} | errors {dict(err)}")
print(f"has balance tag : {nb} ({100*nb/len(rows):.1f}%)")
print(f"has activity tag: {na} ({100*na/len(rows):.1f}%)")
print(f"activity firm-years by start year: {dict(sorted(yrs.items()))}")
print(f"firms with >=2 activity periods: {sum(1 for r in rows if r['n_activity_periods']>=2)}")
