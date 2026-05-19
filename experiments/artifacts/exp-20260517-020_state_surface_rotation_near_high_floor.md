# exp-20260517-020 State-Surface Rotation Near-High Floor

Decision: `rejected_state_surface_near_high_floor`.

Single causal variable: `near_high_60_min` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Floor | Gate 4 | dEV | dPnL | EV Improved | EV Regressed | Trades | Max DD Worse | Single Ticker Positive Share |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| identity_no_near_high_floor | FAIL | 0.0000 | $0.00 | 0 | 0 | 22 | 0.0000% | 29.72% |
| 90.00% | FAIL | -0.3415 | $-4,568.76 | 0 | 1 | 22 | 0.3000% | 19.72% |
| 92.50% | FAIL | -0.2740 | $-4,047.92 | 1 | 1 | 21 | 0.2000% | 20.18% |
| 95.00% | FAIL | -0.2814 | $-4,055.68 | 0 | 2 | 20 | 0.2000% | 20.92% |
| 97.50% | FAIL | -0.5304 | $-8,731.55 | 0 | 2 | 18 | 0.2100% | 24.52% |
| 99.00% | FAIL | -1.0285 | $-18,150.43 | 0 | 3 | 16 | 0.3600% | 22.12% |

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.4537 | 5.4547 | 0.0010 | $123,387.98 | $123,408.40 | $20.42 | 6.22% | 6.22% |
| mid_weak | 2.8498 | 2.5748 | -0.2750 | $90,469.80 | $86,401.46 | $-4,068.34 | 10.83% | 11.03% |
| old_thin | 0.8626 | 0.8626 | 0.0000 | $49,572.69 | $49,572.69 | $0.00 | 9.40% | 9.40% |

## Gate 4

```json
{
  "aggregate_ev_delta": -0.274,
  "aggregate_pnl_delta": -4047.92,
  "by_window": {
    "late_strong": {
      "drawdown_improvement_pct": 0.0,
      "ev_delta_pct": 0.000183,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.000165,
      "sharpe_daily_delta": 0.0,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "mid_weak": {
      "drawdown_improvement_pct": -0.002,
      "ev_delta_pct": -0.096498,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": -0.044969,
      "sharpe_daily_delta": -0.17,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "old_thin": {
      "drawdown_improvement_pct": 0.0,
      "ev_delta_pct": 0.0,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.0,
      "sharpe_daily_delta": 0.0,
      "trade_count_increased_with_win_rate_not_down": false
    }
  },
  "concentration_guard_passed": true,
  "delta_metrics": {
    "after_ev_sum": 8.8921,
    "after_pnl_sum": 259382.55,
    "aggregate_ev_delta": -0.274,
    "aggregate_ev_delta_pct": -0.029893,
    "aggregate_pnl_delta": -4047.92,
    "aggregate_pnl_delta_pct": -0.015366,
    "baseline_ev_sum": 9.1661,
    "baseline_pnl_sum": 263430.47,
    "by_window": {
      "late_strong": {
        "expected_value_score": 0.001,
        "max_drawdown_pct": 0.0,
        "sharpe_daily": 0.0,
        "survival_rate": 0.0,
        "total_pnl": 20.42,
        "total_return_pct": 0.0002,
        "trade_count": -1.0,
        "win_rate": 0.0285
      },
      "mid_weak": {
        "expected_value_score": -0.275,
        "max_drawdown_pct": 0.002,
        "sharpe_daily": -0.17,
        "survival_rate": 0.0,
        "total_pnl": -4068.34,
        "total_return_pct": -0.0407,
        "trade_count": 0.0,
        "win_rate": 0.0
      },
      "old_thin": {
        "expected_value_score": 0.0,
        "max_drawdown_pct": 0.0,
        "sharpe_daily": 0.0,
        "survival_rate": 0.0,
        "total_pnl": 0.0,
        "total_return_pct": 0.0,
        "trade_count": 0.0,
        "win_rate": 0.0
      }
    },
    "by_window_max_drawdown_delta": {
      "late_strong": 0.0,
      "mid_weak": 0.002,
      "old_thin": 0.0
    },
    "max_drawdown_worse_max": 0.002,
    "windows_ev_improved": 1,
    "windows_ev_regressed": 1,
    "windows_pnl_improved": 1,
    "windows_pnl_regressed": 1
  },
  "drawdown_guard_passed": true,
  "max_drawdown_worse_guardrail": 0.005,
  "max_drawdown_worse_max": 0.002,
  "max_single_ticker_positive_share": 0.5,
  "minimum_selected_trades": 9,
  "passed": false,
  "sample_guard_passed": true,
  "selected_trade_count": 21,
  "single_ticker_positive_share": 0.201765,
  "windows_ev_improved": 1,
  "windows_ev_regressed": 1
}
```

## Production Impact

This run is a replay-only alpha scout. Because Gate 4 did not pass, no shared default-off production policy was changed; if a near_high_60 floor ever passes, it must be added to state_surface_sleeve.py with parity tests before promotion. Live/default orders remain disabled.

No JavaScript was used.
