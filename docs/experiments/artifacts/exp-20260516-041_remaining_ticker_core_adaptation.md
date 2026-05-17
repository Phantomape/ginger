# exp-20260516-041 Remaining Ticker Core Adaptation

Decision: `accepted_candidates_for_ordered_single_ticker_review`.

## Per-ticker scalar results

| Ticker | Decision | Selected | dEV | dPnL | Improved | Regressed | Affected | Windows | Fast target? |
|---|---|---:|---:|---:|---|---|---:|---:|---|
| V | rejected_or_watch_only | 0.00 | +0.0992 | $+3,745.34 | old_thin | - | 2 | 1 | False |
| DDOG | rejected_or_watch_only | 0.00 | +0.0781 | $+2,901.82 | old_thin | - | 5 | 3 | False |
| ISRG | accepted_for_single_ticker_promotion_review | 0.25 | +0.0512 | $+1,857.98 | mid_weak, old_thin | - | 2 | 2 | False |

## Baseline negative ticker audit

| Ticker | Trades | Wins | PnL | Windows | Sweep status |
|---|---:|---:|---:|---|---|
| V | 2 | 0 | $-3,635.83 | old_thin | exact_sweep |
| TRIP | 1 | 0 | $-2,935.78 | old_thin | observed_only_singleton |
| MCD | 1 | 0 | $-2,644.00 | old_thin | observed_only_singleton |
| DDOG | 2 | 0 | $-2,187.09 | old_thin | exact_sweep |
| ISRG | 2 | 0 | $-1,894.58 | mid_weak, old_thin | exact_sweep |
| SNOW | 1 | 0 | $-445.19 | mid_weak | observed_only_singleton |
| TSM | 3 | 0 | $-133.35 | mid_weak, old_thin | excluded_current_policy |
| DIS | 1 | 0 | $-51.24 | mid_weak | observed_only_singleton |
| META | 1 | 0 | $-20.56 | mid_weak | observed_only_singleton |
| PLTR | 1 | 0 | $-8.11 | mid_weak | observed_only_singleton |

Production impact: replay-only scout. No shared policy was changed.
