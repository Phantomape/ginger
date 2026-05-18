# exp-20260517-023 State-Surface Rotation Ret5 Floor

Decision: `rejected_underpowered_state_surface_ret5_floor`.

Single causal variable: `ret5_min` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Floor | Gate 4 | dEV | dPnL | EV Improved | EV Regressed | Trades | Changed Trades | Max DD Worse | Single Ticker Positive Share |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| identity_no_ret5_floor | FAIL | +0.0000 | $+0.00 | 0 | 0 | 22 | 0 | +0.0000% | 29.72% |
| -0.050 | FAIL | +0.0698 | $+1,052.22 | 1 | 0 | 21 | 1 | +0.0000% | 29.72% |
| -0.025 | FAIL | +0.0698 | $+1,052.22 | 1 | 0 | 21 | 1 | +0.0000% | 29.72% |
| +0.000 | FAIL | -0.0374 | $-748.36 | 0 | 2 | 21 | 7 | +0.0000% | 18.56% |
| +0.025 | FAIL | -0.2893 | $-4,802.87 | 0 | 3 | 19 | 15 | +0.1300% | 14.73% |
| +0.050 | FAIL | -0.5388 | $-9,085.68 | 0 | 3 | 18 | 18 | +0.1300% | 16.61% |
| +0.100 | FAIL | -0.4182 | $-8,455.18 | 0 | 3 | 16 | 24 | +0.1200% | 30.10% |
| +0.125 | FAIL | -0.2123 | $-4,128.59 | 2 | 1 | 15 | 25 | +0.1000% | 26.62% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Sleeve Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.4537 | 5.4537 | +0.0000 | $123,387.98 | $123,387.98 | $+0.00 | 6.22% | 6.22% | 9 |
| mid_weak | 2.8498 | 2.9196 | +0.0698 | $90,469.80 | $91,522.02 | $+1,052.22 | 10.83% | 10.83% | 9 |
| old_thin | 0.8626 | 0.8626 | +0.0000 | $49,572.69 | $49,572.69 | $+0.00 | 9.40% | 9.40% | 3 |

## Gate 4

```json
{
  "aggregate_ev_delta": 0.0698,
  "aggregate_pnl_delta": 1052.22,
  "by_window": {
    "late_strong": {
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
    },
    "mid_weak": {
      "drawdown_improvement_pct": 0.0,
      "ev_delta_pct": 0.024493,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.011631,
      "sharpe_daily_delta": 0.04,
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
  "changed_selected_trade_count": 1,
  "concentration_guard_passed": true,
  "contrast_guard_passed": false,
  "delta_metrics": {
    "after_ev_sum": 9.2359,
    "after_pnl_sum": 264482.69,
    "aggregate_ev_delta": 0.0698,
    "aggregate_ev_delta_pct": 0.007615,
    "aggregate_pnl_delta": 1052.22,
    "aggregate_pnl_delta_pct": 0.003994,
    "baseline_ev_sum": 9.1661,
    "baseline_pnl_sum": 263430.47,
    "by_window": {
      "late_strong": {
        "expected_value_score": 0.0,
        "max_drawdown_pct": 0.0,
        "sharpe_daily": 0.0,
        "survival_rate": 0.0,
        "total_pnl": 0.0,
        "total_return_pct": 0.0,
        "trade_count": 0.0,
        "win_rate": 0.0
      },
      "mid_weak": {
        "expected_value_score": 0.0698,
        "max_drawdown_pct": 0.0,
        "sharpe_daily": 0.04,
        "survival_rate": 0.0,
        "total_pnl": 1052.22,
        "total_return_pct": 0.0105,
        "trade_count": -1.0,
        "win_rate": 0.0204
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
      "mid_weak": 0.0,
      "old_thin": 0.0
    },
    "max_drawdown_worse_max": 0.0,
    "windows_ev_improved": 1,
    "windows_ev_regressed": 0,
    "windows_pnl_improved": 1,
    "windows_pnl_regressed": 0
  },
  "drawdown_guard_passed": true,
  "max_drawdown_worse_guardrail": 0.005,
  "max_drawdown_worse_max": 0.0,
  "max_single_ticker_positive_share": 0.5,
  "minimum_changed_selected_trades": 3,
  "minimum_selected_trades": 9,
  "passed": false,
  "sample_guard_passed": true,
  "selected_trade_count": 21,
  "single_ticker_positive_share": 0.29717,
  "windows_ev_improved": 1,
  "windows_ev_regressed": 0
}
```

## Production Impact

This run is a replay-only alpha scout. Because Gate 4 did not pass, no shared default-off production policy was changed. If a ret5 floor ever passes, it must be added to state_surface_sleeve.py with parity tests before promotion. Live/default orders remain disabled.

No JavaScript was used.
