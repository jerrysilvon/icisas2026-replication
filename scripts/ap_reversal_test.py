"""Does net programme flow(t) predict OCF(t+1) beyond the payables channel?

The concern: net flow(t) moves AP at the year-t balance sheet date. AP(t) is the
opening balance for dAP(t+1), and dAP(t+1) sits inside OCF(t+1). A coefficient
near -1 is what mechanical reversal looks like. Controlling dAP(t) handles the
contemporaneous leak but not the t+1 one.

Test: build dAP(t+1) from cached companyfacts and (a) control for it, (b) strip
it out of the outcome. If net flow survives both, the result is not the identity.
"""
import json, glob, sys, datetime as dt
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analysis import load, fit, BCN  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
AP_TAGS = ["AccountsPayableCurrent", "AccountsPayableAndAccruedLiabilitiesCurrent"]


def ap_series(cik):
    """{period_end_date: AP value} from the cached companyfacts file."""
    p = ROOT / f"data/raw/companyfacts/CIK{cik:010d}.json"
    if not p.exists():
        return {}
    g = json.loads(p.read_text(encoding="utf-8")).get("facts", {}).get("us-gaap", {})
    out = {}
    for tag in AP_TAGS:
        for f in g.get(tag, {}).get("units", {}).get("USD", []):
            if f.get("end") and f.get("form") == "10-K":
                out.setdefault(f["end"], f["val"])
        if out:
            break
    return out


def nearest(series, target, tol=45):
    """AP reported within tol days of target date."""
    t = dt.date.fromisoformat(target)
    best, bd = None, tol + 1
    for k, v in series.items():
        d = abs((dt.date.fromisoformat(k) - t).days)
        if d < bd:
            best, bd = v, d
    return best


df = load()
print(f"estimation sample n={len(df)} firms={df.cik.nunique()}")

rows = []
for r in df.itertuples():
    s = ap_series(int(r.cik))
    if not s:
        continue
    end_t = str(r.period_end)[:10]
    end_t1 = str(r.ocf_t1_end)[:10] if getattr(r, "ocf_t1_end", None) else None
    if not end_t1 or end_t1 == "None":
        continue
    ap_t, ap_t1 = nearest(s, end_t), nearest(s, end_t1)
    if ap_t is None or ap_t1 is None:
        continue
    rows.append({"cik": r.cik, "period_end": end_t, "ap_t": ap_t, "ap_t1": ap_t1})

ap = pd.DataFrame(rows)
print(f"rows with AP(t) and AP(t+1) recovered: {len(ap)}")

d = df.merge(ap, on=["cik", "period_end"], how="inner")
A = (d["assets"] + d["assets_begin"]) / 2
d["d_ap_t1"] = (d["ap_t1"] - d["ap_t"]) / A
d["y_ex_ap"] = d["y"] - d["d_ap_t1"]          # OCF(t+1) stripped of the payables change
print(f"merged sample n={len(d)} firms={d.cik.nunique()}")
print(f"corr(netflow, d_ap_t1) = {d['netflow'].corr(d['d_ap_t1']):.3f}")
print()

def run(dat, ycol, cols, label):
    sub = dat.dropna(subset=[ycol] + cols).copy()
    if ycol != "y":
        sub = sub.drop(columns=["y"]).rename(columns={ycol: "y"})
    m = fit(sub, cols, label)
    i = m.names.index("netflow")
    print(f"  {label:<46} n={len(sub):>3} coef={m.beta[i]:+.3f} "
          f"se={m.se[i]:.3f} p={m.p()[i]:.3f} adjR2={m.adj_r2:.4f}")

print("--- (a) outcome = OCF(t+1), baseline + net flow ---")
run(d, "y", BCN + ["netflow"], "on the merged subsample")

print("--- (b) outcome = OCF(t+1), + dAP(t+1) as control ---")
run(d, "y", BCN + ["netflow", "d_ap_t1"], "net flow controlling dAP(t+1)")

print("--- (c) outcome = OCF(t+1) minus dAP(t+1) ---")
run(d, "y_ex_ap", BCN + ["netflow"], "net flow on non-payables OCF")
