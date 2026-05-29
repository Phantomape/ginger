# exp-20260528-029 Outside-PEAD Deconcentration Attribution

- Decision: `observed_only_no_promotable_edge`
- Status: `observed_only`
- Changed variable: `outside_pead_primary_positive_short_horizon_deconcentration_v1`
- Strategy behavior changed: `false`

## Scenario Outcomes

| scenario | rows | tickers | 1d closed | 1d avg | 1d pnl | 2d closed | 2d avg | 2d pnl | 3d closed | 3d avg | 3d pnl |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| outside_all_rows | 25 | 9 | 25 | 0.014817 | 3704.200000 | 20 | 0.023987 | 4797.490000 | 14 | 0.004434 | 620.720000 |
| outside_ex_top_positive_ticker | 20 | 8 | 20 | -0.007022 | -1404.430000 | 16 | -0.006835 | -1093.630000 | 12 | -0.003224 | -386.900000 |
| outside_ticker_first_dedup | 9 | 9 | 9 | -0.006423 | -578.060000 | 7 | 0.002451 | 171.550000 | 5 | 0.006256 | 312.780000 |
| outside_ticker_first_dedup_ex_top | 8 | 8 | 8 | -0.013174 | -1053.920000 | 6 | -0.012254 | -735.230000 | 4 | -0.010879 | -435.140000 |
| inside_non_overextended_reference | 8 | 4 | 8 | 0.004366 | 349.310000 | 8 | 0.008062 | 644.980000 | 8 | 0.015804 | 1264.290000 |
| inside_residual_leader_reference | 7 | 5 | 7 | -0.025940 | -1815.820000 | 7 | -0.032210 | -2254.680000 | 7 | -0.020333 | -1423.310000 |

## Top Contributor

- Top ticker: `MU`
- Combined 1d/2d positive-PnL share: `0.861819`

## Gate Details

- Data gaps: `[]`
- Row-level positive: `True`
- Ex-top positive: `False`
- Dedup positive: `False`
- Dedup ex-top positive: `False`
- Concentration flags: `[{"horizon": "1d", "metric": "single_ticker_positive_pnl_share", "value": 0.8848349539450668, "maximum": 0.6}, {"horizon": "1d", "metric": "top5_positive_pnl_share", "value": 0.8848349539450668, "maximum": 0.8}, {"horizon": "2d", "metric": "single_ticker_positive_pnl_share", "value": 0.842808235346294, "maximum": 0.6}, {"horizon": "2d", "metric": "top5_positive_pnl_share", "value": 0.8739060955353962, "maximum": 0.8}]`

## Interpretation

The all-row outside-PEAD bucket remains positive at 1d/2d, but the edge is not deconcentrated. Removing the largest positive contributor or de-duplicating to first row per ticker breaks the 1d signal, so this is not promotion evidence for an outside-PEAD ranking or allocation rule.

## Related Files

- `quant/experiments/exp_20260528_029_expectation_outside_pead_deconcentration_attribution.py`
- `data/experiments/exp-20260527-908/last_earnings_date_pit_join_into_expectation_revision_watchlist_row.json`
- `data/experiments/exp-20260528-029/expectation_outside_pead_deconcentration_attribution.json`
- `experiments/artifacts/exp-20260528-029_expectation_outside_pead_deconcentration_attribution.md`
- `experiments/logs/exp-20260528-029.json`
- `experiments/tickets/exp-20260528-029.json`
- `docs/experiments/tickets/exp-20260528-029.json`
- `docs/experiment_log.jsonl`
- `docs/experiment_registry.json`
