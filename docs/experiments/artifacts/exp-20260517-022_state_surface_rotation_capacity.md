# exp-20260517-022 State-Surface Rotation Capacity

Decision: `rejected_state_surface_capacity_sweep`.

Single causal variable: `max_active_surface_positions` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Max active | Gate 4 | dEV | dPnL | EV Improved | EV Regressed | Trades | Max DD Worse | Single Ticker Positive Share |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | FAIL | -0.6209 | $-15,245.71 | 1 | 2 | 8 | +0.0039 | 30.42% |
| 2 | FAIL | -0.0489 | $-1,997.21 | 1 | 2 | 15 | +0.0014 | 34.15% |
| 3 | FAIL | +0.0000 | $+0.00 | 0 | 0 | 22 | +0.0000 | 29.72% |
| 4 | FAIL | -0.0761 | $+2,703.07 | 2 | 1 | 27 | +0.0017 | 24.85% |
| 5 | FAIL | -0.0691 | $+6,362.43 | 2 | 1 | 32 | +0.0103 | 22.31% |
| 6 | FAIL | -0.1386 | $+7,572.88 | 2 | 1 | 37 | +0.0164 | 20.66% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Sleeve trades | Capacity skips |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.4537 | 5.5154 | +0.0617 | $123,387.98 | $123,387.17 | $-0.81 | 6.22% | 6.36% | 6 | 82 |
| mid_weak | 2.8498 | 2.7571 | -0.0927 | $90,469.80 | $88,937.34 | $-1,532.46 | 10.83% | 10.87% | 7 | 60 |
| old_thin | 0.8626 | 0.8447 | -0.0179 | $49,572.69 | $49,108.75 | $-463.94 | 9.40% | 9.43% | 2 | 46 |

## Gate 4

```json
{
  "aggregate_ev_delta": -0.0489,
  "aggregate_pnl_delta": -1997.21,
  "by_window": {
    "late_strong": {
      "drawdown_improvement_pct": -0.0014,
      "ev_delta_pct": 0.011313,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": -7e-06,
      "sharpe_daily_delta": 0.05,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "mid_weak": {
      "drawdown_improvement_pct": -0.0004,
      "ev_delta_pct": -0.032529,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": -0.016939,
      "sharpe_daily_delta": -0.05,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "old_thin": {
      "drawdown_improvement_pct": -0.0003,
      "ev_delta_pct": -0.020751,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": -0.009359,
      "sharpe_daily_delta": -0.02,
      "trade_count_increased_with_win_rate_not_down": false
    }
  },
  "concentration_guard_passed": true,
  "delta_metrics": {
    "after_ev_sum": 9.1172,
    "after_pnl_sum": 261433.26,
    "aggregate_ev_delta": -0.0489,
    "aggregate_ev_delta_pct": -0.005335,
    "aggregate_pnl_delta": -1997.21,
    "aggregate_pnl_delta_pct": -0.007582,
    "baseline_ev_sum": 9.1661,
    "baseline_pnl_sum": 263430.47,
    "by_window": {
      "late_strong": {
        "expected_value_score": 0.0617,
        "max_drawdown_pct": 0.0014,
        "sharpe_daily": 0.05,
        "survival_rate": 0.0,
        "total_pnl": -0.81,
        "total_return_pct": 0.0,
        "trade_count": -3.0,
        "win_rate": 0.0093
      },
      "mid_weak": {
        "expected_value_score": -0.0927,
        "max_drawdown_pct": 0.0004,
        "sharpe_daily": -0.05,
        "survival_rate": 0.0,
        "total_pnl": -1532.46,
        "total_return_pct": -0.0153,
        "trade_count": -3.0,
        "win_rate": -0.0058
      },
      "old_thin": {
        "expected_value_score": -0.0179,
        "max_drawdown_pct": 0.0003,
        "sharpe_daily": -0.02,
        "survival_rate": 0.0,
        "total_pnl": -463.94,
        "total_return_pct": -0.0046,
        "trade_count": -1.0,
        "win_rate": -0.0217
      }
    },
    "by_window_max_drawdown_delta": {
      "late_strong": 0.0014,
      "mid_weak": 0.0004,
      "old_thin": 0.0003
    },
    "max_drawdown_worse_max": 0.0014,
    "windows_ev_improved": 1,
    "windows_ev_regressed": 2,
    "windows_pnl_improved": 0,
    "windows_pnl_regressed": 3
  },
  "drawdown_guard_passed": true,
  "max_drawdown_worse_guardrail": 0.005,
  "max_drawdown_worse_max": 0.0014,
  "max_single_ticker_positive_share": 0.5,
  "minimum_selected_trades": 9,
  "passed": false,
  "sample_guard_passed": true,
  "selected_trade_count": 15,
  "single_ticker_positive_share": 0.341544,
  "windows_ev_improved": 1,
  "windows_ev_regressed": 2
}
```

## Production Impact

This run is a replay-only alpha scout. If Gate 4 passes, the active cap must be promoted in shared state_surface_sleeve.py with parity tests before acceptance. Live/default orders remain disabled.

No JavaScript was used.
