# exp-20260517-015 State-Surface Rotation Benchmark Gate

Decision: `rejected_rotation_benchmark_gate_threshold`.

Single causal variable: `benchmark_momentum_gate_min_return` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Threshold | Gate 4 | dEV | dPnL | EV Improved | EV Regressed | Trades | Max DD Worse |
|---:|---|---:|---:|---:|---:|---:|---:|
| 0.000% | FAIL | +0.0000 | $+0.00 | 0 | 0 | 19 | +0.0000 |
| 0.500% | FAIL | +0.0000 | $+0.00 | 0 | 0 | 19 | +0.0000 |
| 1.000% | FAIL | -0.0023 | $-689.47 | 0 | 1 | 19 | +0.0004 |
| 1.500% | FAIL | -0.0956 | $-4,185.25 | 1 | 2 | 19 | +0.0004 |
| 2.000% | FAIL | -0.2100 | $-5,577.66 | 1 | 2 | 19 | +0.0004 |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.2972 | 5.2972 | +0.0000 | $121,773.93 | $121,773.93 | $+0.00 | 6.18% | 6.18% |
| mid_weak | 2.8003 | 2.8003 | +0.0000 | $89,752.93 | $89,752.93 | $+0.00 | 10.83% | 10.83% |
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
    "after_ev_sum": 8.9601,
    "after_pnl_sum": 261099.55,
    "aggregate_ev_delta": 0.0,
    "aggregate_ev_delta_pct": 0.0,
    "aggregate_pnl_delta": 0.0,
    "aggregate_pnl_delta_pct": 0.0,
    "baseline_ev_sum": 8.9601,
    "baseline_pnl_sum": 261099.55,
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
  "selected_trade_count": 19,
  "single_ticker_positive_share": 0.320308,
  "windows_ev_improved": 0,
  "windows_ev_regressed": 0
}
```

## Production Impact

Default-off paper state-surface benchmark momentum gate threshold would be changed only if the best non-control variant clears Gate 4; live/default orders remain disabled.
