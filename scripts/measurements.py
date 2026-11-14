"""Conservative measurement primitives; synthetic tests are not empirical results."""
from datetime import date
from math import isfinite


def first_available_fact(facts, start, end, as_of, unit="USD"):
    candidates = [f for f in facts if f.get("start") == start and f["end"] == end
                  and f["filed"] <= as_of and f.get("unit", "USD") == unit
                  and f.get("form") in {"10-K", "10-Q", "10-K/A", "10-Q/A"}]
    if not candidates:
        return None
    first_date = min(f["filed"] for f in candidates)
    earliest = [f for f in candidates if f["filed"] == first_date]
    if len({f["val"] for f in earliest}) != 1:
        raise ValueError("Conflicting earliest-vintage facts require source review")
    return sorted(earliest, key=lambda f: f["accn"])[0]


def supplier_rollforward(opening, confirmations, settlements, closing, assets,
                         other_changes=0.0, tolerance=0.0):
    values = [opening, confirmations, settlements, closing, assets, other_changes]
    if any(v is None for v in values):
        return {"status": "missing_input"}
    if not all(isfinite(v) for v in values) or assets <= 0:
        raise ValueError("Nonfinite input or nonpositive assets")
    if min(opening, confirmations, settlements, closing) < 0:
        raise ValueError("Balances and gross flows must use nonnegative magnitude convention")
    error = closing - (opening + confirmations - settlements + other_changes)
    return {"status": "reconciled" if abs(error) <= tolerance else "review_required",
            "reconciliation_error_usd": error,
            "balance_assets": closing / assets,
            "confirmations_assets": confirmations / assets,
            "settlements_assets": settlements / assets,
            "gross_turnover": settlements / ((opening + closing) / 2) if opening + closing > 0 else None}


def conditional_maturity(instruments, as_of, horizon_end):
    """Stress exposure conditional on documented trigger failure, not a probability."""
    now, horizon = date.fromisoformat(as_of), date.fromisoformat(horizon_end)
    if horizon <= now:
        raise ValueError("Horizon must follow as-of date")
    ids = [r["instrument_id"] for r in instruments]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate instruments would double-count exposure")
    nominal_due, shifted_debt, lost_undrawn = 0.0, 0.0, 0.0
    for row in instruments:
        if row["source_filed"] > as_of:
            raise ValueError("Future filing in predictor")
        if row["drawn_usd"] < 0 or row["undrawn_available_usd"] < 0:
            raise ValueError("Negative exposure")
        nominal = date.fromisoformat(row["nominal_maturity"])
        spring = date.fromisoformat(row["conditional_maturity"])
        if spring >= nominal:
            raise ValueError("Conditional date must precede nominal maturity")
        if spring <= now:
            raise ValueError("Past trigger requires observed amendment/outcome review")
        if now < nominal <= horizon:
            nominal_due += row["drawn_usd"]
        if spring <= horizon < nominal:
            shifted_debt += row["drawn_usd"]
            lost_undrawn += row["undrawn_available_usd"]
    return {"nominal_due_usd": nominal_due, "conditional_extra_drawn_usd": shifted_debt,
            "conditional_lost_undrawn_usd": lost_undrawn}
