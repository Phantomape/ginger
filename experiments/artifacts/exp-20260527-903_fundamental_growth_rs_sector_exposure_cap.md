# exp-20260527-903 Fundamental Growth + RS Sector Exposure Cap

Decision: `rejected_fundamental_growth_rs_sector_exposure_cap`.

Single variable: skip a Companyfacts-growth + OHLCV-RS paper candidate when the same sector already has an open paper trade in the sleeve; same-day lower-ranked candidates remain eligible.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Sector skips | Sectors | Tickers |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.5425 | +0.3797 | $117,072.92 | $120,491.04 | $+3,418.12 | -0.0026 | 29 | 305 | 4 | 6 |
| mid_weak | 2.1402 | 2.6129 | +0.4727 | $78,110.11 | $86,520.20 | $+8,410.09 | +0.0018 | 27 | 451 | 5 | 10 |
| old_thin | 0.5911 | 0.6771 | +0.0860 | $39,667.96 | $43,131.55 | $+3,463.59 | +0.0297 | 31 | 428 | 6 | 12 |

## Aggregate

- EV delta: `0.9384` (`0.118874`)
- PnL delta: `$15291.8` (`0.065113`)
- target trades: `87`
- max drawdown drift: `0.0297`
- max single positive share: `0.349584`
- positive PnL HHI: `0.175277`

## Sector Cap Audit

```json
{
  "late_strong": {
    "daily_top1_filtered": 9,
    "expired_sector_count": 29,
    "input_candidates": 379,
    "missing_trade_filtered": 31,
    "rule_version": "fundamental_growth_rs_sector_exposure_cap_v1",
    "same_ticker_core_overlap_filtered": 5,
    "sector_cap_filtered": 305,
    "selected_sector_counts": {
      "Financials": 6,
      "Healthcare": 6,
      "Industrials": 6,
      "Technology": 11
    },
    "selected_ticker_counts": {
      "AMD": 2,
      "GOOG": 2,
      "GS": 6,
      "LLY": 6,
      "MU": 7,
      "RTX": 6
    },
    "selected_trades": 29,
    "selected_unique_sectors": 4,
    "selected_unique_tickers": 6,
    "skipped_sector_counts": {
      "Financials": 34,
      "Healthcare": 25,
      "Industrials": 47,
      "Technology": 199
    }
  },
  "mid_weak": {
    "daily_top1_filtered": 1,
    "expired_sector_count": 27,
    "input_candidates": 501,
    "missing_trade_filtered": 17,
    "rule_version": "fundamental_growth_rs_sector_exposure_cap_v1",
    "same_ticker_core_overlap_filtered": 5,
    "sector_cap_filtered": 451,
    "selected_sector_counts": {
      "Communication Services": 5,
      "Financials": 4,
      "Healthcare": 1,
      "Industrials": 5,
      "Technology": 12
    },
    "selected_ticker_counts": {
      "AMD": 2,
      "APP": 2,
      "COIN": 3,
      "CRDO": 3,
      "GE": 5,
      "GS": 1,
      "LLY": 1,
      "MU": 2,
      "NFLX": 5,
      "PLTR": 3
    },
    "selected_trades": 27,
    "selected_unique_sectors": 5,
    "selected_unique_tickers": 10,
    "skipped_sector_counts": {
      "Communication Services": 18,
      "Financials": 18,
      "Healthcare": 3,
      "Industrials": 35,
      "Technology": 377
    }
  },
  "old_thin": {
    "daily_top1_filtered": 1,
    "expired_sector_count": 30,
    "input_candidates": 472,
    "missing_trade_filtered": 7,
    "rule_version": "fundamental_growth_rs_sector_exposure_cap_v1",
    "same_ticker_core_overlap_filtered": 5,
    "sector_cap_filtered": 428,
    "selected_sector_counts": {
      "Communication Services": 9,
      "Consumer Discretionary": 1,
      "Financials": 4,
      "Healthcare": 2,
      "Industrials": 3,
      "Technology": 12
    },
    "selected_ticker_counts": {
      "APP": 4,
      "AVGO": 2,
      "COIN": 3,
      "CRDO": 2,
      "GE": 1,
      "GS": 1,
      "ISRG": 2,
      "MU": 1,
      "NFLX": 9,
      "PLTR": 3,
      "RTX": 2,
      "TRIP": 1
    },
    "selected_trades": 31,
    "selected_unique_sectors": 6,
    "selected_unique_tickers": 12,
    "skipped_sector_counts": {
      "Communication Services": 43,
      "Consumer Discretionary": 1,
      "Financials": 26,
      "Healthcare": 7,
      "Industrials": 30,
      "Technology": 321
    }
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0297,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.349584,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.175277,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 87,
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
