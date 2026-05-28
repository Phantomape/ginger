# exp-20260528-027 PEAD Window x Residual Leadership Bucket Attribution

Decision: `rejected_no_residual_pead_edge`.

Read-only `alpha_discovery`. First true PEAD bucket comparison enabled by
the `exp-20260527-908` measurement repair (`last_earnings_date` PIT join).
Tests the alpha hypothesis from
`docs/alpha_direction_expectation_residual_leadership.md`: that positive
expectation revision rows inside the T+2..T+15 PEAD window outperform
when accompanied by residual leadership.

The 5d primary horizon shows residual leadership actively **hurts** PEAD
continuation in this window (avg return -2.0% for residual eligible vs
+1.6% for non-residual eligible; lift = **-3.6 pp**, win rate lift =
**-19.6 pp**). The 10d horizon shows the opposite sign with a small +0.7
pp lift, but only 4 closed non-residual observations (below the
published `min_bucket_closed_10d=5` floor).

Per AGENTS.md Section 12 ("If feature looks plausible but attribution is
unstable, monotonicity does not exist, or it only works in a single
window -> reject"), the hypothesis is rejected at the 5d horizon. This
does not modify entries, exits, ranking, sizing, LLM/news inputs, paper
sleeves, or live orders.

## Buckets observed

| Bucket | Rows | 5d closed | 5d avg ret | 5d win | 10d closed | 10d avg ret | 10d win |
|---|---|---|---|---|---|---|---|
| `residual_eligible` | 7 | 7 | **-2.03%** | 42.9% | 7 | +2.48% | 57.1% |
| `non_residual_eligible` | 8 | 8 | **+1.57%** | 62.5% | 4 | +1.80% | 50.0% |
| `all_eligible_pead` (1+2) | 15 | 15 | -0.11% | 53.3% | 11 | +2.23% | 54.5% |
| `outside_pead_primary_positive` | 25 | 14 | +0.52% | 57.1% | 2 | -6.55% | 0.0% |
| `blocked_missing_last_earnings_date` | 7 | 4 | -0.75% | 50.0% | 3 | +0.47% | 66.7% |
| `not_primary_7d_positive` | 653 | 514 | +0.15% | 52.3% | 378 | +1.11% | 57.4% |

## Three comparisons

### 1. residual_eligible vs non_residual_eligible (within PEAD)

| Horizon | Lift (avg ret) | Lift (win rate) | Bucket size pass | Concentration pass |
|---|---|---|---|---|
| 5d | **-3.60 pp** | **-19.6 pp** | False | False |
| 10d | +0.68 pp | +7.14 pp | False (non-res 4<5) | False |

The 5d signal is the primary test. Residual leadership goes the wrong
way by a meaningful margin given the bucket sizes; this is sufficient
to reject without invoking the 10d directional flip (which would
require a much larger sample to take seriously).

### 2. all_eligible_pead vs outside_pead_primary_positive (PEAD window effect)

| Horizon | Lift (avg ret) | Lift (win rate) | Bucket size pass | Concentration pass |
|---|---|---|---|---|
| 5d | -0.63 pp | -3.8 pp | True | False |
| 10d | +8.78 pp | +54.5 pp | False (outside 2<5) | False |

The PEAD window itself does not produce a 5d lift over primary positive
rows that are outside the T+2..T+15 window. The 10d positive lift is
driven by an outside bucket of only 2 closed observations, with one
heavy loser (-6.55% avg) — not a comparison that can be trusted.

### 3. all_eligible_pead vs not_primary_7d_positive (positive revision x PEAD vs baseline)

| Horizon | Lift (avg ret) | Lift (win rate) | Bucket size pass | Concentration pass |
|---|---|---|---|---|
| 5d | -0.26 pp | +1.0 pp | True | False |
| 10d | +1.12 pp | -2.9 pp | True | False |

Positive expectation revision combined with the PEAD window barely
beats the non-primary-positive baseline. At 5d the lift is -0.26 pp;
at 10d it is +1.12 pp with a negative win-rate lift. None of these is
the clean "top bucket > mid bucket > bottom bucket" monotonicity that
the playbook requires.

## Gate evaluation

```json
{
  "all_passed": false,
  "gate1": {"name": "baseline_buckets_populated", "passed": true,
            "residual_eligible_row_count": 7,
            "non_residual_eligible_row_count": 8},
  "gate2": {"name": "required_input_fields_present", "passed": true,
            "bucketed_total_rows": 700},
  "gate3": {"name": "survival_rate_not_affected_read_only_attribution",
            "passed": true},
  "gate4": {
    "name": "primary_residual_vs_non_residual_within_pead_window",
    "passed": false,
    "status": "rejected_no_residual_pead_edge",
    "primary_horizon": "5d",
    "primary_horizon_lift": -0.036,
    "residual_lift_floor": 0.01,
    "primary_horizon_bucket_size_passed": false,
    "primary_horizon_concentration_passed": false,
    "decision_rule": "If residual_eligible avg_return @ 5d minus non_residual_eligible avg_return @ 5d is negative -> rejected_no_residual_pead_edge."
  }
}
```

## Honest caveats

- Window: 2026-05-08 to 2026-05-26 (14 trading days). Single window;
  do not over-extrapolate.
- The 47 primary positive rows split into 15 PEAD-eligible (7 residual,
  8 non-residual) and 25 outside-window. Sample sizes are thin even on
  the unblocked data.
- 10d shows a directional flip vs 5d. With a residual eligible 10d
  sample of 7 and non-residual 10d sample of 4, neither side meets the
  published `min_bucket_closed_10d=5` floor jointly. The flip is
  consistent with PEAD continuation playing out slowly, but the sample
  cannot decide between "real but delayed edge" and "noise".

## Next evidence needed

- Accumulate more PEAD-eligible rows (multiple earnings seasons of
  watchlist data) before retrying. A second clean comparison after
  Q3/Q4 2026 reports would change the sample size to a level where the
  10d directional flip can actually be tested.
- The non-residual eligible bucket has a meaningfully positive 5d
  return (+1.57%, win 62.5%). The doc's "residual leadership is the
  key discriminator" framing is the part that just got rejected; a
  weaker "primary positive expectation revision + PEAD window" alone
  may still be worth measuring at scale.
- Add a control for sector/theme residual at the PEAD-eligible bucket
  level: the published 027-009/010 results suggested SPY/QQQ-only
  residuals are a weak proxy.

## Files touched

- `quant/experiments/exp_20260528_027_pead_window_residual_leadership_bucket_attribution_on_enriched_watchlist.py` (new)
- `quant/test_exp_20260528_027_pead_window_residual_bucket_attribution.py` (new, 10 tests)
- `data/experiments/exp-20260528-027/pead_window_residual_leadership_bucket_attribution_on_enriched_watchlist.json` (new)
- `experiments/artifacts/exp-20260528-027_pead_window_residual_leadership_bucket_attribution_on_enriched_watchlist.md` (this file)
- `experiments/logs/exp-20260528-027.json` (new)
- `experiments/tickets/exp-20260528-027.json` (status updated)
- `docs/experiment_log.jsonl`, `docs/experiment_registry.json`

No JavaScript was used.
