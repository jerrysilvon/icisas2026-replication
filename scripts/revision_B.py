"""Paper B revision tests, for the ICISAS 2026 reviews of submission 117.

R2 Q1  battery degradation and cycle-dependent aging
R2 Q2  sensitivity to price forecast error, the dispatch being perfect-foresight

Both quantities are asserted in the shipped paper and not measured there: the
Limitations say degradation cost falls alongside revenue so the profit loss is
smaller than the revenue loss, and that perfect foresight affects the level far
more than the ratio between ceilings. These two tests put numbers on both.

No published Rs/MWh degradation cost is used. The marginal cycling cost is swept
across a range and reported against the mean price of the series, so a reader can
place any cost assumption on the result instead of inheriting ours.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paperB_analysis import ETA_RT, DURATIONS, apply_cap, dispatch_day  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/price_caps"

CAPS = [20000, 12000, 10000, 8000]
# Rs/MWh discharged. The range is the sweep itself, not a borrowed estimate. The
# top of it is about 70% of the series mean price, by which point arbitrage value
# has fallen by roughly three quarters without reaching zero.
DEG_COSTS = [0, 50, 100, 200, 250, 350, 500, 1000, 1500, 2000, 3000]


def dispatch_path(prices, dur, eta, cdeg=0.0):
    """The dispatch DP of paperB_analysis, carrying a cost per MWh discharged
    and returning the chosen action path.

    State is energy stored in 1 MWh steps; each hour charges, holds or discharges
    at 1 MW; the battery starts and ends the day empty. With cdeg = 0 and the path
    discarded this is dispatch_day, which main() asserts.
    """
    n = len(prices)
    if n < 2:
        return 0.0, np.zeros(0, int)
    NEG = -1e18
    value = np.full(dur + 1, NEG)
    value[0] = 0.0
    back = np.zeros((n, dur + 1), np.int8)
    prev = np.zeros((n, dur + 1), np.int16)
    for t in range(n):
        nxt = np.full(dur + 1, NEG)
        p = prices[t]
        for s in range(dur + 1):
            if value[s] == NEG:
                continue
            v = value[s]
            if v > nxt[s]:
                nxt[s], back[t, s], prev[t, s] = v, 0, s
            if s + 1 <= dur and v - p > nxt[s + 1]:
                nxt[s + 1], back[t, s + 1], prev[t, s + 1] = v - p, 1, s
            if s - 1 >= 0 and v + p * eta - cdeg > nxt[s - 1]:
                nxt[s - 1], back[t, s - 1], prev[t, s - 1] = v + p * eta - cdeg, -1, s
        value = nxt
    best = value[0]
    if best <= 0.0:
        return 0.0, np.zeros(n, int)
    acts = np.zeros(n, int)
    s = 0
    for t in range(n - 1, -1, -1):
        acts[t] = back[t, s]
        s = prev[t, s]
    return float(best), acts


def settle(prices, acts, eta, cdeg=0.0):
    """Cash flow from a committed schedule, valued at the prices that obtained."""
    dis = acts == -1
    cha = acts == 1
    return float((prices[dis] * eta - cdeg).sum() - prices[cha].sum())


def by_day(series):
    g = series.set_index("ts").sort_index()
    return [(d, c["price"].to_numpy(float)) for d, c in g.groupby(g.index.date)]


def annual(total, n_days):
    return total / n_days * 365


def degradation(base, n_days):
    """Value removed by each ceiling, net of a marginal cycling cost."""
    print("\n--- R2 Q1: degradation ---")
    mean_price = float(base["price"].mean())
    print(f"  mean price of the base series Rs{mean_price:,.0f}/MWh; "
          f"costs below are Rs/MWh discharged")
    rows = []
    for dur in DURATIONS:
        for cdeg in DEG_COSTS:
            ref = None
            for cap in CAPS:
                days = by_day(apply_cap(base, cap))
                tot = sum(dispatch_path(p, dur, ETA_RT, cdeg)[0] for _, p in days)
                v = annual(tot, n_days)
                if ref is None:
                    ref = v
                rows.append(dict(duration_h=dur, deg_cost=cdeg, cap=cap,
                                 annual_rs_per_mw=v,
                                 removed_pct=(100.0 * (1 - v / ref)) if ref else 0.0,
                                 pct_of_uncapped=(100.0 * v / ref) if ref else 0.0))
    df = pd.DataFrame(rows)
    for dur in DURATIONS:
        print(f"  {dur}-hour battery, % of Rs20 value remaining "
              f"(rows = cost, cols = ceiling):")
        piv = df[df.duration_h == dur].pivot(index="deg_cost", columns="cap",
                                             values="annual_rs_per_mw")
        hdr = "".join(f"{c//1000:>12}" for c in CAPS)
        print(f"    {'cost':>6}{hdr}      removed @Rs10")
        for c in DEG_COSTS:
            r = piv.loc[c]
            rem = 100.0 * (1 - r[10000] / r[20000]) if r[20000] > 0 else float("nan")
            print(f"    {c:>6}" + "".join(f"{r[k]/1e6:>11.3f}M" for k in CAPS)
                  + f"   {rem:>8.1f}%")
    return df


def foresight(base, n_days):
    """Dispatch against a previous-day persistence forecast, settled at realised
    prices, with the ceiling applied to forecast and settlement alike."""
    print("\n--- R2 Q2: imperfect foresight ---")
    rows = []
    for cap in CAPS:
        capped = apply_cap(base, cap)
        days = by_day(capped)
        usable = [i for i in range(1, len(days))
                  if len(days[i][1]) == len(days[i - 1][1])]
        for dur in DURATIONS:
            pf = sum(dispatch_path(days[i][1], dur, ETA_RT)[0] for i in usable)
            im = 0.0
            for i in usable:
                _, acts = dispatch_path(days[i - 1][1], dur, ETA_RT)
                im += settle(days[i][1], acts, ETA_RT)
            rows.append(dict(cap=cap, duration_h=dur, days=len(usable),
                             perfect=annual(pf, len(usable)),
                             imperfect=annual(im, len(usable))))
    df = pd.DataFrame(rows)
    print(f"  matched day set: {int(df.days.iloc[0])} days with a preceding day")
    out = []
    for dur in DURATIONS:
        d = df[df.duration_h == dur].set_index("cap")
        print(f"  {dur}-hour battery:")
        print(f"    {'ceiling':>8}{'perfect':>12}{'persistence':>13}"
              f"{'capture':>9}{'removed PF':>12}{'removed IF':>12}")
        for cap in CAPS:
            r = d.loc[cap]
            rem_pf = 100.0 * (1 - r.perfect / d.loc[20000].perfect)
            rem_if = 100.0 * (1 - r.imperfect / d.loc[20000].imperfect)
            cap_rate = 100.0 * r.imperfect / r.perfect
            print(f"    {cap//1000:>8}{r.perfect/1e6:>11.3f}M"
                  f"{r.imperfect/1e6:>12.3f}M{cap_rate:>8.1f}%"
                  f"{rem_pf:>11.1f}%{rem_if:>11.1f}%")
            out.append(dict(duration_h=dur, cap=cap, days=int(r.days),
                            perfect=float(r.perfect), imperfect=float(r.imperfect),
                            capture_of_perfect_pct=cap_rate,
                            removed_perfect_pct=rem_pf, removed_imperfect_pct=rem_if))
    return out


def main():
    panel = pd.read_csv(OUT / "panel.csv.gz", parse_dates=["ts"])
    price = panel[panel.site == panel.site.iloc[0]][["ts", "price", "regime"]].copy()
    base = price[price.regime == "A"][["ts", "price"]].copy()
    n_days = base.ts.dt.date.nunique()

    chk = sum(dispatch_path(p, 4, ETA_RT)[0] for _, p in by_day(base))
    ref = sum(dispatch_day(p, 4, ETA_RT)[0] for _, p in by_day(base))
    v = annual(chk, n_days)
    print(f"reproduction check: 4h battery at Rs20 = Rs{v/1e6:.3f}M/MW/yr "
          f"over {n_days} days")
    assert abs(chk - ref) < 1.0, (chk, ref)
    assert abs(v - 5246428.36) < 1000.0, v
    print("  path-tracking DP matches dispatch_day and the as-reviewed Rs5.246M\n")

    res = dict(base_series=dict(hours=int(len(base)), days=int(n_days),
                                mean_price=float(base["price"].mean())),
               degradation=degradation(base, n_days).to_dict(orient="records"),
               foresight=foresight(base, n_days))
    (OUT / "revision_tests.json").write_text(json.dumps(res, indent=2),
                                             encoding="utf-8")
    print(f"\nwrote {OUT/'revision_tests.json'}")


if __name__ == "__main__":
    main()
