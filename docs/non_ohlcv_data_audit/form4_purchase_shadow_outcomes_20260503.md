# Form 4 Purchase Shadow Outcomes

- experiment_id: `exp-20260503-046`
- generated_at: `2026-05-03T19:58:42+00:00`
- production_impact: `shadow_outcome_analysis_only`
- input: `data/non_ohlcv/form4_transactions_20241002_20260502.jsonl`
- output: `data/non_ohlcv/form4_purchase_shadow_outcomes_20241002_20260421.json`

## Coverage

- purchase event-days: `58`
- tickers: `23`
- events with at least one forward outcome: `42`

## Cohorts

### all_open_market_purchase

- event_count: `58`
- ticker_count: `23`
- total_purchase_value: `$1,107,959,765.66`

| Horizon | Count | Avg return | Median return | Win rate | Avg excess vs SPY | Excess win rate |
|---|---:|---:|---:|---:|---:|---:|
| 5d | 42 | 2.717% | 2.158% | 0.6429 | 1.763% | 0.6429 |
| 10d | 42 | 3.893% | 4.324% | 0.7381 | 2.545% | 0.7143 |
| 20d | 40 | 6.094% | 6.512% | 0.625 | 4.479% | 0.7 |
| 60d | 32 | 22.62% | 22.78% | 0.7188 | 18.91% | 0.6875 |

### meaningful_purchase_v1

- event_count: `47`
- ticker_count: `20`
- total_purchase_value: `$1,103,509,599.41`

| Horizon | Count | Avg return | Median return | Win rate | Avg excess vs SPY | Excess win rate |
|---|---:|---:|---:|---:|---:|---:|
| 5d | 34 | 2.977% | 2.158% | 0.6471 | 2.004% | 0.6471 |
| 10d | 34 | 4.843% | 5.234% | 0.7647 | 3.168% | 0.7353 |
| 20d | 32 | 7.425% | 7.477% | 0.6875 | 5.166% | 0.6875 |
| 60d | 26 | 24.27% | 23.04% | 0.7308 | 20.62% | 0.6923 |

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
