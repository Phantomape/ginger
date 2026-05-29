# exp-20260529-008 Fundamental Growth+RS / VBB Source Agreement

Decision: `rejected_fundamental_growth_rs_vbb_source_agreement_support`.

Single variable: already-selected Fundamental Growth+RS paper trades receive a default-off notional scalar only when the same ticker had a prior accepted VBB paper confirmation inside the selected lookback.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Adjusted / Before Trades | Incremental PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 7.6805 | 7.8434 | +0.1629 | $142,757.37 | $144,176.36 | $+1,418.99 | -0.0005 | 17/99 | $+1,419.00 |
| mid_weak | 6.0711 | 6.1672 | +0.0961 | $134,019.30 | $134,952.45 | $+933.15 | -0.0004 | 9/116 | $+933.15 |
| old_thin | 2.6844 | 2.7062 | +0.0218 | $85,218.47 | $85,637.85 | $+419.38 | +0.0001 | 21/121 | $+419.38 |

## Aggregate

- EV delta: `0.2808` (`0.017084`)
- PnL delta: `$2771.52` (`0.007656`)
- adjusted trades: `47`
- max drawdown drift: `0.0001`
- max single positive share: `0.463474`
- positive PnL HHI: `0.311388`

## Gate 4

```json
{
  "aggregate": {
    "after_expected_value_score_sum": 16.7168,
    "after_total_pnl_sum": 364766.66,
    "baseline_expected_value_score_sum": 16.436,
    "baseline_total_pnl_sum": 361995.14,
    "expected_value_score_delta_pct": 0.017084,
    "expected_value_score_delta_sum": 0.2808,
    "max_drawdown_delta_max": 0.0001,
    "target_trade_count_sum": 47,
    "total_pnl_delta_pct": 0.007656,
    "total_pnl_delta_sum": 2771.52,
    "windows_ev_improved": 3,
    "windows_ev_regressed": 0,
    "windows_pnl_improved": 3,
    "windows_pnl_regressed": 0
  },
  "concentration_passed": false,
  "drawdown_guard": {
    "max_allowed_worse": 0.005,
    "observed_max_delta": 0.0001
  },
  "failed_reasons": [
    "target_concentration_failed"
  ],
  "passed": false,
  "target_trade_summary": {
    "by_ticker_count": {
      "APP": 10,
      "AVGO": 3,
      "COIN": 3,
      "CRDO": 2,
      "ISRG": 2,
      "MU": 17,
      "NFLX": 1,
      "PLTR": 9
    },
    "by_ticker_pnl": {
      "APP": 25.49,
      "AVGO": -183.95,
      "COIN": 715.08,
      "CRDO": 552.28,
      "ISRG": -106.18,
      "MU": 1419.0,
      "NFLX": 58.43,
      "PLTR": 291.38
    },
    "by_window_pnl": {
      "late_strong": 1419.0,
      "mid_weak": 933.15,
      "old_thin": 419.38
    },
    "max_single_positive_pnl_share": 0.463474,
    "positive_by_ticker_pnl": {
      "APP": 25.49,
      "COIN": 715.08,
      "CRDO": 552.28,
      "MU": 1419.0,
      "NFLX": 58.43,
      "PLTR": 291.38
    },
    "positive_pnl_hhi": 0.311388,
    "total_pnl": 2771.53,
    "total_trade_count": 47,
    "windows_with_target_trades": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ]
  }
}
```

## Source Agreement Audit

```json
{
  "late_strong": {
    "adjusted_incremental_pnl": 1419.0,
    "adjusted_incremental_pnl_by_ticker": {
      "MU": 1419.0
    },
    "adjusted_ticker_counts": {
      "MU": 17
    },
    "adjusted_trade_count": 17,
    "adjusted_unique_tickers": 1,
    "confirmation_reason_counts": {
      "no_prior_same_ticker_vbb_confirmation": 82,
      "prior_same_ticker_vbb_confirmation": 17
    },
    "days_since_nearest_vbb_signal_counts": {
      "0": 3,
      "1": 1,
      "10": 2,
      "3": 2,
      "4": 1,
      "5": 2,
      "6": 2,
      "7": 2,
      "8": 1,
      "9": 1
    },
    "fundamental_trade_count": 99,
    "unconfirmed_trade_count": 82
  },
  "mid_weak": {
    "adjusted_incremental_pnl": 933.15,
    "adjusted_incremental_pnl_by_ticker": {
      "APP": -21.3,
      "COIN": 402.17,
      "CRDO": 552.28
    },
    "adjusted_ticker_counts": {
      "APP": 5,
      "COIN": 2,
      "CRDO": 2
    },
    "adjusted_trade_count": 9,
    "adjusted_unique_tickers": 3,
    "confirmation_reason_counts": {
      "no_prior_same_ticker_vbb_confirmation": 107,
      "prior_same_ticker_vbb_confirmation": 9
    },
    "days_since_nearest_vbb_signal_counts": {
      "0": 1,
      "10": 1,
      "5": 1,
      "6": 1,
      "7": 1,
      "8": 2,
      "9": 2
    },
    "fundamental_trade_count": 116,
    "unconfirmed_trade_count": 107
  },
  "old_thin": {
    "adjusted_incremental_pnl": 419.38,
    "adjusted_incremental_pnl_by_ticker": {
      "APP": 46.79,
      "AVGO": -183.95,
      "COIN": 312.91,
      "ISRG": -106.18,
      "NFLX": 58.43,
      "PLTR": 291.38
    },
    "adjusted_ticker_counts": {
      "APP": 5,
      "AVGO": 3,
      "COIN": 1,
      "ISRG": 2,
      "NFLX": 1,
      "PLTR": 9
    },
    "adjusted_trade_count": 21,
    "adjusted_unique_tickers": 6,
    "confirmation_reason_counts": {
      "no_prior_same_ticker_vbb_confirmation": 100,
      "prior_same_ticker_vbb_confirmation": 21
    },
    "days_since_nearest_vbb_signal_counts": {
      "0": 6,
      "1": 2,
      "10": 1,
      "3": 1,
      "4": 2,
      "5": 2,
      "6": 2,
      "7": 2,
      "8": 3
    },
    "fundamental_trade_count": 121,
    "unconfirmed_trade_count": 100
  }
}
```

## Production Impact

```json
{
  "backtester_adapter_changed": false,
  "default_off_paper_only": true,
  "parity_test_added": false,
  "production_orders_changed": false,
  "production_watchlist_changed": false,
  "promotion_requirement": "If Gate 4 passes, retain only after moving the same prior-only VBB confirmation metadata into the shared Fundamental Growth+RS paper adapter and adding parity tests. Live/default orders still require a separate activation experiment.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false,
  "trade_enabled": false
}
```

## Repro

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260529_008_fundamental_growth_rs_vbb_source_agreement.py
```
