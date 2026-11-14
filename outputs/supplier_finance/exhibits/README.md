# Exhibits — what each shows, and the caption text

Built by `scripts/exhibits_paper1.py` from `outputs/supplier_finance/panel.json`.
Rebuild with `python scripts/exhibits_paper1.py`.

| File | Type | Placement |
|---|---|---|
| `table1_descriptives.md` | Table I | single column |
| `table2_results.md` | Table II | **full width** (5 model columns) |
| `fig1_stock_vs_flow.svg` | Figure 1 | **full width** (7.12 in, two panels) |
| `fig2_mandate_robustness.svg` | Figure 2 | single column (3.46 in) |

Figures are SVG. matplotlib cannot run on this machine (Windows Application
Control blocks its compiled extension), so they are drawn by `scripts/svg_plot.py`.
SVG is vector and sized in points — Figure 1 is exactly 7.12 in, Figure 2 exactly
3.46 in, so both drop into the IEEE grid at 100% scale with no resampling.

---

## Table I — Descriptive statistics

N = 230 firm-years, 167 firms, fiscal years 2022–2024. All variables scaled by
average total assets, winsorised 1/99.

**The two rows that carry the paper's argument:**
- Obligations added: mean 0.0710, median 0.0408
- Net programme flow: mean 0.0011, median 0.0001

Gross flows are roughly **60× larger than the net flow** at the mean. The
programme moves enormous gross volume and nets to almost nothing — which is why
the gross/net distinction is not a technicality.

## Table II — Main results

Five specifications. Table facts: dependent variable is operating cash flow in
year *t+1* scaled by average total assets; baseline is the Barth–Cram–Nelson
disaggregated-accrual specification; standard errors are cluster-robust by firm,
shown in parentheses; significance marks are *** p<0.01, ** p<0.05, * p<0.10.

**Quote each p-value against its own specification.** The balance is insignificant
in both, but the figure differs:

| Claim | Correct specification | Statistic |
|---|---|---|
| Balance has marginal standalone content | (2) baseline + balance | −0.124, p = 0.031 |
| Balance is subsumed by **net flow** | (5) baseline + net flow + balance | Wald χ²=1.496, **p = 0.221** |
| Balance is subsumed by **gross activity** | baseline + balance + added + settled | **p = 0.618** |
| Net flow survives the balance | (5) | χ²=5.049, p = 0.025 |
| Net flow over baseline | (4) | −0.959, χ²=10.059, p = 0.0013 |

Both support the claim; use the one matching the model displayed in the table.

**Also note** ΔAP moves from −0.904 to −0.760 when net flow enters. There is shared
variation with the payables accrual, as expected, but net flow survives it — the
correlation between them is only 0.37.

## Figure 1 — Stock versus flow *(full width)*

**Panel (a)** — histogram of obligations added during the year ÷ year-end balance.
Median **4.5×**. Uses additions alone; additions + settlements would double-count
each obligation as it enters and leaves the programme.

*Content:* Programme turnover. One year's confirmed additions are typically 4.5
times the year-end balance, so the balance is a thin summary of the year's
activity.

**Panel (b)** — added-variable plot. Both outcome and predictor are residualised
on the baseline **and on the other predictor**, which is exactly what each
coefficient in the joint model measures. The x-axis is in standard-deviation
units so the two slopes are comparable; on raw scales the wider-spread series
reads as the stronger one regardless of its slope.

*Content:* Incremental content. With both variables and the baseline included,
net programme flow retains a clear negative slope against next-year operating
cash flow; the year-end balance is flat.

## Figure 2 — Mandate robustness *(single column)*

Each predictor is added **separately** to the baseline, within each subsample —
this is not the joint model. State that in the caption or the figure overstates
the contrast.

*Content:* Coefficient on each predictor, added separately to the baseline, by
mandate status. Point estimates for net programme flow are near-identical across
the mandate boundary (−0.94 mandated vs −1.02 voluntary), which argues against an
early-adopter selection story; the wider interval on the mandated subsample
reflects its smaller size (N=146).

**Caption must note:** on the mandated-only subsample the net-flow interval
touches zero (p = 0.053); the pooled sample carries the significance, and the
split is presented as a stability check on the coefficient.

---

## Reproduction

```
python scripts/build_panel.py        # rebuild panel from cached companyfacts
python scripts/analysis.py           # regression results -> analysis.json
python scripts/exhibits_paper1.py    # tables + figures
```

Inputs are cached under `data/raw/companyfacts/` (215 firms), so a rebuild makes
no network calls.
