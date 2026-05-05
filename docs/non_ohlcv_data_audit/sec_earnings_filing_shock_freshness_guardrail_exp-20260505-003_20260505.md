# SEC / Earnings / Filing Shock Freshness Guardrail (exp-20260505-003)

## Hypothesis

SEC filing shock and earnings surprise may improve C-strategy grading or A/B event confirmation only if fresh PIT-safe same-accession or forward paper evidence exists beyond the prior shadow table.

## Mechanism Family

`earnings_sec_filing_shock_event_confirmation_overlay`

## Single Causal Variable

Fresh PIT-safe SEC earnings filing-shock evidence availability after `exp-20260505-001`.

## Historical Check

This direction has already been tried repeatedly. The blocking record is `exp-20260505-001`, which reused the 300-row normalized shadow table and found zero positive filing-shock rows, four negative rows without closed outcomes, and all financial shock fields null. Earlier guardrails (`exp-20260504-040`, `exp-20260504-050`, `exp-20260504-054`) reached the same conclusion: do not retune SEC reaction thresholds, keyword lists, Companyfacts stale-background buckets, event notionals, capacity, or holding periods without new PIT evidence.

## Coverage Table

| Source | Coverage | PIT status | Usable now? |
|---|---:|---|---|
| SEC submissions | 1286 rows / 48 tickers | Accepted timestamp usable as EDGAR proxy; backfill does not prove daily local observation | Timestamp context only |
| SEC filing text | 306 rows / 48 tickers | Replay context after accepted_at; keyword/language tests already exhausted | Context only |
| Companyfacts selected | 17109 rows / 48 tickers | PIT-safe stale/background facts; too stale for same-accession event grading | Not for filing shock |
| Earnings snapshots | 138 files / 6081 rows | Available through earnings_snapshot_20260503.json; no 20260504 snapshot | Partial context |
| Existing filing-shock shadow table | 300 rows / 279 tickers | 300 PIT timestamp-safe rows; financial shock fields missing | Data gap |
| 20260504 daily non-OHLCV files | 0 relevant files | No quant/news/earnings snapshot for 20260504 | Not usable |

## Shadow Tagging

| Tag | Rows | Forward 5d | Forward 10d | Forward 20d | Forward 60d |
|---|---:|---:|---:|---:|---:|
| A no recent filing event | 0 | n/a | n/a | n/a | n/a |
| B positive filing shock | 0 | n/a | n/a | n/a | n/a |
| C negative filing shock | 4 | n/a | n/a | n/a | n/a |
| D unclear / missing data | 296 | n/a | n/a | n/a | n/a |

Forward returns are not computed because current rows do not have closed forward paper outcomes or complete shock fields. Reporting nulls is intentional; filling them from non-PIT data would bias the audit.

## Candidate Overlap And Slot Value

Current persisted daily core candidates: `0` from `data/quant_signals_20260503.json`. Current same-day SEC queue candidates: `0`. Existing normalized shadow table overlap with production/pilot universe rows: `1`. Scarce-slot opportunity cost is not computable without current candidates or closed SEC/event-bundle paper outcomes.

## Baseline Metrics

No production or replay logic changed. Canonical fixed-window metrics remain the accepted baseline:

| Window | EV | Return | Sharpe daily | Max DD | Win rate | Trades | Generated | Survived | Survival | vs SPY | vs QQQ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 0.786 | 4.35 | 0.0541 | 0.7895 | 19 | 51 | 41 | 0.8039 | 0.7319 | 0.728 |
| mid_weak | 1.4415 | 0.5502 | 2.62 | 0.0879 | 0.5238 | 21 | 53 | 42 | 0.7925 | 0.2958 | 0.2151 |
| old_thin | 0.3179 | 0.2464 | 1.29 | 0.0805 | 0.4091 | 22 | 60 | 55 | 0.9167 | 0.3137 | 0.3213 |

`data/backtest_results_20260504.json` is a baseline refresh, not new SEC evidence.

## Decision

`data_gap`. Do not move this to default-off replay or production candidate status yet.

## Next Minimal Action

Run the daily production pipeline long enough to produce event-bundle/SEC paper states and closed outcomes, or add PIT same-accession XBRL/analyst revision/structured LLM filing-grade rows. Only then rerun filing-shock tagging against frozen same-day A/B alternatives.
