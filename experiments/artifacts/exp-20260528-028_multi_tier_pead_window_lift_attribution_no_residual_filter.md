# exp-20260528-028 Multi-Tier PEAD Window Lift Attribution (no residual filter)

Decision: `rejected_no_pead_window_lift_across_tiers`.

Read-only `alpha_discovery`. Tests the weaker form of the
expectation-residual-PEAD hypothesis from
`docs/alpha_direction_expectation_residual_leadership.md`: after
`exp-20260528-027` rejected residual leadership as a PEAD discriminator,
does positive expectation revision **alone** (without requiring residual
leadership) produce a forward-return lift inside the T+2..T+15 PEAD
window?

To avoid the rejection resting on a single tier specification, the
experiment runs the same protocol across three independent positive
revision tiers already on the enriched watchlist:

| Tier | Rows | Source semantics |
|---|---|---|
| `primary_expectation_positive` | 47 | strictest; multi-evidence positive |
| `wide_watchlist_positive` | 61 | broader; prev-delta + 7d-delta |
| `scout_prev_positive` | 25 | prev-delta scout flag only |

For each tier we compute `pead_in` (tier=True, `last_earnings_date`
present, `pead_window=True`), `pead_out` (same tier flag,
`pead_window=False`), and `baseline_not_in_tier` (tier=False), then
two comparisons per tier at 5d and 10d.

Gate thresholds mirror `exp-20260527-005`'s published values; the
single causal variable is the PEAD-window flag inside each tier.

## 5d primary horizon — all three tiers show non-positive lift

| Tier | pead_in N | pead_in 5d avg | pead_out 5d avg | Lift | Size pass | Concentration pass |
|---|---|---|---|---|---|---|
| primary_expectation_positive | 15 closed | -0.11% | +0.52% | **-0.63 pp** | True | False |
| wide_watchlist_positive | 25 closed | -0.02% | +0.38% | **-0.40 pp** | True | True |
| scout_prev_positive | 13 closed | -0.08% | +0.86% | **-0.94 pp** | False | False |

`wide_watchlist_positive` is the cleanest comparison: 25 PEAD-in closed
observations meets the `min_bucket_closed_5d=8` floor by a wide margin,
and both concentration limits (`max_single_ticker_positive_share<=0.5`
and `max_top5_positive_share<=0.6`) pass. Its lift is -0.40 pp: the
PEAD window inside this tier does not improve 5d returns. The narrower
`primary_expectation_positive` tier and the prev-delta-only
`scout_prev_positive` tier are directionally consistent.

## Baseline (not in tier) comparisons

| Tier | pead_in 5d avg | baseline 5d avg | 5d lift | pead_in 10d avg | baseline 10d avg | 10d lift |
|---|---|---|---|---|---|---|
| primary_expectation_positive | -0.11% | +0.15% | **-0.26 pp** | +2.23% | +1.11% | +1.12 pp |
| wide_watchlist_positive | -0.02% | +0.11% | **-0.14 pp** | +1.49% | +1.15% | +0.35 pp |
| scout_prev_positive | -0.08% | +0.11% | **-0.19 pp** | +0.65% | +1.13% | **-0.48 pp** |

At 5d, every tier underperforms its own baseline by 0.14 to 0.26 pp.
At 10d, the primary tier shows a +1.12 pp lift over baseline, the wide
tier +0.35 pp, the scout tier flips negative at -0.48 pp. The scout
flip is informative: the directional inconsistency at 10d is exactly
the single-window instability that AGENTS.md Section 12 lists as a
rejection criterion.

## Why the 10d pead_in vs pead_out lifts look big but are not real

The 10d `pead_in_vs_pead_out` comparison shows lifts of +5.30 pp to
+8.78 pp across the three tiers. This is **not** evidence of a PEAD
effect:

| Tier | pead_in 10d closed | pead_out 10d closed | pead_out 10d avg |
|---|---|---|---|
| primary_expectation_positive | 11 | 2 | -6.55% |
| wide_watchlist_positive | 20 | 3 | -5.91% |
| scout_prev_positive | 11 | 1 | -4.65% |

