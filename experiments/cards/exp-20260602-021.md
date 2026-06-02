# exp-20260602-021 Sector Peer Moderate-Shock Ticker Cooldown

Decision: `rejected_sector_peer_moderate_shock_ticker_cooldown`.

Single variable: selected same-ticker admission cooldown = `30` calendar days on top of the fixed exp-20260602-020 moderate peer-shock source.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.8658 | -0.2970 | $117,072.92 | $114,219.55 | $-2,853.37 | +0.0010 | 7 | 26 |
| mid_weak | 2.1402 | 2.4343 | +0.2941 | $78,110.11 | $82,802.77 | $+4,692.66 | -0.0042 | 15 | 109 |
| old_thin | 0.5911 | 0.9439 | +0.3528 | $39,667.96 | $49,676.75 | $+10,008.79 | +0.0003 | 8 | 41 |

## Aggregate

- EV delta: `0.3499` (`0.044324`)
- PnL delta: `$11848.08` (`0.050449`)
- target trades: `30` across `3` windows
- max single positive share: `0.487816`
- positive PnL HHI: `0.280687`

## Cooldown Diagnostics

```json
{
  "cooldown_days": 30,
  "cooldown_filtered_by_ticker_sample": {
    "AMD": 2,
    "APP": 7,
    "AVGO": 1,
    "CRDO": 6,
    "DE": 1,
    "DIS": 4,
    "GOOG": 5,
    "MU": 3,
    "NFLX": 6,
    "NVDA": 2,
    "PLTR": 1
  },
  "cooldown_filtered_by_window_sample": {
    "late_strong": 5,
    "mid_weak": 15,
    "old_thin": 18
  },
  "filter_reason_counts_sample": {
    "daily_top1_limit": 97,
    "missing_next_open_or_exit": 10,
    "same_ticker_core_overlap": 1,
    "same_ticker_selected_admission_cooldown": 38
  },
  "selected_by_ticker": {
    "AMD": 1,
    "APP": 2,
    "AVGO": 2,
    "CAT": 2,
    "CRDO": 3,
    "DDOG": 1,
    "DE": 1,
    "DIS": 3,
    "GOOG": 3,
    "MU": 1,
    "NFLX": 1,
    "NVDA": 2,
    "PLTR": 4,
    "RTX": 2,
    "SNOW": 2
  },
  "selected_by_window": {
    "late_strong": 7,
    "mid_weak": 15,
    "old_thin": 8
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
    "window_pnl_regression",
    "target_concentration_failed"
  ],
  "max_drawdown_worse": 0.001,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.487816,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.280687,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 30,
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

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, exit, LLM, or news behavior changed.

No JavaScript was used.
