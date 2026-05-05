# Form 4 Historical Forward Queue Replay

- experiment_id: `exp-20260504-005`
- timestamp: `2026-05-04T00:50:58+00:00`
- decision: `default_off_candidate_observation_only`
- production_impact: `historical_shadow_replay_only_no_strategy_change`

## Hypothesis

Historical PIT-safe Form 4 forward queue replay can show whether the existing default-off queue would have produced enough candidates and forward returns across canonical windows to justify a default-off replay harness.

## Data Availability

- transaction_file: `data/non_ohlcv/form4_transactions_20241002_20260502.jsonl`
- PIT-safe rows: `27879`
- queue candidates: `17`
- missing CIK tickers: `['SNXX']`

## Queue Replay

- queue_name: `FORM4_MEANINGFUL_PURCHASE_FORWARD_QUEUE`
- rule_version: `form4_meaningful_purchase_ge_500k_v1`
- historical_candidate_days: `17`
- historical_candidate_count: `17`

| Horizon | Count | Avg return | Avg excess SPY | Avg excess QQQ | Excess SPY win rate |
|---|---:|---:|---:|---:|---:|
| 5d | 13 | 2.67% | 1.96% | 1.92% | 0.6923 |
| 10d | 13 | 6.10% | 4.76% | 4.52% | 0.8462 |
| 20d | 13 | 6.58% | 5.02% | 4.63% | 0.6923 |
| 60d | 12 | 14.51% | 10.79% | 9.64% | 0.5833 |
| 90d | 11 | 18.92% | 10.87% | 9.08% | 0.5455 |

## Three-Window Replay

| Window | Candidates | 10d valid | 10d avg excess SPY | 60d valid | 60d avg excess SPY |
|---|---:|---:|---:|---:|---:|
| old_thin | 3 | 1 | 0.33% | 1 | -4.16% |
| mid_weak | 10 | 8 | 5.27% | 8 | 16.98% |
| late_strong | 4 | 4 | 4.84% | 3 | -0.73% |

## Overlap And Slot Value

- accepted trade matches within 20d: `0`
- top skipped matches within 120d: `0`
- same-day accepted-trade conflicts: `2`
- same-day top-skipped conflicts: `2`

## Decision

Historical replay confirms the existing default-off Form 4 queue would have emitted nonzero PIT-safe candidates across all three canonical windows, with positive average 10d SPY excess in windows that have valid outcomes. It still does not justify production promotion: old_thin has only one valid 10d sample, current live queue candidates remain zero, and slot-conflict value is not portfolio-capacity aware.

## Next Action

Keep the queue default-off and add/monitor closed-out replacement-value snapshots; the next valid promotion test is a shared default-off event-sleeve replay with explicit slot-capacity accounting, not another simple value or owner-role sweep.
