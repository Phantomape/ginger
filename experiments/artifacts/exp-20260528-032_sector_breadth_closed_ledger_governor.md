# exp-20260528-032 Sector-Breadth Closed-Ledger Governor

Decision: `rejected_sector_breadth_closed_ledger_governor`.

Single variable: prior-closed paper outcome governor on the locked sector-breadth confirmed breakout paper candidate pool.

Selected variant: `cap1500_dd1500_scalar005`.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Adjusted | Candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.9918 | -0.1710 | $117,072.92 | $115,545.72 | $-1,527.20 | +0.0026 | 6 | 0 | 17 |
| mid_weak | 2.1402 | 2.4546 | +0.3144 | $78,110.11 | $85,232.56 | $+7,122.45 | -0.0001 | 35 | 7 | 94 |
| old_thin | 0.5911 | 0.6550 | +0.0639 | $39,667.96 | $41,724.57 | $+2,056.61 | -0.0027 | 32 | 24 | 72 |

## Aggregate

- EV delta vs core: `0.2073` (`0.02626`)
- PnL delta vs core: `$7651.86` (`0.032582`)
- EV delta vs raw sector-breadth control: `0.0758`
- PnL delta vs raw sector-breadth control: `$21.93`
- raw sector-breadth EV/PnL delta vs core: `0.1315` / `$7629.93`
- target trades: `73` across `3` windows
- adjusted trades: `31`
- max single positive share: `0.318394`
- positive PnL HHI: `0.189942`

## Variant Summary

