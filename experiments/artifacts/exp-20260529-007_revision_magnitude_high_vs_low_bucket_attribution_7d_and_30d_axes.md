# exp-20260529-007 Revision Magnitude High-vs-Low Attribution (7d + 30d axes)

Decision: `rejected_no_revision_magnitude_edge`.

Read-only `alpha_discovery`. Re-runs the `exp-20260527-002` revision
magnitude hypothesis now that `exp-20260528-030` filled
`eps_estimate_delta_30d` (which was 0% covered when 027-002 closed
`observed_only_data_gap`). Tests whether **larger** positive expectation
revisions beat **smaller** ones on two magnitude axes.

On the decisive axis (7d, both high/low buckets clear the published
`min_bucket_closed_5d=8` floor), larger revisions **underperform** at
the 5d primary horizon by -1.15 pp. Per AGENTS.md Section 12 the
hypothesis is rejected. This changes no entries, exits, ranking, sizing,
LLM/news inputs, paper sleeves, or live orders.

## Method

For each axis, primary-positive rows with a positive delta are split at
the median of the positive deltas into `high_magnitude` (strictly above
median) and `low_magnitude` (at or below). High vs low is compared at
5d (primary) and 10d (secondary), using `exp-20260527-002`'s published
`gate_thresholds`. An axis is "decisive" only when both buckets clear
the closed-outcome floor for that horizon.

## Results

### eps_estimate_delta_7d (decisive at both horizons)

Median split = 0.05; high N=21, low N=26.

| Horizon | High avg ret | Low avg ret | Lift | High win | Low win | High closed | Low closed | Decisive |
|---|---|---|---|---|---|---|---|---|
| 5d | -0.48% | +0.67% | **-1.15 pp** | 52.9% | 56.3% | 17 | 16 | True |
| 10d | +1.33% | -0.07% | +1.40 pp | 50.0% | 50.0% | 10 | 6 | True |

The 5d primary horizon shows larger 7d revisions underperforming
smaller ones. The 10d horizon flips to a positive +1.40 pp lift — the
same single-window directional instability seen across the PEAD
experiments (exp-20260528-027/028). The primary horizon is the gate,
and it is negative.

### eps_estimate_delta_30d (not decisive — newly unblocked but thin)

Median split = 0.38; high N=11, low N=14.

| Horizon | High avg ret | Low avg ret | Lift | High closed | Low closed | Decisive |
|---|---|---|---|---|---|---|
| 5d | -0.71% | +0.16% | -0.87 pp | 7 | 7 | False (7 < 8) |
| 10d | +1.61% | +3.30% | -1.69 pp | 4 | 5 | False |

The 30d axis that `exp-20260528-030` unblocked is directionally
unfavorable to the hypothesis (larger revisions underperform at both
horizons) but is not decisive: each bucket has only 7 closed 5d
outcomes, below the `min_bucket_closed_5d=8` floor. It does not drive
the gate, but it does not rescue the hypothesis either.

## Gate evaluation

```json
{
  "all_passed": false,
  "gate1": {"name": "axes_have_positive_revision_rows", "passed": true,
            "positive_row_counts": {"eps_estimate_delta_7d": 47,
                                    "eps_estimate_delta_30d": 25}},
  "gate2": {"name": "required_input_fields_present", "passed": true},
  "gate3": {"name": "survival_rate_not_affected_read_only_attribution",
            "passed": true},
  "gate4": {
    "name": "revision_magnitude_high_vs_low_5d",
    "passed": false,
    "status": "rejected_no_revision_magnitude_edge",
    "primary_horizon": "5d",
    "lift_floor": 0.01,
    "decisive_axes": ["eps_estimate_delta_7d"],
    "per_axis_5d_diagnostic": {
      "eps_estimate_delta_7d": {"lift": -0.0115, "decisive": true,
                                "concentration_passed": false, "accepted": false},
      "eps_estimate_delta_30d": {"lift": -0.0087, "decisive": false,
                                 "concentration_passed": false, "accepted": false}
    }
  }
}
```

## Reading

- The only axis with enough closed outcomes to decide (7d) says larger
  revisions do **not** help at the 5d horizon; they hurt by -1.15 pp.
- The 30d axis (just unblocked) points the same direction at 5d
  (-0.87 pp) but cannot be called decisive on this single-window sample.
- The 7d 10d flip (+1.40 pp) is not strong evidence: 10d low bucket has
  only 6 closed observations, and the sign disagrees with 5d. AGENTS.md
  Section 12 treats single-window sign flips as a rejection signal, not
  a discovery.

This is the third consecutive rejection of the
`docs/alpha_direction_expectation_residual_leadership.md` main line at
the 5d primary horizon: residual leadership (027), PEAD window (028),
and now revision magnitude (this experiment). The expectation-revision
direction does not produce a clean 5d edge on the current
single-earnings-season watchlist.

## Next evidence needed

- Wait for the watchlist to accumulate more than one earnings season.
  The recurring 5d-negative / 10d-positive flip across multiple
  sub-hypotheses suggests any edge (if real) plays out slowly and needs
  a larger 10d sample to confirm; the current 10d buckets are too thin.
- The magnitude axes themselves are now populated (7d 100% on primary
  positive, 30d 80.85%). Future retries do not need a measurement repair
  here — they need more rows.
- A different discriminator worth measuring with the same protocol:
  revision *direction agreement* across the 7d and 30d axes (a row
  where both 7d and 30d revised up may be cleaner than 7d-up-only),
  once the 30d sample is deeper.

## Files touched

- `quant/experiments/exp_20260529_007_revision_magnitude_high_vs_low_bucket_attribution_7d_and_30d_axes.py` (new)
- `quant/test_exp_20260529_007_revision_magnitude_attribution.py` (new, 10 tests)
- `data/experiments/exp-20260529-007/revision_magnitude_high_vs_low_bucket_attribution_7d_and_30d_axes.json` (new)
- `experiments/artifacts/exp-20260529-007_revision_magnitude_high_vs_low_bucket_attribution_7d_and_30d_axes.md` (this file)
- `experiments/logs/exp-20260529-007.json` (new)
- `experiments/tickets/exp-20260529-007.json` (status updated)
- `docs/experiment_log.jsonl`, `docs/experiment_registry.json`

No JavaScript was used.
