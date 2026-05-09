# SEC / Earnings / Filing Shock Fresh Audit - exp-20260509-002

## Decision

`data_gap`. Fresh 2026-05-07 and 2026-05-08 SEC archives are present and timestamped, but they still do not contain the directional numeric or structured surprise fields required for a filing-shock C-strategy grading harness or A/B event-confirmation overlay. No production path changed.

## Protocol

| Field | Value |
|---|---|
| mechanism_family | SEC / earnings / filing shock event-quality overlay |
| single_causal_variable | fresh SEC filing-shock field availability on 2026-05-07 and 2026-05-08 |
| mode | data audit plus fresh shadow event table |
| production_impact | replay_only=true; no signal, sizing, ranking, order, run, backtester, risk, or portfolio change |
| mechanism insight check | Avoids raw filing recency, C-sleeve re-enable, and OHLCV threshold retest no-repeat zones |

## Historical Check

| Experiment | Result to preserve |
|---|---|
| exp-20260507-004 | Full candidate filing-shock tags produced 138 rows, zero B/C directional rows, and negative scarce-slot value for filing presence. |
| exp-20260507-006 | Full candidate persistence exists; directional same-accession/companyfacts or PIT consensus fields remain the blocker. |
| exp-20260507-011 | Simple earnings_event_long re-enable regressed all windows; C needs richer event-quality data. |
| exp-20260508-002 | Fresh 2026-05-06 audit remained data_gap due missing numeric shock fields and immature forward returns. |

## Coverage Table

| Trade date | SEC events | SEC text | SEC features | Current-day usable feature rows | Event rows | Earnings rows | EPS estimate rows | Missing accepted/usable | PIT note |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 2026-05-07 | 82 | 51 | 51 | 6 | 9 | 48 | 41 | 0 | SEC accepted/usable complete; earnings not consensus truth |
| 2026-05-08 | 82 | 49 | 49 | 11 | 9 | 51 | 44 | 0 | SEC accepted/usable complete; earnings not consensus truth |

## Directional Field Availability

| Trade date | SEC feature rows | EPS surprise | Revenue surprise | Gross margin delta | FCF/net income gap | Inventory growth | Receivables growth | Guidance raise/cut | Fiscal period end |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-05-07 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2026-05-08 | 11 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Fresh Shadow Event Table Summary

- Shadow rows written: `21` to `data/non_ohlcv/sec_earnings_filing_shock_shadow_events_exp-20260509-002.json`.
- SEC filing-feature rows: `17`; earnings semantic rows: `4`.
- Filing shock tag counts: `{'D_unclear_or_missing_data': 21}`.
- Numeric directional filing-shock rows: `0`.
- Fresh forward returns: not mature for 5/10/20/60 trading-day windows.

## Carried-Forward Shadow Metrics

| Tag | Candidates | 5d avg % | 10d avg % | 20d avg % | 60d avg % |
|---|---:|---:|---:|---:|---:|
| A_no_recent_filing_event | 67 | 0.4767 | 1.731 | 2.845 | 0.977 |
| B_positive_filing_shock | 0 | None | None | None | None |
| C_negative_filing_shock | 0 | None | None | None | None |
| D_unclear_or_missing_data | 71 | 0.8224 | 1.0909 | 2.8629 | 11.2336 |

## Candidate Overlap And Slot Value

- Fresh 2026-05-07/08 production `quant_signals` contain zero current core signals, so fresh overlap and slot-conflict value are not measurable yet.
- Historical carried-forward candidate_count is `138`; selected_by_entry_plan rows `113`; selected_with_recent_filing `57`.
- Historical scarce-slot comparable count is `16`; 20d slot delta avg `-2.2776%`, median `-1.8267%`, win rate `43.75%`.

## Baseline Metrics

| Scope | EV | Return % | PnL | Sharpe daily | Max DD % | Win % | Trades | Signals | Survival % | vs SPY pp | vs QQQ pp |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| latest baseline file | 0.3583 | 27.35 | 27347.42 | 1.31 | 9.03 | 40.91 | 22 | 60/55 | 91.67 | 34.07 | 34.84 |
| late_strong carried baseline | 3.7435 | 83.56 | 83562.53 | 4.48 | 5.39 | 78.95 | 19 | 51/41 | 80.39 | 78.15 | 77.77 |
| mid_weak carried baseline | 1.5478 | 57.54 | 57542.74 | 2.69 | 8.79 | 52.38 | 21 | 53/42 | 79.25 | 32.1 | 24.04 |
| old_thin carried baseline | 0.3359 | 26.24 | 26242.68 | 1.28 | 9.05 | 40.91 | 22 | 60/55 | 91.67 | 32.97 | 33.73 |

## Conclusion

The data source is useful for continued shadow logging, not for default-off replay promotion. The gap is not SEC timestamp coverage; it is directional field coverage and outcome maturity. The next valid experiment needs same-accession XBRL/companyfacts values, PIT consensus/guidance data, or closed forward outcomes for fresh semantic rows.
