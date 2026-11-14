"""Recompute the mandate split and the differencing comparison for Paper A.

Both appear in FINDINGS.md but are absent from analysis.json and uncovered by
verify_docs.py, and the mandate-split table and its surrounding text disagree
(-0.896 vs -0.942). Recomputed here with the same load/fit machinery.
"""
import sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd
from analysis import load, fit, BCN  # noqa: E402

df = load()
print(f"estimation sample: n={len(df)} firms={df.cik.nunique()}")

# rollforward mandatory for fiscal years beginning after 2023-12-15
ps = pd.to_datetime(df["period_start"])
mand = ps > pd.Timestamp("2023-12-15")
print(f"mandated rows={int(mand.sum())} firms={df[mand].cik.nunique()} | "
      f"voluntary rows={int((~mand).sum())} firms={df[~mand].cik.nunique()}")

print("\n--- net flow coefficient by subsample ---")
for label, sub in [("All", df), ("Mandated (FY beginning >2023-12-15)", df[mand]),
                   ("Voluntary (earlier)", df[~mand])]:
    if len(sub) < 30:
        print(f"{label:<38} n={len(sub)} too small"); continue
    base = fit(sub, BCN, "base")
    m = fit(sub, BCN + ["netflow"], "netflow")
    i = m.names.index("netflow")
    print(f"{label:<38} n={len(sub):>3} firms={sub.cik.nunique():>3} "
          f"coef={m.beta[i]:+.3f} se={m.se[i]:.3f} p={m.p()[i]:.3f} "
          f"adjR2 {base.adj_r2:.4f} -> {m.adj_r2:.4f}")

# differencing comparison: rows where a prior-year balance exists
print("\n--- rollforward net flow vs differenced balance ---")
d = df.dropna(subset=["balance_begin", "balance_end"]).copy()
A = (d["assets"] + d["assets_begin"]) / 2
d["dbal"] = (d["balance_end"] - d["balance_begin"]) / A
print(f"rows with both balances: {len(d)} of {len(df)} "
      f"({100*(1-len(d)/len(df)):.1f}% lack a prior-year balance)")
for label, cols in [("baseline", BCN), ("+ differenced balance", BCN + ["dbal"]),
                    ("+ rollforward net flow", BCN + ["netflow"])]:
    m = fit(d, cols, label)
    extra = ""
    if len(cols) > len(BCN):
        i = m.names.index(cols[-1])
        extra = f" coef={m.beta[i]:+.3f} p={m.p()[i]:.3f}"
    print(f"  {label:<24} adjR2={m.adj_r2:.4f}{extra}")

print(f"\ncorr(netflow, dbal) = {d['netflow'].corr(d['dbal']):.3f}")
print(f"corr(netflow, d_ap) = {df['netflow'].corr(df['d_ap']):.3f}")
