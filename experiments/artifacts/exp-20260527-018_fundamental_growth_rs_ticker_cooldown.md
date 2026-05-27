# exp-20260527-018 Fundamental Growth + RS Ticker Cooldown

Decision: `rejected_fundamental_growth_rs_ticker_cooldown`.

Single variable: add a 20-trading-day same-ticker cooldown to the exp-20260527-017 Companyfacts-growth + OHLCV-RS default-off paper candidate source.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Cooldown skips | Tickers |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.7384 | -0.4244 | $117,072.92 | $113,627.60 | $-3,445.32 | +0.0028 | 33 | 304 | 13 |
| mid_weak | 2.1402 | 3.0579 | +0.9177 | $78,110.11 | $93,803.04 | $+15,692.93 | -0.0056 | 45 | 440 | 15 |
| old_thin | 0.5911 | 0.8918 | +0.3007 | $39,667.96 | $48,468.09 | $+8,800.13 | +0.0396 | 44 | 407 | 17 |

## Aggregate

- EV delta: `0.794` (`0.100581`)
- PnL delta: `$21047.74` (`0.089622`)
- target trades: `122`
- max drawdown drift: `0.0396`
- max single positive share: `0.2257`
- positive PnL HHI: `0.12652`

## Cooldown Audit

```json
{
  "late_strong": {
    "cooldown_filtered": 304,
    "daily_top1_filtered": 13,
    "input_candidates": 379,
    "missing_trade_filtered": 24,
    "rule_version": "fundamental_growth_rs_ticker_cooldown_v1",
    "same_ticker_core_overlap_filtered": 5,
    "selected_ticker_counts": {
      "AMD": 3,
      "APP": 2,
      "AVGO": 2,
      "CRDO": 3,
      "DDOG": 1,
      "GE": 2,
      "GOOG": 3,
      "GS": 3,
      "LLY": 4,
      "MU": 5,
      "PLTR": 1,
      "RTX": 3,
      "SNOW": 1
    },
    "selected_trades": 33,
    "selected_unique_tickers": 13,
    "ticker_cooldown_trading_days": 20
  },
  "mid_weak": {
    "cooldown_filtered": 440,
    "daily_top1_filtered": 5,
    "input_candidates": 501,
    "missing_trade_filtered": 6,
    "rule_version": "fundamental_growth_rs_ticker_cooldown_v1",
    "same_ticker_core_overlap_filtered": 5,
    "selected_ticker_counts": {
      "AMD": 3,
      "APP": 4,
      "AVGO": 6,
      "COIN": 2,
      "CRDO": 5,
      "DDOG": 1,
      "GE": 3,
      "GS": 1,
      "LLY": 1,
      "META": 1,
      "MU": 3,
      "NFLX": 3,
      "NVDA": 2,
      "PLTR": 6,
      "SNOW": 4
    },
    "selected_trades": 45,
    "selected_unique_tickers": 15,
    "ticker_cooldown_trading_days": 20
  },
  "old_thin": {
    "cooldown_filtered": 407,
    "daily_top1_filtered": 7,
    "input_candidates": 472,
    "missing_trade_filtered": 9,
    "rule_version": "fundamental_growth_rs_ticker_cooldown_v1",
    "same_ticker_core_overlap_filtered": 5,
    "selected_ticker_counts": {
      "APP": 5,
      "AVGO": 3,
      "COIN": 3,
      "CRDO": 5,
      "DDOG": 1,
      "GE": 1,
      "GS": 2,
      "ISRG": 2,
      "META": 1,
      "MU": 1,
      "NFLX": 5,
      "NOW": 3,
      "NVDA": 2,
      "PLTR": 6,
      "RTX": 1,
      "SNOW": 2,
      "TRIP": 1
    },
    "selected_trades": 44,
    "selected_unique_tickers": 17,
    "ticker_cooldown_trading_days": 20
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0396,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.2257,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.12652,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 122,
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