The "comparison" buckets contain 1-3 closed observations each, all
strongly negative. The headline lift is a small-sample artifact of
choosing the wrong control group for the 10d horizon. The
`pead_in vs baseline_not_in_tier` comparison is the structurally
sound control and produces only +0.35 to +1.12 pp 10d lifts, with
the scout tier flipping negative.

## Gate evaluation

```json
{
  "all_passed": false,
  "gate1": {"name": "all_three_tiers_have_pead_in_rows", "passed": true,
            "row_counts": {"primary_expectation_positive": 15,
                           "wide_watchlist_positive": 25,
                           "scout_prev_positive": 13}},
  "gate2": {"name": "required_input_fields_present", "passed": true},
  "gate3": {"name": "survival_rate_not_affected_read_only_attribution",
            "passed": true},
  "gate4": {
    "name": "multi_tier_pead_window_lift",
    "passed": false,
    "status": "rejected_no_pead_window_lift_across_tiers",
    "primary_horizon": "5d",
    "lift_floor": 0.01,
    "per_tier_5d_diagnostic": {
      "primary_expectation_positive": {"lift": -0.0063, "accepted": false,
                                       "bucket_size_passed": true,
                                       "concentration_passed": false},
      "wide_watchlist_positive": {"lift": -0.0040, "accepted": false,
                                  "bucket_size_passed": true,
                                  "concentration_passed": true},
      "scout_prev_positive": {"lift": -0.0094, "accepted": false,
                              "bucket_size_passed": false,
                              "concentration_passed": false}
    }
  }
}
```

## Reading

- The cleanest single test (`wide_watchlist_positive`, 25 closed 5d
  observations, size + concentration ok) returns a -0.40 pp 5d lift.
  The "PEAD window has alpha among positive revision rows" hypothesis
  is rejected at the primary horizon by this comparison alone.
- All three tiers agree directionally: the residual filter from
  `exp-20260528-027` was not the only obstacle; the PEAD window itself
  does not provide a 5d edge in this measurement window.
- The 10d horizon shows directional inconsistency between tiers (scout
  flips). A future retry should wait until the watchlist has
  accumulated multiple earnings seasons so the 10d sample is large
  enough to decide between "no edge" and "edge that takes more than
  5d to play out".
- Independent of the PEAD framing, the `not_primary_7d_positive`
  baseline returns +0.15% at 5d and +1.11% at 10d, while every PEAD-in
  tier returns less or roughly equal at 5d. This is suggestive but not
  decisive evidence that the positive-revision-tier flags themselves
  do not separate forward returns in this window.

## Next evidence needed

- Wait for the watchlist to span at least one more earnings season,
  then re-run this protocol; the question is whether the 5d negative
  lift is window-specific or persistent.
- Independent of PEAD, the existing `eps_estimate_delta_30d` field is
  0% coverage (the same blocker that exp-20260527-002 hit). Filling
  that field would let a different alpha hypothesis -- magnitude of
  revision -- be tested without depending on the PEAD window.
- The doc's Hypothesis 3 (residual leadership measured against sector
  and theme, not just SPY/QQQ) remains untested because
  `ret20_excess_sector` and `ret20_excess_theme` coverage is still
  partial. Joining a full sector/theme residual layer onto the
  watchlist is the next high-leverage measurement repair.

## Files touched

- `quant/experiments/exp_20260528_028_multi_tier_pead_window_lift_attribution_no_residual_filter.py` (new)
- `quant/test_exp_20260528_028_multi_tier_pead_window_lift_attribution.py` (new, 8 tests)
- `data/experiments/exp-20260528-028/multi_tier_pead_window_lift_attribution_no_residual_filter.json` (new)
- `experiments/artifacts/exp-20260528-028_multi_tier_pead_window_lift_attribution_no_residual_filter.md` (this file)
- `experiments/logs/exp-20260528-028.json` (new)
- `experiments/tickets/exp-20260528-028.json` (status updated)
- `docs/experiment_log.jsonl`, `docs/experiment_registry.json`

No JavaScript was used.
