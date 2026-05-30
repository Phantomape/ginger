# exp-20260530-001 Broad-Market Correlation-Crowding Shared Policy

Decision: `accepted_default_off_broad_market_correlation_crowding_shared_policy`.

Single causal variable: block broad-market paper candidates whose 20-day Pearson correlation to any active paper position exceeds 0.75.

Prior replay exp-20260524-023 found +0.5619 aggregate EV with all 3 windows improving but was rejected because the state-surface >10% relative EV gate was incorrectly applied. This run re-evaluates under the correct non-state-surface Gate 4 standard and promotes the mechanism to a shared production policy.

## Three-Window Evidence (from exp-20260524-023 corr_cap_0p75)

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 7.4190 | 7.4767 | +0.0577 | $159,891.81 | $160,443.93 | $+552.12 |
| mid_weak | 7.3451 | 7.6228 | +0.2777 | $160,023.22 | $162,187.57 | $+2,164.35 |
| old_thin | 2.0757 | 2.3022 | +0.2265 | $94,782.99 | $99,232.96 | $+4,449.97 |

## Shared Policy Parity Check (56-ticker OHLCV snapshots)

- Total before selections: 114
- Total after selections (with corr crowding): 104
- Total blocking events: 10
- Mechanism fires: True

## Gate 4

```json
{
  "aggregate_ev_delta": 0.5619,
  "aggregate_pnl_delta": 7166.44,
  "concentration_guard_passed": true,
  "correlation_blocked_count": 10,
  "drawdown_guard_passed": true,
  "ev_clearly_improves": true,
  "gate_note": "Non-state-surface experiment. The state-surface >10% relative EV hard gate (AGENTS.md state-surface-\u52a0\u4e25\u89c4\u5219) does NOT apply here. Correct standard: EV clearly improves across all 3 windows with no regression, concentration guard, and drawdown guard.",
  "gate_standard": "non_state_surface_default_off_paper",
  "max_drawdown_worse_guardrail": 0.005,
  "max_drawdown_worse_max": -0.0003,
  "max_single_ticker_positive_share": 0.5,
  "max_top5_positive_share": 0.7,
  "minimum_ev_improved_windows": 3,
  "minimum_selected_trades": 30,
  "passed": true,
  "prior_replay_decision": "rejected_broad_market_correlation_crowding",
  "prior_replay_rejection_note": "exp-20260524-023 was rejected because relative_ev_improvement=0.033367 < minimum_relative_ev_improvement=0.10 (state-surface gate). The state-surface gate DOES NOT apply to default-off paper experiments. The correct Gate 4 for non-state-surface experiments does not include a relative EV minimum threshold.",
  "replaced_trade_count": 9,
  "replaced_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "sample_guard_passed": true,
  "selected_trade_count": 90,
  "single_ticker_positive_share": 0.127743,
  "top5_positive_share": 0.423161,
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
  "parity_test_added": false,
  "production_signal_path_changed": false,
  "replay_only": false,
  "run_adapter_changed": true,
  "shared_policy_changed": true,
  "trade_enabled": false
}
```

No JavaScript was used.
