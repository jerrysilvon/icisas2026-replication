"""Test Paper A's result against the competing explanation in Brockbank, Hill &
Mutlu (2025): programmes used for opportunistic year-end payables manipulation,
concentrated in firms with December fiscal year-ends.

If net flow only predicts among December filers, the finding is a manipulation
artifact. If it holds among non-December filers, it is not.
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analysis import load, fit, BCN  # noqa: E402

df = load()
m = pd.to_datetime(df["period_end"]).dt.month
df["dec_fye"] = (m == 12).astype(float)
df["nf_x_dec"] = df["netflow"] * df["dec_fye"]

print(f"December fiscal year-ends: {int(df.dec_fye.sum())} of {len(df)} "
      f"({100*df.dec_fye.mean():.0f}%)")
print()

def show(sub, label, cols=None):
    cols = cols or BCN + ["netflow"]
    mm = fit(sub, cols, label)
    i = mm.names.index("netflow")
    extra = ""
    if "nf_x_dec" in mm.names:
        j = mm.names.index("nf_x_dec")
        extra = f" | interaction={mm.beta[j]:+.3f} p={mm.p()[j]:.3f}"
    print(f"  {label:<34} n={len(sub):>3} firms={sub.cik.nunique():>3} "
          f"coef={mm.beta[i]:+.3f} se={mm.se[i]:.3f} p={mm.p()[i]:.3f}{extra}")

print("--- split by fiscal year-end month ---")
show(df, "all")
show(df[df.dec_fye == 1], "December FYE only")
show(df[df.dec_fye == 0], "non-December FYE only")
print()
print("--- interaction in one model ---")
show(df, "netflow x December", BCN + ["netflow", "dec_fye", "nf_x_dec"])
