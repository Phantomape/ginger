# SEC Current-Candidate Filing-Shock Tag Audit - exp-20260504-037

## Decision

Decision: `data_gap`.

This was an observe-only data audit. It did not change production signals, ranking, sizing, exits, risk, LLM prompts, SEC thresholds, or OHLCV logic.

## Hypothesis

Current persisted Ginger candidates may be taggable with SEC / earnings / filing-shock context. If tags overlap real candidates and later show positive replacement value, they could support C-strategy event grading or A/B event confirmation.

## Historical Experiment Check

| Family | Prior finding |
|---|---|
| Positive results 8-K reaction | `exp-20260504-002` rejected it as C-strategy revival evidence; slot proxy was negative. |
| Companyfacts context | `exp-20260504-004` / `014` found stale or non-monotonic grading value. |
| SEC filing text negative reaction | `exp-20260504-007` to `012` made it default-off queue-ready, not production-ready. |
| Leadership-change negative reaction | `exp-20260504-015` / `018` / `026` was shadow-promising but sleeve/replacement evidence was weak or rejected. |
| Agreement/debt packet | `exp-20260504-019` rejected it across windows. |
| Repeated same-family audits | `exp-20260504-021`, `024`, `025`, `027`, `029`, `032`, `033`, `035` found no new production-ready evidence or closed replacement outcomes. |

Mechanism guardrail: do not rerun SEC reaction thresholds, keyword phrase lists, Companyfacts checklists, item-code splits, leadership sleeves, or queue-promotion debates on the same sample.

## Scope

- non-OHLCV data source: SEC shadow filing table, SEC filing-text default-off queue, current SEC/news feed, and production earnings snapshot.
- mechanism family: `earnings_sec_filing_shock_event_confirmation_overlay`
- single causal variable: current persisted candidate overlap with PIT-proxy SEC filing shock rows
- run type: data audit / current-candidate shadow tagging
- production change allowed: no
- production impact: `data_audit_only_no_production_change`

## Coverage Table

| Source | Coverage | PIT status | Main blocker |
|---|---:|---|---|
| Current quant signal snapshot | 0 signal rows; 0 before entry filters; 0 after entry plan | Persisted production output for 2026-05-03 | Zero current candidates to tag |
| SEC shadow event table | 300 rows; 284 ticker-mapped; 1 production/pilot universe overlaps | Row-level accepted timestamp proxy | Fundamental shock fields mostly missing |
| SEC default-off queue | 0 current candidates; 0 same-day rows evaluated | Shared observe-only policy, disabled | No same-day queue candidates or closed outcomes |
| Current SEC/news feed | 300 SEC items; 284 ticker-mapped | Current observed feed only | No closed 5/10/20/60d outcomes |
| Earnings snapshot | 48 persisted tickers; 41 EPS estimates; 41 surprise histories | Production snapshot | No revenue/guidance/same-accession XBRL fields |

## Field Missingness

| Field | Non-null rows | Coverage |
|---|---:|---:|
| `eps_surprise` | 0 / 300 | 0.00% |
| `revenue_surprise` | 0 / 300 | 0.00% |
| `gross_margin_delta` | 0 / 300 | 0.00% |
| `fcf_to_net_income_gap` | 0 / 300 | 0.00% |
| `inventory_growth` | 0 / 300 | 0.00% |
| `receivables_growth` | 0 / 300 | 0.00% |
| `guidance_raise_cut` | 0 / 300 | 0.00% |
| `fiscal_period_end` | 0 / 300 | 0.00% |

## Current Candidate Tagging

| Tag | Current candidate count | Forward 5d | Forward 10d | Forward 20d | Forward 60d |
|---|---:|---|---|---|---|
| A. no recent filing event | 0 | n/a | n/a | n/a | n/a |
| B. positive filing shock | 0 | n/a | n/a | n/a | n/a |
| C. negative filing shock | 0 | n/a | n/a | n/a | n/a |
| D. unclear / missing data | 0 | n/a | n/a | n/a | n/a |

The persisted 2026-05-03 production signal list has zero new-trade candidates, so forward returns and slot value are not measurable in this run. The SEC shadow table has 1 production/pilot universe overlap row, but it is context-only, not a candidate.

## Universe Context Overlap

| Ticker | Event date | Usable trade date | Form | Filing-shock tag | Reason |
|---|---|---|---|---|---|
| TSLA | 2026-04-30 | 2026-05-01 | 10-K | unclear / missing data | statement_without_xbrl_metric_parse |

## Baseline Metrics

No production or replay behavior changed; expected-value delta is `0.0` in every window.

| Window | EV | Return | PnL | Sharpe daily | Max DD | Win rate | Trades | Signals generated/survived | Survival | vs SPY | vs QQQ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 78.60% | 78,600.33 | 4.35 | 5.41% | 78.95% | 19 | 51 / 41 | 80.39% | 73.19% | 72.80% |
| mid_weak | 1.4415 | 55.02% | 55,015.08 | 2.62 | 8.79% | 52.38% | 21 | 53 / 42 | 79.25% | 29.58% | 21.51% |
| old_thin | 0.3179 | 24.64% | 24,642.07 | 1.29 | 8.05% | 40.91% | 22 | 60 / 55 | 91.67% | 31.36% | 32.13% |

## Candidate Overlap And Slot Value

- candidate_count: `0`
- overlap_with_existing_signals: `0`
- current SEC queue candidate_count: `0`
- scarce-slot opportunity cost: `not_measured`
- reason: no current candidates, no SEC queue candidates, zero available production slots, and no closed forward outcomes for same-day alternatives.

## Data Gap

Available now: `ticker`, `event_date`, `usable_trade_date`, `form_type`, `accepted_datetime`, `eight_k_item_type`, `data_source`, `pit_safe`, current earnings `eps_estimate`, and historical surprise snapshot fields.

Still missing or incomplete: `revenue_surprise`, `gross_margin_delta`, `fcf_to_net_income_gap`, `inventory_growth`, `receivables_growth`, `guidance_raise_cut`, same-accession/same-day XBRL event links, and persistent SEC queue replacement-value ledger outcomes.

`quant/backtester.py` already discloses earnings snapshot coverage through `earnings_event_long_data_quality`; the current blocker is not "earnings has no snapshots", but that filing-shock fields and closed replacement-value outcomes are still absent.

## Next Minimum Action

Add or reuse a persistent SEC queue paper/outcome ledger that freezes same-day A/B/cash alternatives, then wait for closed outcomes before another production-promotion or replacement-value test. A valid alternate next step is a frozen LLM semantic grading packet over filing text, measured only after realized outcomes exist.
