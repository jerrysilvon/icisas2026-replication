"""Paper B exhibits: two figures and two tables, IEEE-sized.

Drawn with scripts/svg_plot.py (matplotlib cannot load on this machine).
Every number is computed here from outputs/price_caps/, never transcribed.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paperB_analysis import run, apply_cap, DURATIONS, ETA_RT   # noqa: E402
from svg_plot import Fig                                         # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/price_caps/exhibits"
COL, FULL = 3.46, 7.12
INK, ACC, MUT, WARM = "#1a1a1a", "#0b6fa4", "#9aa0a6", "#c2410c"
CAPS = [20000, 12000, 10000, 8000]


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.save(OUT / f"{name}.svg")
    print(f"  wrote {name}.svg")


def load():
    panel = pd.read_csv(ROOT / "outputs/price_caps/panel.csv.gz", parse_dates=["ts"])
    price = panel[panel.site == panel.site.iloc[0]][["ts", "price", "regime", "cap"]].copy()
    res = json.loads((ROOT / "outputs/price_caps/analysis.json").read_text(encoding="utf-8"))
    return panel, price, res


# ------------------------------------------------------------------ Figure 1
def fig1(price):
    """(a) price duration curves by regime  (b) share of hours at the ceiling."""
    fig = Fig(FULL, 2.6)
    a = fig.add_axes(0.075, 0.20, 0.375, 0.60)
    b = fig.add_axes(0.585, 0.20, 0.375, 0.60)

    a.grid_axis = "both"
    for r, col, dash, lab in [("A", ACC, None, "A: Rs20 ceiling"),
                              ("B", WARM, "4,2", "B: Rs12 ceiling"),
                              ("C", MUT, "2,2", "C: Rs10 ceiling")]:
        s = np.sort(price[price.regime == r]["price"].to_numpy())[::-1] / 1000.0
        x = np.linspace(0, 100, len(s))
        k = max(1, len(s) // 400)
        a.plot(list(x[::k]), list(s[::k]), color=col, lw=1.2, dash=dash, label=lab)
    a.xlim = (0, 25)
    a.xlabel = "Percent of hours exceeded"
    a.ylabel = "Price (Rs/kWh)"
    a.title = "(a) Ceilings flatten the upper tail"
    a.legend_loc = "upper right"

    b.grid_axis = "y"
    regs = ["A", "B", "C"]
    vals, caps = [], []
    for r in regs:
        s = price[price.regime == r]
        caps.append(s["cap"].iloc[0] / 1000)
        vals.append((s.price >= s["cap"] - 1e-9).mean() * 100)
    for i, (v, c) in enumerate(zip(vals, caps)):
        b.plot([i + 1, i + 1], [0, v], color=ACC, lw=9)
        b.annotate(f"{v:.1f}%", i + 1, v, dx=0, dy=-4, size=7, anchor="middle")
    b.xlim = (0.4, 3.6)
    b.ylim = (0, max(vals) * 1.25)
    b.xticks = [1, 2, 3]
    b.xtick_labels = ["A (Rs20)", "B (Rs12)", "C (Rs10)"]
    b.yticks = [0, 5, 10, 15, 20]
    b.xlabel = "Price ceiling regime"
    b.ylabel = "Hours at the ceiling (%)"
    b.title = "(b) Censoring rises as the ceiling falls"
    save(fig, "figB1_censoring")


# ------------------------------------------------------------------ Figure 2
def fig2(price):
    """Arbitrage revenue vs ceiling, same observed series, two battery durations."""
    fig = Fig(COL, 2.6)
    ax = fig.add_axes(0.20, 0.20, 0.75, 0.60)
    ax.grid_axis = "both"
    base = price[price.regime == "A"][["ts", "price"]].copy()
    nd = base.ts.dt.date.nunique()
    for dur, col, mk, dash in [(4, ACC, "o", None), (2, MUT, "s", "4,2")]:
        xs, ys = [], []
        for cap in sorted(CAPS):
            d = run(apply_cap(base, cap), dur)
            xs.append(cap / 1000)
            ys.append(d.revenue.sum() / nd * 365 / 1e6)
        ax.plot(xs, ys, color=col, marker=mk, ms=3.8, lw=1.2, dash=dash,
                label=f"{dur}-hour battery")
    ax.xlabel = "Price ceiling (Rs/kWh)"
    ax.ylabel = "Arbitrage revenue (Rs M / MW / yr)"
    ax.title = "Revenue falls with the ceiling"
    ax.legend_loc = "lower right"
    save(fig, "figB2_revenue_vs_cap")


# ------------------------------------------------------------------- Tables
def tables(price, res, panel):
    OUT.mkdir(parents=True, exist_ok=True)
    c = res["censoring"]
    t1 = ["### TABLE I. PRICE REGIMES AND CENSORING", "",
          "Regime boundaries are set from the observed series: the ceiling is taken to",
          "change on the first day after which it is never exceeded. Both transitions fall",
          "within one day of CERC's interventions of 1 April 2022 and 1 April 2023.", "",
          "| Regime | Ceiling (Rs/kWh) | Hours | Mean (Rs/kWh) | 99th pct | Hours at ceiling |",
          "|---|---|---|---|---|---|"]
    for r in c:
        t1.append(f"| {r['regime']} | {r['cap']/1000:.0f} | {r['hours']} | "
                  f"{r['mean']/1000:.2f} | {r['p99']/1000:.2f} | {r['pct_at_cap']:.2f}% |")
    (OUT / "tableB1_regimes.md").write_text("\n".join(t1) + "\n", encoding="utf-8")

    t2 = ["### TABLE II. ARBITRAGE VALUE REMOVED BY THE CEILING", "",
          "Ceilings applied to a single observed price series (regime A), so the ceiling is",
          "the only thing that differs between columns. Dispatch is exact perfect-foresight",
          f"daily optimisation by dynamic programming, round-trip efficiency {ETA_RT:.0%}.", "",
          "| Ceiling (Rs/kWh) | 2h: Rs M/MW/yr | 2h: value removed | 4h: Rs M/MW/yr | 4h: value removed |",
          "|---|---|---|---|---|"]
    by = {d["duration_h"]: d for d in res["counterfactual"]}
    for cap in CAPS:
        r2, r4 = by[2][f"cap_{cap}"], by[4][f"cap_{cap}"]
        t2.append(f"| {cap/1000:.0f} | {r2['annual_rs_per_mw']/1e6:.3f} | "
                  f"{100-r2['pct_of_uncapped']:.1f}% | {r4['annual_rs_per_mw']/1e6:.3f} | "
                  f"{100-r4['pct_of_uncapped']:.1f}% |")
    t2 += ["", "**Realised revenue by regime (descriptive, not causal)**", "",
           "| Regime | 2h | 4h | Days |", "|---|---|---|---|"]
    rl = {(x["regime"], x["duration_h"]): x for x in res["realised"]}
    for r in ["A", "B", "C"]:
        t2.append(f"| {r} | {rl[(r,2)]['annual_rs_per_mw']/1e6:.3f} | "
                  f"{rl[(r,4)]['annual_rs_per_mw']/1e6:.3f} | {rl[(r,2)]['days']} |")
    t2 += ["", "Realised revenue is *higher* under the tighter ceilings because underlying",
           "volatility rose over the period. That is precisely why the fixed-series",
           "counterfactual above is the identifying comparison and the realised column is not."]
    (OUT / "tableB2_results.md").write_text("\n".join(t2) + "\n", encoding="utf-8")

    sites = (panel.groupby("site")["pv_kw_per_kwp"].sum() /
             panel.site.nunique() * 0 + panel.groupby("site")["pv_kw_per_kwp"].sum())
    yrs = panel.ts.dt.year.nunique()
    t3 = ["### TABLE III. SOLAR SITES", "",
          "PVGIS v5.3 (EU JRC), hourly, 2021-2023, 1 kWp, 14% system loss.", "",
          "| Site | Mean annual yield (kWh/kWp) | Capacity factor |", "|---|---|---|"]
    for s, v in sites.sort_values(ascending=False).items():
        y = v / yrs
        t3.append(f"| {s.replace('_',', ')} | {y:,.0f} | {y/8760*100:.1f}% |")
    (OUT / "tableB3_sites.md").write_text("\n".join(t3) + "\n", encoding="utf-8")
    print("  wrote tableB1_regimes.md, tableB2_results.md, tableB3_sites.md")


def main():
    panel, price, res = load()
    fig1(price)
    fig2(price)
    tables(price, res, panel)
    print(f"\nexhibits -> {OUT}")


if __name__ == "__main__":
    main()
