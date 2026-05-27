# exp-20260527-021 Broad-Market Sector Open-Crowding Support

Decision: `rejected_broad_market_sector_open_crowding_support`.

Single variable: already-selected broad-market paper trades receive a paper-notional support scalar when another same-sector broad-market paper position is still open.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 7.4190 | 7.4244 | +0.0054 | $159,891.81 | $160,009.50 | $+117.69 | 13 |
| mid_weak | 7.3451 | 7.3476 | +0.0025 | $160,023.22 | $160,428.09 | $+404.87 | 15 |
| old_thin | 2.0757 | 2.0690 | -0.0067 | $94,782.99 | $94,910.44 | $+127.45 | 14 |

## Sweep Summary

```json
[
  {
    "adjusted_pnl": 0,
    "adjusted_trade_count": 0,
    "adjusted_windows": [],
    "aggregate_ev_delta": 0.0,
    "aggregate_pnl_delta": 0.0,
    "event_risk": {
      "max_consecutive_losses": 5,
      "tail_loss_share": 0.2945,
      "worst_trade_pct": -0.398773
    },
    "max_drawdown_worse_max": 0.0,
    "min_active_same_sector": 1,
    "notional_added": 0,
    "passed": false,
    "pre_adjusted_pnl": 0,
    "selected_trade_count": 90,
    "single_ticker_positive_share": 0.135208,
    "support_scalar": 1.0,
    "top5_positive_share": 0.427171,
    "variant_name": "baseline_no_sector_open_crowding_support",
    "windows_ev_improved": 0,
    "windows_ev_regressed": 0,
    "windows_pnl_regressed": 0
  },
  {
    "adjusted_pnl": 6824.91,
    "adjusted_trade_count": 42,
    "adjusted_windows": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ],
    "aggregate_ev_delta": -0.0121,
    "aggregate_pnl_delta": 324.99,
    "event_risk": {
      "max_consecutive_losses": 5,
      "tail_loss_share": 0.2946,
      "worst_trade_pct": -0.398773
    },
    "max_drawdown_worse_max": 0.0005,
    "min_active_same_sector": 1,
    "notional_added": 18883.13,
    "passed": false,
    "pre_adjusted_pnl": 6499.92,
    "selected_trade_count": 90,
    "single_ticker_positive_share": 0.132641,
    "support_scalar": 1.05,
    "top5_positive_share": 0.424315,
    "variant_name": "same_sector_active_gte_1_scalar_1p05",
    "windows_ev_improved": 1,
    "windows_ev_regressed": 2,
    "windows_pnl_regressed": 0
  },
  {
    "adjusted_pnl": 7149.92,
    "adjusted_trade_count": 42,
    "adjusted_windows": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ],
    "aggregate_ev_delta": 0.0012,
    "aggregate_pnl_delta": 650.01,
    "event_risk": {
      "max_consecutive_losses": 5,
      "tail_loss_share": 0.2947,
      "worst_trade_pct": -0.398773
    },
    "max_drawdown_worse_max": 0.0009,
    "min_active_same_sector": 1,
    "notional_added": 37766.23,
    "passed": false,
    "pre_adjusted_pnl": 6499.92,
    "selected_trade_count": 90,
    "single_ticker_positive_share": 0.130168,
    "support_scalar": 1.1,
    "top5_positive_share": 0.421566,
    "variant_name": "same_sector_active_gte_1_scalar_1p10",
    "windows_ev_improved": 2,
    "windows_ev_regressed": 1,
    "windows_pnl_regressed": 0
  },
  {
    "adjusted_pnl": 7799.89,
    "adjusted_trade_count": 42,
    "adjusted_windows": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ],
    "aggregate_ev_delta": -0.004,
    "aggregate_pnl_delta": 1299.98,
    "event_risk": {
      "max_consecutive_losses": 5,
      "tail_loss_share": 0.2958,
      "worst_trade_pct": -0.398773
    },
    "max_drawdown_worse_max": 0.0018,
    "min_active_same_sector": 1,
    "notional_added": 75532.5,
    "passed": false,
    "pre_adjusted_pnl": 6499.92,
    "selected_trade_count": 90,
    "single_ticker_positive_share": 0.125491,
    "support_scalar": 1.2,
    "top5_positive_share": 0.416364,
    "variant_name": "same_sector_active_gte_1_scalar_1p20",
    "windows_ev_improved": 1,
    "windows_ev_regressed": 2,
    "windows_pnl_regressed": 0
  },
  {
    "adjusted_pnl": 8774.87,
    "adjusted_trade_count": 42,
    "adjusted_windows": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ],
    "aggregate_ev_delta": -0.0218,
    "aggregate_pnl_delta": 2274.98,
    "event_risk": {
      "max_consecutive_losses": 5,
      "tail_loss_share": 0.3018,
      "worst_trade_pct": -0.398773
    },
    "max_drawdown_worse_max": 0.0031,
    "min_active_same_sector": 1,
    "notional_added": 132181.87,
    "passed": false,
    "pre_adjusted_pnl": 6499.92,
    "selected_trade_count": 90,
    "single_ticker_positive_share": 0.119073,
    "support_scalar": 1.35,
    "top5_positive_share": 0.409226,
    "variant_name": "same_sector_active_gte_1_scalar_1p35",
    "windows_ev_improved": 1,
    "windows_ev_regressed": 2,
    "windows_pnl_regressed": 0
  }
]
```

## Baseline Replay Parity

```json
{
  "passed": true,
  "pnl_drift": {
    "late_strong": 0.0,
    "mid_weak": 0.0,
    "old_thin": 0.0
  },
  "replayed_pnl_by_window": {
    "late_strong": 10307.76,
    "mid_weak": 14607.88,
    "old_thin": 4059.9
  },
  "replayed_trade_count_by_window": {
    "late_strong": 30,
    "mid_weak": 30,
    "old_thin": 30
  },
  "source_experiment_id": "exp-20260520-004",
  "source_pnl_by_window": {
    "late_strong": 10307.76,
    "mid_weak": 14607.88,
    "old_thin": 4059.9
  },
  "source_trade_count_by_window": {
    "late_strong": 30,
    "mid_weak": 30,
    "old_thin": 30
  },
  "trade_count_drift": {
    "late_strong": 0,
    "mid_weak": 0,
    "old_thin": 0
  }
}
```

## Production Impact

```json
{
  "alters_candidate_ranking": false,
  "alters_exits": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "backtester_adapter_changed": false,
  "default_off_paper_only": true,
  "production_signal_path_changed": false,
  "promotion_blocker": "If positive, implement through shared broad_market_paper_sleeve state-aware default-off adapter before retention; this run does not create production/backtest behavior divergence because it does not promote the support scalar.",
  "replay_only": true,
  "research_replay_alters_paper_notional": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false,
  "trade_enabled": false
}
```

No JavaScript was used.
