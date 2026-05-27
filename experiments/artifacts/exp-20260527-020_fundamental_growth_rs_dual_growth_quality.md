# exp-20260527-020 Fundamental Growth + RS Dual-Growth Quality

Decision: `rejected_fundamental_growth_rs_dual_growth_quality`.

Single variable: require both EPS-growth and revenue-growth pass flags inside the exp-20260527-017 Companyfacts-growth + OHLCV-RS default-off paper candidate source.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Retained candidates | Filtered candidates | Tickers |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 6.1389 | +0.9761 | $117,072.92 | $132,018.75 | $+14,945.83 | -0.0031 | 85 | 155 | 224 | 6 |
| mid_weak | 2.1402 | 2.8850 | +0.7448 | $78,110.11 | $93,672.40 | $+15,562.29 | +0.0174 | 97 | 179 | 322 | 6 |
| old_thin | 0.5911 | 3.1309 | +2.5398 | $39,667.96 | $93,739.39 | $+54,071.43 | +0.0797 | 89 | 181 | 291 | 4 |

## Aggregate

- EV delta: `4.2607` (`0.539732`)
- PnL delta: `$84579.55` (`0.360141`)
- target trades: `271`
- max drawdown drift: `0.0797`
- max single positive share: `0.595166`
- positive PnL HHI: `0.437887`

## Dual-Growth Quality Audit

```json
{
  "late_strong": {
    "filtered_candidates": 224,
    "filtered_ticker_counts": {
      "AMZN": 5,
      "APP": 19,
      "AVGO": 16,
      "CRDO": 14,
      "DDOG": 8,
      "GE": 16,
      "GOOG": 50,
      "GS": 44,
      "RTX": 41,
      "SNOW": 11
    },
    "filtered_unique_tickers": 10,
    "input_candidates": 379,
    "retained_candidates": 155,
    "retained_days": 96,
    "retained_ticker_counts": {
      "AMD": 32,
      "AVGO": 8,
      "CRDO": 5,
      "LLY": 33,
      "MU": 71,
      "PLTR": 6
    },
    "retained_unique_tickers": 6,
    "rule_version": "fundamental_growth_rs_dual_growth_quality_v1"
  },
  "mid_weak": {
    "filtered_candidates": 322,
    "filtered_ticker_counts": {
      "APP": 30,
      "AVGO": 75,
      "COIN": 22,
      "CRDO": 66,
      "DDOG": 4,
      "GE": 29,
      "GS": 1,
      "LLY": 4,
      "NFLX": 24,
      "NVDA": 34,
      "SNOW": 33
    },
    "filtered_unique_tickers": 11,
    "input_candidates": 501,
    "retained_candidates": 179,
    "retained_days": 105,
    "retained_ticker_counts": {
      "AMD": 41,
      "APP": 11,
      "GE": 11,
      "META": 1,
      "MU": 39,
      "PLTR": 76
    },
    "retained_unique_tickers": 6,
    "rule_version": "fundamental_growth_rs_dual_growth_quality_v1"
  },
  "old_thin": {
    "filtered_candidates": 291,
    "filtered_ticker_counts": {
      "AVGO": 28,
      "COIN": 21,
      "CRDO": 61,
      "GE": 13,
      "GS": 9,
      "ISRG": 10,
      "LLY": 1,
      "META": 13,
      "MU": 3,
      "NFLX": 59,
      "NVDA": 21,
      "RTX": 21,
      "SNOW": 29,
      "TRIP": 2
    },
    "filtered_unique_tickers": 14,
    "input_candidates": 472,
    "retained_candidates": 181,
    "retained_days": 93,
    "retained_ticker_counts": {
      "APP": 69,
      "DDOG": 13,
      "NOW": 27,
      "PLTR": 72
    },
    "retained_unique_tickers": 4,
    "rule_version": "fundamental_growth_rs_dual_growth_quality_v1"
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0797,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.595166,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.437887,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 271,
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
