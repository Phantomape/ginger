# exp-20260529-012 Cash-Conversion Closed-Ledger Governor

Decision: `rejected_cash_conversion_closed_ledger_governor`.

Single variable: apply the accepted closed-paper-ledger profit-cap and drawdown governor to the exp-20260528-006 cash-conversion Companyfacts+RS default-off paper sleeve.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Profit-cap scaled | DD scaled |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.1525 | -1.0103 | $117,072.92 | $108,424.75 | $-8,648.17 | +0.0033 | 100 | 3 | 34 |
| mid_weak | 2.1402 | 2.5735 | +0.4333 | $78,110.11 | $85,498.94 | $+7,388.83 | +0.0117 | 118 | 7 | 46 |
| old_thin | 0.5911 | 2.2907 | +1.6996 | $39,667.96 | $78,176.09 | $+38,508.13 | -0.0025 | 123 | 53 | 21 |

## Aggregate

- EV delta: `1.1226` (`0.142207`)
- PnL delta: `$37248.79` (`0.158606`)
- target trades: `341`
- max drawdown drift: `0.0117`
- max single positive share: `0.468467`
- positive PnL HHI: `0.357362`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_checks": [
    "window_ev_regression",
    "window_pnl_regression",
    "drawdown_drift_too_high",
    "target_concentration_failed"
  ],
  "max_drawdown_worse": 0.0117,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.468467,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.357362,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 341,
  "target_trade_count_min": 30,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 2,
  "windows_ev_regressed": 1,
  "windows_pnl_regressed": 1
}
```

## Governor Audit

```json
{
  "late_strong": {
    "daily_top1_filtered": 189,
    "filtered_candidates": 224,
    "final_closed_pnl": -8648.17,
    "global_closed_drawdown_trigger_usd": 7500.0,
    "global_drawdown_scalar": 0.25,
    "global_drawdown_scaled": 34,
    "input_candidates": 324,
    "max_closed_drawdown_seen_usd": 12775.76,
    "missing_trade_filtered": 31,
    "rule_version": "cash_conversion_closed_ledger_governor_v1",
    "same_ticker_core_overlap_filtered": 4,
    "scaled_ticker_counts": {
      "MU": 3
    },
    "selected_ticker_counts": {
      "AMD": 10,
      "APP": 5,
      "CRDO": 2,
      "GE": 2,
      "GOOG": 5,
      "LLY": 17,
      "MU": 54,
      "RTX": 5
    },
    "selected_trades": 100,
    "selected_unique_tickers": 8,
    "ticker_closed_profit_cap_usd": 9000.0,
    "ticker_profit_cap_scalar": 0.05,
    "ticker_profit_cap_scaled": 3
  },
  "mid_weak": {
    "both_scalars_applied": 5,
    "daily_top1_filtered": 285,
    "filtered_candidates": 309,
    "final_closed_pnl": 7388.83,
    "global_closed_drawdown_trigger_usd": 7500.0,
    "global_drawdown_scalar": 0.25,
    "global_drawdown_scaled": 46,
    "input_candidates": 427,
    "max_closed_drawdown_seen_usd": 10968.86,
    "missing_trade_filtered": 20,
    "rule_version": "cash_conversion_closed_ledger_governor_v1",
    "same_ticker_core_overlap_filtered": 4,
    "scaled_ticker_counts": {
      "PLTR": 7
    },
    "selected_ticker_counts": {
      "AMD": 21,
      "APP": 21,
      "AVGO": 5,
      "CRDO": 18,
      "DDOG": 1,
      "GE": 1,
      "MU": 20,
      "NFLX": 2,
      "PLTR": 29
    },
    "selected_trades": 118,
    "selected_unique_tickers": 9,
    "ticker_closed_profit_cap_usd": 9000.0,
    "ticker_profit_cap_scalar": 0.05,
    "ticker_profit_cap_scaled": 7
  },
  "old_thin": {
    "both_scalars_applied": 3,
    "daily_top1_filtered": 232,
    "filtered_candidates": 250,
    "final_closed_pnl": 38508.13,
    "global_closed_drawdown_trigger_usd": 7500.0,
    "global_drawdown_scalar": 0.25,
    "global_drawdown_scaled": 21,
    "input_candidates": 373,
    "max_closed_drawdown_seen_usd": 12222.82,
    "missing_trade_filtered": 13,
    "rule_version": "cash_conversion_closed_ledger_governor_v1",
    "same_ticker_core_overlap_filtered": 5,
    "scaled_ticker_counts": {
      "APP": 33,
      "PLTR": 20
    },
    "selected_ticker_counts": {
      "APP": 50,
      "AVGO": 13,
      "COIN": 1,
      "GE": 5,
      "ISRG": 2,
      "META": 3,
      "MU": 1,
      "NFLX": 6,
      "NOW": 3,
      "PLTR": 27,
      "RTX": 12
    },
    "selected_trades": 123,
    "selected_unique_tickers": 11,
    "ticker_closed_profit_cap_usd": 9000.0,
    "ticker_profit_cap_scalar": 0.05,
    "ticker_profit_cap_scaled": 53
  }
}
```

## Comparison With exp-20260528-006

```json
{
  "aggregate_delta_after_vs_ungoverned_cash_conversion_quality": {
    "expected_value_score_delta_sum": -3.0084,
    "max_drawdown_pct_delta_max": -0.0949,
    "total_pnl_delta_sum": -45599.6
  },
  "available": true,
  "by_window_delta_after_vs_ungoverned_cash_conversion_quality": {
    "late_strong": {
      "expected_value_score_delta": -1.263,
      "max_drawdown_pct_delta": 0.0054,
      "total_pnl_delta": -14379.71
    },
    "mid_weak": {
      "expected_value_score_delta": -1.3296,
      "max_drawdown_pct_delta": 0.0,
      "total_pnl_delta": -22922.69
    },
    "old_thin": {
      "expected_value_score_delta": -0.4158,
      "max_drawdown_pct_delta": -0.1209,
      "total_pnl_delta": -8297.2
    }
  },
  "reference_decision": "rejected_fundamental_growth_rs_cash_conversion_quality",
  "reference_experiment_id": "exp-20260528-006",
  "reference_gate4": {
    "aggregate_ev_delta_positive": true,
    "aggregate_pnl_delta_positive": true,
    "max_drawdown_worse": 0.1184,
    "max_drawdown_worse_guardrail": 0.005,
    "passed": false,
    "survival_guard_passed": true,
    "target_concentration": {
      "max_single_positive_pnl_share": 0.662732,
      "max_single_positive_pnl_share_guardrail": 0.4,
      "passed": false,
      "positive_pnl_hhi": 0.477423,
      "positive_pnl_hhi_guardrail": 0.3
    },
    "target_trade_count": 341,
    "target_trade_count_min": 30,
    "target_window_count_min": 3,
    "target_windows": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ],
    "windows_ev_improved": 3,
    "windows_ev_regressed": 0,
    "windows_pnl_regressed": 0
  }
}
```

## Production Impact

Experiment-only default-off paper evidence. No shared policy, run adapter, backtester adapter, production watchlist, live/default order path, core entry, ranking, sizing, or exit behavior changed. A production promotion would need this exact closed-ledger state and governor in a shared adapter plus parity tests.

No JavaScript was used.
