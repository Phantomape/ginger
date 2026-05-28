# exp-20260528-012 Fundamental Growth + RS Gross-Margin Expansion

Decision: `rejected_fundamental_growth_rs_gross_margin_expansion`.

Single variable: require current PIT same-quarter gross margin to be non-declining year over year inside the operating-profit Companyfacts + OHLCV-RS default-off paper source.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Retained candidates | Filtered candidates | Tickers |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.4586 | +0.2958 | $117,072.92 | $123,215.48 | $+6,142.56 | +0.0000 | 76 | 145 | 115 | 5 |
| mid_weak | 2.1402 | 4.7252 | +2.5850 | $78,110.11 | $116,961.90 | $+38,851.79 | -0.0242 | 96 | 202 | 197 | 4 |
| old_thin | 0.5911 | 1.3806 | +0.7895 | $39,667.96 | $61,086.06 | $+21,418.10 | -0.0003 | 59 | 81 | 278 | 5 |

## Aggregate

- EV delta: `3.6703` (`0.464942`)
- PnL delta: `$66412.45` (`0.282785`)
- target trades: `231`
- max drawdown drift: `0.0`
- max single positive share: `0.414207`
- positive PnL HHI: `0.275585`

## Gross-Margin Quality Audit

```json
{
  "late_strong": {
    "filtered_candidates": 115,
    "filtered_ticker_counts": {
      "AMZN": 5,
      "APP": 19,
      "GOOG": 50,
      "RTX": 41
    },
    "filtered_unique_tickers": 4,
    "gross_margin_status_counts": {
      "missing_current_gross_profit": 115,
      "ok": 145
    },
    "input_candidates": 260,
    "retained_candidates": 145,
    "retained_days": 87,
    "retained_ticker_counts": {
      "AMD": 25,
      "AVGO": 24,
      "CRDO": 19,
      "MU": 71,
      "PLTR": 6
    },
    "retained_unique_tickers": 5,
    "rule_version": "fundamental_growth_rs_gross_margin_expansion_quality_v1"
  },
  "mid_weak": {
    "filtered_candidates": 197,
    "filtered_ticker_counts": {
      "APP": 41,
      "COIN": 21,
      "META": 1,
      "NFLX": 24,
      "NVDA": 34,
      "PLTR": 76
    },
    "filtered_unique_tickers": 6,
    "gross_margin_status_counts": {
      "gross_margin_declined": 110,
      "missing_current_gross_profit": 87,
      "ok": 202
    },
    "input_candidates": 399,
    "retained_candidates": 202,
    "retained_days": 102,
    "retained_ticker_counts": {
      "AMD": 22,
      "AVGO": 75,
      "CRDO": 66,
      "MU": 39
    },
    "retained_unique_tickers": 4,
    "rule_version": "fundamental_growth_rs_gross_margin_expansion_quality_v1"
  },
  "old_thin": {
    "filtered_candidates": 278,
    "filtered_ticker_counts": {
      "APP": 69,
      "AVGO": 28,
      "COIN": 21,
      "DDOG": 13,
      "META": 13,
      "NFLX": 59,
      "PLTR": 52,
      "RTX": 21,
      "TRIP": 2
    },
    "filtered_unique_tickers": 9,
    "gross_margin_status_counts": {
      "gross_margin_declined": 93,
      "missing_current_gross_profit": 185,
      "ok": 81
    },
    "input_candidates": 359,
    "retained_candidates": 81,
    "retained_days": 59,
    "retained_ticker_counts": {
      "ISRG": 10,
      "MU": 3,
      "NOW": 27,
      "NVDA": 21,
      "PLTR": 20
    },
    "retained_unique_tickers": 5,
    "rule_version": "fundamental_growth_rs_gross_margin_expansion_quality_v1"
  }
}
```

## Accepted Governor Audit

```json
{
  "late_strong": {
    "daily_top1_filtered": 41,
    "filtered_candidates": 69,
    "final_closed_pnl": 6142.56,
    "global_closed_drawdown_trigger_usd": 7500.0,
    "global_drawdown_scalar": 0.25,
    "global_drawdown_scaled": 10,
    "input_candidates": 145,
    "max_closed_drawdown_seen_usd": 9747.3,
    "missing_trade_filtered": 26,
    "rule_version": "operating_profit_quality_closed_ledger_governor_v1",
    "same_ticker_core_overlap_filtered": 2,
    "scaled_ticker_counts": {
      "MU": 33
    },
    "selected_ticker_counts": {
      "AMD": 4,
      "AVGO": 3,
      "CRDO": 4,
      "MU": 64,
      "PLTR": 1
    },
    "selected_trades": 76,
    "selected_unique_tickers": 5,
    "ticker_closed_profit_cap_usd": 9000.0,
    "ticker_profit_cap_scalar": 0.05,
    "ticker_profit_cap_scaled": 33
  },
  "mid_weak": {
    "daily_top1_filtered": 96,
    "filtered_candidates": 106,
    "final_closed_pnl": 38851.79,
    "global_closed_drawdown_trigger_usd": 7500.0,
    "global_drawdown_scalar": 0.25,
    "input_candidates": 202,
    "max_closed_drawdown_seen_usd": 3422.58,
    "missing_trade_filtered": 9,
    "rule_version": "operating_profit_quality_closed_ledger_governor_v1",
    "same_ticker_core_overlap_filtered": 1,
    "scaled_ticker_counts": {
      "CRDO": 34
    },
    "selected_ticker_counts": {
      "AMD": 15,
      "AVGO": 15,
      "CRDO": 46,
      "MU": 20
    },
    "selected_trades": 96,
    "selected_unique_tickers": 4,
    "ticker_closed_profit_cap_usd": 9000.0,
    "ticker_profit_cap_scalar": 0.05,
    "ticker_profit_cap_scaled": 34
  },
  "old_thin": {
    "daily_top1_filtered": 21,
    "filtered_candidates": 22,
    "final_closed_pnl": 21418.1,
    "global_closed_drawdown_trigger_usd": 7500.0,
    "global_drawdown_scalar": 0.25,
    "input_candidates": 81,
    "max_closed_drawdown_seen_usd": 11482.87,
    "rule_version": "operating_profit_quality_closed_ledger_governor_v1",
    "same_ticker_core_overlap_filtered": 1,
    "scaled_ticker_counts": {},
    "selected_ticker_counts": {
      "ISRG": 7,
      "MU": 3,
      "NOW": 24,
      "NVDA": 6,
      "PLTR": 19
    },
    "selected_trades": 59,
    "selected_unique_tickers": 5,
    "ticker_closed_profit_cap_usd": 9000.0,
    "ticker_profit_cap_scalar": 0.05
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "core_gate4_passed": false,
  "current_accepted_stack_comparison_passed": false,
  "current_accepted_stack_failed_checks": [
    "aggregate_ev_not_above_current_accepted_exp008",
    "aggregate_pnl_not_above_current_accepted_exp008",
    "window_ev_regressed_vs_current_accepted_exp008",
    "window_pnl_regressed_vs_current_accepted_exp008"
  ],
  "max_drawdown_worse": 0.0,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.414207,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.275585,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 231,
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
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed. Positive retention would require shared adapter parity before promotion.

No JavaScript was used.
