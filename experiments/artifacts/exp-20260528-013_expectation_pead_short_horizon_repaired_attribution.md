# exp-20260528-013 Repaired PEAD Short-Horizon Attribution

- Decision: `observed_only_no_promotable_edge`
- Status: `observed_only`
- Changed variable: `repaired_pead_t2_t15_non_overextended_short_horizon_bucket_v1`
- Strategy behavior changed: `false`

## Bucket Outcomes

| bucket | rows | 1d closed | 1d avg | 1d pnl | 2d closed | 2d avg | 2d pnl | 3d closed | 3d avg | 3d pnl |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| eligible_t2_t15_non_overextended | 8 | 8 | 0.004366 | 349.310000 | 8 | 0.008062 | 644.980000 | 8 | 0.015804 | 1264.290000 |
| eligible_t2_t15_residual_leader | 7 | 7 | -0.025940 | -1815.820000 | 7 | -0.032210 | -2254.680000 | 7 | -0.020333 | -1423.310000 |
| primary_positive_outside_t2_t15 | 25 | 25 | 0.014817 | 3704.200000 | 20 | 0.023987 | 4797.490000 | 14 | 0.004434 | 620.720000 |
| primary_positive_missing_last_earnings_date | 7 | 7 | -0.026462 | -1852.360000 | 6 | -0.032874 | -1972.460000 | 4 | -0.007495 | -299.800000 |
| primary_positive_other_pead_status | 0 | 0 |  |  | 0 |  |  | 0 |  |  |
| not_primary_7d_positive | 653 | 653 | 0.001997 | 13037.240000 | 608 | 0.004495 | 27332.010000 | 514 | 0.006348 | 32629.110000 |

## Gate Details

- Data gaps: `[]`
- Residual avoidance signal: `True`
- Inside-PEAD promotable signal: `False`
- Concentration flags: `['1d_top5_positive_pnl_concentration', '1d_single_ticker_positive_pnl_concentration', '2d_top5_positive_pnl_concentration', '2d_single_ticker_positive_pnl_concentration']`

## Interpretation

The short-horizon sample is mature enough to compare 1d/2d buckets. Non-overextended inside-PEAD rows beat residual leaders, but they do not beat outside-PEAD primary-positive rows, so this does not support an inside-PEAD short-horizon promotion.

## Related Files

- `quant/experiments/exp_20260528_013_expectation_pead_short_horizon_repaired_attribution.py`
- `data/experiments/exp-20260527-908/last_earnings_date_pit_join_into_expectation_revision_watchlist_row.json`
- `data/experiments/exp-20260528-013/expectation_pead_short_horizon_repaired_attribution.json`
- `experiments/artifacts/exp-20260528-013_expectation_pead_short_horizon_repaired_attribution.md`
- `experiments/logs/exp-20260528-013.json`
- `experiments/tickets/exp-20260528-013.json`
- `docs/experiments/tickets/exp-20260528-013.json`
- `docs/experiment_log.jsonl`
- `docs/experiment_registry.json`
