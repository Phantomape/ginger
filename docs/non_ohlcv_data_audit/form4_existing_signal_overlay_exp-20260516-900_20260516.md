# Form 4 Existing-Signal Overlay Shadow

- experiment_id: `exp-20260516-900`
- generated_at: `2026-05-16T17:21:14+00:00`
- mechanism_family: `insider_form4_open_market_purchase_confirmation_overlay`
- run_mode: `data_audit_shadow_only`
- production_impact: no signal, ranking, sizing, order, run, or backtest path changed

## Hypothesis

Public-market insider Form 4 buying, especially CEO/CFO large buys, cluster buying, first buys, and post-drawdown buys, may confirm existing trend_long/breakout_long candidates. This run only audits local PIT-safe availability and tags existing signal surfaces; it does not create entries.

## Data Availability / PIT

- source: `data/non_ohlcv/form4_transactions_20260515.jsonl`
- date_range: `2026-05-05 -> 2026-05-15`
- rows: `890`
- PIT-safe rows: `890`
- CIK mapping gap: `CORZ, GS, JPM, NVO, SNXX, TSM`
- open-market purchase transactions: `1`
- meaningful >=$50k event-days: `1`
- forward queue >=$500k candidates: `0`
- CIK mapping report: `docs/non_ohlcv_data_audit/form4_cik_mapping_exp-20260516-900_20260516.md`

## Baseline Metrics

| Window | EV | Return | PnL | Sharpe | Max DD | Win rate | Trades | Generated | Survived | Survival | vs SPY | vs QQQ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1344 | 1.1669 | $116,686.40 | 4.40 | 0.0665 | 0.7895 | 19 | 51 | 41 | 0.8039 | 1.1128 | 1.1089 |
| mid_weak | 2.1054 | 0.7656 | $76,563.68 | 2.75 | 0.1083 | 0.5238 | 21 | 53 | 42 | 0.7925 | 0.5112 | 0.4305 |
| old_thin | 0.5295 | 0.3729 | $37,292.45 | 1.42 | 0.1001 | 0.4091 | 22 | 60 | 52 | 0.8667 | 0.4401 | 0.4478 |

## Fresh Shadow Overlay

- production-core tagged candidates: `0`
- pilot tagged candidates: `0`
- default-off state-surface tagged candidates: `1`
- insider buy but no production signal: `0`
- scarce-slot value: `No fresh production-core Form 4 overlay hit and no trade-enabled Form 4 queue candidate; slot conflict value is not measurable this run.`
- forward returns: `Fresh overlay candidates do not have mature 10/20/60/90d outcomes, and there is no production-core tagged signal.`

## Historical Reference

These rows are carried forward from prior artifacts; they are not new acceptance evidence.

| Cohort | Horizon | Count | Avg return | Win rate | Avg excess vs SPY | Excess win rate |
|---|---:|---:|---:|---:|---:|---:|
| meaningful_purchase_v1 | 5d | 27 | 3.1152% | 0.6667 | 1.9654% | 0.6296 |
| meaningful_purchase_v1 | 10d | 27 | 4.7094% | 0.7407 | 2.8283% | 0.7037 |
| meaningful_purchase_v1 | 20d | 26 | 6.0838% | 0.6538 | 3.5670% | 0.6538 |
| meaningful_purchase_v1 | 60d | 20 | 17.8977% | 0.6500 | 14.4326% | 0.6000 |
| meaningful_purchase_v1 | 90d | 0 | n/a% | n/a | n/a% | n/a |

## Decision

`shadow_only`. Data is present and PIT-dateable, but the latest snapshot adds no production-core overlay hit, no mature tagged-candidate forward return, and no measurable scarce-slot value. Prior Form 4 promotion variants remain rejected for sample and materiality.

