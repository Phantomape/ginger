# exp-20260518-017 space_vsat_isolated_fallback_pool

- hypothesis: VSAT has one mature satcom forward row that beat cash, same-theme replacement, SPY, QQQ, UFO, and ARKX, but adding it to the official Space peer basket contaminated existing Space peer/basket states in exp-20260517-018. An isolated fallback pool may preserve VSAT replacement alpha without changing the accepted official Space basket.
- change_type: candidate_pool_governance
- changed_variable: `space_vsat_forward_benchmark_same_theme_isolated_fallback_membership`
- backtest_protocol: docs/backtesting.md fixed 3-window Space protocol using frozen Space augmented snapshots
- decision: `reject`
- rejection_reason: no_window_regressed; drawdown_delta_within_limit; no_window_ev_regression; max_window_drawdown_delta_lte_0_5pp

## Gate Answers

- alpha_hypothesis: Isolated VSAT satcom trend fallback can add replacement-value alpha without contaminating official Space peer/basket states.
- prior_similar_experiments: exp-20260516-032 and exp-20260516-036 rejected VSAT fallback membership; exp-20260517-018 rejected risk-scaled VSAT fallback and explicitly required a field that prevents official peer-basket contamination.
- one_independent_variable: space_vsat_forward_benchmark_same_theme_isolated_fallback_membership
- success_criteria: Three fixed Space windows; aggregate EV/PnL positive, no EV-regressed window, max drawdown drift <= 0.5pp, survival > 5%, fallback signals present.
- reproducibility: .venv\Scripts\python.exe quant\experiments\exp_20260518_017_space_vsat_isolated_fallback_pool.py

## Three-Window Metrics

| window | before EV | after EV | EV delta | before PnL | after PnL | PnL delta | DD delta | survival delta | trades delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.735600 | 9.142900 | 0.407300 | 248172.75 | 270496.33 | 22323.58 | 0.032200 | -0.021900 | 1 |
| mid_weak | 19.022900 | 22.895600 | 3.872700 | 420858.87 | 484054.50 | 63195.63 | -0.005300 | 0.018900 | 1 |
| old_thin | 1.238400 | 1.197600 | -0.040800 | 68797.02 | 67276.92 | -1520.10 | 0.000000 | 0.000000 | 0 |

## Aggregate Delta

- expected_value_score_delta: `4.2392`
- total_pnl_delta: `83999.11`
- max_drawdown_delta: `0.0322`
- min_survival_delta: `0.0066`

## Fallback Audit

```json
{
  "by_action": {
    "filtered": 2,
    "kept": 4,
    "risk_scaled": 4
  },
  "by_iwm_state": {
    "smallcap_laggard": 4,
    "smallcap_leader": 2,
    "unknown": 4
  },
  "by_peer_state": {
    "leader": 4,
    "nonleader": 2,
    "unknown": 4
  },
  "by_reason": {
    "kept_trend_fallback": 4,
    "non_trend": 2,
    "unknown": 4
  },
  "counts": {
    "filtered_VSAT": 2,
    "filtered_breakout_long": 2,
    "filtered_extension_non_trend": 2,
    "filtered_extension_signal": 2,
    "kept_VSAT": 4,
    "kept_extension_signal": 4,
    "risk_scaled_VSAT": 4,
    "risk_scaled_extension_signal": 4
  },
  "records": [
    {
      "action": "filtered",
      "date": "",
      "reason": "non_trend",
      "risk_scalar": 1.0,
      "space_iwm_relative_state": "smallcap_leader",
      "space_peer_momentum_state": "nonleader",
      "strategy": "breakout_long",
      "ticker": "VSAT"
    },
    {
      "action": "filtered",
      "date": "",
      "reason": "non_trend",
      "risk_scalar": 1.0,
      "space_iwm_relative_state": "smallcap_laggard",
      "space_peer_momentum_state": "leader",
      "strategy": "breakout_long",
      "ticker": "VSAT"
    },
    {
      "action": "kept",
      "date": "",
      "reason": "kept_trend_fallback",
      "risk_scalar": 1.0,
      "space_iwm_relative_state": "smallcap_laggard",
      "space_peer_momentum_state": "nonleader",
      "strategy": "trend_long",
      "ticker": "VSAT"
    },
    {
      "action": "risk_scaled",
      "date": "",
      "new_shares": 3142,
      "old_shares": 3142,
      "risk_scalar": 1.0,
      "strategy": "trend_long",
      "ticker": "VSAT"
    },
    {
      "action": "kept",
      "date": "",
      "reason": "kept_trend_fallback",
      "risk_scalar": 1.0,
      "space_iwm_relative_state": "smallcap_laggard",
      "space_peer_momentum_state": "leader",
      "strategy": "trend_long",
      "ticker": "VSAT"
    },
    {
      "action": "risk_scaled",
      "date": "",
      "new_shares": 5405,
      "old_shares": 5405,
      "risk_scalar": 1.0,
      "strategy": "trend_long",
      "ticker": "VSAT"
    },
    {
      "action": "kept",
      "date": "",
      "reason": "kept_trend_fallback",
      "risk_scalar": 1.0,
      "space_iwm_relative_state": "smallcap_laggard",
      "space_peer_momentum_state": "leader",
      "strategy": "trend_long",
      "ticker": "VSAT"
    },
    {
      "action": "risk_scaled",
      "date": "",
      "new_shares": 4509,
      "old_shares": 4509,
      "risk_scalar": 1.0,
      "strategy": "trend_long",
      "ticker": "VSAT"
    },
    {
      "action": "kept",
      "date": "",
      "reason": "kept_trend_fallback",
      "risk_scalar": 1.0,
      "space_iwm_relative_state": "smallcap_leader",
      "space_peer_momentum_state": "leader",
      "strategy": "trend_long",
      "ticker": "VSAT"
    },
    {
      "action": "risk_scaled",
      "date": "",
      "new_shares": 3762,
      "old_shares": 3762,
      "risk_scalar": 1.0,
      "strategy": "trend_long",
      "ticker": "VSAT"
    }
  ],
  "risk_scalar": 1.0,
  "rule": "VSAT is eligible only as a trend_long fallback on dates with no base official Space signal, then sized by the tested fallback risk scalar."
}
```

## Gate Detail

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_ev_positive": true,
  "aggregate_pnl_delta_positive": true,
  "at_least_two_windows_improved": true,
  "drawdown_delta_within_limit": false,
  "extension_trades_present": true,
  "fallback_signals_present": true,
  "forward_gate_passed": true,
  "max_window_drawdown_delta_lte_0_5pp": false,
  "no_window_ev_regression": false,
  "no_window_regressed": false,
  "nonzero_risk_scalar": true,
  "survival_rate_ok": true,
  "trade_count_ok": true
}
```

## Production Impact

```text
production_impact:
  shared_policy_changed: False
  backtester_adapter_changed: False
  run_adapter_changed: False
  replay_only: True
  parity_test_added: False
  live_slots: 0
```
