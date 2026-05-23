# exp-20260523-012 Entry-Day Ranking / Canonical Vector Validation

Decision: `accepted_measurement_repair_no_strategy_change`.

This is measurement repair, not a strategy promotion. It validates whether the new cross-sectional ranking and canonical state-vector surfaces can be reconstructed point-in-time for historical core trades.

## Trial Accounting

- trial_family: `canonical_state_vector_ranking_validation`
- changed_variable: `entry_day_ranking_vector_attribution_surface`
- prior_trial_count: `0`
- multiple_testing_risk_bucket: `minimal`
- new_evidence_type: `entry_day_pit_canonical_vector_coverage`

## Three-Window Coverage

| Window | Trades | PIT-safe | Alpha score coverage | Policy research ready |
|---|---:|---:|---:|:---:|
| late_strong | 18 | 18 | 18 | yes |
| mid_weak | 21 | 21 | 21 | yes |
| old_thin | 22 | 22 | 22 | yes |

Aggregate coverage: `61 / 61` point-in-time safe trades.

## Main Readout

The continuous `alpha_score` does not yet discriminate much inside already-filled core trades: 56 of 61 trades were in the entry-day top decile and the remaining 5 were in the top quartile.

The more useful candidate signal is `leadership_vector.state`:

| Bucket | Trades | Total PnL | Avg PnL |
|---|---:|---:|---:|
| strong | 9 | $47,744.41 | $5,304.93 |
| neutral | 52 | $187,106.58 | $3,598.20 |

By window, `strong` was positive in all three windows, but only had 2 / 5 / 2 trades. This is enough to define the next alpha hypothesis, not enough to skip a proper Gate 1-4 strategy experiment.

## Production Impact

```text
production_impact:
  shared_policy_changed: false
  backtester_adapter_changed: false
  run_adapter_changed: false
  replay_only: true
  parity_test_added: false
```

`daily_context_archive` now includes `canonical_state_vectors`, but this remains passive context. No entries, exits, ranking, sizing, heat, LLM/news, watchlists, or orders changed.

## Next Alpha Hypothesis

Test a small post-sizing top-up only for already-selected core stock signals whose entry-day `leadership_vector.state == strong`, with no hot risk state. Use a dedicated shared-policy experiment before any production behavior changes.

No JavaScript was used.