```json
{
  "cap1500_dd1500_scalar005": {
    "aggregate": {
      "adjusted_trade_count_sum": 31,
      "after_expected_value_score_sum": 8.1014,
      "after_total_pnl_sum": 242502.85,
      "baseline_expected_value_score_sum": 7.8941,
      "baseline_total_pnl_sum": 234850.99,
      "expected_value_score_delta_pct": 0.02626,
      "expected_value_score_delta_sum": 0.2073,
      "max_drawdown_delta_max": 0.0026,
      "target_trade_count_sum": 73,
      "total_pnl_delta_pct": 0.032582,
      "total_pnl_delta_sum": 7651.86,
      "windows_ev_improved": 2,
      "windows_ev_regressed": 1,
      "windows_pnl_improved": 2,
      "windows_pnl_regressed": 1
    },
    "gate4": {
      "aggregate_ev_delta_positive": true,
      "aggregate_pnl_delta_positive": true,
      "failed_reasons": [
        "window_ev_regression",
        "window_pnl_regression"
      ],
      "max_drawdown_worse": 0.0026,
      "max_drawdown_worse_guardrail": 0.005,
      "passed": false,
      "survival_guard_passed": true,
      "target_concentration": {
        "max_single_positive_pnl_share": 0.318394,
        "max_single_positive_pnl_share_guardrail": 0.4,
        "passed": true,
        "positive_pnl_hhi": 0.189942,
        "positive_pnl_hhi_guardrail": 0.3
      },
      "target_trade_count": 73,
      "target_trade_count_min": 20,
      "target_window_count_min": 3,
      "target_windows": [
        "late_strong",
        "mid_weak",
        "old_thin"
      ],
      "windows_ev_improved": 2,
      "windows_ev_regressed": 1,
      "windows_pnl_regressed": 1
    },
    "target_trade_summary": {
      "adjusted_trade_count": 31,
      "by_ticker_count": {
        "AAPL": 2,
        "AMD": 4,
        "AMZN": 3,
        "APP": 5,
        "AVGO": 4,
        "BKNG": 3,
        "COIN": 14,
        "CRDO": 3,
        "DDOG": 2,
        "GOOG": 2,
        "GS": 7,
        "JPM": 2,
        "MA": 2,
        "MCD": 3,
        "MSFT": 1,
        "NVDA": 1,
        "PLTR": 1,
        "SNOW": 1,
        "TRIP": 4,
        "TSLA": 5,
        "TSM": 1,
        "V": 3
      },
      "by_ticker_pnl": {
        "AAPL": -186.39,
        "AMD": 1205.06,
        "AMZN": -94.15,
        "APP": 2020.91,
        "AVGO": -1453.61,
        "BKNG": 726.04,
        "COIN": 4111.24,
        "CRDO": 2143.06,
        "DDOG": -282.52,
        "GOOG": 3.77,
        "GS": 404.78,
        "JPM": -31.35,
        "MA": 75.12,
        "MCD": -531.48,
        "MSFT": -173.47,
        "NVDA": -597.7,
        "PLTR": 241.0,
        "SNOW": -710.35,
        "TRIP": -1103.87,
        "TSLA": 1970.56,
        "TSM": 10.88,
        "V": -95.67
      },
      "by_window_pnl": {
        "late_strong": -1527.2,
        "mid_weak": 7122.45,
        "old_thin": 2056.61
      },
      "max_single_positive_pnl_share": 0.318394,
      "positive_by_ticker_pnl": {
        "AMD": 1205.06,
        "APP": 2020.91,
        "BKNG": 726.04,
        "COIN": 4111.24,
        "CRDO": 2143.06,
        "GOOG": 3.77,
        "GS": 404.78,
        "MA": 75.12,
        "PLTR": 241.0,
        "TSLA": 1970.56,
        "TSM": 10.88
      },
      "positive_pnl_hhi": 0.189942,
      "total_pnl": 7651.86,
      "total_trade_count": 73,
      "windows_with_target_trades": [
        "late_strong",
        "mid_weak",
        "old_thin"
      ]
    }
  },
  "cap1500_dd1500_scalar025": {
    "aggregate": {
      "adjusted_trade_count_sum": 31,
      "after_expected_value_score_sum": 8.0663,
      "after_total_pnl_sum": 241875.33,
      "baseline_expected_value_score_sum": 7.8941,
      "baseline_total_pnl_sum": 234850.99,
      "expected_value_score_delta_pct": 0.021814,
      "expected_value_score_delta_sum": 0.1722,
      "max_drawdown_delta_max": 0.0026,
      "target_trade_count_sum": 73,
      "total_pnl_delta_pct": 0.02991,
      "total_pnl_delta_sum": 7024.34,
      "windows_ev_improved": 2,
      "windows_ev_regressed": 1,
      "windows_pnl_improved": 2,
      "windows_pnl_regressed": 1
    },
    "gate4": {
      "aggregate_ev_delta_positive": true,
      "aggregate_pnl_delta_positive": true,
      "failed_reasons": [
        "window_ev_regression",
        "window_pnl_regression"
      ],
      "max_drawdown_worse": 0.0026,
      "max_drawdown_worse_guardrail": 0.005,
      "passed": false,
      "survival_guard_passed": true,
      "target_concentration": {
        "max_single_positive_pnl_share": 0.28137,
        "max_single_positive_pnl_share_guardrail": 0.4,
        "passed": true,
        "positive_pnl_hhi": 0.177729,
        "positive_pnl_hhi_guardrail": 0.3
      },
      "target_trade_count": 73,
      "target_trade_count_min": 20,
      "target_window_count_min": 3,
      "target_windows": [
        "late_strong",
        "mid_weak",
        "old_thin"
      ],
      "windows_ev_improved": 2,
      "windows_ev_regressed": 1,
      "windows_pnl_regressed": 1
    },
    "target_trade_summary": {
      "adjusted_trade_count": 31,
      "by_ticker_count": {
        "AAPL": 2,
        "AMD": 4,
        "AMZN": 3,
        "APP": 5,
        "AVGO": 4,
        "BKNG": 3,
        "COIN": 14,
        "CRDO": 3,
        "DDOG": 2,
        "GOOG": 2,
        "GS": 7,
        "JPM": 2,
        "MA": 2,
        "MCD": 3,
        "MSFT": 1,
        "NVDA": 1,
        "PLTR": 1,
        "SNOW": 1,
        "TRIP": 4,
        "TSLA": 5,
        "TSM": 1,
        "V": 3
      },
      "by_ticker_pnl": {
        "AAPL": -186.39,
        "AMD": 1205.06,
        "AMZN": -94.15,
        "APP": 2020.91,
        "AVGO": -1453.61,
        "BKNG": 726.04,
        "COIN": 3456.6,
        "CRDO": 2143.06,
        "DDOG": -282.52,
        "GOOG": 3.77,
        "GS": 404.78,
        "JPM": -31.35,
        "MA": 75.12,
        "MCD": -531.48,
        "MSFT": -173.47,
        "NVDA": -597.7,
        "PLTR": 241.0,
        "SNOW": -710.35,
        "TRIP": -1103.87,
        "TSLA": 1997.68,
        "TSM": 10.88,
        "V": -95.67
      },
      "by_window_pnl": {
        "late_strong": -1527.2,
        "mid_weak": 6467.81,
        "old_thin": 2083.73
      },
      "max_single_positive_pnl_share": 0.28137,
      "positive_by_ticker_pnl": {
        "AMD": 1205.06,
        "APP": 2020.91,
        "BKNG": 726.04,
        "COIN": 3456.6,
        "CRDO": 2143.06,
        "GOOG": 3.77,
        "GS": 404.78,
        "MA": 75.12,
        "PLTR": 241.0,
        "TSLA": 1997.68,
        "TSM": 10.88
      },
      "positive_pnl_hhi": 0.177729,
      "total_pnl": 7024.34,
      "total_trade_count": 73,
      "windows_with_target_trades": [
        "late_strong",
        "mid_weak",
        "old_thin"
      ]
    }
  },
  "cap2500_dd2000_scalar025": {
    "aggregate": {
      "adjusted_trade_count_sum": 31,
      "after_expected_value_score_sum": 8.0663,
      "after_total_pnl_sum": 241875.33,
      "baseline_expected_value_score_sum": 7.8941,
      "baseline_total_pnl_sum": 234850.99,
      "expected_value_score_delta_pct": 0.021814,
      "expected_value_score_delta_sum": 0.1722,
      "max_drawdown_delta_max": 0.0026,
      "target_trade_count_sum": 73,
      "total_pnl_delta_pct": 0.02991,
      "total_pnl_delta_sum": 7024.34,
      "windows_ev_improved": 2,
      "windows_ev_regressed": 1,
      "windows_pnl_improved": 2,
      "windows_pnl_regressed": 1
    },
    "gate4": {
      "aggregate_ev_delta_positive": true,
      "aggregate_pnl_delta_positive": true,
      "failed_reasons": [
        "window_ev_regression",
        "window_pnl_regression"
      ],
      "max_drawdown_worse": 0.0026,
      "max_drawdown_worse_guardrail": 0.005,
      "passed": false,
      "survival_guard_passed": true,
      "target_concentration": {
        "max_single_positive_pnl_share": 0.28137,
        "max_single_positive_pnl_share_guardrail": 0.4,
        "passed": true,
        "positive_pnl_hhi": 0.177729,
        "positive_pnl_hhi_guardrail": 0.3
      },
      "target_trade_count": 73,
      "target_trade_count_min": 20,
      "target_window_count_min": 3,
      "target_windows": [
        "late_strong",
        "mid_weak",
        "old_thin"
      ],
      "windows_ev_improved": 2,
      "windows_ev_regressed": 1,
      "windows_pnl_regressed": 1
    },
    "target_trade_summary": {
      "adjusted_trade_count": 31,
      "by_ticker_count": {
        "AAPL": 2,
        "AMD": 4,
        "AMZN": 3,
        "APP": 5,
        "AVGO": 4,
        "BKNG": 3,
        "COIN": 14,
        "CRDO": 3,
        "DDOG": 2,
        "GOOG": 2,
        "GS": 7,
        "JPM": 2,
        "MA": 2,
        "MCD": 3,
        "MSFT": 1,
        "NVDA": 1,
        "PLTR": 1,
        "SNOW": 1,
        "TRIP": 4,
        "TSLA": 5,
        "TSM": 1,
        "V": 3
      },
      "by_ticker_pnl": {
        "AAPL": -186.39,
        "AMD": 1205.06,
        "AMZN": -94.15,
        "APP": 2020.91,
        "AVGO": -1453.61,
        "BKNG": 726.04,
        "COIN": 3456.6,
        "CRDO": 2143.06,
        "DDOG": -282.52,
        "GOOG": 3.77,
        "GS": 404.78,
        "JPM": -31.35,
        "MA": 75.12,
        "MCD": -531.48,
        "MSFT": -173.47,
        "NVDA": -597.7,
        "PLTR": 241.0,
        "SNOW": -710.35,
        "TRIP": -1103.87,
        "TSLA": 1997.68,
        "TSM": 10.88,
        "V": -95.67
      },
      "by_window_pnl": {
        "late_strong": -1527.2,
        "mid_weak": 6467.81,
        "old_thin": 2083.73
      },
      "max_single_positive_pnl_share": 0.28137,
      "positive_by_ticker_pnl": {
        "AMD": 1205.06,
        "APP": 2020.91,
        "BKNG": 726.04,
        "COIN": 3456.6,
        "CRDO": 2143.06,
        "GOOG": 3.77,
        "GS": 404.78,
        "MA": 75.12,
        "PLTR": 241.0,
        "TSLA": 1997.68,
        "TSM": 10.88
      },
      "positive_pnl_hhi": 0.177729,
      "total_pnl": 7024.34,
      "total_trade_count": 73,
      "windows_with_target_trades": [
        "late_strong",
        "mid_weak",
        "old_thin"
      ]
    }
  },
  "raw_sector_breadth_control": {
    "aggregate": {
      "adjusted_trade_count_sum": 0,
      "after_expected_value_score_sum": 8.0256,
      "after_total_pnl_sum": 242480.92,
      "baseline_expected_value_score_sum": 7.8941,
      "baseline_total_pnl_sum": 234850.99,
      "expected_value_score_delta_pct": 0.016658,
      "expected_value_score_delta_sum": 0.1315,
      "max_drawdown_delta_max": 0.0026,
      "target_trade_count_sum": 73,
      "total_pnl_delta_pct": 0.032488,
      "total_pnl_delta_sum": 7629.93,
      "windows_ev_improved": 2,
      "windows_ev_regressed": 1,
      "windows_pnl_improved": 2,
      "windows_pnl_regressed": 1
    },
    "gate4": {
      "aggregate_ev_delta_positive": true,
      "aggregate_pnl_delta_positive": true,
      "failed_reasons": [
        "window_ev_regression",
        "window_pnl_regression"
      ],
      "max_drawdown_worse": 0.0026,
      "max_drawdown_worse_guardrail": 0.005,
      "passed": false,
      "survival_guard_passed": true,
      "target_concentration": {
        "max_single_positive_pnl_share": 0.270349,
        "max_single_positive_pnl_share_guardrail": 0.4,
        "passed": true,
        "positive_pnl_hhi": 0.161544,
        "positive_pnl_hhi_guardrail": 0.3
      },
      "target_trade_count": 73,
      "target_trade_count_min": 20,
      "target_window_count_min": 3,
      "target_windows": [
        "late_strong",
        "mid_weak",
        "old_thin"
      ],
      "windows_ev_improved": 2,
      "windows_ev_regressed": 1,
      "windows_pnl_regressed": 1
    },
    "target_trade_summary": {
      "adjusted_trade_count": 0,
      "by_ticker_count": {
        "AAPL": 2,
        "AMD": 4,
        "AMZN": 3,
        "APP": 5,
        "AVGO": 4,
        "BKNG": 3,
        "COIN": 14,
        "CRDO": 3,
        "DDOG": 2,
        "GOOG": 2,
        "GS": 7,
        "JPM": 2,
        "MA": 2,
        "MCD": 3,
        "MSFT": 1,
        "NVDA": 1,
        "PLTR": 1,
        "SNOW": 1,
        "TRIP": 4,
        "TSLA": 5,
        "TSM": 1,
        "V": 3
      },
      "by_ticker_pnl": {
        "AAPL": -589.51,
        "AMD": 1841.69,
        "AMZN": 107.05,
        "APP": 4446.92,
        "AVGO": -1742.31,
        "BKNG": 603.56,
        "COIN": 3255.46,
        "CRDO": 1872.41,
        "DDOG": -1130.04,
        "GOOG": 0.56,
        "GS": 784.66,
        "JPM": 129.08,
        "MA": 300.5,
        "MCD": -483.57,
        "MSFT": -693.89,
        "NVDA": -597.7,
        "PLTR": 964.02,
        "SNOW": -710.35,
        "TRIP": -2020.94,
        "TSLA": 2099.37,
        "TSM": 43.51,
        "V": -850.55
      },
      "by_window_pnl": {
        "late_strong": -1527.2,
        "mid_weak": 4276.51,
        "old_thin": 4880.62
      },
      "max_single_positive_pnl_share": 0.270349,
      "positive_by_ticker_pnl": {
        "AMD": 1841.69,
        "AMZN": 107.05,
        "APP": 4446.92,
        "BKNG": 603.56,
        "COIN": 3255.46,
        "CRDO": 1872.41,
        "GOOG": 0.56,
        "GS": 784.66,
        "JPM": 129.08,
        "MA": 300.5,
        "PLTR": 964.02,
        "TSLA": 2099.37,
        "TSM": 43.51
      },
      "positive_pnl_hhi": 0.161544,
      "total_pnl": 7629.93,
      "total_trade_count": 73,
      "windows_with_target_trades": [
        "late_strong",
        "mid_weak",
        "old_thin"
      ]
    }
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "window_ev_regression",
    "window_pnl_regression"
  ],
  "max_drawdown_worse": 0.0026,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.318394,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.189942,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 73,
  "target_trade_count_min": 20,
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
