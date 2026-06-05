# exp-20260605-023 Breadth Alignment Monotonic Validation

Decision: `rejected_breadth_alignment_component_edge`.

## Hypothesis

Existing breadth_alignment component should show durable monotonic broad-universe forward-return evidence before it remains a continuous ranking input.

## Gate 1 Baseline

- baseline artifact: `data/experiments/exp-20260602-003/exp_20260602_003_post_earnings_explicit_continuation.json`
- aggregate EV: `7.8941`
- aggregate PnL: `$234850.99`
- min survival: `0.7925`
- max drawdown: `0.1119`

## Observed Ladder

| Window | Obs | 5d Q5-Q1 | 5d monotonic | 10d Q5-Q1 | 20d Q5-Q1 |
|---|---:|---:|---:|---:|---:|
| late_strong | 30366 | -0.002142 | False | -8.6e-05 | -0.005832 |
| mid_weak | 31812 | 0.002006 | False | -0.01317 | 0.000387 |
| old_thin | 34655 | 0.00064 | False | -0.002724 | 0.000181 |

## Pooled

- observations: `96833`
- pooled 5d Q5-Q1: `0.004007`
- pooled 5d monotonic: `False`
- RS-controlled 5d residual spread: `0.003254`
- within-day variance share: `0.7058`

## Gate 4

```json
{
  "decision": "rejected_breadth_alignment_component_edge",
  "decision_rule": "Accept observed-only only if pooled 5d top-minus-bottom >= 0.005, residual 5d spread after relative-strength control >= 0.005, the pooled 5d bucket ladder is monotonic, and at least 2/3 windows are both positive and monotonic. No production behavior can change from this observed-only result.",
  "dispersion": {
    "across_day_variance": 0.00200352,
    "cross_sectional": true,
    "distinct": 125,
    "max": 0.7578,
    "min": 0.5,
    "n": 96833,
    "near_constant": false,
    "std": 0.082523,
    "within_day_variance": 0.00480753,
    "within_day_variance_share": 0.7058
  },
  "edge_floor": 0.005,
  "failed_reasons": [
    "pooled_5d_edge_below_floor",
    "rs_controlled_residual_edge_below_floor",
    "insufficient_monotonic_windows",
    "pooled_ladder_not_monotonic"
  ],
  "min_required_monotonic_windows": 2,
  "min_required_positive_windows": 2,
  "monotonic_windows": 0,
  "name": "breadth_alignment_monotonic_edge",
  "passed": false,
  "per_window_5d_monotonic": {
    "late_strong": false,
    "mid_weak": false,
    "old_thin": false
  },
  "per_window_5d_top_minus_bottom": {
    "late_strong": -0.002142,
    "mid_weak": 0.002006,
    "old_thin": 0.00064
  },
  "pooled_5d_monotonic": false,
  "pooled_5d_top_minus_bottom": 0.004007,
  "positive_windows": 2,
  "primary_horizon": 5,
  "residual_5d_spread_vs_relative_strength": 0.003254
}
```

## Production Impact

Read-only attribution only. No shared policy, run adapter, backtester adapter, ranking, sizing, exits, watchlists, reports, paper sleeves, LLM/news path, or orders changed.

No JavaScript was used.
