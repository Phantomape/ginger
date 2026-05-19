# exp-20260519-036 Broad-Market Shared Paper Adapter

Decision: `accepted_default_off_broad_market_shared_paper_adapter`.

Single causal variable: move the fixed exp-20260519-035 price_floor_40 candidate logic into a shared default-off paper adapter.

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Broad Trades |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 7.1202 | 7.1323 | +0.0121 | $149,584.06 | $154,379.70 | $+4,795.64 | 30 |
| mid_weak | 6.5001 | 7.1660 | +0.6659 | $145,415.33 | $156,462.94 | $+11,047.61 | 30 |
| old_thin | 1.9959 | 2.0387 | +0.0428 | $90,723.08 | $93,519.29 | $+2,796.21 | 30 |

## Gate 4

```json
{
  "aggregate_ev_delta": 0.7208,
  "aggregate_pnl_delta": 18639.46,
  "concentration_guard_passed": true,
  "drawdown_guard_passed": true,
  "max_drawdown_worse_guardrail": 0.005,
  "max_drawdown_worse_max": 0.0023,
  "max_single_ticker_positive_share": 0.5,
  "max_top5_positive_share": 0.7,
  "minimum_selected_trades": 30,
  "minimum_selected_windows": 3,
  "passed": true,
  "sample_guard_passed": true,
  "selected_trade_count": 90,
  "selected_windows": 3,
  "single_ticker_positive_share": 0.111598,
  "top5_positive_share": 0.394167,
  "window_guard_passed": true,
  "windows_ev_improved": 3,
  "windows_ev_regressed": 0,
  "windows_pnl_improved": 3,
  "windows_pnl_regressed": 0
}
```

## Production Impact

```json
{
  "alters_candidate_ranking": false,
  "alters_exits": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_sizing": false,
  "backtester_adapter_changed": false,
  "default_off_paper_only": true,
  "live_order_path_changed": false,
  "parity_test_added": true,
  "production_signal_path_changed": false,
  "replay_only": false,
  "run_adapter_changed": true,
  "shared_policy_changed": true,
  "trade_enabled": false
}
```

No JavaScript was used.
