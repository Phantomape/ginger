# Form 4 Insider Overlay Audit

- experiment_id: `exp-20260511-035`
- generated_at: `2026-05-11T17:29:00+00:00`
- mechanism_family: `insider_form4_open_market_purchase_confirmation_overlay`
- run_mode: `data_audit_shadow_only_overlay_refresh`
- production_impact: no signal, ranking, sizing, order, run, or backtester path changed

## Hypothesis

Public-market insider Form 4 buying, especially large CEO/CFO or clustered open-market purchases, may confirm existing trend_long/breakout_long candidates; this run only checks the latest local PIT-safe data and shadow overlap without changing production.

## Latest Data Coverage

- source: `data/non_ohlcv/form4_transactions_20260510.jsonl`
- date_range: `2026-04-30 -> 2026-05-10`
- rows: `887`
- PIT-safe rows: `887` / `887`
- tickers mapped/requested: `51` / `52`
- CIK mapping gaps: `SNXX`
- open-market purchase transactions: `1`
- meaningful >=$50k event-days: `1`
- forward-queue >=$500k candidates: `0`

## Fresh Shadow Overlay

- production core tagged: `0`
- pilot tagged: `0`
- default-off state-surface scored tagged: `1`
- scarce-slot value: `No fresh >=$500k Form 4 forward-queue candidate and no production-core signal overlap; only the default-off CAT state-surface scored row is tagged.`
- forward 10/20/60/90d: `No fresh production-tagged candidate and no mature 10/20/60/90d outcome for the one default-off CAT state-surface tag as of this run.`

## Baseline Metrics

| Window | EV | Return | PnL | Sharpe | Max DD | Win rate | Trades | Generated | Survived | Survival | vs SPY | vs QQQ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2340 | 0.9409 | $94,086.91 | 4.50 | 0.0548 | 0.7895 | 19 | 51 | 41 | 0.8039 | 0.8868 | 0.8829 |
| mid_weak | 1.6689 | 0.6181 | $61,813.40 | 2.70 | 0.0941 | 0.5238 | 21 | 53 | 42 | 0.7925 | 0.3637 | 0.2830 |
| old_thin | 0.3853 | 0.2854 | $28,544.11 | 1.35 | 0.0815 | 0.4091 | 22 | 60 | 55 | 0.9167 | 0.3526 | 0.3603 |

## Historical Shadow Reference

Historical returns below are carried forward from prior artifacts and are not new evidence in this run.

| Cohort | Horizon | Count | Avg return | Win rate | Avg excess vs SPY | Excess win rate |
|---|---:|---:|---:|---:|---:|---:|
| meaningful_purchase_v1 | 10d | 27 | 4.7094% | 0.7407 | 2.8283% | 0.7037 |
| meaningful_purchase_v1 | 20d | 26 | 6.0838% | 0.6538 | 3.5670% | 0.6538 |
| meaningful_purchase_v1 | 60d | 20 | 17.8977% | 0.6500 | 14.4326% | 0.6000 |
| meaningful_purchase_v1 | 90d | 17 | 24.5834% | 0.7059 | 17.8828% | 0.6471 |

## Decision

`shadow_only`. The latest snapshot adds no production-core overlap, no >=$500k forward-queue candidate, no closed paper outcome, and no measurable slot-conflict value.
