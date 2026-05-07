# SEC Guidance-Raise Selloff Recovery

- experiment_id: `exp-20260506-013`
- timestamp: `2026-05-06T10:12:08+00:00`
- decision: `rejected_no_stable_alpha`
- production_impact: `experiment_only_replay_overlay_no_live_or_default_backtest_strategy_change`

## Hypothesis

A fixed Item 2.02 SEC event packet where the company explicitly raises guidance but the first tradeable day underperforms SPY may capture underreaction and improve portfolio expected value as a bounded 10k-notional event sleeve.

## Three-Window Results

| Window | Baseline EV | Overlay EV | Delta EV | Baseline PnL | Overlay PnL | Event PnL | Trades | Win rate | Gate read |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| late_strong | 3.4191 | 3.3175 | -0.1016 | 78600.33 | 77875.07 | -1363.48 | 21 | 0.7143 | none |
| mid_weak | 1.4415 | 1.4858 | 0.0443 | 55015.08 | 55855.75 | 617.31 | 23 | 0.5217 | none |
| old_thin | 0.3179 | 0.3249 | 0.007 | 24642.07 | 24994.63 | 352.56 | 24 | 0.4167 | passes_trade_count |

## Aggregate

```json
{
  "baseline_ev_sum": 5.1785,
  "baseline_pnl_sum": 158257.48,
  "ev_delta_pct": -0.009713,
  "ev_delta_sum": -0.0503,
  "overlay_ev_sum": 5.1282,
  "overlay_pnl_sum": 158725.45,
  "pnl_delta": 467.97,
  "pnl_delta_pct": 0.002957,
  "windows_ev_improved": 2,
  "windows_ev_regressed": 1,
  "windows_material_ev_or_pnl": 0,
  "windows_trade_count_win_rate_gate": 1
}
```

## Decision Rationale

The fixed event sleeve did not improve the majority of fixed windows without regression.

## Production Parity

No production or default backtester strategy path changed in this run. Any positive result requires a shared default-off event sleeve adapter before it can affect live orders.

## Do-Not-Repeat Note

Do not retry guidance-raise selloff recovery on the same sample; look for a different event source or new forward evidence.
