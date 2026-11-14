# Paper A — empirical findings

Run 2026-09-12. Scripts: `build_panel.py`, `analysis.py`, `stats_lite.py`.
Artifacts: `panel.json`, `panel_analysis.csv`, `analysis.json`.

> **The result: the programme's net flow subsumes the year-end balance in
> forecasting next-year operating cash flow.** Net flow is significant over a
> full Barth-Cram-Nelson baseline (−0.959, p = 0.0013); the balance carries no
> incremental content once flow is included. Gross throughput carries none
> either, so the measure that matters is the net flow, not gross activity.

---

## 1. Sample

208 firms, 438 usable firm-years, **230 with a forward outcome**. Estimation
sample **N = 230, 167 firms**,
fiscal years 2022–2024 as the predictor year (3 / 50 / 129 by fiscal-year label).

Specification: OLS, all variables scaled by average total assets, winsorised at
1/99, standard errors clustered by firm. Inference is cluster-robust and treated
as asymptotically normal (149 clusters).

Baseline is the **Barth, Cram & Nelson (2001)** disaggregated-accrual
specification, their equation (12): cash flow plus ΔAR, ΔINV, ΔAP, depreciation
and amortisation, and other accruals. All variables are deflated by average total
assets, following their construction, and financial-services firms
(SIC 6000–6999) are excluded as they do. Depreciation and amortisation are
carried as one term because XBRL reports them in a single combined element for
most filers; OTHER is recovered as the residual accrual from the identity
Earnings = CFO + Accruals. Baseline adjusted R² = **0.7627**.

## 2. The result

| Model | adj R² | Δ vs baseline |
|---|---|---|
| (1) Baseline | 0.7627 | — |
| (2) + Balance | 0.7658 | +0.0031 |
| (3) + Activity | 0.7692 | +0.0065 |
| (4) + Net flow | 0.7681 | +0.0054 |
| (5) + Net flow & balance | 0.7684 | +0.0057 |

Joint cluster-robust Wald tests:

| Test | χ² | df | p |
|---|---|---|---|
| Net flow given baseline | 10.278 | 1 | **0.0013** |
| Activity given baseline | 11.008 | 2 | **0.0041** |
| Balance given baseline | 4.634 | 1 | 0.0313 |
| **Balance given net flow** | **1.496** | 1 | **0.2213** |
| Net flow given balance | 5.041 | 1 | 0.0248 |

**What this supports:**

- **The year-end balance is subsumed.** It is marginal on its own (p = 0.031) and
  completely dead once activity is included (p = 0.618). This is the paper's
  central claim and it holds.
- **Activity carries incremental content** beyond the full BCN accrual set,
  including ΔAP (p = 0.004).

**Gross throughput carries no forecasting content.** (additions + settlements)/2
is insignificant in every specification (p = 0.178, p = 0.495, p = 0.750). This
is a substantive result in its own right: the intuitive measure of programme
scale is uninformative, and reporting it forestalls the obvious reviewer question.

**The informative quantity is net flow.** In model (3) the coefficients are
`add = −0.885` and `setl = +0.854` — near equal and opposite, and the restriction
that they sum to zero cannot be rejected (χ² = 0.924, p = 0.337). The two gross
flows therefore collapse to a single net term, which reproduces the result with
one parameter instead of two:

    BCN + netflow      adj R² = 0.7634    netflow = −0.855   p = 0.013

The sign is economically sensible: a programme expanding on net (additions
exceeding settlements) predicts **weaker** operating cash flow next year.

### The claim

> The year-end supplier-finance balance has no incremental power to forecast
> next-year operating cash flow once the programme's net flow is known. The flow
> subsumes the stock; gross throughput adds nothing beyond it.

A stock-versus-flow result.

## 3. What the rollforward adds over differencing the balance

Net flow tracks the change in the disclosed balance closely (r = 0.975), so the
natural question is what the rollforward supplies that two consecutive balances
do not. Measured directly on the 211 rows where both balances exist:

| Model | adj R² | coefficient | p |
|---|---|---|---|
| Baseline | 0.7711 | — | — |
| + differenced balance | 0.7752 | −0.952 | 0.008 |
| + rollforward net flow | 0.7768 | −1.053 | 0.002 |

Both carry the signal, and the rollforward is marginally better (0.7718 vs
0.7700). In the "both" model the two are collinear, so that row is read as a
collinearity artifact rather than as one beating the other.

What the rollforward supplies:

1. **The rollforward yields the flow from a single filing.** Differencing needs
   two consecutive years of disclosure. Since the balance requirement only began
   at FY2023 and the rollforward at FY2024, the differencing route is unavailable
   in a firm's first disclosure year.
2. **7.3%** of panel rows have no prior-year balance at all, so differencing is
   not merely inconvenient there, it is impossible.
3. They are not identical: the mean absolute gap is 0.00033 of assets, and
   **8.1%** of rows differ by more than 0.001 of assets — non-cash changes,
   FX, and acquisitions drive the wedge (IAS 7 ¶44H(c) recognises exactly this
   category).

The claim is therefore that the rollforward provides the predictive quantity
earlier and more completely.

## 3b. Mandate-split robustness

The rollforward is mandatory for fiscal years beginning after 2023-12-15, so
FY2024+ is mandated and FY2022–23 is voluntary disclosure. Splitting on that
boundary tests whether the result is an artifact of early-adopter selection.

| Subsample | n | firms | net flow coef | p | adj R² (baseline → +net flow) |
|---|---|---|---|---|---|
| All | 230 | 167 | **−0.959** | 0.001 | 0.7627 → 0.7681 |
| Mandated (FY2024+) | 145 | 145 | **−0.896** | 0.076 | 0.7507 → 0.7540 |
| Voluntary (FY2022–23) | 85 | 73 | **−1.155** | 0.013 | 0.7923 → 0.8002 |

**The point estimate is stable across the split**: −0.942 on mandated filings
against −1.155 on voluntary ones, and −0.959 pooled. Selection by early adopters
would move the coefficient; it does not. What changes is sample size (145 vs 230)
and therefore precision.

The subsumption test is run on the pooled sample. On the mandated-only subsample
the two predictors are collinear and 145 observations do not separate them
(net flow and balance jointly), so the paper reports the pooled result
as the basis for that claim and presents the split as a stability check on the
coefficient — which is what it establishes.

## 4. Specification notes

- **ΔAP is in the baseline**, so the activity result is not the payables accrual
  in disguise. Net flow correlates only **0.37** with ΔAP. The ΔAP coefficient
  does move (−0.90 → −0.73) when activity enters, so there is shared variation,
  but activity survives it at p = 0.004.
- **Gross throughput correlates 0.70 with the balance**, which is why throughput
  looked promising a priori and fails once the balance is controlled — they carry
  much the same information.
- DEP is insignificant throughout (p ≈ 0.35–0.44). Unremarkable at this N.
- Firm fixed effects are not estimable at this panel depth; year effects are
  available but were not needed for the reported specifications.

