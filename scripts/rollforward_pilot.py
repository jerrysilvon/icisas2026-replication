"""Reconcile original-filing annual supplier-finance facts for access-pilot issuers."""
from datetime import date, timedelta
from discover import ROOT, save_json
from measurements import supplier_rollforward
import json


def match(facts, accn, end, start=None):
    selected = [f for f in facts if f["accn"] == accn and f["end"] == end and f.get("start") == start]
    values = {f["val"] for f in selected}
    return next(iter(values)) if len(values) == 1 else None


if __name__ == "__main__":
    results = []
    for path in (ROOT / "data/raw/http").glob("*.json"):
        envelope = json.loads(path.read_text(encoding="utf-8"))
        data = envelope["payload"]
        if "facts" not in data:
            continue
        gaap = data["facts"].get("us-gaap", {})
        def facts(tag):
            return gaap.get(tag, {}).get("units", {}).get("USD", [])
        increases = facts("SupplierFinanceProgramObligationIncrease")
        seen = set()
        for inc in sorted(increases, key=lambda f: (f["filed"], f["accn"])):
            if "start" not in inc or inc["form"] != "10-K" or inc["filed"] > "2026-09-12":
                continue
            start, end, accn = inc["start"], inc["end"], inc["accn"]
            if not 350 <= (date.fromisoformat(end) - date.fromisoformat(start)).days <= 380:
                continue
            if (start, end) in seen:
                continue
            seen.add((start, end))
            opening_end = (date.fromisoformat(start) - timedelta(days=1)).isoformat()
            opening = match(facts("SupplierFinanceProgramObligation"), accn, opening_end)
            closing = match(facts("SupplierFinanceProgramObligation"), accn, end)
            confirmations = match(increases, accn, end, start)
            settlements = match(facts("SupplierFinanceProgramObligationDecreaseSettlement"), accn, end, start)
            assets = match(facts("Assets"), accn, end)
            results.append(dict(cik=data["cik"], entity=data["entityName"], start=start, end=end,
                filed=inc["filed"], accession=accn, opening_usd=opening, closing_usd=closing,
                confirmations_usd=confirmations, settlements_usd=settlements, assets_usd=assets,
                source=envelope["url"], source_cache=path.name,
                other_changes_assumption_usd=0, rounding_tolerance_usd=0,
                measurement=supplier_rollforward(opening, confirmations, settlements, closing, assets),
                status="pilot_unvalidated_against_filing_not_inference"))
    save_json(ROOT / "outputs/supplier_finance/rollforward_pilot.json", results)
    print(json.dumps(results, indent=2))
