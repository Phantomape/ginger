# SEC / Earnings / Filing Shock Refreshed Audit - exp-20260510-002

## Decision

`data_gap`. The refreshed 2026-05-08 SEC files were newer than the prior exp-20260509-003 shadow table, but the refresh did not add any same-accession Companyfacts rows or directional filing-shock fields. No production path changed.

## Protocol

| Field | Value |
|---|---|
| hypothesis | Post-exp-20260509-003 refreshed SEC filing metadata/features may contain same-accession or directional filing-shock fields that can later grade earnings_event_long or confirm A/B candidates. |
| mechanism_family | SEC / earnings / filing shock event-quality overlay |
| single_causal_variable | post-exp-20260509-003 refreshed SEC filing-shock field availability |
| mode | data_audit_plus_refreshed_shadow_event_table |
| production_impact | replay_only=true; no signal, sizing, ranking, order, run, backtester, risk, or portfolio change |
| source refresh after prior shadow | sec_filing_events_20260508.jsonl, sec_filing_text_20260508.jsonl, sec_filing_features_20260508.jsonl |

## Historical Check

| Experiment | Result to preserve |
|---|---|
| exp-20260507-004 | Full candidate filing-shock tags produced 138 rows, zero B/C directional rows, and negative scarce-slot value for raw filing presence. |
| exp-20260507-006 | Full candidate persistence exists; directional same-accession/companyfacts or PIT consensus fields remain the blocker. |
| exp-20260507-011 | Simple earnings_event_long re-enable regressed all windows; C needs richer event-quality data. |
| exp-20260508-002 | Fresh 2026-05-06 audit remained data_gap due missing numeric shock fields and immature forward returns. |
| exp-20260509-003 | Fresh 2026-05-07/08 audit found all rows D_unclear_or_missing_data; this run only rechecked files refreshed after that shadow table. |

## Coverage Table

| Trade date | SEC events | SEC text | SEC features | Usable feature rows | Event rows | Earnings rows | EPS estimate rows | Same-accession rows | Missing accepted/usable | PIT note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-05-07 | 82 | 51 | 51 | 6 | 9 | 48 | 41 | 0 | 0 | SEC accepted_datetime/usable_trade_date present for usable rows; Companyfacts filed date remains a public-availability proxy. |
| 2026-05-08 | 84 | 50 | 50 | 11 | 11 | 58 | 51 | 0 | 0 | SEC accepted_datetime/usable_trade_date present for usable rows; Companyfacts filed date remains a public-availability proxy. |

## Directional Field Availability

| Trade date | Feature rows | EPS surprise | Revenue surprise | Gross margin delta | FCF/net income gap | Inventory growth | Receivables growth | Guidance raise/cut | Fiscal period end | Same-accession facts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-05-07 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2026-05-08 | 11 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Fresh Shadow Event Table Summary

- Shadow rows written: `21` to `data/non_ohlcv/sec_earnings_filing_shock_shadow_events_exp-20260510-002.json`.
- SEC filing-feature rows on usable trade dates: `17`.
- Earnings semantic rows: `4`.
- Filing shock tag counts: `{'D_unclear_or_missing_data': 21}`.
- Numeric directional filing-shock rows: `0`.
- Same-accession feature rows: `0`.
- Missing fresh trade-date files: `['2026-05-09', '2026-05-10']`.
- Fresh forward returns: not mature for 5/10/20/60 trading-day windows.

## Carried-Forward Tagged Candidate Forward Returns

| Tag | Candidates | 5d avg % | 10d avg % | 20d avg % | 60d avg % |
| --- | --- | --- | --- | --- | --- |
| A_no_recent_filing_event | 67 | 0.4767 | 1.731 | 2.845 | 0.977 |
| B_positive_filing_shock | 0 | None | None | None | None |
| C_negative_filing_shock | 0 | None | None | None | None |
| D_unclear_or_missing_data | 71 | 0.8224 | 1.0909 | 2.8629 | 11.2336 |

## Candidate Overlap And Slot Value

- Fresh 2026-05-07/08 production `quant_signals` contain zero current core signals, so fresh overlap and slot-conflict value remain not measurable.
- Historical carried-forward candidate_count is `138`; selected_by_entry_plan rows `113`; selected_with_recent_filing `57`.
- Historical scarce-slot opportunity cost: `{'avg_20d_delta_pct': -2.2776, 'comparable_count': 16, 'median_20d_delta_pct': -1.8267, 'win_rate_pct': 43.75}`.

## Baseline Metrics

| Scope | EV | Return % | PnL | Sharpe daily | Max DD % | Win % | Trades | Signals | Survival % | vs SPY pp | vs QQQ pp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| latest baseline file | 4.0674 | 90.79 | 90788.88 | 4.48 | 5.39 | 78.95 | 19 | 51/41 | 80.39 | 85.38 | 84.99 |
| mid_weak carried baseline | 1.6195 | 59.54 | 59540.63 | 2.72 | 8.79 | 52.38 | 21 | 53/42 | 79.25 | not_rerun_this_audit | not_rerun_this_audit |
| old_thin latest file | 0.3583 | 27.35 | 27347.42 | 1.31 | 9.03 | 40.91 | 22 | 60/55 | 91.67 | 34.07 | 34.84 |

## PIT Status

SEC `accepted_datetime` and `usable_trade_date` are complete for usable rows and are the only tradable-date fields used here. `period_end_date` / fiscal period end is not used as an entry date. Companyfacts filed-date joins remain public-availability proxies, and this refresh produced zero same-accession rows.

## Conclusion

The refreshed source confirms the bottleneck: not SEC timestamp coverage, but directional event-quality coverage. The source is useful for continued shadow logging, not for default-off replay promotion. The next minimum action is an accession-level join audit explaining why `sec_companyfacts_selected_20241002_20260505.jsonl` yields zero same-accession rows for refreshed 2026-05-08 filings, or ingestion of PIT consensus/guidance fields.
