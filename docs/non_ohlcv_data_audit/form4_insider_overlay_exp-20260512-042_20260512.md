# Form 4 Insider Overlay Refresh

- experiment_id: `exp-20260512-042`
- generated_at: `2026-05-12T17:28:46+00:00`
- mechanism_family: `insider_form4_open_market_purchase_confirmation_overlay`
- run_mode: `data_audit_shadow_only`
- production_impact: no production signal, ranking, sizing, order, run, or backtest path changed

## Hypothesis

Public-market insider Form 4 buying, especially CEO/CFO large buys, clustered buys, first buys, and post-drawdown buys, may confirm existing trend_long/breakout_long candidates. This run refreshes local PIT-safe availability and existing-signal shadow overlap only.

## Data Availability / PIT

- source: `data/non_ohlcv/form4_transactions_20260511.jsonl`
- date_range: `2026-05-01 -> 2026-05-11`
- rows: `882`
- PIT-safe rows: `882`
- CIK mapping gap: `SNXX`
- open-market purchase transactions: `30`
- meaningful >=$50k event-days: `1`
- forward queue >=$500k candidates: `0`

## Baseline Metrics

| Window | EV | Return | PnL | Sharpe | Max DD | Win rate | Trades | Generated | Survived | Survival | vs SPY | vs QQQ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2340 | 0.9409 | $94,086.91 | 4.50 | 0.0548 | 0.7895 | 19 | 51 | 41 | 0.8039 | 0.8868 | 0.8829 |
| mid_weak | 1.6689 | 0.6181 | $61,813.40 | 2.70 | 0.0941 | 0.5238 | 21 | 53 | 42 | 0.7925 | 0.3637 | 0.2830 |
| old_thin | 0.3853 | 0.2854 | $28,544.11 | 1.35 | 0.0815 | 0.4091 | 22 | 60 | 55 | 0.9167 | 0.3526 | 0.3603 |

## Fresh Shadow Overlay

- production-core tagged candidates: `0`
- pilot tagged candidates: `0`
- default-off state-surface tagged candidates: `1`
- scarce-slot value: `No fresh production-core Form 4 overlay hit and no trade-enabled Form 4 queue candidate; slot value is not measurable this run.`
- forward returns: `Fresh 2026-05-11 overlay candidates do not have mature 10/20/60/90d outcomes, and there is no production-core tagged signal.`

## Historical Reference

These rows are carried forward from prior artifacts; they are not new acceptance evidence.

| Cohort | Horizon | Count | Avg return | Win rate | Avg excess vs SPY | Excess win rate |
|---|---:|---:|---:|---:|---:|---:|
| meaningful_purchase_v1 | 5d | 0 | n/a% | n/a | n/a% | n/a |
| meaningful_purchase_v1 | 10d | 27 | 4.7094% | 0.7407 | 2.8283% | 0.7037 |
| meaningful_purchase_v1 | 20d | 26 | 6.0838% | 0.6538 | 3.5670% | 0.6538 |
| meaningful_purchase_v1 | 60d | 20 | 17.8977% | 0.6500 | 14.4326% | 0.6000 |
| meaningful_purchase_v1 | 90d | 17 | 24.5834% | 0.7059 | 17.8828% | 0.6471 |

## Decision

`shadow_only`. Data is present and PIT-dateable, but the latest snapshot has no production-core Form 4 overlay hit and no mature forward outcome. Keep collecting append-only paper evidence.
