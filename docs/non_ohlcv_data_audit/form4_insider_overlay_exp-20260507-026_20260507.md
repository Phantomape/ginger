# Form 4 Insider Overlay Audit

- experiment_id: `exp-20260507-026`
- generated_at: `2026-05-07T17:29:17+00:00`
- mode: `shadow_overlay_and_data_availability_audit`
- production_impact: `shadow_audit_only_no_live_or_default_backtest_strategy_change`
- current snapshot: `data/non_ohlcv/form4_transactions_20260506.jsonl`
- historical replay file: `data/non_ohlcv/form4_transactions_20241002_20260502.jsonl`

## Decision

`shadow_only`. Form 4 buying remains useful enough to keep observing, but this run does not justify production or core-slot changes.

## Current Data Availability

- rows_written: `750`
- pit_safe_count: `750`
- open_market_purchase_count: `4`
- tickers_mapped/requested: `51/52`
- missing_cik_tickers: `['SNXX']`
- current_meaningful_purchase_event_count: `1`
- current_forward_queue_candidate_count: `0`

## Historical Shadow Outcomes

| Cohort | Events | Tickers | 10d avg | 20d avg | 60d avg | 90d avg | 20d excess vs SPY |
|---|---:|---:|---:|---:|---:|---:|---:|
| all_open_market_purchase | 50 | 20 | 4.128724% | 3.662655% | 14.9441% | 24.925019% | 2.822734% |
| meaningful_purchase_v1 | 40 | 16 | 4.755596% | 4.025277% | 14.780537% | 29.199813% | 2.883286% |
| ceo_cfo_purchase_v1 | 0 | 0 | n/a | n/a | n/a | n/a | n/a |
| forward_queue_ge_500k | 17 | 10 | 6.100954% | 6.577192% | 14.512325% | 25.359344% | 5.017808% |

## Historical Event Counts By Window

| Cohort | old_thin | mid_weak | late_strong |
|---|---:|---:|---:|
| all_open_market_purchase | 13 | 16 | 21 |
| meaningful_purchase_v1 | 9 | 13 | 18 |
| ceo_cfo_purchase_v1 | 0 | 0 | 0 |
| forward_queue_ge_500k | 3 | 10 | 4 |

## Accepted Signal Overlap

| Prior lookback | Matched trades | Matched avg PnL | Matched win rate | Unmatched avg PnL | Unmatched win rate |
|---|---:|---:|---:|---:|---:|
| 10d | 0 | n/a | n/a | 4.98029% | 0.5645 |
| 20d | 0 | n/a | n/a | 4.98029% | 0.5645 |
| 60d | 2 | 7.9319% | 0.5 | 4.881903% | 0.5667 |
| 90d | 5 | 6.95812% | 0.6 | 4.806796% | 0.5614 |

## Slot Value

The current run did not replay Form 4 into core slots. Prior slot-capacity work remains the relevant blocker: `exp-20260504-006` was `shadow_only_capacity_inconclusive`, while `exp-20260504-034` was positive but sub-material as a satellite overlay.

## PIT Status

Rows include SEC acceptance timestamps, conservative next-session `usable_trade_date`, parsed transaction code/value/role fields, and `pit_safe_flag`. The historical file is still a backfilled replay artifact, so it is valid for shadow research but not enough for production evidence.

## Next Step

Keep collecting forward Form 4 queue/sleeve outcomes; next useful test is a default-off same-day candidate snapshot join that measures add-on/hold confirmation without consuming core A/B slots.
