# exp-20260525-008 core_residual_beta_lagging_haircut

## Hypothesis
Existing core entries whose 20-day return lags SPY, QQQ, and any theme peer basket on a residual basis may be beta participation rather than true leadership. Haircutting only those already-sized non-ETF/non-Commodity core signals may improve expected value without adding a new entry filter or ticker.

## Trial accounting
- trial_family: core_residual_strength_beta_lagging_haircut
- changed_variable: residual_beta_lagging_post_sizing_scalar
- prior_trial_count: 1
- multiple_testing_risk_bucket: moderate_high
- new_evidence_type: new_production_visible_residual_strength_field

## Three-window aggregate
- baseline EV: 7.8941
- best EV: 7.8941
- EV delta: 0.0
- PnL delta: 0.0
- decision: rejected_failed_gate4

## Sweep summary
| variant | multiplier | EV delta | PnL delta | DD delta | adjusted | changed trades | max pos share | passed |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| residual_beta_lagging_haircut_000 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0.0 | False |
| residual_beta_lagging_haircut_025 | 0.25 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0.0 | False |
| residual_beta_lagging_haircut_050 | 0.5 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0.0 | False |
| residual_beta_lagging_haircut_075 | 0.75 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0.0 | False |

## Selected Window Deltas
| window | EV | PnL | DD | survival | worst trade | tail loss share |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| mid_weak | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| old_thin | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## Production impact
```json
{
  "backtester_adapter_changed": false,
  "parity_test_added": false,
  "promotion_required_if_accepted": "Move residual strength exposure and haircut policy into shared daily context/risk/portfolio modules with parity tests, then rerun the same three-window protocol before production use.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

## Closeout
Best variant failed adjusted-signal sample guard; residual beta-lagging did not touch enough sized core signals.
