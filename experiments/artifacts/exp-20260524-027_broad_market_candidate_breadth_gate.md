# exp-20260524-027 Broad-Market Candidate-Breadth Gate

Decision: `rejected_broad_market_candidate_breadth_gate`.

Single causal variable: minimum same-day broad-market candidate count before the default-off paper sleeve opens new entries.

## Trial Accounting

- mechanism_family: `broad_market_participation_quality`
- trial_family: `broad_market_candidate_breadth_selection_gate`
- changed_variable: `broad_market_day_candidate_count_breadth_gate`
- prior_trial_count: `7`
- multiple_testing_risk_bucket: `high`
- new_evidence_type: `new_production_visible_market_participation_field`

## Sweep

| Variant | Gate 4 | Min Count | Trades | Changed | Blocked Days | dEV | Rel EV | dPnL | EV Improved | EV Regressed | Max DD Worse |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_no_candidate_breadth_gate | FAIL | none | 90 | 0 | 0 | +0.0000 | +0.00% | $+0.00 | 0 | 0 | +0.0000% |
| candidate_count_gte_10 | FAIL | 10 | 90 | 32 | 10 | -0.1088 | -0.65% | $-2,873.44 | 0 | 1 | +1.6600% |
| candidate_count_gte_15 | FAIL | 15 | 90 | 70 | 20 | -0.7663 | -4.55% | $-10,343.48 | 0 | 2 | +3.9500% |
| candidate_count_gte_20 | FAIL | 20 | 85 | 87 | 34 | -0.8526 | -5.06% | $-9,845.07 | 0 | 2 | +3.9500% |
| candidate_count_gte_25 | FAIL | 25 | 81 | 131 | 73 | -0.9196 | -5.46% | $-16,318.36 | 0 | 3 | +2.4100% |
| candidate_count_gte_30 | FAIL | 30 | 76 | 144 | 103 | -1.6995 | -10.09% | $-28,921.22 | 0 | 3 | +2.6500% |
| candidate_count_gte_40 | FAIL | 40 | 66 | 156 | 158 | -0.1189 | -0.71% | $-3,169.78 | 1 | 2 | +0.8200% |

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 7.4190 | 7.4190 | +0.0000 | $159,891.81 | $159,891.81 | $+0.00 |
| mid_weak | 7.3451 | 7.3451 | +0.0000 | $160,023.22 | $160,023.22 | $+0.00 |
| old_thin | 2.0757 | 1.9669 | -0.1088 | $94,782.99 | $91,909.55 | $-2,873.44 |

## Gate 4

```json
{
  "aggregate_ev_delta": -0.1088,
  "aggregate_pnl_delta": -2873.44,
  "breadth_blocked_day_count": 10,
  "changed_guard_passed": false,
  "changed_trade_count": 32,
  "changed_windows": [
    "old_thin"
  ],
  "concentration_guard_passed": true,
  "drawdown_guard_passed": false,
  "identity_control_passed": true,
  "materiality_guard_passed": false,
  "max_drawdown_worse_guardrail": 0.005,
  "max_drawdown_worse_max": 0.0166,
  "max_single_ticker_positive_share": 0.5,
  "max_top5_positive_share": 0.7,
  "minimum_changed_trades": 4,
  "minimum_changed_windows": 2,
  "minimum_ev_improved_windows": 3,
  "minimum_relative_ev_improvement": 0.1,
  "minimum_selected_trades": 30,
  "minimum_selected_windows": 3,
  "passed": false,
  "relative_ev_improvement": -0.006461,
  "sample_guard_passed": true,
  "selected_trade_count": 90,
  "selected_windows": 3,
  "single_ticker_positive_share": 0.133099,
  "top5_positive_share": 0.444913,
  "windows_ev_improved": 0,
  "windows_ev_regressed": 1,
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
  "live_order_path_changed": false,
  "parity_test_added": false,
  "production_signal_path_changed": false,
  "replay_only": false,
  "run_adapter_changed": false,
  "shared_policy_changed": false,
  "trade_enabled": false
}
```

No JavaScript was used.
