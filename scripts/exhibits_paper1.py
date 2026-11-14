"""Paper 1 exhibits: two tables, two figures, sized for IEEE two-column.

IEEE column width is 88 mm (3.46 in); full text width 181 mm (7.12 in). Figures
are written as SVG (vector; matplotlib cannot load here - see svg_plot.py).
Every number here is computed from outputs/supplier_finance/panel.json - nothing
is transcribed by hand.
"""
import json
import sys
from pathlib import Path

import numpy as np                        # noqa: E402
import pandas as pd                       # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analysis import load, BCN            # noqa: E402
from stats_lite import OLS                # noqa: E402
from svg_plot import Fig                  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/supplier_finance/exhibits"
COL, FULL = 3.46, 7.12

INK, ACC, MUT = "#1a1a1a", "#0b6fa4", "#9aa0a6"


def fit(d, cols):
    X = np.c_[np.ones(len(d)), d[cols].to_numpy(float)]
    return OLS(d["y"].to_numpy(float), X, d["cik"].to_numpy(), ["const"] + cols)


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.save(OUT / f"{name}.svg")
    print(f"  wrote {name}.svg")


# ---------------------------------------------------------------- Table I
def table1(df):
    rows = [("OCF_{t+1} / assets", "y"), ("OCF_t / assets", "cf"),
            ("DeltaAR / assets", "d_ar"), ("DeltaAP / assets", "d_ap"),
            ("DeltaINV / assets", "d_inv"), ("Depreciation / assets", "dep"),
            ("Programme balance / assets", "bal"),
            ("Obligations added / assets", "add"),
            ("Obligations settled / assets", "setl"),
            ("Gross throughput / assets", "thru"),
            ("Net programme flow / assets", "netflow")]
    lines = ["| Variable | Mean | SD | P25 | Median | P75 |",
             "|---|---|---|---|---|---|"]
    for lab, c in rows:
        s = df[c]
        lines.append(f"| {lab} | {s.mean():.4f} | {s.std():.4f} | "
                     f"{s.quantile(.25):.4f} | {s.median():.4f} | {s.quantile(.75):.4f} |")
    fy = df.assign(f=df.period_start.str[:4].astype(int)).groupby("f").agg(
        n=("cik", "size"), firms=("cik", "nunique"))
    comp = ["", "**Sample composition**", "",
            "| Fiscal year | Firm-years | Firms |", "|---|---|---|"]
    for y, r in fy.iterrows():
        comp.append(f"| {y} | {int(r.n)} | {int(r.firms)} |")
    comp.append(f"| **Total** | **{len(df)}** | **{df.cik.nunique()}** |")
    txt = ("### TABLE I. DESCRIPTIVE STATISTICS\n\n"
           f"All variables scaled by average total assets and winsorised at the 1st "
           f"and 99th percentiles. N = {len(df)} firm-years, {df.cik.nunique()} firms.\n\n"
           + "\n".join(lines) + "\n" + "\n".join(comp) + "\n")
    (OUT / "table1_descriptives.md").write_text(txt, encoding="utf-8")
    df.to_csv(OUT / "table1_underlying_panel.csv", index=False)
    print("  wrote table1_descriptives.md")


# --------------------------------------------------------------- Table II
def table2(df):
    specs = [("(1) Baseline", BCN), ("(2) + Balance", BCN + ["bal"]),
             ("(3) + Activity", BCN + ["add", "setl"]),
             ("(4) + Net flow", BCN + ["netflow"]),
             ("(5) + Net flow & balance", BCN + ["netflow", "bal"])]
    ms = [(l, fit(df, c)) for l, c in specs]
    names = ["cf", "d_ar", "d_ap", "d_inv", "dep", "bal", "add", "setl", "netflow"]
    pretty = {"cf": "OCF_t", "d_ar": "DeltaAR", "d_ap": "DeltaAP", "d_inv": "DeltaINV",
              "dep": "Depreciation", "bal": "Programme balance",
              "add": "Obligations added", "setl": "Obligations settled",
              "netflow": "Net programme flow"}
    head = "| Variable | " + " | ".join(l for l, _ in ms) + " |"
    sep = "|---" * (len(ms) + 1) + "|"
    lines = [head, sep]
    for n in names:
        cells = []
        for _, m in ms:
            if n in m.names:
                i = m.names.index(n)
                b, se, p = m.beta[i], m.se[i], m.p()[i]
                st = "***" if p < .01 else "**" if p < .05 else "*" if p < .1 else ""
                cells.append(f"{b:.3f}{st}<br>({se:.3f})")
            else:
                cells.append("")
        lines.append(f"| {pretty[n]} | " + " | ".join(cells) + " |")
    lines.append("| Adjusted R2 | " + " | ".join(f"{m.adj_r2:.4f}" for _, m in ms) + " |")
    lines.append("| N | " + " | ".join(str(m.n) for _, m in ms) + " |")
    lines.append("| Firms | " + " | ".join(str(m.G) for _, m in ms) + " |")

    w = []
    for lab, m, cols in [("Activity given baseline", ms[2][1], ["add", "setl"]),
                         ("Net flow given baseline", ms[3][1], ["netflow"]),
                         ("Balance given baseline", ms[1][1], ["bal"]),
                         ("Balance given net flow", ms[4][1], ["bal"]),
                         ("Net flow given balance", ms[4][1], ["netflow"])]:
        s, p = m.wald(cols)
        w.append(f"| {lab} | {s:.3f} | {len(cols)} | {p:.4f} |")

    txt = ("### TABLE II. FORECASTING NEXT-YEAR OPERATING CASH FLOW\n\n"
           "Dependent variable is operating cash flow in year t+1 scaled by average "
           "total assets. Baseline is the Barth-Cram-Nelson disaggregated-accrual "
           "specification. Cluster-robust standard errors by firm in parentheses. "
           "*** p<0.01, ** p<0.05, * p<0.10.\n\n"
           + "\n".join(lines)
           + "\n\n**Joint cluster-robust Wald tests**\n\n"
           + "| Test | chi2 | df | p |\n|---|---|---|---|\n" + "\n".join(w) + "\n")
    (OUT / "table2_results.md").write_text(txt, encoding="utf-8")
    print("  wrote table2_results.md")
    return ms


