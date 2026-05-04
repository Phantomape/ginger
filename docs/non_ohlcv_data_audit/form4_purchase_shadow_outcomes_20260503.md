# Form 4 Purchase Shadow Outcomes

- experiment_id: `exp-20260503-046`
- generated_at: `2026-05-03T20:01:19+00:00`
- production_impact: `shadow_outcome_analysis_only`
- input: `data/non_ohlcv/form4_transactions_20241002_20260502.jsonl`
- output: `data/non_ohlcv/form4_purchase_shadow_outcomes_20241002_20260421.json`

## Coverage

- purchase event-days: `50`
- tickers: `20`
- events with at least one forward outcome: `34`

## Cohorts

### all_open_market_purchase

- event_count: `50`
- ticker_count: `20`
- total_purchase_value: `$1,082,903,941.25`

| Horizon | Count | Avg return | Median return | Win rate | Avg excess vs SPY | Excess win rate |
|---|---:|---:|---:|---:|---:|---:|
| 5d | 34 | 3.131% | 2.158% | 0.6765 | 1.967% | 0.6471 |
| 10d | 34 | 4.111% | 4.537% | 0.7353 | 2.537% | 0.7059 |
| 20d | 33 | 5.329% | 5.847% | 0.6061 | 3.369% | 0.697 |
| 60d | 26 | 17.34% | 15.68% | 0.6538 | 13.76% | 0.6154 |

### meaningful_purchase_v1

- event_count: `40`
- ticker_count: `16`
- total_purchase_value: `$1,078,500,547.52`

| Horizon | Count | Avg return | Median return | Win rate | Avg excess vs SPY | Excess win rate |
|---|---:|---:|---:|---:|---:|---:|
| 5d | 27 | 3.115% | 1.798% | 0.6667 | 1.965% | 0.6296 |
| 10d | 27 | 4.709% | 5.448% | 0.7407 | 2.828% | 0.7037 |
| 20d | 26 | 6.084% | 6.812% | 0.6538 | 3.567% | 0.6538 |
| 60d | 20 | 17.9% | 15.68% | 0.65 | 14.43% | 0.6 |

### ceo_cfo_purchase_v1

- event_count: `10`
- ticker_count: `7`
- total_purchase_value: `$1,036,993,466.70`

| Horizon | Count | Avg return | Median return | Win rate | Avg excess vs SPY | Excess win rate |
|---|---:|---:|---:|---:|---:|---:|
| 5d | 8 | 1.139% | 0.5243% | 0.625 | 1.016% | 0.625 |
| 10d | 8 | 3.727% | 3.568% | 0.75 | 3.032% | 0.75 |
| 20d | 7 | 1.098% | 2.065% | 0.5714 | -0.1846% | 0.5714 |
| 60d | 7 | 17.32% | 8.914% | 0.5714 | 13.44% | 0.5714 |

## Initial Read

This is shadow-only evidence. The result should be used to decide whether a
Form 4 confirmation overlay deserves a controlled multi-window backtest, not
to directly add entries or sizing rules.
