# SEC / Earnings / Filing Shock Audit - exp-20260504-029

## Hypothesis

SEC filing shock, financial surprise, 8-K event type, and post-earnings drift may improve `earnings_event_long` grading or act as an event-confirmation overlay for `trend_long` / `breakout_long`.

This run did not test a new signal. It only checked whether fresh PIT-safe evidence exists after `exp-20260504-027`.

## Scope

- Mechanism family: `earnings_sec_filing_shock_event_confirmation_overlay`
- Single causal variable: fresh PIT-safe SEC / earnings / filing-shock evidence since `exp-20260504-027`
- Run type: data audit / duplicate guardrail
- Production change allowed: no
- Production impact: no orders, ranking, sizing, signal generation, or adapters changed
- Existing schema reused: `data/non_ohlcv/sec_filing_schema.md`
- Existing shadow table reused: `data/non_ohlcv/sec_filing_shadow_events_20260503.json`

## Historical Check

| Experiment | Finding |
|---|---|
| `exp-20260504-002` | Positive results-8K reaction did not revive C strategy; slot proxy was negative. |
| `exp-20260504-004` | Simple Companyfacts financial-quality scoring was not stable. |
| `exp-20260504-007` | Filing text became replayable, but positive keyword language was not alpha. |
| `exp-20260504-008` to `exp-20260504-012` | Negative filing language plus negative reaction became default-off queue-ready, not production-ready. |
| `exp-20260504-014` | Latest-prior Companyfacts was stale for 8-K earnings-reaction grading. |
| `exp-20260504-015` to `exp-20260504-018` | Leadership-change negative reaction was shadow-promising but replacement value was weak. |
| `exp-20260504-019` | Agreement/debt packet rejected. |
| `exp-20260504-021`, `025`, `027` | Data audits found no production-ready filing-shock evidence. |
| `exp-20260504-026` | Leadership-change sleeve failed portfolio-level promotion. |

Mechanism guardrail: do not rerun reaction threshold sweeps, Companyfacts checklists, keyword phrase lists, or same-sample leadership sleeves. A valid retry needs new forward replacement-value evidence, same-accession/same-day PIT XBRL, analyst revisions, or frozen LLM semantic grading.

## Coverage

| Source | Coverage | PIT status | Current blocker |
|---|---:|---|---|
| Current SEC/news feed `data/news_20260503.json` | 300 SEC items, 284 ticker-mapped | Current observed PIT feed | No closed 5/10/20/60d outcomes after `exp-20260504-027` |
| SEC submissions backfill | 1,286 rows; 969 8-K, 199 10-Q, 88 10-K plus amendments | Public EDGAR `accepted_at` proxy | Not proof historical production observed each filing |
| SEC Companyfacts selected facts | 17,109 rows, 51 tickers with CIK | Filed-date public proxy | Same-accession event linkage remains sparse |
| SEC filing text packets | 306 Item 2.02 8-K accessions, 12,024,232 chars | Public filing text replay context | Useful for LLM packets, not standalone production evidence |
| Earnings snapshots | 138 snapshots, 6,081 ticker rows, 5,239 EPS estimate rows | Production snapshots from 2025-10-23 forward | Older fixed windows remain snapshot-limited |
| Shadow event table | 300 rows, 284 ticker-mapped | Current observed shadow table | 296 unclear/missing, 4 negative filing shock |

## Field Status

Available now: `ticker`, `event_date`, `usable_trade_date`, `form_type`, `accepted_datetime`, `eight_k_item_type`, `data_source`, PIT proxy flag, earnings `eps_estimate`, and historical surprise from snapshots.

Partial or missing for this hypothesis: `revenue_surprise`, `gross_margin_delta`, `fcf_to_net_income_gap`, `inventory_growth`, `receivables_growth`, `guidance_raise_cut`, same-accession XBRL event links, and a complete three-window pre-entry candidate dump for exact no-recent-filing tagging.

`quant/backtester.py` now discloses earnings snapshot coverage through `earnings_event_long_data_quality`; the old "eps_estimate always None" interpretation is no longer accurate when snapshots exist.

## Baseline Metrics

| Window | EV | Return | PnL | Sharpe daily | Max DD | Win rate | Trades | Signals survived | Survival | vs SPY | vs QQQ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 78.60% | 78,600.33 | 4.35 | 5.41% | 78.95% | 19 | 41/51 | 80.39% | 73.19% | 72.80% |
| mid_weak | 1.4415 | 55.02% | 55,015.08 | 2.62 | 8.79% | 52.38% | 21 | 42/53 | 79.25% | 29.58% | 21.51% |
| old_thin | 0.3179 | 24.64% | 24,642.07 | 1.29 | 8.05% | 40.91% | 22 | 55/60 | 91.67% | 31.36% | 32.13% |

Expected value score delta: 0.0 in all windows because this was data audit only.

## Shadow / Slot Metrics

No new candidate set was generated in this run. Reusing same-sample candidates would repeat rejected work.

| Tag family | Candidate count | Forward evidence | Slot evidence | Decision |
|---|---:|---|---|---|
| Positive filing shock proxy | 21 | 5d -1.1756%, 10d -1.8280%, 20d +1.3323% excess | 10d replacement proxy -9.8719 pp | Rejected |
| SEC text negative reaction | 16 | 10d net excess +4.7408% | Active-slot proxy +0.9943 pp | Default-off / not promoted |
| Residual other-filing mild negative | 22 | 5d -0.7680%, 10d +2.5478%, 20d +2.5426% excess; no 60d sample | Only two valid replacement samples, both negative | Shadow-only |
| Leadership negative reaction sleeve | 23 primary candidates, 11 sleeve trades | Sleeve EV 0.004122, Sharpe daily 0.3208 | Portfolio-level replay rejected | Rejected |

Candidate overlap and scarce-slot value for new data: not measured, because there is no new PIT-safe evidence after `exp-20260504-027`.

## Decision

Decision: `data_gap`.

The repo already has useful SEC and earnings artifacts, but no new PIT-safe evidence or closed forward replacement-value outcomes exist after `exp-20260504-027`. Do not promote this into production and do not rerun same-sample reaction, keyword, Companyfacts, item-code, or leadership-sleeve variants.

## Next Minimum Action

Create a default-off SEC paper/outcome ledger analogous to `data/form4_event_sleeve_paper_state.json`, then let forward replacement-value samples close. The other valid next branch is a frozen LLM semantic grader over existing filing-text packets, measured against later realized replacement value.