# --------------------------------------------------------------- Figure 1
def fig1(df):
    fig = Fig(FULL, 2.6)
    a = fig.add_axes(0.075, 0.20, 0.375, 0.60)
    b = fig.add_axes(0.585, 0.20, 0.375, 0.60)

    # (a) programme turnover: obligations added during the year relative to the
    # year-end balance. Uses additions alone; additions+settlements would double
    # count each obligation as it enters and leaves.
    d = df[df.bal > 0]
    turn = (d["add"] / d["bal"])   # d.add is DataFrame.add, the method
    turn = turn[(turn > 0) & (turn < 25)]
    a.grid_axis = "y"
    a.hist(list(turn), bins=34, color=ACC)
    med = float(turn.median())
    a.axvline(med, color=INK, lw=1.0, dash="3,2")
    a.annotate(f"median {med:.1f}x", med, a.ylim[1] * 0.90, dx=5, size=7)
    a.xlabel = "Obligations added during year / year-end balance"
    a.ylabel = "Firm-years"
    a.title = "(a) One year's additions dwarf the balance"

    # (b) added-variable plot of the subsumption claim. Each predictor is
    # residualised on the baseline AND on the other predictor, which is exactly
    # what its coefficient in the joint model measures. x is in SD units so the
    # two slopes are comparable; net flow and the balance otherwise occupy very
    # different scales and the eye reads the wider series as the stronger one.
    def resid(target, cols):
        X = np.c_[np.ones(len(df)), df[cols].to_numpy(float)]
        return target - X @ (np.linalg.pinv(X.T @ X) @ X.T @ target)

    b.grid_axis = "y"
    for var, other, lab, col, mk, dash in [
            ("netflow", "bal", "Net flow (given balance)", ACC, "o", None),
            ("bal", "netflow", "Balance (given net flow)", MUT, "s", "4,2")]:
        ctrl = BCN + [other]
        ey = resid(df["y"].to_numpy(float), ctrl)
        ex = resid(df[var].to_numpy(float), ctrl)
        ex = ex / ex.std()
        q = pd.qcut(pd.Series(ex).rank(method="first"), 8, labels=False)
        gx = pd.Series(ex).groupby(q).mean().tolist()
        gy = pd.Series(ey).groupby(q).mean().tolist()
        b.plot(gx, gy, color=col, marker=mk, ms=3.6, lw=0, label=lab)
        sl = np.polyfit(ex, ey, 1)
        xs = [min(gx), max(gx)]
        b.plot(xs, [sl[0] * x + sl[1] for x in xs], color=col, lw=1.2, dash=dash)
    b.axhline(0.0, color=INK, lw=0.5, dash="2,2")
    b.legend_loc = "upper right"
    b.xlabel = "Predictor residual (standard deviations)"
    b.ylabel = "OCF t+1 residual"
    b.title = "(b) With both included, only the flow slopes"
    save(fig, "fig1_stock_vs_flow")


# --------------------------------------------------------------- Figure 2
def fig2(df):
    df = df.copy()
    df["mandated"] = df.period_start.str[:4].astype(int) >= 2024
    nl = chr(10)
    n_m, n_v = int(df.mandated.sum()), int((~df.mandated).sum())
    subs = [(f"All{nl}(N={len(df)})", df),
            (f"Mandated{nl}FY2024+{nl}(N={n_m})", df[df.mandated]),
            (f"Voluntary{nl}FY2022-23{nl}(N={n_v})", df[~df.mandated])]
    fig = Fig(COL, 2.7)
    ax = fig.add_axes(0.28, 0.19, 0.68, 0.62)
    ax.grid_axis = "x"
    ys = [len(subs) - i for i in range(len(subs))]
    first = True
    for (lab, d), y in zip(subs, ys):
        for var, off, col, mk, nm in [("netflow", 0.16, ACC, "o", "Net programme flow"),
                                      ("bal", -0.16, MUT, "s", "Programme balance")]:
            m = fit(d, BCN + [var])
            i = m.names.index(var)
            ax.errorbar(float(m.beta[i]), y + off, 1.96 * float(m.se[i]),
                        color=col, marker=mk, ms=4.2,
                        label=nm if first else None)
        first = False
    ax.axvline(0, color=INK, lw=0.7, dash=None)
    ax.ylim = (min(ys) - 0.55, max(ys) + 1.05)   # headroom so the legend clears row 1
    ax.yticks = ys
    ax.ytick_labels = [l for l, _ in subs]
    ax.xlabel = "Coefficient (95% CI)"
    ax.title = "Net flow vs. balance, by mandate status"
    save(fig, "fig2_mandate_robustness")


def main():
    df = load()
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"panel: {len(df)} firm-years, {df.cik.nunique()} firms")
    table1(df)
    table2(df)
    fig1(df)
    fig2(df)
    print(f"\nexhibits -> {OUT}")


if __name__ == "__main__":
    main()
