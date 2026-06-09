# exp-20260609-009: Companyfacts Shareholder-Yield + FCF Combo

- decision: `rejected_companyfacts_shareholder_yield_fcf_combo`
- aggregate EV: `7.8941` -> `9.1322` (+1.2381)
- aggregate PnL: `$234,850.99` -> `$263,758.34` (+28,907.35)
- target trades: `26`
- max single positive share: `0.950689`
- positive PnL HHI: `0.906241`
- failed gates: `all_windows_expected_value_improved, all_windows_pnl_improved, target_window_count_passed, concentration_guard_passed, accepted_low_liability_comparator_passed`
- accepted comparator failed checks: `aggregate_ev_not_above_accepted_exp017, aggregate_pnl_not_above_accepted_exp017, window_ev_regressed_vs_accepted_exp017, window_pnl_regressed_vs_accepted_exp017`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | target trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1628 | +0.0000 | $+0.00 | 0 |
| mid_weak | 2.1402 | 2.1951 | +0.0549 | $+850.72 | 2 |
| old_thin | 0.5911 | 1.7743 | +1.1832 | $+28,056.63 | 24 |

## Accepted Comparator

```json
{
  "aggregate_delta_after_vs_accepted_low_liability": {
    "expected_value_score_delta_sum": -7.3038,
    "max_drawdown_pct_delta_max": 0.0166,
    "total_pnl_delta_sum": -98236.8
  },
  "available": true,
  "by_window_delta_after_vs_accepted_low_liability": {
    "late_strong": {
      "expected_value_score_delta": -2.5177,
      "max_drawdown_pct_delta": 0.0098,
      "total_pnl_delta": -25684.45
    },
    "mid_weak": {
      "expected_value_score_delta": -3.876,
      "max_drawdown_pct_delta": 0.0208,
      "total_pnl_delta": -55058.47
    },
    "old_thin": {
      "expected_value_score_delta": -0.9101,
      "max_drawdown_pct_delta": -0.0062,
      "total_pnl_delta": -17493.88
    }
  },
  "current_after_aggregate": {
    "expected_value_score_sum": 9.1322,
    "max_drawdown_pct_max": 0.111,
    "total_pnl_sum": 263758.34
  },
  "reference_after_aggregate": {
    "expected_value_score_sum": 16.436,
    "max_drawdown_pct_max": 0.0944,
    "total_pnl_sum": 361995.14
  },
  "reference_experiment_id": "exp-20260528-017"
}
```

## Reflection

The intersection was too sparse to evaluate as a durable candidate-pool edge. Combining two individually interesting Companyfacts fields removed too many source rows.

This scout used only SEC Companyfacts rows filed on or before the signal date plus the source paper row's signal-day close. It made no live/default order, ranking, sizing, exit, LLM, news, watchlist, or shared adapter change.

## Top Positive Contributors

| ticker | trades | paper PnL | positive PnL share |
|---|---:|---:|---:|
| APP | 16 | $30,027.56 | 0.950689 |
| NFLX | 9 | $-100.04 | 0.049311 |
| META | 1 | $-1,020.17 | 0.0 |
