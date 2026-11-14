"""Does the optimisation horizon change the measured ceiling effect?

Sioshansi, Denholm, Jenkin & Weiss (2009) optimise storage dispatch over a
two-week horizon with perfect foresight, which admits inter-day and weekend
arbitrage. The main results here use a daily horizon with the battery empty at
each day boundary. This compares the two.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paperB_analysis import apply_cap, ETA_RT      # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/price_caps"


def dispatch_block(prices, dur, eta):
    """Exact DP over an arbitrary-length block; starts and ends empty."""
    n = len(prices)
    NEG = -1e18
    val = np.full(dur + 1, NEG)
    val[0] = 0.0
    for t in range(n):
        p = prices[t]
        nxt = val.copy()                       # hold
        chg = np.full(dur + 1, NEG)
        chg[1:] = val[:-1] - p                 # charge 1 MWh
        dis = np.full(dur + 1, NEG)
        dis[:-1] = val[1:] + p * eta           # discharge 1 MWh
        val = np.maximum(nxt, np.maximum(chg, dis))
    return max(val[0], 0.0)


def run(series, dur, days_per_block, eta=ETA_RT):
    g = series.set_index("ts").sort_index()
    d0 = g.index.normalize()
    block = ((d0 - d0[0]).days // days_per_block)
    total, n_days = 0.0, g.index.normalize().nunique()
    for _, idx in pd.Series(block, index=g.index).groupby(block):
        chunk = g.loc[idx.index, "price"].to_numpy(float)
        total += dispatch_block(chunk, dur, eta)
    return total / n_days * 365


def main():
    panel = pd.read_csv(OUT / "panel.csv.gz", parse_dates=["ts"])
    price = panel[panel.site == panel.site.iloc[0]][["ts", "price", "regime"]]
    base = price[price.regime == "A"][["ts", "price"]].copy()

    print("Arbitrage revenue (Rs M/MW/yr) and value removed, by optimisation horizon")
    print(f"{'horizon':<12}{'cap':>6}{'2h':>10}{'removed':>10}{'4h':>10}{'removed':>10}")
    rows = []
    for label, dpb in [("daily", 1), ("weekly", 7), ("two-week", 14)]:
        ref = {}
        for cap in (20000, 12000, 10000, 8000):
            s = apply_cap(base, cap)
            v2, v4 = run(s, 2, dpb), run(s, 4, dpb)
            ref.setdefault(2, v2); ref.setdefault(4, v4)
            r2 = 100 * (1 - v2 / ref[2]); r4 = 100 * (1 - v4 / ref[4])
            print(f"{label:<12}{cap//1000:>6}{v2/1e6:>10.3f}{r2:>9.1f}%{v4/1e6:>10.3f}{r4:>9.1f}%")
            rows.append(dict(horizon=label, cap=cap, rs_2h=v2, removed_2h=r2,
                             rs_4h=v4, removed_4h=r4))
        print()
    pd.DataFrame(rows).to_csv(OUT / "horizon_check.csv", index=False)
    print(f"wrote {OUT/'horizon_check.csv'}")


if __name__ == "__main__":
    main()
