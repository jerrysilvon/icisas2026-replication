# Paper B — findings

**Administrative price ceilings and the merchant storage business case:
evidence from India's day-ahead power exchange.**

Run 2026-09-12. Scripts: `paperB_build.py`, `paperB_analysis.py`,
`exhibits_paperB.py`. Data provenance and validation:
`research/paper-B-data-and-novelty.md`.

---

## 1. The headline: an asymmetry

> As India's price ceiling fell from ₹20 to ₹10/kWh, the arbitrage value of a
> co-located 4-hour battery fell **18.6%**, while the capture price of the solar
> plant beside it fell only **4.3%**. The ceiling is close to neutral for merchant
> solar and materially costly for storage.

Mechanism, measured: solar output is concentrated in midday hours, where
day-ahead prices are low and the ceiling is not binding. Battery discharge is
concentrated in evening peak hours, where the ceiling binds. The ceiling
truncates the part of the price distribution storage revenue is drawn from.

Context: the petitions to CERC to raise the ₹10 ceiling come from the storage
industry and NSEFI, not from solar generators.

## 2. Censoring by regime

Regime boundaries are set from the observed series — the ceiling is taken to
change on the first day after which it is never exceeded — and both transitions
land within a day of CERC's interventions of 1 April 2022 and 1 April 2023.

| Regime | Ceiling | Hours | Mean | 99th pct | Hours at ceiling |
|---|---|---|---|---|---|
| A | ₹20/kWh | 10,896 | ₹4.26 | ₹18.72 | **0.44%** |
| B | ₹12/kWh | 8,664 | ₹5.92 | ₹12.00 | **12.40%** |
| C | ₹10/kWh | 3,720 | ₹5.39 | ₹10.00 | **19.19%** |

Under the ₹10 ceiling roughly **one hour in five clears at the cap**. The 99th
percentile equals the cap exactly in regimes B and C — the upper tail is not
merely compressed, it is flat.

## 3. Identification

**The design avoids estimating a counterfactual price.** A ceiling applied to an
observed series changes only the ceiling; nothing else moves. Regime A is the
least censored series available (cap binds 0.44% of hours), so it is the base
onto which the tighter ceilings are imposed.

**Value removed, same series, different ceilings:**

| Ceiling | 2h battery (₹M/MW/yr) | removed | 4h battery (₹M/MW/yr) | removed |
|---|---|---|---|---|
| ₹20 | 3.583 | — | 5.246 | — |
| ₹12 | 3.069 | **14.4%** | 4.588 | **12.5%** |
| ₹10 | 2.835 | **20.9%** | 4.273 | **18.6%** |
| ₹8 | 2.531 | **29.4%** | 3.847 | **26.7%** |

**Realised revenue by regime:**

| Regime | 2h | 4h | Days |
|---|---|---|---|
| A (₹20) | 3.583 | 5.246 | 454 |
| B (₹12) | 4.778 | 7.572 | 361 |
| C (₹10) | 3.513 | 6.356 | 155 |

Realised revenue was **higher** under the tighter ceilings, because the 2022 fuel
crisis raised both the level and volatility of prices by more than the ceiling
removed. Month-matching (April–August only) gives the same pattern — A ₹3.492M,
B ₹7.001M, C ₹6.379M per MW-year — so the movement is in the market, not the
season.

The fixed-series comparison and the realised comparison therefore move in
opposite directions over this period.

## 4. Dispatch model

Price-taker perfect-foresight daily arbitrage, solved **exactly by dynamic
programming** over state of charge: 1 MWh steps, 1 MW power, 85% round-trip
efficiency, battery starts and ends each day empty, multiple cycles per day
permitted where profitable. Every reported schedule is chronologically feasible.

**Horizon.** Sioshansi, Denholm, Jenkin & Weiss (2009) optimise over a two-week
horizon with perfect foresight, which admits inter-day and weekend arbitrage. The
daily horizon used here was compared against weekly and two-week horizons on the
same series (`outputs/price_caps/horizon_check.csv`):

| Horizon | 4h revenue at Rs20 | Value removed at Rs10 |
|---|---|---|
| Daily | Rs5.246M/MW/yr | 18.6% |
| Weekly | Rs5.364M/MW/yr | 19.2% |
| Two-week | Rs5.371M/MW/yr | 19.2% |

A longer horizon raises revenue by about 2% and moves the measured value removed
by at most 0.6 percentage points. Sioshansi et al. use 80% round-trip efficiency;
85% is used here.

## 5. Co-location and space

Solar capture price (generation-weighted mean price received), 8 Indian sites:

| Ceiling | Mean capture price | Capture ratio |
|---|---|---|
| ₹20 | ₹4.89/kWh | ~0.98 |
| ₹12 | ₹4.83/kWh | — |
| ₹10 | ₹4.68/kWh | 0.958–0.980 |
| ₹8 | ₹4.45/kWh | — |

**Two findings:**

1. **Capture ratios are 0.96–0.98** over 2021–2023: Indian merchant solar
   captured close to the flat average price in this window. Trade reporting of
   capture rates at ₹2.23/kWh covers FY2026, outside this sample period.
2. **Spatial variation is negligible: 2.3% across eight sites** spanning Bhadla,
   Jaisalmer, Kutch, Pavagada, Kurnool, Nagpur, Jodhpur and Bengaluru. The
   day-ahead price is effectively national and solar shape varies little across
   the country, so site choice barely moves capture price.

## 6. Exhibits

| File | Content |
|---|---|
| `exhibits/figB1_censoring.svg` | (a) price duration curves by regime; (b) share of hours at the ceiling |
| `exhibits/figB2_revenue_vs_cap.svg` | arbitrage revenue vs ceiling, 2h and 4h |
| `exhibits/tableB1_regimes.md` | regimes and censoring |
| `exhibits/tableB2_results.md` | value removed, plus the realised-revenue contrast |
| `exhibits/tableB3_sites.md` | the eight solar sites and their yields |

Both figures are vector SVG sized exactly to the IEEE grid (7.12 in full width,
3.46 in single column) and were rendered and visually checked before acceptance.
