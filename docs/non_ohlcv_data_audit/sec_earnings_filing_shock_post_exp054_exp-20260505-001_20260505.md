# SEC / earnings / filing shock freshness audit (exp-20260505-001)

## Decision

`data_gap`. No production signal path, candidate ranking, sizing, exit, SEC threshold, LLM prompt, or event-sleeve parameter changed.

## Hypothesis

SEC filing shock and earnings surprise may improve C-strategy grading or A/B event confirmation only if fresh PIT-safe evidence exists after `exp-20260504-054`.

## Mechanism family

`earnings_sec_filing_shock_event_confirmation_overlay`.

## Historical experiment check

Recent records already tested or blocked this family: `exp-20260504-027`, `exp-20260504-040`, `exp-20260504-046`, `exp-20260504-050`, `exp-20260504-052`, `exp-20260504-053`, `exp-20260504-054`, and `exp-20260504-055`.

The mechanism insight guardrail remains unchanged: do not rerun SEC reaction threshold sweeps, stale Companyfacts background buckets, filing keyword tuning, holding-period/notional/capacity sweeps, or direct event-bundle promotion without new forward or PIT evidence.

## Coverage table

| Source | Coverage | PIT status | Blocking gap |
|---|---:|---|---|
| SEC submissions backfill | 1,286 rows / 48 tickers | EDGAR accepted timestamp proxy | Backfill does not prove production observed every historical filing |
| SEC Companyfacts selected facts | 17,109 rows / 48 tickers | Filed-date proxy | Too stale/sparse for same-accession shock grading |
| SEC 8-K filing text | 306 rows / 48 tickers | Available after accepted timestamp | Useful for LLM packet input, not standalone evidence |
| Earnings snapshots | 138 files, 6,081 ticker rows | PIT production snapshots | Last file is `earnings_snapshot_20260503.json`; no `20260504` snapshot |
| Normalized filing-shock shadow table | 300 rows, 284 ticker-mapped | accepted_datetime + usable_trade_date proxy | financial shock fields remain null |
| SEC/event paper ledgers | 0 current files | Missing | no closed forward outcomes |

## Shadow tag table

Reused manifest: `data/non_ohlcv/sec_earnings_filing_shock_shadow_events_exp-20260505-001.json`.

| Tag | Rows | Forward 5d | Forward 10d | Forward 20d | Forward 60d |
|---|---:|---:|---:|---:|---:|
| A_no_recent_filing_event | 0 | n/a | n/a | n/a | n/a |
| B_positive_filing_shock | 0 | n/a | n/a | n/a | n/a |
| C_negative_filing_shock | 4 | blocked | blocked | blocked | blocked |
| D_unclear_missing_data | 296 | blocked | blocked | blocked | blocked |

Field non-null counts: `accepted_datetime=300`, `usable_trade_date=300`, `pit_safe=300`, `eight_k_item_type=100`; `eps_surprise`, `revenue_surprise`, `gross_margin_delta`, `fcf_to_net_income_gap`, `inventory_growth`, `receivables_growth`, and `guidance_raise_cut` are all `0`.

## Candidate overlap and slot value

Current trade candidates: `0`. Current overlap with existing live signals: `0`. Normalized shadow table overlap with production or pilot universe rows: `1`.

Scarce-slot opportunity cost is not computable because there are no current candidates, no SEC/event paper ledger state, and no closed forward outcomes. The latest useful slot-value context remains the replay-only event bundle from `exp-20260504-049`, which improved aggregate EV/PnL but is blocked from live promotion until forward paper evidence exists.

## Baseline metrics

| Window | EV | Return | PnL | Sharpe daily | Max DD | Win rate | Trades | Signals survived |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 78.60% | $78,600.33 | 4.35 | 5.41% | 78.95% | 19 | 41/51 |
| mid_weak | 1.4415 | 55.02% | $55,015.08 | 2.62 | 8.79% | 52.38% | 21 | 42/53 |
| old_thin | 0.3179 | 24.64% | $24,642.07 | 1.29 | 8.05% | 40.91% | 22 | 55/60 |

Expected-value delta: `0.0` in all windows by construction; this is a data audit only.

## Data gap classification

- Field gap: financial shock fields are absent from the normalized table.
- Coverage gap: no `20260504` daily news, quant_signals, or earnings snapshot files exist.
- PIT timestamp gap: accepted timestamps exist for shadow rows, but same-accession/same-day XBRL and analyst revision timestamps do not.
- Outcome gap: no SEC/event-bundle paper state or closed forward outcomes exist.

## Next smallest valid action

Run the daily production pipeline so event-bundle attribution can appear in `quant_signals`, then let the default-off SEC/event ledgers accumulate closed outcomes. A new filing-shock experiment should wait for closed paper replacement value, PIT same-accession XBRL, analyst revisions, or persisted LLM filing-text grades joined to outcomes.
