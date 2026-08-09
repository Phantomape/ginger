# exp-20260715-002 — capital-conserving portfolio-contribution Gate 4-P

Decision: `rejected_alpha_retained_evaluation_gate`.

The owner-authorized Gate 4-P implementation is retained as evaluation
infrastructure, but every candidate in the complete frozen 31-family panel is
`portfolio_reject`. No strategy, paper order, live order, core ranking, sizing,
or exit behavior changed.

## What changed

- Left the existing champion-replacement Gate 4 API and thresholds unchanged.
- Added an independent portfolio-contribution evaluator with separate economic
  hard failures and measurement/statistical evidence blockers.
- Added three fail-closed outcomes: `portfolio_reject`,
  `portfolio_forward_watch`, and `accepted_portfolio_paper`.
- Made the full-stack verdict inherit the evaluator mode, reject contradictory
  reports, and prohibit every Gate 4-P result from becoming `live_eligible`.
- Added a distinct `portfolio_contribution` experiment fingerprint.
- Added one complete 31-family batch runner with a frozen OHLCV replay path.

## Locked measurement contract

- Formal comparator: `90% active core + 10% candidate` versus `100% active core`.
- Diagnostic comparator only: the same funded blend versus `90% core + 10% cash`.
- Candidate leg: `$10,000` initial cash per window, no negative cash or hidden
  leverage. Entries debit funded principal plus entry cost; same-day entries are
  allocated pro rata; same-day closing proceeds cannot fund the morning entry;
  later entries use actual prior exit proceeds, including realized gains/losses.
- Fixed active post-MTM core calendars. Entry after the window is excluded;
  cross-boundary positions are force-closed at the final calendar close.
- Cost: source entry and normal exit prices embed 5 bp per leg; a forced exit
  explicitly applies 5 bp sell slippage; funded notional also pays 17.5 bp per
  side, for 45 bp all-in round trip.
- Joint inference: 10,000 paired, window-stratified circular block-bootstrap
  draws, block length 20, seed 2026071502, shared across all 31 candidates, with
  one-sided 90% max-T simultaneous lower bounds.
- The 31 representatives are a complete family batch, but the approximately
  264-candidate historical selection panel was not preserved. Therefore
  `selection_panel_complete=false`; even an economic pass could be no better
  than `portfolio_forward_watch` in this experiment.

## Frozen input and replay integrity

- Potential OHLCV superset: 13,590 ticker-date rows.
- Actually consumed funded paths: 10,319 rows; missing: 0.
- Gzip SHA-256:
  `27148fd7c0eac5023f9acfadc543e81f16d7edb0ac9617dd669df96e33b2714f`.
- Cash ledgers: 93/93 family-window ledgers stayed non-negative and reconciled
  ending cash to ending MTM equity (maximum absolute error below `8e-12`).
- Source rows: 2,230; full fills: 1,030; partial fills: 625; no-cash skips: 559;
  post-window entries excluded: 16; invalid rows: 0; boundary force-closes: 91.

An early internal draft was discarded because it divided the source `$4,000`
notional by a `$100,000` candidate NAV and then multiplied it by 10% again,
leaving only about `$400` per trade. The reported result below is exclusively
the corrected `$10,000` cash-ledger run reproduced from the frozen snapshot.

## Result

| Metric | 100% core | Best funded blend | Formal delta |
|---|---:|---:|---:|
| Aggregate EV sum | 12.263404 | 11.314064 | -0.949340 |
| Aggregate PnL | $237,852.28 | $218,504.04 | -$19,348.24 |
| Worst window max drawdown | 9.7477% | 10.2195% | +0.4718 pp |

The best formal candidate was `exp-20260626-003`,
`companyfacts_purchase_obligation_maturity_ladder_candidate_pool`:

- versus `90% core + 10% cash`, it added EV `+0.641426` and PnL `+$11,059.52`;
- its worst-window ES95 worsened `+5.71%`, above the 5% cap;
- two of three windows were material regressions;
- its simultaneous 90% EV lower bound was `-2.494851`.

Across the complete panel:

- 0/31 had positive formal aggregate EV;
- 0/31 had positive formal aggregate PnL;
- 0/31 had a positive simultaneous EV lower bound;
- 18/31 added both EV and PnL versus leaving the sleeve in cash;
- 28/31 added PnL versus cash;
- final verdicts were 31/31 `portfolio_reject`.

The result separates two claims that the old Gate 4 conflated. Several sleeves
have positive standalone use of otherwise idle cash, but none earned enough to
cover the opportunity cost of replacing 10% of the current core. Under the
predeclared contract, that is a real economic rejection rather than a
champion-gate false negative.

## Verification

```powershell
.\.venv\Scripts\python.exe -B quant\portfolio_contribution_batch.py --ohlcv-snapshot data\experiments\exp-20260715-002\candidate_ohlcv_rowset.json.gz --ohlcv-snapshot-sha256 27148fd7c0eac5023f9acfadc543e81f16d7edb0ac9617dd669df96e33b2714f
.\.venv\Scripts\python.exe -B -m pytest quant\test_portfolio_contribution_batch.py quant\test_portfolio_contribution_gate.py quant\test_full_stack_candidate_pool.py quant\test_experiment_fingerprint.py -q
```

The frozen replay completed without consulting the mutable warehouse and the
focused suite passed 240 tests.

## Reflection and retry boundary

Why it failed: current core returns are strong enough that the funded 10%
replacement opportunity cost dominates the positive cash-relative contribution
of these sleeves. The best candidate also missed the tail-risk cap and regressed
materially in two windows.

Forbidden near-neighbor retry: do not change the weight, thresholds, hold,
notional, event subtype, or candidate ordering and rerun these same 31 frozen
representatives. Do not restore additive exposure or the discarded
double-scaled measurement.

A new experiment requires at least one genuinely new evidence axis: a
prospective first-seen ledger, a complete pre-frozen selection panel, a new
candidate family/data source, or an independently authorized risk-budget gate
whose objective explicitly permits return sacrifice for tail-risk reduction.
