# exp-20260518-001 State-Surface Rotation Hold Days

Decision: `rejected_state_surface_hold_days`.

Single causal variable: `hold_days` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Hold days | Gate 4 | dEV | dPnL | EV Improved | EV Regressed | Trades | Max DD Worse | Single Ticker Positive Share |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 5 | FAIL | -1.4066 | $-21,593.84 | 0 | 3 | 57 | +0.4300% | 23.10% |
| 10 | FAIL | -0.4043 | $-9,887.38 | 1 | 2 | 36 | +0.3100% | 20.16% |
| 15 | FAIL | -0.2536 | $-6,685.69 | 1 | 2 | 30 | +0.3000% | 21.76% |
| 20 | FAIL | +0.0000 | $+0.00 | 0 | 0 | 24 | +0.0000% | 34.04% |
| 25 | FAIL | +0.2717 | $+3,186.77 | 2 | 1 | 24 | +0.0100% | 29.43% |
| 30 | FAIL | -0.4276 | $-6,749.66 | 0 | 3 | 21 | +0.0500% | 31.07% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Sleeve trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.6541 | 5.9314 | +0.2773 | $125,367.73 | $128,385.23 | $+3,017.50 | 6.35% | 6.22% | 9 |
| mid_weak | 3.0489 | 3.0522 | +0.0033 | $93,811.54 | $94,204.09 | $+392.55 | 10.83% | 10.80% | 12 |
| old_thin | 0.8626 | 0.8537 | -0.0089 | $49,572.69 | $49,349.41 | $-223.28 | 9.40% | 9.41% | 3 |

## Gate 4

```json
{
  "aggregate_ev_delta": 0.2717,
  "aggregate_pnl_delta": 3186.77,
  "by_window": {
    "late_strong": {
      "drawdown_improvement_pct": 0.0013,
      "ev_delta_pct": 0.049044,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": true,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.024069,
      "sharpe_daily_delta": 0.11,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "mid_weak": {
      "drawdown_improvement_pct": 0.0003,
      "ev_delta_pct": 0.001082,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.004184,
      "sharpe_daily_delta": -0.01,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "old_thin": {
      "drawdown_improvement_pct": -0.0001,
      "ev_delta_pct": -0.010318,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": -0.004504,
      "sharpe_daily_delta": -0.01,
      "trade_count_increased_with_win_rate_not_down": false
    }
  },
  "concentration_guard_passed": true,
  "delta_metrics": {
    "after_ev_sum": 9.8373,
    "after_pnl_sum": 271938.73,
    "aggregate_ev_delta": 0.2717,
    "aggregate_ev_delta_pct": 0.028404,
    "aggregate_pnl_delta": 3186.77,
    "aggregate_pnl_delta_pct": 0.011858,
    "baseline_ev_sum": 9.5656,
    "baseline_pnl_sum": 268751.96,
    "by_window": {
      "late_strong": {
        "expected_value_score": 0.2773,
        "max_drawdown_pct": -0.0013,
        "sharpe_daily": 0.11,
        "survival_rate": 0.0,
        "total_pnl": 3017.5,
        "total_return_pct": 0.0302,
        "trade_count": 0.0,
        "win_rate": 0.0741
      },
      "mid_weak": {
        "expected_value_score": 0.0033,
        "max_drawdown_pct": -0.0003,
        "sharpe_daily": -0.01,
        "survival_rate": 0.0,
        "total_pnl": 392.55,
        "total_return_pct": 0.0039,
        "trade_count": 0.0,
        "win_rate": -0.0606
      },
      "old_thin": {
        "expected_value_score": -0.0089,
        "max_drawdown_pct": 0.0001,
        "sharpe_daily": -0.01,
        "survival_rate": 0.0,
        "total_pnl": -223.28,
        "total_return_pct": -0.0022,
        "trade_count": 0.0,
        "win_rate": 0.0
      }
    },
    "by_window_max_drawdown_delta": {
      "late_strong": -0.0013,
      "mid_weak": -0.0003,
      "old_thin": 0.0001
    },
    "max_drawdown_worse_max": 0.0001,
    "windows_ev_improved": 2,
    "windows_ev_regressed": 1,
    "windows_pnl_improved": 2,
    "windows_pnl_regressed": 1
  },
  "drawdown_guard_passed": true,
  "max_drawdown_worse_guardrail": 0.005,
  "max_drawdown_worse_max": 0.0001,
  "max_single_ticker_positive_share": 0.5,
  "minimum_selected_trades": 9,
  "passed": false,
  "sample_guard_passed": true,
  "selected_trade_count": 24,
  "single_ticker_positive_share": 0.29431,
  "windows_ev_improved": 2,
  "windows_ev_regressed": 1
}
```

No JavaScript was used.
