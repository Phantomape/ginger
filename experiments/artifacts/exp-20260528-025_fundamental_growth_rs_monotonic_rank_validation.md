# exp-20260528-025 Fundamental Growth + RS Monotonic Rank Validation

Decision: `observed_only_partial_rank_evidence_not_promotable`.

Single variable: `fundamental_growth_rs_score_v1` tercile monotonicity on accepted exp-20260528-017 target trades. No production or backtest strategy behavior changed.

## Overall Buckets

| Bucket | Trades | Avg score | PnL | Avg PnL | Win rate | Max single positive share |
|---|---:|---:|---:|---:|---:|---:|
| top_tercile | 112 | 2.317598 | $56,723.26 | $506.46 | 0.633929 | 0.399128 |
| middle_tercile | 112 | 1.796027 | $39,334.92 | $351.20 | 0.598214 | 0.343664 |
| bottom_tercile | 112 | 1.386551 | $31,085.97 | $277.55 | 0.571429 | 0.243886 |

## Window Evidence

| Window | Top avg PnL | Middle avg PnL | Bottom avg PnL | Strict monotonic | Top > bottom |
|---|---:|---:|---:|---|---|
| late_strong | $208.34 | $388.29 | $181.69 | False | True |
| mid_weak | $412.59 | $219.99 | $822.07 | False | False |
| old_thin | $292.30 | $740.42 | $98.74 | False | True |

## Validation

```json
{
  "monotonic_windows": [],
  "overall_strictly_monotonic": true,
  "overall_top_beats_bottom": true,
  "passed_observed_only_validation": false,
  "reason": "Top score bucket beats bottom in enough places to keep observing, but strict monotonicity is not stable enough for promotion.",
  "status": "observed_only_partial_rank_evidence_not_promotable",
  "top_beats_bottom_windows": [
    "late_strong",
    "old_thin"
  ],
  "top_positive_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "window_count": 3
}
```

## Interpretation

fundamental_growth_rs_score_v1 validation status: observed_only_partial_rank_evidence_not_promotable. Top score bucket beats bottom in enough places to keep observing, but strict monotonicity is not stable enough for promotion. The accepted historical paper EV remains the reference evidence, but this run does not justify another scalar or live ranking change; forward replacement-value rows are still required.

No JavaScript was used.
