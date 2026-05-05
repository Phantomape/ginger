# SEC / Earnings / Filing Shock No-New-Evidence Audit - exp-20260504-038

## Hypothesis

SEC filing shock, financial surprise, 8-K event type, and post-earnings drift may improve `earnings_event_long` grading or act as an event-confirmation overlay for `trend_long` / `breakout_long`.

This run did not test a new signal. It checked whether fresh PIT-safe evidence exists after `exp-20260504-037`.

## Scope

- Mechanism family: `earnings_sec_filing_shock_event_confirmation_overlay`
- Single causal variable: fresh PIT-safe SEC / earnings / filing-shock evidence since `exp-20260504-037`
- Run type: data audit / duplicate guardrail
- Production change allowed: no
- Production impact: no orders, ranking, sizing, signal generation, adapters, prompts, or thresholds changed
- Existing schema reused: `data/non_ohlcv/sec_filing_schema.md`
- Existing shadow table reused: `data/non_ohlcv/sec_filing_shadow_events_20260503.json`

## Historical Check

| Experiment | Finding |
|---|---|
| `exp-20260504-002` | Positive results-8K reaction did not revive C strategy; slot proxy was negative. |
| `exp-20260504-004` / `014` | Simple Companyfacts quality/context scoring did not produce a stable event discriminator. |
| `exp-20260504-007` to `012` | Filing text and negative-reaction packets are default-off queue-ready, not production-ready. |
| `exp-20260504-015` / `018` / `026` | Leadership-change negative reaction was shadow-promising but rejected or slot-weak at sleeve gates. |
| `exp-20260504-019` | Agreement/debt packet rejected. |
| `exp-20260504-021`, `024`, `025`, `027`, `029`, `032`, `033`, `035` | Data audits found no production-ready filing-shock evidence or fresh closed outcomes. |
| `exp-20260504-037` | Current-candidate tagging found 0 current candidates, 0 SEC queue candidates, and 1 TSLA overlap row marked unclear/missing. |

Mechanism guardrail: do not rerun reaction threshold sweeps, Companyfacts checklists, keyword phrase lists, item-code splits, leadership sleeves, or queue-promotion debates on the same sample. A valid retry needs new forward replacement-value evidence, same-accession/same-day PIT XBRL, analyst revisions, or frozen LLM semantic grading packets with realized outcomes.

## Coverage Table

| Source | Coverage | PIT status | Current blocker |
|---|---:|---|---|
| Current SEC feed `data/news_20260503.json` | 300 SEC items, 284 ticker-mapped | Current observed PIT feed | No closed 5/10/20/60d outcomes after `exp-20260504-037` |
| Current earnings snapshot `data/earnings_snapshot_20260503.json` | 48 tickers, 41 EPS estimates, 41 surprise histories | Production snapshot | No revenue/guidance/same-accession XBRL fields |
| Current SEC shadow table | 300 rows, 284 ticker-mapped, 279 unique tickers | Forward shadow table | 296 unclear/missing tags, 4 negative filing-shock tags |
| Current quant signal snapshot | 0 signal rows | Persisted production output | Zero current candidates to tag |
| SEC default-off queue | 0 candidates, disabled | Shared observe-only policy | No same-day queue candidates or closed outcomes |
| SEC submissions backfill | 1286 rows | Public EDGAR accepted-at proxy | Not proof historical production observed each filing |
| SEC Companyfacts selected facts | 17109 rows | Filed-date proxy | Same-accession event linkage remains sparse |
| SEC filing text packets | 306 rows | Public filing text replay context | Useful for LLM packets, not standalone production evidence |

## Field Audit

Available now: `ticker`, `event_date`, `usable_trade_date`, `form_type`, `accepted_datetime`, `eight_k_item_type`, `data_source`, PIT proxy flag, earnings `eps_estimate`, and historical surprise from snapshots.

Partial or missing for this hypothesis: `revenue_surprise`, `gross_margin_delta`, `fcf_to_net_income_gap`, `inventory_growth`, `receivables_growth`, `guidance_raise_cut`, same-accession XBRL event links, a complete three-window pre-entry candidate dump for exact no-recent-filing tagging, and a persistent SEC queue paper/outcome ledger.

`quant/backtester.py` already discloses earnings snapshot coverage through `earnings_event_long_data_quality`; the blocker is no longer "earnings has no snapshots." The blocker is missing filing-shock fields plus missing closed replacement-value outcomes.

## Baseline Metrics

No production or replay behavior changed.

| Window | EV | Return | PnL | Sharpe daily | Max DD | Win rate | Trades | Signals generated/survived | Survival | vs SPY | vs QQQ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 78.60% | 78,600.33 | 4.35 | 5.41% | 78.95% | 19 | 51 / 41 | 80.39% | 73.19% | 72.80% |
| mid_weak | 1.4415 | 55.02% | 55,015.08 | 2.62 | 8.79% | 52.38% | 21 | 53 / 42 | 79.25% | 29.58% | 21.51% |
| old_thin | 0.3179 | 24.64% | 24,642.07 | 1.29 | 8.05% | 40.91% | 22 | 60 / 55 | 91.67% | 31.36% | 32.13% |

Expected value score delta: 0.0 in all windows because this was a data audit only.

## Shadow / Slot Metrics

No new candidate set was generated in this run. Reusing same-sample candidates would repeat rejected work.

| Tag family | Candidate count | Forward evidence | Slot evidence | Decision |
|---|---:|---|---|---|
| A. no recent filing event | n/a | Not measured | Not measured | Requires complete candidate dump |
| B. positive filing shock proxy | 21 | 5d -1.1756%, 10d -1.8280%, 20d +1.3323% excess | 10d replacement proxy -9.8719 pp | Rejected |
| C. SEC text negative reaction | 16 | 10d net excess +4.7408% | Active-slot proxy +0.9943 pp | Default-off / not promoted |
| C. leadership negative reaction | 23 | Shadow 10d excess +3.8135%; sleeve EV 0.004122 | Replacement evidence weak; sleeve rejected | Rejected |
| D. unclear / missing data | 296 | Not measured | Not measured | Data gap |

New candidate count: 0. New overlap with existing signals: 0. New scarce-slot opportunity cost: not measured because no new PIT-safe evidence exists.

## Decision

Decision: `data_gap`.

The repo already has useful SEC and earnings artifacts, but no new PIT-safe same-family evidence or closed forward replacement-value outcomes exist after `exp-20260504-037`. Do not promote this into production and do not rerun same-sample reaction, keyword, Companyfacts, item-code, queue-promotion, or leadership-sleeve variants.

## Next Minimum Action

Add or reuse a persistent SEC queue paper/outcome ledger analogous to the Form 4 paper state, then wait for closed outcomes before another replacement-value or production-promotion test.

A valid alternate next step is a frozen LLM/document semantic grading packet over filing text, measured only after realized outcomes exist. A data-vendor path would need PIT-safe same-accession/same-day XBRL or analyst revisions.
