# Form 4 Insider Overlay Fresh Audit

- experiment_id: `exp-20260509-018`
- generated_at: `2026-05-09T17:23:01+00:00`
- decision: `shadow_only`
- production_impact: `shadow_data_audit_only_no_production_change`
- source: `SEC EDGAR Form 4 transaction-level XML`

## Hypothesis

Public-market insider buying may confirm existing trend_long/breakout_long candidates, especially CEO/CFO buying, clusters, and post-drawdown purchases. This run audits fresh as-of data only; it does not change production signals or retune prior Form 4 thresholds.

## Historical Guardrail

Prior Form 4 work found positive standalone forward returns but sparse A/B overlap and weak slot replacement evidence. `exp-20260508-028` rejected cluster-buying promotion because only 3 event trades were selected and single-ticker positive contribution exceeded the guard. This run is not a cluster-window, owner-role, or purchase-value retry.

## Current Data Coverage

- transaction file: `data/non_ohlcv/form4_transactions_20260508.jsonl`
- date range: `2026-04-28 -> 2026-05-08`
- rows_written: `1004`
- PIT-safe rows: `1004`
- open-market purchase transactions: `4`
- raw open-market event-days: `2`
- base meaningful >=$50k events: `1`
- forward queue >=$500k candidates: `0`
- missing CIK tickers: `SNXX`

## Fresh Raw Purchase Events

| Ticker | Usable date | Value | Owners | CEO/CFO | Forward queue |
|---|---:|---:|---:|---:|---:|
| TSM | 2026-04-30 | $7,760.00 | 1 | False | False |
| CAT | 2026-05-06 | $219,210.00 | 1 | False | False |

## Shadow Metrics

Fresh as-of 2026-05-08 produced no >=$500k forward queue candidate, so current candidate_count, overlap_with_existing_signals, forward returns, and scarce-slot value are all zero or not measurable.

Historical reference, not new evidence:

- historical meaningful purchase event-days: `40`
- meaningful 10d avg return / excess vs SPY: `4.7094%` / `2.8283%`
- accepted-trade overlap <=20d: `0` trades
- accepted-trade overlap <=60d: `2` trades, avg net PnL `7.9319%`
- top-skipped oracle overlap <=120d: `0` candidates
- slot replacement comparisons: `2`; avg vs accepted avg SPY excess `-2.194575%`

## PIT And Schema Risks

- `accepted_at` is the normalized EDGAR filing timestamp; there is no literal `filing_datetime` alias.
- `10b5_1_flag`, `option_exercise_flag`, `open_market_purchase_flag`, role flags, transaction value, and `usable_trade_date` are available.
- `insider_buy_value_to_market_cap` is blocked until a PIT market-cap join exists.
- `first_purchase_3y` is not PIT-safe from the current archive window alone.

## Decision

`shadow_only`: keep collecting Form 4 paper snapshots. Do not promote, do not retune thresholds, and do not add production overlay logic from this run.
