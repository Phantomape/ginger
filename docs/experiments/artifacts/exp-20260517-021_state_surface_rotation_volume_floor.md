# exp-20260517-021 State-Surface Rotation Volume Floor

Decision: `rejected_state_surface_volume_floor`.

Single causal variable: `volume_ratio_20_min` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Floor | Gate 4 | dEV | dPnL | EV Improved | EV Regressed | Trades | Max DD Worse | Single Ticker Positive Share |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| identity_no_volume_floor | FAIL | +0.0000 | $+0.00 | 0 | 0 | 22 | +0.0000% | 29.72% |
| 0.50x | FAIL | +0.0698 | $+1,052.22 | 1 | 0 | 21 | +0.0000% | 29.72% |
| 0.75x | FAIL | +0.0188 | $+453.46 | 1 | 1 | 21 | +0.0000% | 30.24% |
| 1.00x | FAIL | -0.0965 | $-1,277.91 | 0 | 2 | 21 | +0.0000% | 31.87% |
| 1.25x | FAIL | -0.8890 | $-15,229.90 | 0 | 3 | 21 | +0.6600% | 19.58% |
| 1.50x | FAIL | -0.5792 | $-12,842.70 | 1 | 2 | 17 | +0.3000% | 30.17% |

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.4537 | 5.4537 | +0.0000 | $123,387.98 | $123,387.98 | $+0.00 | 6.22% | 6.22% |
| mid_weak | 2.8498 | 2.9196 | +0.0698 | $90,469.80 | $91,522.02 | $+1,052.22 | 10.83% | 10.83% |
| old_thin | 0.8626 | 0.8626 | +0.0000 | $49,572.69 | $49,572.69 | $+0.00 | 9.40% | 9.40% |

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
  "concentration_guard_passed": true,
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

This run is a replay-only alpha scout. Because Gate 4 did not pass, no shared default-off production policy was changed; if a volume_ratio_20 floor ever passes, it must be added to state_surface_sleeve.py with parity tests before promotion. Live/default orders remain disabled.

No JavaScript was used.
