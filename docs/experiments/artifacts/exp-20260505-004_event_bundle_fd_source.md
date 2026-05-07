# exp-20260505-004 Event Bundle FD Source Composition

Alpha search. Compares the current three-source default-off event bundle with the same bundle plus the frozen FD/Other Event negative-reaction source.

## Marginal Three-Window Result

| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL | FD trades | FD PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.0085 | 4.1364 | 0.1279 | $86,951.61 | $89,145.88 | $2,194.27 | 5 | $2,194.27 |
| mid_weak | 2.0246 | 2.1085 | 0.0839 | $65,309.93 | $66,723.64 | $1,413.71 | 3 | $1,413.72 |
| old_thin | 0.3516 | 0.3860 | 0.0344 | $26,046.73 | $27,572.91 | $1,526.18 | 4 | $1,526.18 |

## Marginal Gate

```json
{
  "after_bundle_ev_sum": 6.6309,
  "after_bundle_pnl_sum": 183442.43,
  "aggregate_ev_delta": 0.2462,
  "aggregate_ev_delta_pct": 0.038561,
  "aggregate_pnl_delta": 5134.16,
  "aggregate_pnl_delta_pct": 0.028794,
  "baseline_bundle_ev_sum": 6.3847,
  "baseline_bundle_pnl_sum": 178308.27,
  "by_window": {
    "late_strong": {
      "drawdown_improvement_pct": 0.0005,
      "ev_delta_pct": 0.031907,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.025236,
      "sharpe_daily_delta": 0.03,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "mid_weak": {
      "drawdown_improvement_pct": 0.0007,
      "ev_delta_pct": 0.04144,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": true,
      "pnl_delta_pct": 0.021646,
      "sharpe_daily_delta": 0.06,
      "trade_count_increased_with_win_rate_not_down": true
    },
    "old_thin": {
      "drawdown_improvement_pct": -0.0126,
      "ev_delta_pct": 0.097838,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": true,
      "passes_sharpe": false,
      "passes_trade_count": true,
      "pnl_delta_pct": 0.058594,
      "sharpe_daily_delta": 0.05,
      "trade_count_increased_with_win_rate_not_down": true
    }
  },
  "passes_drawdown_any_window": false,
  "passes_material_ev": false,
  "passes_pnl": false,
  "passes_sharpe_any_window": false,
  "passes_trade_count_any_window": true,
  "passes_trade_count_majority_windows": true,
  "satellite_source_acceptance_note": "Trade-count lift is diagnostic for a new satellite source; it is not sufficient by itself because added source capacity mechanically adds trades.",
  "trade_count_gate_windows": 2,
  "windows_ev_improved": 3,
  "windows_ev_regressed": 0,
  "windows_pnl_improved": 3,
  "windows_pnl_regressed": 0
}
```

## Decision

The FD/Other source improved the event bundle directionally, but the marginal lift versus the existing three-source bundle did not clear Gate 4 materiality.
