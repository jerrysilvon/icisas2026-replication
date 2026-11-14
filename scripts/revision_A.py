"""Paper A revision tests, for the ICISAS 2026 reviews of submission 116.

R3 Q1  out-of-sample forecast accuracy against the baseline
R3 Q2  sensitivity to influential firms, outliers and alternative specifications
R3 Q4  liquidity and financing-constraint confounds
R2 Q2  industry differences in working-capital-dependent sectors

Winsorising in analysis.py is applied to the whole sample, which is correct for
the in-sample result but leaks the test fold's tails into training. Every
out-of-sample fit below therefore takes its winsor bounds from the training rows
only, and build() reproduces analysis.py exactly when the training set is
everything.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stats_lite import OLS, norm_sf2  # noqa: E402
from analysis import BCN, _sic_map  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/supplier_finance"

WINS = ["y", "cf", "d_ar", "d_ap", "d_inv", "dep", "bal", "add", "setl",
        "thru", "netflow"]


def load_raw():
    d = json.loads((OUT / "panel.json").read_text(encoding="utf-8"))
    df = pd.DataFrame(d["data"])
    df["avg_assets"] = df[["assets", "assets_begin"]].mean(axis=1)
    df = df.dropna(subset=["ocf_t1", "ocf_t", "additions", "settlements",
                           "avg_assets"])
    df = df[df["avg_assets"] > 0].copy()

    for c, b in [("ar", "ar_begin"), ("ap", "ap_begin"), ("inv", "inv_begin")]:
        df[f"d_{c}"] = (df[c] - df[b]).fillna(0.0)
    df["dep"] = df["dep"].fillna(0.0)

    A = df["avg_assets"]
    df["y"] = df["ocf_t1"] / A
    df["cf"] = df["ocf_t"] / A
    for c in ["d_ar", "d_ap", "d_inv"]:
        df[c] = df[c] / A
    df["dep"] = df["dep"] / A
    df["bal"] = (df["balance_end"] / A).fillna(0.0)
    df["add"] = df["additions"] / A
    df["setl"] = df["settlements"] / A
    df["thru"] = (df["additions"] + df["settlements"]) / (2 * A)
    df["netflow"] = (df["additions"] - df["settlements"]) / A
    df["ni_s"] = pd.to_numeric(df["ni"], errors="coerce").fillna(0.0) / A

    df["cash_s"] = df["cash"] / A
    df["lev_s"] = df["debt"] / A
    df["size"] = np.log(A)
    df["ap_lvl"] = df["ap"] / A

    sic = _sic_map()
    df["sic"] = df["cik"].map(lambda c: sic.get(int(c)))
    return df.reset_index(drop=True)


def build(raw, train=None, lo=0.01, hi=0.99):
    """Scale-and-winsorise exactly as analysis.py does, with bounds from `train`.

    analysis.py winsorises the BCN components first and only then forms OTHER
    from the winsorised values, so the order here is not interchangeable. The
    financial-firm exclusion also comes last there, which means the two
    SIC 6000-6999 rows are inside the quantile calculation; that is reproduced.
    """
    df = raw.copy()
    src = df if train is None else df.loc[train]
    bounds = {}
    for c in WINS:
        bounds[c] = (src[c].quantile(lo), src[c].quantile(hi))
        df[c] = df[c].clip(*bounds[c])

    other = (df["ni_s"] - df["cf"] - df["d_ar"] - df["d_inv"]
             + df["d_ap"] + df["dep"])
    b = (other.loc[src.index].quantile(lo), other.loc[src.index].quantile(hi))
    df["other"] = other.clip(*b)
    bounds["other"] = b

    fin = df["sic"].astype(str).str.startswith("6")
    return df[~fin].copy(), bounds


def fit(df, cols, label=""):
    X = np.c_[np.ones(len(df)), df[cols].to_numpy(float)]
    m = OLS(df["y"].to_numpy(float), X, df["cik"].to_numpy(), ["const"] + cols)
    m.label, m.cols = label, cols
    return m


def coef(m, name):
    i = m.names.index(name)
    return float(m.beta[i]), float(m.se[i]), float(m.p()[i])


def line(label, m, name="netflow", extra=""):
    c, s, p = coef(m, name)
    print(f"  {label:<44} n={m.n:>4} coef={c:>8.3f} se={s:>6.3f} "
          f"p={p:>6.3f}{extra}")
    return dict(label=label, n=int(m.n), firms=int(m.G), coef=c, se=s, p=p,
                adj_r2=float(m.adj_r2))


# ---------------------------------------------------------------- R3 Q1

def out_of_sample(raw):
    """Leave-one-firm-out CV and one forward holdout, baseline vs + net flow."""
    print("\n--- R3 Q1: out-of-sample forecast accuracy ---")
    full, _ = build(raw)
    ciks = full["cik"].unique()

    preds = {k: np.full(len(full), np.nan) for k in ("base", "flow")}
    pos = {c: i for i, c in enumerate(full["cik"].to_numpy())}
    idx_of = {}
    for i, c in enumerate(full["cik"].to_numpy()):
        idx_of.setdefault(c, []).append(i)

    for c in ciks:
        tr_mask = raw["cik"] != c
        tr, _ = build(raw, train=tr_mask)
        trn = tr[tr["cik"] != c]
        tst = tr[tr["cik"] == c]
        if len(trn) < 20 or tst.empty:
            continue
        for key, cols in (("base", BCN), ("flow", BCN + ["netflow"])):
            m = fit(trn, cols)
            Xt = np.c_[np.ones(len(tst)), tst[cols].to_numpy(float)]
            preds[key][idx_of[c]] = Xt @ m.beta

    y = full["y"].to_numpy(float)
    ok = np.isfinite(preds["base"]) & np.isfinite(preds["flow"])
    res = {}
    sst = float(((y[ok] - y[ok].mean()) ** 2).sum())
    for key in ("base", "flow"):
        e = y[ok] - preds[key][ok]
        res[key] = dict(rmse=float(np.sqrt((e ** 2).mean())),
                        mae=float(np.abs(e).mean()),
                        r2_oos=float(1.0 - (e ** 2).sum() / sst))
        print(f"  LOFO {key:<5} n={ok.sum():>4} RMSE={res[key]['rmse']:.5f} "
              f"MAE={res[key]['mae']:.5f} R2oos={res[key]['r2_oos']:.4f}")

    d2 = (y[ok] - preds["base"][ok]) ** 2 - (y[ok] - preds["flow"][ok]) ** 2
    grp = pd.Series(d2).groupby(full["cik"].to_numpy()[ok]).mean()
    t = grp.mean() / (grp.std(ddof=1) / np.sqrt(len(grp)))
    res["dm"] = dict(mean_loss_diff=float(d2.mean()), t=float(t),
                     p=float(norm_sf2(t)), clusters=int(len(grp)))
    res["rmse_change_pct"] = 100.0 * (res["flow"]["rmse"] / res["base"]["rmse"] - 1)
    print(f"  RMSE change with net flow: {res['rmse_change_pct']:+.2f}%  "
          f"(Diebold-Mariano on firm means t={t:.2f}, p={norm_sf2(t):.3f})")

    tr_mask = raw["fy"] <= 2024
    h, _ = build(raw, train=tr_mask)
    trn, tst = h[h["fy"] <= 2024], h[h["fy"] == 2025]
    hold = dict(n_train=int(len(trn)), n_test=int(len(tst)))
    sst_h = float(((tst["y"] - tst["y"].mean()) ** 2).sum())
    for key, cols in (("base", BCN), ("flow", BCN + ["netflow"])):
        m = fit(trn, cols)
        Xt = np.c_[np.ones(len(tst)), tst[cols].to_numpy(float)]
        e = tst["y"].to_numpy(float) - Xt @ m.beta
        hold[key] = dict(rmse=float(np.sqrt((e ** 2).mean())),
                         mae=float(np.abs(e).mean()),
                         r2_oos=float(1.0 - (e ** 2).sum() / sst_h))
        print(f"  holdout FY<=2024 -> FY2025 {key:<5} n={len(tst):>3} "
              f"RMSE={hold[key]['rmse']:.5f} R2oos={hold[key]['r2_oos']:.4f}")
    hold["rmse_change_pct"] = 100.0 * (hold["flow"]["rmse"] / hold["base"]["rmse"] - 1)
    print(f"  holdout RMSE change with net flow: {hold['rmse_change_pct']:+.2f}%")
    res["holdout"] = hold
    return res


# ---------------------------------------------------------------- R3 Q2

def robustness(raw):
    """Influential firms, outlier treatment and alternative specifications."""
    print("\n--- R3 Q2: influence and alternative specifications ---")
    full, _ = build(raw)
    cols = BCN + ["netflow"]
    base = fit(full, cols)
    rows = [line("as reported", base)]

    drops = []
    for c in full["cik"].unique():
        m = fit(full[full["cik"] != c], cols)
        drops.append((c, *coef(m, "netflow")))
    dd = pd.DataFrame(drops, columns=["cik", "coef", "se", "p"])
    sig = int((dd["p"] < 0.05).sum())
    print(f"  leave-one-firm-out: coef [{dd['coef'].min():.3f}, "
          f"{dd['coef'].max():.3f}] median {dd['coef'].median():.3f} | "
          f"p<0.05 in {sig}/{len(dd)} fits | max p {dd['p'].max():.3f}")
    worst = dd.loc[dd["coef"].idxmax()]
    lofo = dict(coef_min=float(dd["coef"].min()), coef_max=float(dd["coef"].max()),
                coef_median=float(dd["coef"].median()), p_max=float(dd["p"].max()),
                n_sig_05=sig, n_fits=int(len(dd)),
                most_influential_cik=int(worst["cik"]),
                most_influential_coef=float(worst["coef"]))

    X = np.c_[np.ones(len(full)), full[cols].to_numpy(float)]
    XtXi = np.linalg.pinv(X.T @ X)
    h = np.einsum("ij,jk,ik->i", X, XtXi, X)
    j = cols.index("netflow") + 1
    dfb = (XtXi[j] @ X.T) * base.resid / (1.0 - h)
    order = np.argsort(-np.abs(dfb))
    for k in (1, 5, 10):
        keep = np.ones(len(full), bool)
        keep[order[:k]] = False
        rows.append(line(f"drop {k} most influential obs (DFBETA)",
                         fit(full[keep], cols)))

    for lo, hi, tag in ((0.0, 1.0, "unwinsorised"), (0.02, 0.98, "winsor 2/98"),
                        (0.05, 0.95, "winsor 5/95")):
        alt, _ = build(raw, lo=lo, hi=hi)
        rows.append(line(tag, fit(alt, cols)))

    fy = pd.get_dummies(full["fy"].astype(int), prefix="fy", drop_first=True)
    wy = pd.concat([full.reset_index(drop=True), fy.reset_index(drop=True)], axis=1)
    rows.append(line("with fiscal-year effects", fit(wy, cols + list(fy.columns))))

    med = fit(full[full["netflow"].abs() > 0], cols)
    rows.append(line("excluding exactly-zero net flow", med))

    return dict(specs=rows, lofo=lofo)


# ---------------------------------------------------------------- R3 Q4

def confounds(raw):
    """Liquidity, leverage and size as competing explanations."""
    print("\n--- R3 Q4: liquidity and financing-constraint controls ---")
    full, _ = build(raw)
    cols = BCN + ["netflow"]
    rows = [line("as reported", fit(full, cols))]
    for add, tag in ((["size"], "+ size (log avg assets)"),
                     (["cash_s"], "+ cash/assets"),
                     (["cash_s", "size"], "+ cash/assets, size"),
                     (["lev_s"], "+ long-term debt/assets"),
                     (["cash_s", "lev_s", "size"], "+ cash, leverage, size")):
        sub = full.dropna(subset=add)
        rows.append(line(tag, fit(sub, cols + add)))
    return rows


# ---------------------------------------------------------------- R2 Q2

def industry(raw):
    """Industry composition, and where the sample supports a comparison."""
    print("\n--- R2 Q2: industry differences ---")
    full, _ = build(raw)
    s = full["sic"].astype(int)
    comp = {
        "manufacturing 2000-3999": int(s.between(2000, 3999).sum()),
        "trade 5000-5999": int(s.between(5000, 5999).sum()),
        "other": int((~s.between(2000, 3999) & ~s.between(5000, 5999)).sum()),
    }
    print(f"  composition: {comp}")
    top = s.astype(str).str[:2].value_counts().head(8)
    print(f"  most common 2-digit SIC: {dict(top)}")

    cols = BCN + ["netflow"]
    out = dict(composition=comp, top_sic2={k: int(v) for k, v in top.items()})

    mfg = full[s.between(2000, 3999)].copy()
    mfg["dur"] = s[s.between(2000, 3999)].ge(3000).astype(float).to_numpy()
    mfg["nf_dur"] = mfg["netflow"] * mfg["dur"]
    print(f"  within manufacturing: {int(mfg['dur'].sum())} durable "
          f"(SIC 30-39), {int(len(mfg) - mfg['dur'].sum())} non-durable")
    out["durable"] = [
        line("non-durable manufacturing only", fit(mfg[mfg["dur"] == 0], cols)),
        line("durable manufacturing only", fit(mfg[mfg["dur"] == 1], cols)),
    ]
    m = fit(mfg, cols + ["dur", "nf_dur"])
    c, se, p = coef(m, "nf_dur")
    print(f"  {'net flow x durable interaction':<44} n={m.n:>4} "
          f"coef={c:>8.3f} se={se:>6.3f} p={p:>6.3f}")
    out["durable_interaction"] = dict(n=int(m.n), coef=c, se=se, p=p)

    wc = full.dropna(subset=["ap_lvl"]).copy()
    wc["ap_c"] = wc["ap_lvl"] - wc["ap_lvl"].mean()
    wc["nf_ap"] = wc["netflow"] * wc["ap_c"]
    m = fit(wc, cols + ["ap_c", "nf_ap"])
    c, se, p = coef(m, "nf_ap")
    print(f"  {'net flow x payables intensity (centred)':<44} n={m.n:>4} "
          f"coef={c:>8.3f} se={se:>6.3f} p={p:>6.3f}")
    out["wc_interaction"] = dict(n=int(m.n), coef=c, se=se, p=p,
                                 ap_mean=float(wc["ap_lvl"].mean()))
    return out


def main():
    raw = load_raw()
    full, _ = build(raw)
    c, s, p = coef(fit(full, BCN + ["netflow"]), "netflow")
    print(f"reproduction check: n={len(full)} firms={full['cik'].nunique()} "
          f"netflow={c:.4f} p={p:.4f}")
    assert len(full) == 230, len(full)
    assert full["cik"].nunique() == 167
    assert abs(c - (-0.9588)) < 5e-4, c
    assert abs(p - 0.0013) < 5e-4, p
    print("  matches the as-reviewed result\n")

    summary = dict(
        reproduction=dict(n=int(len(full)), firms=int(full["cik"].nunique()),
                          netflow=c, se=s, p=p),
        out_of_sample=out_of_sample(raw),
        robustness=robustness(raw),
        confounds=confounds(raw),
        industry=industry(raw),
    )
    (OUT / "revision_tests.json").write_text(json.dumps(summary, indent=2),
                                             encoding="utf-8")
    print(f"\nwrote {OUT/'revision_tests.json'}")


if __name__ == "__main__":
    main()
