"""Paper 2 horse race: does gross programme activity forecast cash flow better
than the year-end balance?

Baseline is Barth, Cram & Nelson (2001) disaggregated accruals, not a naive
lagged-cash-flow model. Activity must add content beyond the payables accrual,
which is already a BCN component, or the result is trivially explained.

Inference is cluster-robust by firm (scripts/stats_lite.py; scipy will not load
on this machine).
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stats_lite import OLS, chi2_sf  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/supplier_finance"
# Barth, Cram & Nelson (2001) equation (12) disaggregates earnings into cash flow
# plus DeltaAR, DeltaINV, DeltaAP, DEPR, AMORT and OTHER, all deflated by average
# total assets, excluding financial firms (SIC 6000-6999). XBRL reports
# depreciation and amortisation in a single combined element for most filers, so
# DEPR and AMORT are carried as one term; OTHER is recovered as the residual
# accrual from Earnings = CFO + Accruals.
BCN = ["cf", "d_ar", "d_ap", "d_inv", "dep", "other"]


def winsorize(s, lo=0.01, hi=0.99):
    return s.clip(s.quantile(lo), s.quantile(hi))


def load():
    d = json.loads((OUT / "panel.json").read_text(encoding="utf-8"))
    df = pd.DataFrame(d["data"])
    df["avg_assets"] = df[["assets", "assets_begin"]].mean(axis=1)
    df = df.dropna(subset=["ocf_t1", "ocf_t", "additions", "settlements", "avg_assets"])
    df = df[df["avg_assets"] > 0].copy()

    for c, b in [("ar", "ar_begin"), ("ap", "ap_begin"), ("inv", "inv_begin")]:
        df[f"d_{c}"] = (df[c] - df[b]).fillna(0.0)
    df["dep"] = df["dep"].fillna(0.0)

    A = df["avg_assets"]
    df["y"] = winsorize(df["ocf_t1"] / A)
    df["cf"] = winsorize(df["ocf_t"] / A)
    for c in ["d_ar", "d_ap", "d_inv"]:
        df[c] = winsorize(df[c] / A)
    df["dep"] = winsorize(df["dep"] / A)
    df["bal"] = winsorize((df["balance_end"] / A).fillna(0.0))
    df["add"] = winsorize(df["additions"] / A)
    df["setl"] = winsorize(df["settlements"] / A)
    df["thru"] = winsorize((df["additions"] + df["settlements"]) / (2 * A))
    df["netflow"] = winsorize((df["additions"] - df["settlements"]) / A)
    # OTHER accrual: total accruals (NI - CFO) less the separately identified
    # components, per the identity Accruals = dAR + dINV - dAP - DEP + OTHER
    ni = pd.to_numeric(df["ni"], errors="coerce").fillna(0.0) / A
    df["other"] = winsorize(ni - df["cf"] - df["d_ar"] - df["d_inv"]
                            + df["d_ap"] + df["dep"])

    # BCN exclude financial services firms (SIC 6000-6999)
    sic = _sic_map()
    df["sic"] = df["cik"].map(lambda c: sic.get(int(c)))
    fin = df["sic"].astype(str).str.startswith("6")
    if fin.any():
        print(f"  excluding {int(fin.sum())} financial-firm rows (SIC 6000-6999)")
    return df[~fin].copy()


def _sic_map():
    d = json.loads((ROOT / "data/discovery/supplier_finance.json").read_text(encoding="utf-8"))
    out = {}
    for x in d:
        s = x.get("sics")
        if s:
            for c in x["ciks"]:
                out.setdefault(int(c), str(s[0]))
    return out


def fit(df, cols, label):
    X = np.c_[np.ones(len(df)), df[cols].to_numpy(float)]
    m = OLS(df["y"].to_numpy(float), X, df["cik"].to_numpy(), ["const"] + cols)
    m.label, m.cols = label, cols
    return m


def main():
    df = load()
    # Specifications must match exhibits_paper1.py table2 exactly; the two are
    # read together and any divergence between them is a reporting error.
    specs = [
        ("(1) Baseline", BCN),
        ("(2) + Balance", BCN + ["bal"]),
        ("(3) + Activity", BCN + ["add", "setl"]),
        ("(4) + Net flow", BCN + ["netflow"]),
        ("(5) + Net flow & balance", BCN + ["netflow", "bal"]),
        ("(6) + Throughput", BCN + ["thru"]),
        ("(7) + Balance & activity", BCN + ["bal", "add", "setl"]),
        ("(8) + Balance & throughput", BCN + ["bal", "thru"]),
    ]
    res = [fit(df, c, l) for l, c in specs]

    print(f"\nN = {len(df)} firm-years | {df['cik'].nunique()} firms | "
          f"FY {int(df['fy'].min())}-{int(df['fy'].max())}")
    print(df["fy"].value_counts().sort_index().to_string())

    base = res[0].adj_r2
    print(f"\n{'model':<34}{'n':>5}{'adjR2':>9}{'delta':>9}")
    for m in res:
        print(f"{m.label:<34}{m.n:>5}{m.adj_r2:>9.4f}{m.adj_r2-base:>9.4f}")

    print("\ncoefficients  (coef / clustered SE / z / p)")
    for m in res:
        print(f"\n{m.label}   adjR2={m.adj_r2:.4f}")
        for r in m.summary_rows():
            s = "***" if r["p"] < .01 else "**" if r["p"] < .05 else "*" if r["p"] < .1 else ""
            print(f"   {r['name']:<8}{r['coef']:>10.4f}{r['se']:>10.4f}"
                  f"{r['z']:>8.2f}{r['p']:>9.3f} {s}")

    print("\njoint cluster-robust Wald tests")
    tests = {}
    for label, model, cols in [
        ("activity given baseline", res[2], ["add", "setl"]),
        ("net flow given baseline", res[3], ["netflow"]),
        ("balance given baseline", res[1], ["bal"]),
        ("balance given net flow", res[4], ["bal"]),
        ("net flow given balance", res[4], ["netflow"]),
        ("activity given baseline + balance", res[6], ["add", "setl"]),
        ("balance given baseline + activity", res[6], ["bal"]),
        ("throughput given baseline", res[5], ["thru"]),
        ("throughput given baseline + balance", res[7], ["thru"]),
    ]:
        stat, p = model.wald(cols)
        tests[label] = dict(chi2=stat, df=len(cols), p=p)
        print(f"   {label:<28} chi2={stat:8.3f}  df={len(cols)}  p={p:.4f}")

    summary = dict(
        n=int(len(df)), firms=int(df["cik"].nunique()),
        fy_counts={int(k): int(v) for k, v in df["fy"].value_counts().sort_index().items()},
        models=[dict(label=m.label, n=int(m.n), adj_r2=float(m.adj_r2), r2=float(m.r2),
                     delta_adj_r2=float(m.adj_r2 - base), coefs=m.summary_rows())
                for m in res],
        wald=tests,
        desc={c: {k: float(v) for k, v in df[c].describe().items()}
              for c in ["y", "cf", "bal", "add", "setl", "thru", "netflow"]},
    )
    (OUT / "analysis.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    df.to_csv(OUT / "panel_analysis.csv", index=False)
    print(f"\nwrote {OUT/'analysis.json'} and panel_analysis.csv")


if __name__ == "__main__":
    main()
