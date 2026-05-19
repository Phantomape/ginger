# exp-20260515-038 exec_lag_rr_leadership_risk

- hypothesis: Within the accepted fixed candidate stack, trend/breakout signals in the same-day top quartile of exec_lag_adj_net_rr carry cleaner asymmetric payoff and can support a small cap-aware risk top-up.
- change_type: alpha_search
- changed_variable: exec_lag_rr_leadership_risk_multiplier
- decision: rejected
- selected_multiplier: 1.075
- aggregate_ev_delta: 0.0349
- aggregate_pnl_delta: 2765.78
- rejection_reason: failed_three_window_gate4

## Three-window metrics

| window | before_ev | after_ev | ev_delta | before_pnl | after_pnl | pnl_delta | after_max_dd | adjusted_signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1064 | 5.1204 | 0.0140 | 116319.10 | 117706.32 | 1387.22 | 0.0695 | 7 |
| mid_weak | 2.0987 | 2.1331 | 0.0344 | 76035.04 | 77845.27 | 1810.23 | 0.1119 | 11 |
| old_thin | 0.5294 | 0.5159 | -0.0135 | 37282.59 | 36850.92 | -431.67 | 0.1055 | 10 |

## Gate answers

- prior_similar_experiment: No prior log hit for exec_lag_adj_net_rr top-quartile allocation. Recent failed adjacent ideas were sector thrust, candidate-pool expansion, mature satcom/Space admissions, and simple momentum/quality scalar overlays.
- one_causal_variable: Only the cap-aware risk multiplier for same-day top-quartile exec_lag_adj_net_rr trend/breakout stock signals changes.
- acceptance_criteria: Follow docs/backtesting.md three-window protocol; require positive aggregate EV/PnL, no EV regression by window, min survival_rate >= 5%, nonzero adjusted signals, and max_drawdown no worse by more than 0.5 percentage points.
- reproducibility: This file, experiments artifacts, and docs/experiment_log.jsonl contain the parameters, windows, and before/after metrics.

## Production impact

```text
production_impact:
  shared_policy_changed: false
  backtester_adapter_changed: true
  run_adapter_changed: false
  replay_only: true
  parity_test_added: false
```
