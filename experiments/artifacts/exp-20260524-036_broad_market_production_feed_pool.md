# exp-20260524-036 Broad-Market Production-Feed Candidate Pool

Decision: `rejected_broad_market_production_feed_pool`.

Single causal variable: candidate pool source for the default-off broad-market paper sleeve.

## Sweep

| Variant | Gate 4 | Candidates | Trades | Changed | dEV | Rel EV | dPnL | EV Improved | EV Regressed | Max DD Worse |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_accepted_frozen_pool | FAIL | 712 | 90 | 0 | +0.0000 | +0.00% | $+0.00 | 0 | 0 | +0.0000% |
| shared_universe_state_feed_pool | FAIL | 18 | 49 | 137 | +0.3367 | +2.00% | $+7,481.90 | 1 | 2 | +0.6300% |

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 7.4190 | 7.2664 | -0.1526 | $159,891.81 | $166,278.17 | $+6,386.36 |
| mid_weak | 7.3451 | 8.0595 | +0.7144 | $160,023.22 | $168,608.50 | $+8,585.28 |
| old_thin | 2.0757 | 1.8506 | -0.2251 | $94,782.99 | $87,293.25 | $-7,489.74 |

## Gate 4

```json
{
  "aggregate_ev_delta": 0.3367,
  "aggregate_pnl_delta": 7481.9,
  "candidate_ticker_count": 18,
  "changed_guard_passed": true,
  "changed_trade_count": 137,
  "changed_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "concentration_guard_passed": false,
  "drawdown_guard_passed": false,
  "identity_control_passed": true,
  "materiality_guard_passed": false,
  "max_drawdown_worse_guardrail": 0.005,
  "max_drawdown_worse_max": 0.0063,
  "max_single_ticker_positive_share": 0.5,
  "max_top5_positive_share": 0.7,
  "metrics_gate_passed": false,
  "minimum_changed_trades": 4,
  "minimum_changed_windows": 2,
  "minimum_ev_improved_windows": 3,
  "minimum_relative_ev_improvement": 0.1,
  "minimum_selected_trades": 30,
  "minimum_selected_windows": 3,
  "passed": false,
  "relative_ev_improvement": 0.019994,
  "sample_guard_passed": true,
  "selected_trade_count": 49,
  "selected_windows": 3,
  "single_ticker_positive_share": 0.237129,
  "top5_positive_share": 0.788902,
  "windows_ev_improved": 1,
  "windows_ev_regressed": 2,
  "windows_pnl_regressed": 1
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
  "existing_feed_rule_version": "broad_market_universe_state_observation_feed_v1",
  "live_order_path_changed": false,
  "parity_test_added": false,
  "production_signal_path_changed": false,
  "promotion_requirement": "Any positive production promotion still needs point-in-time universe_state feed history or forward closed outcomes before enabling orders.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false,
  "trade_enabled": false,
  "uses_existing_shared_forward_feed_function": true
}
```

No JavaScript was used.
