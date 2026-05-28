# exp-20260528-006 Fundamental Growth + RS Cash-Conversion Quality

Decision: `rejected_fundamental_growth_rs_cash_conversion_quality`.

Single variable: require latest PIT operating cash flow to be positive and at least 75% of comparable-period net income inside the exp-20260527-017 Companyfacts-growth + OHLCV-RS default-off paper source.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Retained candidates | Filtered candidates | Tickers |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.4155 | +0.2527 | $117,072.92 | $122,804.46 | $+5,731.54 | -0.0021 | 100 | 324 | 55 | 12 |
| mid_weak | 2.1402 | 3.9031 | +1.7629 | $78,110.11 | $108,421.63 | $+30,311.52 | +0.0117 | 118 | 427 | 74 | 12 |
| old_thin | 0.5911 | 2.7065 | +2.1154 | $39,667.96 | $86,473.29 | $+46,805.33 | +0.1184 | 123 | 373 | 99 | 15 |

## Aggregate

- EV delta: `4.131` (`0.523302`)
- PnL delta: `$82848.39` (`0.35277`)
- target trades: `341`
- max drawdown drift: `0.1184`
- max single positive share: `0.662732`
- positive PnL HHI: `0.477423`

## Cash-Conversion Quality Audit

```json
{
  "late_strong": {
    "cash_conversion_status_counts": {
      "non_positive_net_income": 11,
      "non_positive_operating_cash_flow": 44,
      "ok": 324
    },
    "filtered_candidates": 55,
    "filtered_ticker_counts": {
      "GS": 44,
      "SNOW": 11
    },
    "filtered_unique_tickers": 2,
    "input_candidates": 379,
    "retained_candidates": 324,
    "retained_days": 110,
    "retained_ticker_counts": {
      "AMD": 32,
      "AMZN": 5,
      "APP": 19,
      "AVGO": 24,
      "CRDO": 19,
      "DDOG": 8,
      "GE": 16,
      "GOOG": 50,
      "LLY": 33,
      "MU": 71,
      "PLTR": 6,
      "RTX": 41
    },
    "retained_unique_tickers": 12,
    "rule_version": "fundamental_growth_rs_cash_conversion_quality_v1"
  },
  "mid_weak": {
    "cash_conversion_status_counts": {
      "non_positive_net_income": 33,
      "non_positive_operating_cash_flow": 22,
      "ok": 427,
      "weak_cash_conversion": 19
    },
    "filtered_candidates": 74,
    "filtered_ticker_counts": {
      "COIN": 22,
      "CRDO": 18,
      "GS": 1,
      "SNOW": 33
    },
    "filtered_unique_tickers": 4,
    "input_candidates": 501,
    "retained_candidates": 427,
    "retained_days": 126,
    "retained_ticker_counts": {
      "AMD": 41,
      "APP": 41,
      "AVGO": 75,
      "CRDO": 48,
      "DDOG": 4,
      "GE": 40,
      "LLY": 4,
      "META": 1,
      "MU": 39,
      "NFLX": 24,
      "NVDA": 34,
      "PLTR": 76
    },
    "retained_unique_tickers": 12,
    "rule_version": "fundamental_growth_rs_cash_conversion_quality_v1"
  },
  "old_thin": {
    "cash_conversion_status_counts": {
      "non_positive_net_income": 59,
      "non_positive_operating_cash_flow": 40,
      "ok": 373
    },
    "filtered_candidates": 99,
    "filtered_ticker_counts": {
      "CRDO": 61,
      "GS": 9,
      "SNOW": 29
    },
    "filtered_unique_tickers": 3,
    "input_candidates": 472,
    "retained_candidates": 373,
    "retained_days": 129,
    "retained_ticker_counts": {
      "APP": 69,
      "AVGO": 28,
      "COIN": 21,
      "DDOG": 13,
      "GE": 13,
      "ISRG": 10,
      "LLY": 1,
      "META": 13,
      "MU": 3,
      "NFLX": 59,
      "NOW": 27,
      "NVDA": 21,
      "PLTR": 72,
      "RTX": 21,
      "TRIP": 2
    },
    "retained_unique_tickers": 15,
    "rule_version": "fundamental_growth_rs_cash_conversion_quality_v1"
  }
}
```

## Gate 4

```json
{
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
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
