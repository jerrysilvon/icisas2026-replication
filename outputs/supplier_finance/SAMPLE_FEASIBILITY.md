# Paper 2 — sample feasibility, measured 2026-09-12

What fraction of discovered CIKs actually tag the rollforward, and is the
resulting panel large enough to estimate on.

**Verdict: viable.** 208 firms, 438 usable annual rollforward firm-years.

Scripts: `scripts/coverage.py`, `scripts/usable_panel.py`. Raw output:
`tag_coverage.json`, `usable_panel.json`.

## Method

Queried XBRL companyfacts for all 551 CIKs in `data/discovery/supplier_finance.json`
(548 reachable, 3 HTTP 404). A firm-year counts as **usable** only if both
`SupplierFinanceProgramObligationIncrease` and
`SupplierFinanceProgramObligationDecreaseSettlement` exist for the *same* period
of annual length (340–400 days). Requiring both matters — see the asymmetry note.

## Coverage

| | Firms | % of 548 |
|---|---|---|
| Any balance element | 239 | 43.6% |
| Any activity element | 216 | 39.4% |
| ≥1 **usable** annual rollforward | **208** | **38.0%** |

## Panel

| Fiscal start year | Usable firm-years |
|---|---|
| 2022 | 10 |
| 2023 | 80 |
| 2024 | 199 |
| 2025 | 149 |
| **Total** | **438** |

168 firms have ≥2 usable years, so a pooled panel with year effects is available.
Firm fixed effects are not realistic at this depth.

**Predictive observations.** The test is activity in year *t* against operating
cash flow in *t+1*. FY2026 outcomes are not yet filed, so the FY2025 activity
row has no forward outcome:

- FY2022 → FY2023: 10
- FY2023 → FY2024: 80
- FY2024 → FY2025: 199
- FY2025 → FY2026: 149 **unavailable until early 2027**

**CORRECTED 2026-09-12: 232, not 289.** The 289 estimate assumed every FY2022-24
activity row has a filed t+1 outcome. It does not, and the shortfall is not random.
Measured against the built panel (`panel.json`):

| Fiscal start | Usable rows | With forward OCF |
|---|---|---|
| 2022 | 10 | 10 |
| 2023 | 80 | 76 |
| 2024 | 199 | 146 |
| 2025 | 149 | 0 |
| **Total** | **438** | **232** |

Cause, verified: filing lag on off-calendar fiscal years. Grouping FY2024-start rows
by period end month, every row ending **2025-09 or later has zero** forward outcomes,
because its t+1 year ends after the most recent filed 10-K. Rows ending 2024-12
through 2025-06 mostly have one. A further 7 rows lack their own-year OCF under the
element names queried.

So the censoring boundary is a filing date, not a fiscal year, and it cuts into FY2024
as well as eliminating FY2025. Use **232**. Small for accounting research; workable for
a six-page conference paper, provided the limitation is stated rather than hidden.

The 2022 and 2023 rows precede the mandate (ASC 405-50-65-1 makes the rollforward
effective for fiscal years beginning after 15 Dec 2023, prospectively). They are
early adopters or voluntary comparatives. **Characterise them before pooling** —
voluntary early disclosers are plausibly not a random subset.

## Two traps confirmed by measurement

**The SEC frames API undercounts badly here — do not use it for coverage.**
It returned 20 filers for `...ObligationIncrease` in CY2024 against 199 usable
firm-years found per-company, and 1 filer for the CY2023Q4I balance, which is
contradicted by Keurig Dr Pepper alone. Frames matches exact calendar frames and
drops off-cycle fiscal years, which is most retailers and many industrials.
Query companyfacts per company.

**The two activity elements are not always symmetrically reported.** PVH Corp
tags settlements quarterly back to FY2021 but additions only annually from
FY2024. Counting a firm as having "activity" if it has *either* element inflates
the sample and invents pre-mandate history that is not a rollforward.

Across the full set this affects only **3 firms** (settlements present, annual
additions absent), so it is not a material sample problem — but it is a real
extraction bug if the pipeline does not require both elements on the same period.

## Selection, still open

38% usable coverage is not 38% of programme users. Some of the 551 discovered
CIKs are keyword false positives — a filing that mentions "supply chain finance"
without operating a programme. True coverage among actual users is higher and
unknown.

The direction of selection still needs characterising: firms that tag are
plausibly larger, more scrutinised, and more likely to use auditor-supported XBRL
processes than firms that only discuss programmes in text. Compare size,
leverage and industry between tagged and untagged discovered firms before
claiming the sample represents programme users generally.
