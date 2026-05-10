# Form 4 Insider Overlay Fresh Shadow Audit

- experiment_id: `exp-20260510-016`
- generated_at: `2026-05-10T17:28:21+00:00`
- mechanism_family: `insider_form4_open_market_purchase_confirmation_overlay`
- run_mode: `data_audit_shadow_only_overlay_refresh`
- production_impact: no signal, ranking, sizing, order, run, or backtester path changed

## Hypothesis

Meaningful public-market Form 4 open-market insider buying may confirm existing Ginger long candidates, but this run only refreshes data availability and shadow coverage. It does not create standalone entries and does not promote an overlay.

## Historical Check

Prior Form 4 experiments already tested availability, accepted-trade overlap, skipped-slot overlap, standalone sleeves, owner-role filters, sale-pressure de-risking, event queues, default-off event bundles, and cluster buying. The durable read is positive standalone purchase cohorts but sparse production overlap and insufficient slot-value evidence.

## Latest Data Coverage

- source: `data/non_ohlcv/form4_transactions_20260509.jsonl`
- date_range: `2026-04-29 -> 2026-05-09`
- rows: `995`
- PIT-safe rows: `995` / `995`
- tickers mapped/requested: `51` / `52`
- CIK mapping gaps: `SNXX`
- open-market purchase transactions: `4`
- meaningful >=$50k event-days: `1`
- forward-queue >=$500k candidates: `0`

## Fresh Overlay Read

- production core signals tagged: `0` / `0`
- pilot signals tagged: `0` / `1`
- default-off state-surface scored candidates tagged: `1` / `42`
- insider buy but no production signal: `CAT $219,210`
- scarce-slot opportunity cost: `not measurable`; no fresh >=$500k queue candidate or production slot conflict
- forward 10/20/60/90d return of fresh tagged candidates: `pending/unavailable`; no mature local outcome

## Baseline Metrics

| Window | EV | Return | PnL | Sharpe | Max DD | Win rate | Trades | Survival | vs SPY | vs QQQ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2340 | 0.9409 | $94,086.91 | 4.50 | 0.0548 | 0.7895 | 19 | 0.8039 | 0.8868 | 0.8829 |
| mid_weak | 1.6678 | 0.6177 | $61,768.95 | 2.70 | 0.0941 | 0.5238 | 21 | 0.7925 | 0.3633 | 0.2826 |
| old_thin | 0.3693 | 0.2819 | $28,185.10 | 1.31 | 0.0915 | 0.4091 | 22 | 0.9167 | 0.3491 | 0.3568 |

## Historical Shadow Reference

Historical purchase-return numbers below are carried forward/reference only, with 90d computed here from the existing event list where local OHLCV coverage allows it. They are not new production evidence.

| Horizon | Count | Avg return | Win rate | Avg excess vs SPY | Excess win rate |
|---|---:|---:|---:|---:|---:|
| 10d | 27 | 4.7094% | 0.7407 | 2.8283% | 0.7037 |
| 20d | 26 | 6.0838% | 0.6538 | 3.5670% | 0.6538 |
| 60d | 20 | 17.8977% | 0.6500 | 14.4326% | 0.6000 |
| 90d | 17 | 24.5834% | 0.7059 | 17.8828% | 0.6471 |

## Decision

`shadow_only`. The data exists and is PIT-dateable, but the latest refresh does not add a production-overlap or slot-conflict sample. Keep the existing default-off watch and wait for closed forward evidence before any default-off replay or production adapter.
