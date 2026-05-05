# Form 4 Event Sleeve Replay

- experiment_id: `exp-20260504-009`
- timestamp: `2026-05-04T01:35:38+00:00`
- decision: `default_off_event_sleeve_positive_not_promoted`
- production_impact: `default_off_shadow_event_sleeve_replay_only`

## Frozen Replay Config

- queue_rule: `FORM4_MEANINGFUL_PURCHASE_FORWARD_QUEUE / form4_meaningful_purchase_ge_500k_v1`
- min_total_purchase_value: `$500,000`
- hold_days: `10`
- max_event_positions: `1`
- event_notional: `$10,000`
- initial_capital_base: `$100,000`
- round_trip_cost_pct: `0.0035`

## Primary 10d Results

| Window | Candidates | Trades | PnL | Return | Sharpe | Max DD | Win rate | EV | vs SPY |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| old_thin | 3 | 1 | $6.11 | 0.01% | 0.023826 | 0.38% | 100.00% | 1.46e-06 | 6.54% |
| mid_weak | 10 | 4 | $1,991.30 | 1.99% | 1.65413 | 0.85% | 50.00% | 0.03293869 | -22.29% |
| late_strong | 4 | 3 | $1,799.63 | 1.80% | 1.578481 | 0.92% | 100.00% | 0.02840682 | -4.18% |

## Aggregate Read

- total_pnl: `$3,797.04`
- total_return_on_100k_base: `3.80%`
- trade_count: `8`
- win_rate: `75.00%`
- positive_pnl_windows: `3/3`
- expected_value_score_proxy: `0.04121607`

## Diagnostic Holds

20d and 60d are diagnostics only; the decision uses the frozen 10d replay.

| Hold | Aggregate PnL | Return | Trades | Positive windows | EV proxy |
|---|---:|---:|---:|---:|---:|
| 20d | $2,525.92 | 2.53% | 7 | 2/3 | 0.00730998 |
| 60d | $-166.31 | -0.17% | 4 | 1/3 | 0.00070186 |

## Decision

The frozen 10d Form 4 event sleeve made money in all three canonical windows with transaction costs and fixed capacity. It is still not a production candidate because the sample is small and this independent sleeve does not yet answer whether Form 4 should consume scarce A/B core slots.

## Next Action

Treat Form 4 as a positive default-off event-sleeve candidate. The next valid test is a shared event-sleeve harness with explicit capital allocation and forward queue reporting; do not wire it into core A/B ranking or scarce slots yet.
