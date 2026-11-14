"""Build the Paper 2 analysis panel from XBRL companyfacts.

Per firm-year: supplier-finance activity and balance, the forward operating
cash-flow outcome, and the Barth-Cram-Nelson accrual components that the
baseline specification requires.

Caches companyfacts to disk; earlier scripts refetched on every run.
"""
import datetime as dt
import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
UA = {"User-Agent": "Academic Research jerry.silvon@bbabah.christuniversity.in"}
CACHE = ROOT / "data/raw/companyfacts"

INC = "SupplierFinanceProgramObligationIncrease"
SETL = "SupplierFinanceProgramObligationDecreaseSettlement"
BAL = ["SupplierFinanceProgramObligation", "SupplierFinanceProgramObligationCurrent"]

# duration facts (flows)
FLOW = {
    "ocf": ["NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "dep": ["DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet",
            "DepreciationAndAmortization"],
    "ni": ["NetIncomeLoss"],
    "rev": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
            "RevenueFromContractWithCustomerIncludingAssessedTax"],
}
# instant facts (stocks)
STOCK = {
    "assets": ["Assets"],
    "ar": ["AccountsReceivableNetCurrent", "ReceivablesNetCurrent"],
    "ap": ["AccountsPayableCurrent", "AccountsPayableTradeCurrent"],
    "inv": ["InventoryNet"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue"],
    "debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "equity": ["StockholdersEquity"],
}


def companyfacts(cik):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"CIK{cik:010d}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    r = requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json",
                     headers=UA, timeout=45)
    time.sleep(0.15)
    if r.status_code != 200:
        return None
    path.write_text(json.dumps(r.json()), encoding="utf-8")
    return r.json()


def annual_flows(gaap, names):
    """{(start,end): val} for ~annual durations, first matching element wins."""
    for n in names:
        out = {}
        for f in gaap.get(n, {}).get("units", {}).get("USD", []):
            s, e = f.get("start"), f.get("end")
            if not s or not e or f.get("form") not in ("10-K", "10-K/A"):
                continue
            if 340 <= (dt.date.fromisoformat(e) - dt.date.fromisoformat(s)).days <= 400:
                out[(s, e)] = f["val"]
        if out:
            return out
    return {}


def instants(gaap, names):
    """{end: val}, first matching element wins."""
    for n in names:
        out = {}
        for f in gaap.get(n, {}).get("units", {}).get("USD", []):
            e = f.get("end")
            if e and not f.get("start") and f.get("form") in ("10-K", "10-K/A"):
                out[e] = f["val"]
        if out:
            return out
    return {}


def main():
    cov = json.loads((ROOT / "outputs/supplier_finance/tag_coverage.json").read_text())
    ciks = [r["cik"] for r in cov if r.get("has_activity")]
    rows, skipped = [], []
    for i, cik in enumerate(ciks, 1):
        j = companyfacts(cik)
        if not j:
            skipped.append(dict(cik=cik, reason="companyfacts_unavailable"))
            continue
        g = j.get("facts", {}).get("us-gaap", {})
        inc, setl = annual_flows(g, [INC]), annual_flows(g, [SETL])
        periods = sorted(set(inc) & set(setl))
        if not periods:
            skipped.append(dict(cik=cik, reason="no_matched_annual_activity"))
            continue
        ocf = annual_flows(g, FLOW["ocf"])
        flows = {k: annual_flows(g, v) for k, v in FLOW.items() if k != "ocf"}
        stocks = {k: instants(g, v) for k, v in STOCK.items()}
        bal = instants(g, BAL)
        # index annual periods by end-date so t+1 can be located
        ocf_by_end = {e: v for (s, e), v in ocf.items()}
        ends = sorted(ocf_by_end)
        for (s, e) in periods:
            fy = int(e[:4])
            nxt = next((x for x in ends if 340 <= (dt.date.fromisoformat(x)
                                                   - dt.date.fromisoformat(e)).days <= 400), None)
            prior_end = next((x for x in sorted(stocks["assets"], reverse=True) if x < e), None)
            row = dict(
                cik=cik, entity=j.get("entityName", ""), fy=fy, period_start=s, period_end=e,
                additions=inc[(s, e)], settlements=setl[(s, e)],
                balance_end=bal.get(e), balance_begin=bal.get(prior_end) if prior_end else None,
                ocf_t=ocf_by_end.get(e), ocf_t1=ocf_by_end.get(nxt) if nxt else None,
                ocf_t1_end=nxt,
                assets=stocks["assets"].get(e), assets_begin=stocks["assets"].get(prior_end) if prior_end else None,
                ar=stocks["ar"].get(e), ar_begin=stocks["ar"].get(prior_end) if prior_end else None,
                ap=stocks["ap"].get(e), ap_begin=stocks["ap"].get(prior_end) if prior_end else None,
                inv=stocks["inv"].get(e), inv_begin=stocks["inv"].get(prior_end) if prior_end else None,
                cash=stocks["cash"].get(e), debt=stocks["debt"].get(e), equity=stocks["equity"].get(e),
                dep=flows["dep"].get((s, e)), ni=flows["ni"].get((s, e)), rev=flows["rev"].get((s, e)),
            )
            rows.append(row)
        if i % 25 == 0:
            print(f"{i}/{len(ciks)} firms, {len(rows)} rows", flush=True)
    out = ROOT / "outputs/supplier_finance/panel.json"
    out.write_text(json.dumps(dict(
        built_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        firms=len({r["cik"] for r in rows}), rows=len(rows),
        with_forward_ocf=sum(r["ocf_t1"] is not None for r in rows),
        skipped=skipped, data=rows), indent=2), encoding="utf-8")
    print(json.dumps(dict(firms=len({r["cik"] for r in rows}), rows=len(rows),
                          with_forward_ocf=sum(r["ocf_t1"] is not None for r in rows),
                          skipped=len(skipped))), flush=True)


if __name__ == "__main__":
    main()
