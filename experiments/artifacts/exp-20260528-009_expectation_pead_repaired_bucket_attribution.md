# exp-20260528-009 Repaired PEAD Bucket Attribution

- Decision: `observed_only_data_gap`
- Status: `observed_only`
- Changed variable: `repaired_pead_t2_t15_non_overextended_bucket_v1`
- Strategy behavior changed: `false`

## Gate Summary

- Gate 1: `True` observed-only against accepted core baseline.
- Gate 2: `True` source rows include ticker/as_of_date/PEAD fields/outcomes.
- Gate 3: `True` no filter or candidate-pool change.
- Gate 4: `False` observed-only attribution gate.

## Bucket Outcomes

| bucket | rows | 5d closed | 5d avg | 5d pnl | 10d closed | 10d avg | 10d pnl |
|---|---:|---:|---:|---:|---:|---:|---:|
| eligible_t2_t15_non_overextended | 8 | 8 | 0.015655 | 1252.440000 | 4 | 0.017990 | 719.620000 |
| eligible_t2_t15_residual_leader | 7 | 7 | -0.020333 | -1423.310000 | 7 | 0.024780 | 1734.570000 |
| primary_positive_outside_t2_t15 | 25 | 14 | 0.005162 | 722.640000 | 2 | -0.065458 | -1309.150000 |
| primary_positive_missing_last_earnings_date | 7 | 4 | -0.007495 | -299.800000 | 3 | 0.004737 | 142.120000 |
| primary_positive_other_pead_status | 0 | 0 |  |  | 0 |  |  |
| not_primary_7d_positive | 653 | 514 | 0.001460 | 7506.550000 | 378 | 0.011103 | 41970.720000 |

## Gate Details

- Data gaps: `[{"bucket": "eligible_t2_t15_non_overextended", "horizon": "10d", "closed_count": 4, "minimum": 8, "reason": "closed_outcomes_below_minimum"}, {"bucket": "primary_positive_outside_t2_t15", "horizon": "10d", "closed_count": 2, "minimum": 8, "reason": "closed_outcomes_below_minimum"}]`
- Directional pass if sufficient data: `False`
- Concentration flags: `['5d_top5_positive_pnl_concentration', '5d_single_ticker_positive_pnl_concentration', '10d_top5_positive_pnl_concentration', '10d_single_ticker_positive_pnl_concentration']`

## Interpretation

The repaired 5d sample is directionally encouraging for the non-overextended inside-PEAD bucket, but 10d closed outcome coverage remains below the minimum. This is a data-gap result, not a promotable trading rule.

## Related Files

- `quant/experiments/exp_20260528_009_expectation_pead_repaired_bucket_attribution.py`
- `data/experiments/exp-20260527-908/last_earnings_date_pit_join_into_expectation_revision_watchlist_row.json`
- `data/experiments/exp-20260528-009/expectation_pead_repaired_bucket_attribution.json`
- `experiments/artifacts/exp-20260528-009_expectation_pead_repaired_bucket_attribution.md`
- `experiments/logs/exp-20260528-009.json`
- `experiments/tickets/exp-20260528-009.json`
- `docs/experiments/tickets/exp-20260528-009.json`
- `docs/experiment_log.jsonl`
- `docs/experiment_registry.json`
