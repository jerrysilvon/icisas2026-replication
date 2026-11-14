"""Paper B: assemble the hourly price + solar panel for India.

Prices  : Veeramsetty et al. (2024) Mendeley Data, DOI 10.17632/v5znbkzjd4.1,
          CC BY 4.0. Hourly IEX day-ahead. No timestamp column - reconstructed
          and validated here on every run, not assumed.
Solar   : PVGIS v5.3 (EU JRC), free, no key. Real ERA5 irradiance through a PV
          model. v5.2 stops at 2020 and will 400 - must be v5_3.
"""
import datetime as dt
import json
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/paperB"
OUT = ROOT / "outputs/price_caps"
PRICE_URL = ("https://data.mendeley.com/public-files/datasets/v5znbkzjd4/files/"
             "237f0314-4d77-4a9e-82f4-1706cc342da8/file_downloaded")
PVGIS = "https://re.jrc.ec.europa.eu/api/v5_3/seriescalc"

# Spread of solar resource and latitude across the Indian grid.
SITES = {
    "Jaisalmer_RJ":   (26.92, 70.92),   # Thar desert, highest irradiance
    "Bhuj_GJ":        (23.24, 69.67),   # Kutch, major solar/wind hub
    "Bhadla_RJ":      (27.54, 71.91),   # world's largest solar park
    "Pavagada_KA":    (14.10, 77.28),   # Karnataka solar park
    "Kurnool_AP":     (15.83, 78.04),   # Andhra solar park
    "Bengaluru_KA":   (12.97, 77.59),   # southern reference
    "Nagpur_MH":      (21.15, 79.09),   # central India
    "Jodhpur_RJ":     (26.24, 73.02),   # north-west
}
# CERC ceilings, Rs/MWh. Boundaries are set from the OBSERVED series, not from
# order dates: the ceiling is taken to change on the first day after which it is
# never exceeded. Daily maxima give 20,000 on 2022-04-01, a transition day at
# 14,169 on 2022-04-02, then nothing above 12,000; and 12,000 last touched
# 2023-03-29, then nothing above 10,000. Both land within a day of CERC's
# documented 1 April 2022 and 1 April 2023 interventions. 2022-04-02 is excluded
# as a partial-transition day rather than forced into either regime.
REGIMES = [("A", "2021-01-03", "2022-04-01", 20000),
           ("B", "2022-04-03", "2023-03-29", 12000),
           ("C", "2023-03-30", "2023-08-31", 10000)]


def prices():
    RAW.mkdir(parents=True, exist_ok=True)
    f = RAW / "iex_price.xlsx"
    if not f.exists():
        r = requests.get(PRICE_URL, timeout=180,
                         headers={"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36")})
        r.raise_for_status()
        f.write_bytes(r.content)
    df = pd.read_excel(f)

    # --- validate contiguity before trusting reconstructed timestamps
    P = df["P(T)"].to_numpy()
    l1 = df["P(T-1)"].to_numpy()
    l24 = df["P(T-24)"].to_numpy()
    ok1 = (abs(l1[1:] - P[:-1]) < 1e-6).mean()
    ok24 = (abs(l24[24:] - P[:-24]) < 1e-6).mean()
    if ok1 < 1.0 or ok24 < 1.0:
        raise SystemExit(f"series not contiguous: lag1 {ok1:.4f}, lag24 {ok24:.4f}")

    # 48 rows are consumed building the P(T-48) lag, so the series starts 48h
    # after the stated 2021-01-01 and ends at the stated 2023-08-31 23:00.
    start = dt.datetime(2021, 1, 3, 0)
    df["ts"] = [start + dt.timedelta(hours=i) for i in range(len(df))]
    if df["ts"].iloc[-1] != dt.datetime(2023, 8, 31, 23):
        raise SystemExit(f"end timestamp {df['ts'].iloc[-1]} != 2023-08-31 23:00")
    df = df.rename(columns={"P(T)": "price"})[["ts", "price"]]
    print(f"  prices: {len(df)} hrs {df.ts.min()} -> {df.ts.max()} "
          f"(contiguity {ok1:.4f}/{ok24:.4f})")
    return df


def solar(name, lat, lon):
    RAW.mkdir(parents=True, exist_ok=True)
    f = RAW / f"pvgis_{name}.json"
    if not f.exists():
        r = requests.get(PVGIS, timeout=180, params=dict(
            lat=lat, lon=lon, startyear=2021, endyear=2023,
            pvcalculation=1, peakpower=1, loss=14, outputformat="json"))
        r.raise_for_status()
        f.write_text(r.text, encoding="utf-8")
        time.sleep(1.0)
    d = json.loads(f.read_text(encoding="utf-8"))
    h = d["outputs"]["hourly"]
    rows = [(dt.datetime.strptime(x["time"][:11] + "00", "%Y%m%d:%H%M"), x["P"] / 1000.0)
            for x in h]           # W per kWp -> kW per kWp
    return pd.DataFrame(rows, columns=["ts", "pv_kw_per_kwp"])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("building Paper B panel")
    pr = prices()

    frames = []
    for name, (lat, lon) in SITES.items():
        s = solar(name, lat, lon)
        m = pr.merge(s, on="ts", how="inner")
        m["site"] = name
        yld = s.set_index("ts").loc["2022", "pv_kw_per_kwp"].sum()
        print(f"  {name:<15} {len(m):>6} matched hrs | 2022 yield {yld:6.0f} kWh/kWp")
        frames.append(m)
    panel = pd.concat(frames, ignore_index=True)

    def regime(t):
        for r, a, b, cap in REGIMES:
            if pd.Timestamp(a) <= t <= pd.Timestamp(b) + pd.Timedelta(hours=23):
                return r, cap
        return None, None

    rc = panel.ts.map(lambda t: regime(t))
    panel["regime"] = [x[0] for x in rc]
    panel["cap"] = [x[1] for x in rc]
    panel = panel.dropna(subset=["regime"])
    panel["at_cap"] = panel.price >= panel.cap - 1e-9

    panel.to_parquet(OUT / "panel.parquet") if hasattr(panel, "to_parquet") else None
    panel.to_csv(OUT / "panel.csv.gz", index=False, compression="gzip")

    print("\nregime summary (one site's hours; price series is national)")
    one = panel[panel.site == "Bengaluru_KA"]
    g = one.groupby("regime").agg(hours=("price", "size"), mean=("price", "mean"),
                                  p95=("price", lambda s: s.quantile(.95)),
                                  mx=("price", "max"), at_cap=("at_cap", "sum"))
    for r, row in g.iterrows():
        cap = dict((x[0], x[3]) for x in REGIMES)[r]
        print(f"  {r} cap Rs{cap/1000:>5.0f}/kWh | {int(row.hours):>5} hrs | "
              f"mean {row['mean']/1000:5.2f} | p95 {row.p95/1000:5.2f} | "
              f"max {row.mx/1000:5.2f} | at cap {int(row.at_cap):>4} "
              f"({row.at_cap/row.hours*100:.2f}%)")
    print(f"\nwrote {OUT/'panel.csv.gz'}  ({len(panel)} rows, {panel.site.nunique()} sites)")


if __name__ == "__main__":
    main()
