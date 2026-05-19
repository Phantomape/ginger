# exp-20260517-018 space_vsat_fallback_risk_scalar

- hypothesis: VSAT's mature satcom forward row beat cash, same-theme replacement, and broad benchmarks, but full-risk fallback admission failed on drawdown and old_thin. A conservative fallback risk scalar may keep the candidate-pool edge while limiting Space peer-state noise.
- change_type: risk_allocation_candidate_pool
- changed_variable: space_vsat_forward_benchmark_same_theme_satcom_fallback_risk_scalar
- backtest_protocol: docs/backtesting.md fixed 3-window Space protocol using frozen Space augmented snapshots
- selected_scalar: `1.0`
- decision: reject
- rejection_reason: no_window_regressed; drawdown_delta_within_limit; no_window_ev_regression; max_window_drawdown_delta_lte_0_5pp

## Gate Answers

- alpha_hypothesis: VSAT has one mature forward row that beat cash, same-theme, SPY, QQQ, UFO, and ARKX; if it is real alpha, a conservative fallback risk scalar should preserve upside while controlling exp-032 drawdown.
- prior_similar_experiments: exp-20260516-032 rejected full-risk VSAT fallback because old_thin regressed and max drawdown drift breached the guardrail; exp-20260516-036 rejected IWM-gated membership because the selected extension trade vanished and old_thin still regressed.
- one_independent_variable: space_vsat_forward_benchmark_same_theme_satcom_fallback_risk_scalar
- success_criteria: docs/backtesting.md fixed three-window Space protocol; aggregate EV/PnL positive, no EV-regressed window, max drawdown drift <= 0.5pp, survival > 5%, fallback signals present.
- reproducibility: .venv\Scripts\python.exe quant\experiments\exp_20260517_018_space_vsat_fallback_risk_scalar.py

## Sweep

| scalar | decision | dEV | dPnL | max DD delta | improved windows | regressed windows | extension trades |
|---:|---|---:|---:|---:|---|---|---:|
| 0.1250 | reject | 1.029300 | 30703.21 | 0.032200 | late_strong, mid_weak | old_thin | 1 |
| 0.2500 | reject | 1.663100 | 40715.41 | 0.032200 | late_strong, mid_weak | old_thin | 1 |
| 0.5000 | reject | 2.868800 | 59886.76 | 0.032200 | late_strong, mid_weak | old_thin | 1 |
| 0.7500 | reject | 4.130800 | 81700.33 | 0.032200 | late_strong, mid_weak | old_thin | 1 |
| 1.0000 | reject | 5.146800 | 101063.13 | 0.032200 | late_strong, mid_weak | old_thin | 1 |

## Selected Three-Window Metrics

| window | before EV | after EV | EV delta | before PnL | after PnL | PnL delta | DD delta | survival delta | trades delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.735600 | 9.142900 | 0.407300 | 248172.75 | 270496.33 | 22323.58 | 0.032200 | -0.021900 | 1 |
| mid_weak | 19.022900 | 23.803200 | 4.780300 | 420858.87 | 501118.52 | 80259.65 | -0.004300 | 0.018900 | 1 |
| old_thin | 1.238400 | 1.197600 | -0.040800 | 68797.02 | 67276.92 | -1520.10 | 0.000000 | 0.000000 | 0 |

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
