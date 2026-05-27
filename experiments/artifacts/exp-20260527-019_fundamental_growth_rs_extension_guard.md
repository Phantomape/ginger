# exp-20260527-019 Fundamental Growth + RS Extension Guard

Decision: `rejected_fundamental_growth_rs_extension_guard`.

Single variable: add a pre-entry guard to the exp-20260527-017 Companyfacts-growth + OHLCV-RS default-off paper candidate source: skip candidates whose signal-date close is more than 15% above their trailing 50-day moving average.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Retained candidates | Filtered candidates | Tickers |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.3562 | -0.8066 | $117,072.92 | $105,986.91 | $-11,086.01 | +0.0000 | 96 | 225 | 154 | 14 |
| mid_weak | 2.1402 | 3.9768 | +1.8366 | $78,110.11 | $107,483.78 | $+29,373.67 | -0.0050 | 74 | 155 | 346 | 13 |
| old_thin | 0.5911 | 0.9878 | +0.3967 | $39,667.96 | $52,536.78 | $+12,868.82 | +0.0906 | 99 | 199 | 273 | 17 |

## Aggregate

- EV delta: `1.4267` (`0.18073`)
- PnL delta: `$31156.48` (`0.132665`)
- target trades: `269`
- max drawdown drift: `0.0906`
- max single positive share: `0.367613`
- positive PnL HHI: `0.228283`

## Extension Guard Audit

```json
{
  "late_strong": {
    "filtered_candidates": 154,
    "filtered_ticker_counts": {
      "AMD": 21,
      "AMZN": 4,
      "APP": 6,
      "AVGO": 10,
      "CRDO": 12,
      "DDOG": 6,
      "GOOG": 15,
      "GS": 1,
      "LLY": 18,
      "MU": 56,
      "SNOW": 5
    },
    "filtered_unique_tickers": 11,
    "input_candidates": 379,
    "max_pct_above_50d_ma": 0.15,
    "retained_candidates": 225,
    "retained_days": 101,
    "retained_ticker_counts": {
      "AMD": 11,
      "AMZN": 1,
      "APP": 13,
      "AVGO": 14,
      "CRDO": 7,
      "DDOG": 2,
      "GE": 16,
      "GOOG": 35,
      "GS": 43,
      "LLY": 15,
      "MU": 15,
      "PLTR": 6,
      "RTX": 41,
      "SNOW": 6
    },
    "retained_unique_tickers": 14,
    "rule_version": "fundamental_growth_rs_extension_guard_v1"
  },
  "mid_weak": {
    "filtered_candidates": 346,
    "filtered_ticker_counts": {
      "AMD": 39,
      "APP": 39,
      "AVGO": 33,
      "COIN": 22,
      "CRDO": 58,
      "DDOG": 4,
      "GE": 16,
      "MU": 35,
      "NFLX": 15,
      "NVDA": 19,
      "PLTR": 41,
      "SNOW": 25
    },
    "filtered_unique_tickers": 12,
    "input_candidates": 501,
    "max_pct_above_50d_ma": 0.15,
    "retained_candidates": 155,
    "retained_days": 78,
    "retained_ticker_counts": {
      "AMD": 2,
      "APP": 2,
      "AVGO": 42,
      "CRDO": 8,
      "GE": 24,
      "GS": 1,
      "LLY": 4,
      "META": 1,
      "MU": 4,
      "NFLX": 9,
      "NVDA": 15,
      "PLTR": 35,
      "SNOW": 8
    },
    "retained_unique_tickers": 13,
    "rule_version": "fundamental_growth_rs_extension_guard_v1"
  },
  "old_thin": {
    "filtered_candidates": 273,
    "filtered_ticker_counts": {
      "APP": 52,
      "AVGO": 23,
      "COIN": 19,
      "CRDO": 54,
      "DDOG": 11,
      "GS": 5,
      "META": 5,
      "NFLX": 14,
      "NOW": 5,
      "NVDA": 7,
      "PLTR": 60,
      "SNOW": 16,
      "TRIP": 2
    },
    "filtered_unique_tickers": 13,
    "input_candidates": 472,
    "max_pct_above_50d_ma": 0.15,
    "retained_candidates": 199,
    "retained_days": 106,
    "retained_ticker_counts": {
      "APP": 17,
      "AVGO": 5,
      "COIN": 2,
      "CRDO": 7,
      "DDOG": 2,
      "GE": 13,
      "GS": 4,
      "ISRG": 10,
      "LLY": 1,
      "META": 8,
      "MU": 3,
      "NFLX": 45,
      "NOW": 22,
      "NVDA": 14,
      "PLTR": 12,
      "RTX": 21,
      "SNOW": 13
    },
    "retained_unique_tickers": 17,
    "rule_version": "fundamental_growth_rs_extension_guard_v1"
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0906,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.367613,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.228283,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 269,
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

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
