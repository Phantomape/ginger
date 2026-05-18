# exp-20260517-017 State-Surface Rotation Ret20 Excess IWM Floor

Decision: `rejected_state_surface_ret20_excess_iwm_floor`.

Single causal variable: `ret20_excess_iwm_min` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Floor | Gate 4 | dEV | dPnL | EV Improved | EV Regressed | Trades | Max DD Worse | Single Ticker Positive Share |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| identity_no_iwm_floor | FAIL | +0.0000 | $+0.00 | 0 | 0 | 22 | +0.0000 | 29.72% |
| 0.00% | FAIL | +0.0000 | $+0.00 | 0 | 0 | 22 | +0.0000 | 29.72% |
| 2.50% | FAIL | +0.0000 | $+0.00 | 0 | 0 | 22 | +0.0000 | 29.72% |
| 5.00% | FAIL | -0.3107 | $-3,012.25 | 0 | 2 | 21 | +0.0028 | 31.45% |
| 7.50% | FAIL | -0.5096 | $-6,511.38 | 0 | 2 | 21 | +0.0028 | 33.01% |
| 10.00% | FAIL | -0.7425 | $-10,488.38 | 0 | 2 | 20 | +0.0028 | 26.42% |
| 15.00% | FAIL | -0.2521 | $-3,811.97 | 1 | 2 | 18 | +0.0013 | 23.03% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.4537 | 5.4537 | +0.0000 | $123,387.98 | $123,387.98 | $+0.00 | 6.22% | 6.22% |
| mid_weak | 2.8498 | 2.8498 | +0.0000 | $90,469.80 | $90,469.80 | $+0.00 | 10.83% | 10.83% |
| old_thin | 0.8626 | 0.8626 | +0.0000 | $49,572.69 | $49,572.69 | $+0.00 | 9.40% | 9.40% |

## Gate 4

```json
{
  "aggregate_ev_delta": 0.0,
  "aggregate_pnl_delta": 0.0,
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
    "after_ev_sum": 9.1661,
    "after_pnl_sum": 263430.47,
    "aggregate_ev_delta": 0.0,
    "aggregate_ev_delta_pct": 0.0,
    "aggregate_pnl_delta": 0.0,
    "aggregate_pnl_delta_pct": 0.0,
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
        "expected_value_score": 0.0,
        "max_drawdown_pct": 0.0,
        "sharpe_daily": 0.0,
        "survival_rate": 0.0,
        "total_pnl": 0.0,
        "total_return_pct": 0.0,
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
      "mid_weak": 0.0,
      "old_thin": 0.0
    },
    "max_drawdown_worse_max": 0.0,
    "windows_ev_improved": 0,
    "windows_ev_regressed": 0,
    "windows_pnl_improved": 0,
    "windows_pnl_regressed": 0
  },
  "drawdown_guard_passed": true,
  "max_drawdown_worse_guardrail": 0.005,
  "max_drawdown_worse_max": 0.0,
  "max_single_ticker_positive_share": 0.5,
  "minimum_selected_trades": 9,
  "passed": false,
  "sample_guard_passed": true,
  "selected_trade_count": 22,
  "single_ticker_positive_share": 0.29717,
  "windows_ev_improved": 0,
  "windows_ev_regressed": 0
}
```

## Production Impact

Replay-only alpha scout; no shared policy is changed unless Gate 4 passes and a separate shared default-off policy patch is applied.
