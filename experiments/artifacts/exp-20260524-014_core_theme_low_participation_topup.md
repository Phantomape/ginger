# exp-20260524-014 core_theme_low_participation_topup

## Hypothesis
The entry-day ranking surface suggests low theme_participation core stock trades have strong average outcomes across the canonical windows. Low theme participation may mark less crowded, more idiosyncratic continuation entries, so already-qualified non-ETF/non-Commodity core signals with theme_participation <= 0.25 may deserve a small cap-aware top-up without changing entries, exits, ranking, universe, news, or LLM logic.

## Trial accounting
- trial_family: core_theme_low_participation_topup
- changed_variable: theme_low_participation_post_sizing_multiplier
- prior_trial_count: 0
- multiple_testing_risk_bucket: moderate
- new_evidence_type: new_production_visible_theme_crowding_component_field

## Three-window aggregate
- baseline EV: 7.8941
- best EV: 7.885
- EV delta: -0.0091
- PnL delta: 1370.01
- decision: rejected_failed_gate4

## Sweep summary
| variant | multiplier | EV delta | PnL delta | DD delta | adjusted | changed trades | max pos share | passed |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| theme_low_participation_topup_1025 | 1.025 | -0.0183 | 537.29 | 0.0016 | 6 | 14 | 0.539107 | False |
| theme_low_participation_topup_1050 | 1.05 | -0.0091 | 1370.01 | 0.0035 | 6 | 18 | 0.513375 | False |
| theme_low_participation_topup_1075 | 1.075 | -0.0199 | 1972.25 | 0.0051 | 6 | 20 | 0.358661 | False |
| theme_low_participation_topup_1100 | 1.1 | -0.0326 | 2809.25 | 0.0082 | 7 | 23 | 0.34562 | False |

## Selected Window Deltas
| window | EV | PnL | DD | survival | worst trade | tail loss share |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | -0.0036 | 714.72 | 0.0019 | 0.0 | 0.0 | 0.0 |
| mid_weak | -0.0055 | 655.29 | 0.0035 | 0.0 | 0.0 | 0.016296 |
| old_thin | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## Production impact
```json
{
  "backtester_adapter_changed": false,
  "parity_test_added": false,
  "promotion_required_if_accepted": "Move the theme-participation component field and risk policy into shared daily context/risk/portfolio modules with parity tests, then rerun the same three-window protocol before production use.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

## Closeout
Best variant failed Gate 4 because at least one fixed window regressed in expected_value_score.
