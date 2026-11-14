"""Paper B: what do administrative price ceilings cost co-located storage?

Design. The obvious objection to any cap study is that the counterfactual
uncapped price is unknowable. We never estimate one. Instead we hold an OBSERVED
price series fixed and apply different ceilings to it, so the only thing that
changes between scenarios is the ceiling. Regime A (Rs20/kWh) is the least
censored series available - the cap binds in 0.44% of hours - so it serves as the
base series onto which the Rs12 and Rs10 ceilings are imposed.

Battery dispatch is price-taker perfect-foresight daily arbitrage solved exactly
by dynamic programming over state of charge, so every schedule reported is
chronologically feasible and multiple cycles per day are allowed where profitable.
The battery starts and ends each day empty.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/price_caps"

# Battery: 1 MW / D MWh, round-trip efficiency applied on discharge.
DURATIONS = [2, 4]
ETA_RT = 0.85


def dispatch_day(prices, dur, eta):
    """Exact daily dispatch by dynamic programming over state of charge.

    An earlier version charged in the D cheapest hours and discharged in the D
    most expensive. That is chronologically infeasible whenever a discharge hour
    precedes a charge hour, which a diagnostic showed happens on ~30% of days for
    a 4-hour battery - it overstates revenue. This enumerates feasible schedules
    instead: state is energy stored in 1 MWh steps, each hour may charge, hold or
    discharge at 1 MW, and the battery starts and ends the day empty.
    """
    n = len(prices)
    if n < 2:
        return 0.0, True
    NEG = -1e18
    # value[s] = best profit so far ending this hour at state of charge s
    value = np.full(dur + 1, NEG)
    value[0] = 0.0
    for t in range(n):
        nxt = np.full(dur + 1, NEG)
        p = prices[t]
        for s in range(dur + 1):
            if value[s] == NEG:
                continue
            v = value[s]
            if v > nxt[s]:                      # hold
                nxt[s] = v
            if s + 1 <= dur and v - p > nxt[s + 1]:   # charge 1 MWh
                nxt[s + 1] = v - p
            if s - 1 >= 0 and v + p * eta > nxt[s - 1]:  # discharge 1 MWh
                nxt[s - 1] = v + p * eta
        value = nxt
    best = value[0]                              # must end empty
    return (max(best, 0.0), True)


def run(series, dur, eta=ETA_RT):
    """series: DataFrame with ts, price (Rs/MWh). Returns per-day results."""
    g = series.set_index("ts").sort_index()
    days, revs, oks = [], [], []
    for day, chunk in g.groupby(g.index.date):
        r, ok = dispatch_day(chunk["price"].to_numpy(float), dur, eta)
        days.append(day)
        revs.append(r)
        oks.append(ok)
    return pd.DataFrame(dict(day=days, revenue=revs, ordering_ok=oks))  # ordering always feasible under DP


def apply_cap(series, cap):
    s = series.copy()
    s["price"] = s["price"].clip(upper=cap)
    return s


def main():
    panel = pd.read_csv(OUT / "panel.csv.gz", parse_dates=["ts"])
    price = panel[panel.site == panel.site.iloc[0]][["ts", "price", "regime", "cap"]].copy()

    res = {"generated": pd.Timestamp.utcnow().isoformat(), "eta_rt": ETA_RT}

    # ---- 1. how often does each ceiling bind, and how much of the tail is lost
    print("=== 1. Censoring by regime ===")
    cens = []
    for r in ["A", "B", "C"]:
        s = price[price.regime == r]
        cap = s["cap"].iloc[0]
        at = (s.price >= cap - 1e-9).mean() * 100
        cens.append(dict(regime=r, cap=cap, hours=len(s), pct_at_cap=at,
                         mean=s.price.mean(), p99=s.price.quantile(.99)))
        print(f"  {r}: cap Rs{cap/1000:>2.0f}/kWh | {len(s):>5} hrs | "
              f"at cap {at:5.2f}% | mean Rs{s.price.mean()/1000:4.2f} | "
              f"p99 Rs{s.price.quantile(.99)/1000:5.2f}")
    res["censoring"] = cens

    # ---- 2. the clean counterfactual: same series, different ceilings
    print("\n=== 2. Counterfactual ceilings applied to the SAME observed series ===")
    base = price[price.regime == "A"][["ts", "price"]].copy()
    n_days = base.ts.dt.date.nunique()
    print(f"  base series: regime A, {len(base)} hrs, {n_days} days "
          f"(least-censored available, cap binds 0.44% of hours)")
    cf = []
    for dur in DURATIONS:
        row = {"duration_h": dur}
        ref = None
        for cap in [20000, 12000, 10000, 8000]:
            d = run(apply_cap(base, cap), dur)
            tot = d.revenue.sum()
            per_mw_yr = tot / n_days * 365
            if ref is None:
                ref = per_mw_yr
            row[f"cap_{cap}"] = dict(
                annual_rs_per_mw=per_mw_yr,
                pct_of_uncapped=per_mw_yr / ref * 100,
                days_dispatched=int((d.revenue > 0).sum()),
                ordering_feasible_pct=float(d.ordering_ok.mean() * 100))
            print(f"  {dur}h battery, cap Rs{cap/1000:>2.0f}: "
                  f"Rs{per_mw_yr/1e6:6.3f}M/MW/yr  "
                  f"({per_mw_yr/ref*100:5.1f}% of Rs20 case)  "
                  f"dispatched {int((d.revenue>0).sum()):>3}/{n_days} days  "
                  f"ordering ok {d.ordering_ok.mean()*100:5.1f}%")
        cf.append(row)
    res["counterfactual"] = cf

    # ---- 3. realised revenue per regime (descriptive; confounded by fuel/demand)
    print("\n=== 3. Realised revenue by regime (NOT causal - see limitation) ===")
    real = []
    for r in ["A", "B", "C"]:
        s = price[price.regime == r][["ts", "price"]]
        nd = s.ts.dt.date.nunique()
        for dur in DURATIONS:
            d = run(s, dur)
            v = d.revenue.sum() / nd * 365
            real.append(dict(regime=r, duration_h=dur, annual_rs_per_mw=v, days=nd))
            print(f"  {r} {dur}h: Rs{v/1e6:6.3f}M/MW/yr over {nd} days")
    res["realised"] = real

    # ---- 4. month-matched comparison, to strip seasonality from the regime split
    print("\n=== 4. Month-matched (Apr-Aug only, all three regimes) ===")
    mm = price[price.ts.dt.month.isin([4, 5, 6, 7, 8])]
    matched = []
    for r in ["A", "B", "C"]:
        s = mm[mm.regime == r][["ts", "price"]]
        if s.empty:
            continue
        nd = s.ts.dt.date.nunique()
        d = run(s, 4)
        v = d.revenue.sum() / nd * 365
        matched.append(dict(regime=r, annual_rs_per_mw=v, days=nd,
                            mean_price=float(s.price.mean())))
        print(f"  {r}: Rs{v/1e6:6.3f}M/MW/yr | {nd} days | mean Rs{s.price.mean()/1000:4.2f}/kWh")
    res["month_matched"] = matched

    (OUT / "analysis.json").write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote {OUT/'analysis.json'}")


if __name__ == "__main__":
    main()


def colocation(panel, caps=(20000, 12000, 10000, 8000)):
    """Solar capture price and co-located value under each ceiling.

    Capture price is the generation-weighted mean price a solar plant receives -
    the number that matters to a merchant solar investor, and the one a ceiling
    truncates from above. Co-located value adds storage revenue on the same
    connection. Both are computed per site so spatial variation is visible.
    """
    rows = []
    for site, g in panel.groupby("site"):
        g = g.sort_values("ts")
        pv = g["pv_kw_per_kwp"].to_numpy(float)          # kW per kWp = MW per MWp
        gen = pv.sum()
        for cap in caps:
            p = np.minimum(g["price"].to_numpy(float), cap)
            capture = float((p * pv).sum() / gen)        # Rs/MWh, gen-weighted
            flat = float(p.mean())
            rows.append(dict(site=site, cap=cap, capture_price=capture,
                             flat_mean=flat, capture_ratio=capture / flat,
                             gen_mwh_per_mwp=float(gen)))
    return pd.DataFrame(rows)


def run_colocation():
    panel = pd.read_csv(OUT / "panel.csv.gz", parse_dates=["ts"])
    df = colocation(panel)
    print("\n=== 5. Solar capture price by site and ceiling (Rs/kWh) ===")
    piv = df.pivot(index="site", columns="cap", values="capture_price") / 1000
    ratio = df.pivot(index="site", columns="cap", values="capture_ratio")
    print(f"{'site':<16}" + "".join(f"{c//1000:>8}" for c in sorted(piv.columns)) +
          "   capture ratio @Rs10")
    for s in piv.index:
        print(f"{s:<16}" + "".join(f"{piv.loc[s,c]:>8.2f}" for c in sorted(piv.columns)) +
              f"{ratio.loc[s,10000]:>12.3f}")
    lo, hi = piv[10000].min(), piv[10000].max()
    print(f"\nspatial spread at the Rs10 ceiling: Rs{lo:.2f}-{hi:.2f}/kWh "
          f"({(hi/lo-1)*100:.1f}% across {len(piv)} sites)")
    d20, d10 = piv[20000].mean(), piv[10000].mean()
    print(f"mean capture price Rs{d20:.2f} -> Rs{d10:.2f}/kWh as ceiling falls "
          f"Rs20 -> Rs10  ({(1-d10/d20)*100:.1f}% lower)")
    df.to_csv(OUT / "colocation.csv", index=False)
    print(f"wrote {OUT/'colocation.csv'}")
    return df


if __name__ == "__main__" and "--coloc" in sys.argv:
    run_colocation()
