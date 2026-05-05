# SEC / earnings / filing shock no-new-evidence audit

Experiment: `exp-20260504-027`  
Decision: `data_gap`  
Run mode: duplicate guardrail data audit, no production change.

## Hypothesis

SEC filing shock, financial surprise, 8-K event type, and post-earnings drift may improve C-strategy grading or A/B event confirmation. This run only checks whether new PIT-safe SEC/earnings evidence exists after `exp-20260504-026`.

## Historical check

Same-family work is already extensive:

- `exp-20260504-021`: SEC/earnings filing-shock availability audit.
- `exp-20260504-022`: residual other-filing mild-negative branch was shadow-positive but slot-weak.
- `exp-20260504-023`: residual semantic decomposition remained sample-limited.
- `exp-20260504-024` and `exp-20260504-025`: no new closed PIT evidence after the residual branch work.
- `exp-20260504-026`: leadership-change negative-reaction default-off sleeve was rejected at portfolio replay level.

Mechanism guardrail: do not repeat raw positive results-8K reaction gates, nearby SEC reaction threshold sweeps, Companyfacts score weights, keyword phrase-list tuning, or leadership-change sleeve promotion. A valid retry needs new forward replacement-value evidence, same-accession/same-day PIT XBRL, analyst revisions, or frozen LLM semantic grading packets.

## Coverage table

| Source | Coverage | PIT status | Blocker |
| --- | ---: | --- | --- |
| Current SEC feed in `data/news_20260503.json` | 300 SEC items, 284 ticker-mapped | PIT current observation | No closed 5/10/20/60d outcomes after `exp-20260504-026` |
| Historical SEC submissions | 1286 rows, all with accepted-at proxy | Public EDGAR accepted-at proxy | Not proof historical production observed each filing |
| SEC Companyfacts selected fields | 17109 rows, 51 mapped CIKs | Filed-date proxy | Sparse same-accession event linkage |
| SEC Item 2.02 filing text | 306 rows, 48 tickers, 12024232 chars | Public filing text replay context | Needs semantic grading before ranking |
| Latest earnings snapshot | 48 rows, 41 with EPS estimate and surprise history | Production snapshot on 2026-05-03 | Older fixed windows remain snapshot-limited |
| Existing shadow event table | 300 rows, 284 ticker-mapped | Current shadow table only | 296 unclear/missing tags, 4 negative filing-shock tags |

## Field audit

`quant/feature_layer.py` and `quant/data_layer.py` currently expose earnings fields for `days_to_earnings`, `next_earnings_date`, `eps_estimate`, `avg_historical_surprise_pct`, `positive_surprise_history`, and `earnings_event_window`.

Missing joined fields for this hypothesis: `revenue_surprise`, `gross_margin_delta`, `fcf_to_net_income_gap`, `inventory_growth`, `receivables_growth`, `guidance_raise_cut`, and same-accession XBRL/event linkage. `data/non_ohlcv/sec_filing_schema.md` already documents the shadow schema and keeps it out of production.

## Baseline metrics

No production or replay behavior changed.

| Window | EV | Return | PnL | Sharpe daily | Max DD | Win rate | Trades | Signals generated/survived |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | 3.4191 | 78.60% | 78600.33 | 4.35 | 5.41% | 78.95% | 19 | 51 / 41 |
| mid_weak | 1.4415 | 55.02% | 55015.08 | 2.62 | 8.79% | 52.38% | 21 | 53 / 42 |
| old_thin | 0.3179 | 24.64% | 24642.07 | 1.29 | 8.05% | 40.91% | 22 | 60 / 55 |

Latest `data/backtest_results_20260504.json` late_strong benchmark spread: strategy vs SPY +73.19 pp, strategy vs QQQ +72.80 pp.

## Shadow / replay metrics

No new candidate set was generated. Re-running the same SEC reaction, keyword, Companyfacts, or hard-coded item-code logic would repeat already-recorded experiments.

Most recent same-family replay, `exp-20260504-026`, tested `leadership_change + negative_excess_le_minus_2pct` as a fixed-notional default-off sleeve:

| Metric | Value |
| --- | ---: |
| Primary candidates | 23 |
| Sleeve trades | 11 |
| Sleeve PnL | 1285.15 |
| Sleeve return | 1.2852% |
| Sleeve Sharpe daily | 0.3208 |
| Sleeve EV | 0.004122 |
| Sleeve max drawdown | 2.50% |
| Sleeve win rate | 63.64% |
| Window failure | old_thin PnL -458.06, win rate 33.33% |

Prior tagged branch references:

| Tag / branch | Candidates | Forward return | Slot value | Interpretation |
| --- | ---: | --- | --- | --- |
| Positive filing shock proxy | 21 | 10d excess -1.828 pp | slot proxy -9.8719 pp | Rejected as C-strategy revival |
| SEC text negative reaction | 16 | 10d net excess +4.7408 pp | active-slot proxy +0.9943 pp | Shadow candidate, not promoted |
| Residual other-filing mild-negative | 22 | 10d excess +2.5478 pp, 20d +2.5426 pp | 2 replacement samples, avg -9.7802 pp | Shadow-positive, slot-weak |
| Leadership-change negative reaction sleeve | 23 raw / 11 traded | sleeve EV 0.004122 | replacement proxy avg -4.2395 pp across broader event conflicts | Rejected at sleeve gate |

## Candidate overlap and slot value

New candidate count: 0. New overlap with existing signals: 0. New scarce-slot opportunity cost: not measured because there is no new PIT-safe evidence.

The latest same-family slot evidence remains negative or inconclusive. `exp-20260504-026` saw 132 same-day core conflicts across the broader evaluated SEC event set, 122 valid replacement proxies, average 10d replacement proxy -4.2395 pp, and replacement win rate 33.61%. That is not enough for a slot tie-breaker or production ranking rule.

## Decision

`data_gap`: existing SEC/earnings data is useful for frozen packet research, but this run adds no production candidate and no default-on ranking/filtering rule. Expected-value delta is 0.0 in all windows.

## Next minimal action

Do not rerun this audit again until one of these exists:

- a persistent SEC queue ledger with new closed replacement-value outcomes, analogous to the Form 4 paper state;
- a frozen LLM/document semantic grading packet for existing filing text, with later realized outcomes;
- same-accession/same-day PIT XBRL or analyst-revision data that adds new information beyond price reaction, keywords, and stale Companyfacts context.
