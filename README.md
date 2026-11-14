# Replication materials — ICISAS 2026

Data, analysis code and exhibits for two papers submitted to the 3rd
International Conference on Innovation, Sustainability and Applied Sciences
(ICISAS 2026), Curtin University Dubai, 12–13 December 2026.

AVR Akshaya and Jerry Silvon J M, School of Business and Management,
CHRIST (Deemed to be University), Pune, India.

**A. Stock Versus Flow in Supplier-Finance Disclosure: Programme Net Flow
Carries the Forecasting Content.** Does the ASU 2022-04 rollforward carry
information the year-end balance does not? 230 firm-years from 167 US filers,
tested over a Barth–Cram–Nelson disaggregated-accrual baseline.

**B. Administrative Price Ceilings and the Merchant Storage Business Case:
Evidence from India's Day-Ahead Power Exchange.** What does India's day-ahead
price ceiling remove from a merchant battery? 23,304 hourly IEX prices and eight
PVGIS solar sites, with storage dispatch solved exactly by dynamic programming.

## AI disclosure

This repository was compiled with AI assistance.

## Data sources

Every input is public.

| Paper | Source | Access |
|---|---|---|
| A | SEC XBRL `companyfacts` and full-text search | `https://data.sec.gov`, no key required |
| B | Veeramsetty et al., "Electrical energy price dataset: IEX data", Mendeley Data V1 (2024) | DOI `10.17632/v5znbkzjd4.1`, CC BY 4.0 |
| B | PVGIS v5.3, European Commission Joint Research Centre | open service |

The SEC response cache (`data/raw/http`, 3.2 GB) and copyrighted publisher PDFs
are not redistributed here. `scripts/discover.py` and `scripts/fetch_documents.py`
rebuild the cache; they pace requests at 0.6 s and send a contact address in the
User-Agent as SEC policy requires. **Set that address to your own** before
running anything against `data.sec.gov`.

## Reproducing the results

`scipy` and `statsmodels` do not load on the machine this was built on, so OLS
with CR1 cluster-robust covariance, the chi-square tail and the normal tail are
implemented directly in `scripts/stats_lite.py`.

```
python scripts/build_panel.py      # paper A: SEC companyfacts -> outputs/supplier_finance/panel.json
python scripts/analysis.py         # paper A: nested specifications and Wald tests
python scripts/revision_A.py       # paper A: out-of-sample, influence, controls, industry
python scripts/paperB_build.py     # paper B: price and solar panel
python scripts/paperB_analysis.py  # paper B: censoring, counterfactual ceilings, realised revenue
python scripts/revision_B.py       # paper B: degradation sweep and forecast-error dispatch
```

`revision_A.py` and `revision_B.py` each assert the published headline figure
before computing anything further: net programme flow of −0.9588 at p = 0.0013
on N = 230, and Rs 5.246M per MW-year for a four-hour battery under the Rs20
ceiling. If an assertion fails, the environment has diverged and the downstream
numbers should not be trusted.

## Layout

```
data/        the SEC discovery index the panel builder resolves SIC codes from
scripts/     extraction, panel construction, estimation, exhibits
outputs/     input panels, findings, result JSON, exhibit sources
tests/       unit tests on synthetic fixtures
paper/       manuscript sources and compiled PDFs
```

## Licence

Code is MIT. The IEX price dataset is CC BY 4.0 and retains its own terms.
