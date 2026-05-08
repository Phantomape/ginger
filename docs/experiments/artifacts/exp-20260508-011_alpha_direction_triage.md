# exp-20260508-011 Alpha Direction Triage

## Decision

`no_production_change`. This was an alpha-search triage run, not a bug fix.

Analyst estimate revisions are still not usable as a three-window alpha input. The stronger current direction is candidate-pool expansion through liquidity-gated 10-K filing scouts, but only as forward/PIT observation until closed replacement-value outcomes exist.

## Three-Window Core Metrics

| Window | EV before | EV after | Sharpe daily | PnL | Max DD | Win rate | Trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | 3.7435 | 3.7435 | 4.48 | 83562.53 | 5.39% | 78.95% | 19 |
| mid_weak | 1.5478 | 1.5478 | 2.69 | 57542.74 | 8.79% | 52.38% | 21 |
| old_thin | 0.3359 | 0.3359 | 1.28 | 26242.68 | 9.05% | 40.91% | 22 |

No executable rule changed, so before/after core metrics are intentionally identical.

## Estimate Revision Audit

| Window | Snapshot files | Usable rows | Revision steps | Candidate touches |
| --- | ---: | ---: | ---: | ---: |
| late_strong | 129 | 4809 | 37 | 0 |
| mid_weak | 131 | 4904 | 0 | 0 |
| old_thin | 145 | 5424 | 0 | 0 |

Blocker: Estimate revisions are not yet a reliable three-window alpha input: mid_weak and old_thin have zero non-event-day revision steps, and candidate overlap is too sparse for promotion.

## 10-K Candidate-Pool Review

| Window | Candidates | 10d excess avg | 10d excess win rate |
| --- | ---: | ---: | ---: |
| late_strong | 55 | 0.020237 | 0.5273 |
| mid_weak | 1 | -0.102929 | 0.0 |
| old_thin | 47 | 0.005244 | 0.5745 |

Same-day A/B conflict sample: 7 conflicts, 0.068 conflict rate.

Interpretation: This is stronger than the estimate-revision path today because it has positive old/late 10d excess and positive same-day replacement proxy, but it is not production-ready: mid_weak has only one negative candidate and the source remains shadow/PIT-observation rather than a frozen forward entry queue with enough closed outcomes.

## Production Parity

No shared policy, backtester adapter, run adapter, entry, ranking, sizing, exit, LLM, or universe code changed. A future positive 10-K rule must be implemented through a shared policy/adapter before live use.
