# exp-20260522-024 risk_on_breakout_topup

## Hypothesis
Risk-on stock breakout_long signals have a strong current-stack three-window contribution and may deserve a small cap-aware post-sizing top-up. The test should improve EV without changing entries, filters, ranking, exits, universe, LLM, or news logic.

## Trial accounting
- trial_family: risk_on_breakout_risk_allocation
- changed_variable: risk_on_stock_breakout_post_sizing_multiplier
- prior_trial_count: 8
- multiple_testing_risk_bucket: moderate
- new_evidence_type: current_stack_three_window_trade_attribution

## Three-window aggregate
- baseline EV: 7.8941
- best EV: 7.8921
- EV delta: -0.002
- PnL delta: 750.57
- decision: rejected_failed_gate4

## Sweep summary
| variant | multiplier | EV delta | PnL delta | DD delta | adjusted | changed trades | max positive ticker share | passed |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| risk_on_breakout_topup_1025 | 1.025 | -0.0067 | 377.93 | 0.0 | 13 | 6 | 0.959301 | False |
| risk_on_breakout_topup_1050 | 1.05 | -0.002 | 750.57 | 0.0 | 15 | 10 | 0.909458 | False |
| risk_on_breakout_topup_1075 | 1.075 | -0.0134 | 1037.0 | 0.0 | 15 | 10 | 0.873606 | False |
| risk_on_breakout_topup_1100 | 1.1 | -0.0259 | 1256.62 | 0.0 | 17 | 14 | 0.8423 | False |

## Selected window deltas
| window | EV | PnL | DD | survival | worst trade | tail loss share |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | -0.0018 | 754.55 | 0.0019 | 0.0 | 0.0 | 0.0 |
| mid_weak | 0.0 | -0.71 | 0.0 | 0.0 | 0.0 | -0.000228 |
| old_thin | -0.0002 | -3.27 | 0.0 | 0.0 | 0.0 | -0.000101 |

## Production impact
```json
{
  "backtester_adapter_changed": false,
  "parity_test_added": false,
  "promotion_required_if_accepted": "Move the risk-on stock breakout sizing rule into shared portfolio_engine sizing constants/logic, ensure run.py and backtester.py both use it through size_signals, add tests, and rerun the same three-window protocol.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

## Closeout
Best variant failed Gate 4 because at least one fixed window regressed in expected_value_score.
