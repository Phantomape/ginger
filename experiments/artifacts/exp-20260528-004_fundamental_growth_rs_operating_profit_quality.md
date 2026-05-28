# exp-20260528-004 Fundamental Growth + RS Operating-Profit Quality

Decision: `rejected_fundamental_growth_rs_operating_profit_quality`.

Single variable: require latest PIT quarterly operating income to be positive inside the exp-20260527-017 Companyfacts-growth + OHLCV-RS default-off paper candidate source.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Retained candidates | Filtered candidates | Tickers |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 7.0043 | +1.8415 | $117,072.92 | $138,699.12 | $+21,626.20 | -0.0091 | 99 | 260 | 119 | 9 |
| mid_weak | 2.1402 | 5.5691 | +3.4289 | $78,110.11 | $128,316.26 | $+50,206.15 | -0.0204 | 116 | 399 | 102 | 10 |
| old_thin | 0.5911 | 2.8851 | +2.2940 | $39,667.96 | $89,603.75 | $+49,935.79 | +0.1052 | 121 | 359 | 113 | 13 |

## Aggregate

- EV delta: `7.5644` (`0.958235`)
- PnL delta: `$121768.14` (`0.518491`)
- target trades: `336`
- max drawdown drift: `0.1052`
- max single positive share: `0.52877`
- positive PnL HHI: `0.342871`

## Operating-Profit Quality Audit

```json
{
  "late_strong": {
    "filtered_candidates": 119,
    "filtered_ticker_counts": {
      "AMD": 7,
      "DDOG": 8,
      "GE": 16,
      "GS": 44,
      "LLY": 33,
      "SNOW": 11
    },
    "filtered_unique_tickers": 6,
    "input_candidates": 379,
    "operating_income_status_counts": {
      "missing_operating_income_quarter_fact": 93,
      "ok": 286
    },
    "retained_candidates": 260,
    "retained_days": 109,
    "retained_ticker_counts": {
      "AMD": 25,
      "AMZN": 5,
      "APP": 19,
      "AVGO": 24,
      "CRDO": 19,
      "GOOG": 50,
      "MU": 71,
      "PLTR": 6,
      "RTX": 41
    },
    "retained_unique_tickers": 9,
    "rule_version": "fundamental_growth_rs_operating_profit_quality_v1"
  },
  "mid_weak": {
    "filtered_candidates": 102,
    "filtered_ticker_counts": {
      "AMD": 19,
      "COIN": 1,
      "DDOG": 4,
      "GE": 40,
      "GS": 1,
      "LLY": 4,
      "SNOW": 33
    },
    "filtered_unique_tickers": 7,
    "input_candidates": 501,
    "operating_income_status_counts": {
      "missing_operating_income_quarter_fact": 45,
      "ok": 456
    },
    "retained_candidates": 399,
    "retained_days": 123,
    "retained_ticker_counts": {
      "AMD": 22,
      "APP": 41,
      "AVGO": 75,
      "COIN": 21,
      "CRDO": 66,
      "META": 1,
      "MU": 39,
      "NFLX": 24,
      "NVDA": 34,
      "PLTR": 76
    },
    "retained_unique_tickers": 10,
    "rule_version": "fundamental_growth_rs_operating_profit_quality_v1"
  },
  "old_thin": {
    "filtered_candidates": 113,
    "filtered_ticker_counts": {
      "CRDO": 61,
      "GE": 13,
      "GS": 9,
      "LLY": 1,
      "SNOW": 29
    },
    "filtered_unique_tickers": 5,
    "input_candidates": 472,
    "operating_income_status_counts": {
      "missing_operating_income_quarter_fact": 23,
      "ok": 449
    },
    "retained_candidates": 359,
    "retained_days": 127,
    "retained_ticker_counts": {
      "APP": 69,
      "AVGO": 28,
      "COIN": 21,
      "DDOG": 13,
      "ISRG": 10,
      "META": 13,
      "MU": 3,
      "NFLX": 59,
      "NOW": 27,
      "NVDA": 21,
      "PLTR": 72,
      "RTX": 21,
      "TRIP": 2
    },
    "retained_unique_tickers": 13,
    "rule_version": "fundamental_growth_rs_operating_profit_quality_v1"
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.1052,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.52877,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.342871,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 336,
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

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
