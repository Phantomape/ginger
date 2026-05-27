# exp-20260527-023 Fundamental Growth + RS QQQ Confirmation

Decision: `rejected_fundamental_growth_rs_qqq_confirmation`.

Single variable: require QQQ 20-trading-day close-to-close return to be greater than SPY 20-trading-day close-to-close return before the exp-20260527-017 Companyfacts-growth + OHLCV-RS default-off paper candidate source can select a trade.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Retained candidates | Filtered candidates | Tickers |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.3948 | -0.7680 | $117,072.92 | $106,930.32 | $-10,142.60 | -0.0012 | 38 | 173 | 206 | 14 |
| mid_weak | 2.1402 | 3.5835 | +1.4433 | $78,110.11 | $99,821.25 | $+21,711.14 | -0.0205 | 93 | 416 | 85 | 14 |
| old_thin | 0.5911 | 2.1988 | +1.6077 | $39,667.96 | $75,820.47 | $+36,152.51 | +0.0721 | 69 | 291 | 181 | 14 |

## Aggregate

- EV delta: `2.283` (`0.289203`)
- PnL delta: `$47721.05` (`0.203197`)
- target trades: `200`
- max drawdown drift: `0.0721`
- max single positive share: `0.605447`
- positive PnL HHI: `0.42142`

## QQQ Confirmation Audit

```json
{
  "late_strong": {
    "filtered_candidates": 206,
    "filtered_days": 67,
    "filtered_ticker_counts": {
      "AMD": 10,
      "APP": 10,
      "AVGO": 8,
      "CRDO": 3,
      "DDOG": 4,
      "GE": 14,
      "GOOG": 33,
      "GS": 31,
      "LLY": 24,
      "MU": 37,
      "PLTR": 3,
      "RTX": 28,
      "SNOW": 1
    },
    "filtered_unique_tickers": 13,
    "input_candidates": 379,
    "market_confirmation_lookback_days": 20,
    "retained_candidates": 173,
    "retained_days": 46,
    "retained_ticker_counts": {
      "AMD": 22,
      "AMZN": 5,
      "APP": 9,
      "AVGO": 16,
      "CRDO": 16,
      "DDOG": 4,
      "GE": 2,
      "GOOG": 17,
      "GS": 13,
      "LLY": 9,
      "MU": 34,
      "PLTR": 3,
      "RTX": 13,
      "SNOW": 10
    },
    "retained_unique_tickers": 14,
    "rule_version": "fundamental_growth_rs_qqq_confirmation_v1"
  },
  "mid_weak": {
    "filtered_candidates": 85,
    "filtered_days": 25,
    "filtered_ticker_counts": {
      "AMD": 6,
      "APP": 17,
      "AVGO": 15,
      "COIN": 1,
      "CRDO": 21,
      "GE": 1,
      "GS": 1,
      "MU": 6,
      "NFLX": 1,
      "NVDA": 9,
      "PLTR": 7
    },
    "filtered_unique_tickers": 11,
    "input_candidates": 501,
    "market_confirmation_lookback_days": 20,
    "retained_candidates": 416,
    "retained_days": 101,
    "retained_ticker_counts": {
      "AMD": 35,
      "APP": 24,
      "AVGO": 60,
      "COIN": 21,
      "CRDO": 45,
      "DDOG": 4,
      "GE": 39,
      "LLY": 4,
      "META": 1,
      "MU": 33,
      "NFLX": 23,
      "NVDA": 25,
      "PLTR": 69,
      "SNOW": 33
    },
    "retained_unique_tickers": 14,
    "rule_version": "fundamental_growth_rs_qqq_confirmation_v1"
  },
  "old_thin": {
    "filtered_candidates": 181,
    "filtered_days": 60,
    "filtered_ticker_counts": {
      "APP": 24,
      "AVGO": 8,
      "COIN": 5,
      "CRDO": 18,
      "DDOG": 4,
      "GE": 13,
      "GS": 3,
      "ISRG": 8,
      "LLY": 1,
      "META": 6,
      "MU": 3,
      "NFLX": 25,
      "NOW": 3,
      "NVDA": 4,
      "PLTR": 22,
      "RTX": 21,
      "SNOW": 12,
      "TRIP": 1
    },
    "filtered_unique_tickers": 18,
    "input_candidates": 472,
    "market_confirmation_lookback_days": 20,
    "retained_candidates": 291,
    "retained_days": 70,
    "retained_ticker_counts": {
      "APP": 45,
      "AVGO": 20,
      "COIN": 16,
      "CRDO": 43,
      "DDOG": 9,
      "GS": 6,
      "ISRG": 2,
      "META": 7,
      "NFLX": 34,
      "NOW": 24,
      "NVDA": 17,
      "PLTR": 50,
      "SNOW": 17,
      "TRIP": 1
    },
    "retained_unique_tickers": 14,
    "rule_version": "fundamental_growth_rs_qqq_confirmation_v1"
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0721,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.605447,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.42142,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 200,
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
