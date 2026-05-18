# exp-20260517-019 State-Surface Rotation Ret60 Floor

Decision: `rejected_state_surface_ret60_floor`.

Single causal variable: `ret60_min` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Floor | Gate 4 | dEV | dPnL | EV Improved | EV Regressed | Trades | Max DD Worse | Single Ticker Positive Share |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| identity_no_ret60_floor | FAIL | 0.0000 | $0.00 | 0 | 0 | 22 | 0.0000% | 29.72% |
| 0.00% | FAIL | -0.0948 | $-1,322.44 | 1 | 1 | 21 | 0.1300% | 30.92% |
| 5.00% | FAIL | -0.2231 | $-3,215.62 | 1 | 1 | 19 | 0.3100% | 32.80% |
| 10.00% | FAIL | -0.4936 | $-5,994.28 | 0 | 2 | 18 | 0.3600% | 34.26% |
| 15.00% | FAIL | -0.4305 | $-5,599.19 | 0 | 2 | 18 | 0.8900% | 34.80% |
| 20.00% | FAIL | -0.0635 | $-1,615.27 | 1 | 1 | 18 | 0.3600% | 31.20% |

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.4537 | 5.6441 | 0.1904 | $123,387.98 | $125,423.64 | $2,035.66 | 6.22% | 5.96% |
| mid_weak | 2.8498 | 2.5959 | -0.2539 | $90,469.80 | $86,818.87 | $-3,650.93 | 10.83% | 11.19% |
| old_thin | 0.8626 | 0.8626 | 0.0000 | $49,572.69 | $49,572.69 | $0.00 | 9.40% | 9.40% |

## Gate 4

```json
{
  "aggregate_ev_delta": -0.0635,
  "aggregate_pnl_delta": -1615.27,
  "by_window": {
    "late_strong": {
      "drawdown_improvement_pct": 0.0026,
      "ev_delta_pct": 0.034912,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.016498,
      "sharpe_daily_delta": 0.08,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "mid_weak": {
      "drawdown_improvement_pct": -0.0036,
      "ev_delta_pct": -0.089094,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": -0.040355,
      "sharpe_daily_delta": -0.16,
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
    "after_ev_sum": 9.1026,
    "after_pnl_sum": 261815.2,
    "aggregate_ev_delta": -0.0635,
    "aggregate_ev_delta_pct": -0.006928,
    "aggregate_pnl_delta": -1615.27,
    "aggregate_pnl_delta_pct": -0.006132,
    "baseline_ev_sum": 9.1661,
    "baseline_pnl_sum": 263430.47,
    "by_window": {
      "late_strong": {
        "expected_value_score": 0.1904,
        "max_drawdown_pct": -0.0026,
        "sharpe_daily": 0.08,
        "survival_rate": 0.0,
        "total_pnl": 2035.66,
        "total_return_pct": 0.0203,
        "trade_count": -1.0,
        "win_rate": 0.0285
      },
      "mid_weak": {
        "expected_value_score": -0.2539,
        "max_drawdown_pct": 0.0036,
        "sharpe_daily": -0.16,
        "survival_rate": 0.0,
        "total_pnl": -3650.93,
        "total_return_pct": -0.0365,
        "trade_count": -3.0,
        "win_rate": -0.0415
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
      "late_strong": -0.0026,
      "mid_weak": 0.0036,
      "old_thin": 0.0
    },
    "max_drawdown_worse_max": 0.0036,
    "windows_ev_improved": 1,
    "windows_ev_regressed": 1,
    "windows_pnl_improved": 1,
    "windows_pnl_regressed": 1
  },
  "drawdown_guard_passed": true,
  "max_drawdown_worse_guardrail": 0.005,
  "max_drawdown_worse_max": 0.0036,
  "max_single_ticker_positive_share": 0.5,
  "minimum_selected_trades": 9,
  "passed": false,
  "sample_guard_passed": true,
  "selected_trade_count": 18,
  "single_ticker_positive_share": 0.311971,
  "windows_ev_improved": 1,
  "windows_ev_regressed": 1
}
```

## Production Impact

This run is a replay-only alpha scout. Because Gate 4 did not pass, no shared default-off production policy was changed; if a ret60 floor ever passes, it must be added to state_surface_sleeve.py with parity tests before promotion. Live/default orders remain disabled.

No JavaScript was used.
