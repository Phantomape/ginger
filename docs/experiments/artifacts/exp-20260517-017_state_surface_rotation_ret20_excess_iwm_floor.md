# exp-20260517-017 State-Surface Rotation Ret20 Excess IWM Floor

Decision: `accepted_shared_default_off_policy_ret20_excess_iwm_floor`.

Single causal variable: `ret20_excess_iwm_min` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Floor | Gate 4 | dEV | dPnL | EV Improved | EV Regressed | Trades | Max DD Worse | Single Ticker Positive Share |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| identity_no_iwm_floor | FAIL | +0.0000 | $+0.00 | 0 | 0 | 22 | +0.0000 | 31.17% |
| 0.00% | PASS | +0.2234 | $+2,449.90 | 2 | 0 | 22 | +0.0004 | 29.72% |
| 2.50% | PASS | +0.2234 | $+2,449.90 | 2 | 0 | 22 | +0.0004 | 29.72% |
| 5.00% | FAIL | -0.0873 | $-562.35 | 1 | 1 | 21 | +0.0032 | 31.45% |
| 7.50% | FAIL | -0.2862 | $-4,061.48 | 0 | 2 | 21 | +0.0032 | 33.01% |
| 10.00% | FAIL | -0.5191 | $-8,038.48 | 0 | 2 | 20 | +0.0032 | 26.42% |
| 15.00% | FAIL | -0.0287 | $-1,362.07 | 2 | 1 | 18 | +0.0017 | 23.03% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.2798 | 5.4537 | +0.1739 | $121,654.95 | $123,387.98 | $+1,733.03 | 6.18% | 6.22% |
| mid_weak | 2.8003 | 2.8498 | +0.0495 | $89,752.93 | $90,469.80 | $+716.87 | 10.83% | 10.83% |
| old_thin | 0.8626 | 0.8626 | +0.0000 | $49,572.69 | $49,572.69 | $+0.00 | 9.40% | 9.40% |

## Gate 4

```json
{
  "aggregate_ev_delta": 0.2234,
  "aggregate_pnl_delta": 2449.9,
  "by_window": {
    "late_strong": {
      "drawdown_improvement_pct": -0.0004,
      "ev_delta_pct": 0.032937,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.014245,
      "sharpe_daily_delta": 0.08,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "mid_weak": {
      "drawdown_improvement_pct": 0.0,
      "ev_delta_pct": 0.017677,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.007987,
      "sharpe_daily_delta": 0.03,
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
    "aggregate_ev_delta": 0.2234,
    "aggregate_ev_delta_pct": 0.024981,
    "aggregate_pnl_delta": 2449.9,
    "aggregate_pnl_delta_pct": 0.009387,
    "baseline_ev_sum": 8.9427,
    "baseline_pnl_sum": 260980.57,
    "by_window": {
      "late_strong": {
        "expected_value_score": 0.1739,
        "max_drawdown_pct": 0.0004,
        "sharpe_daily": 0.08,
        "survival_rate": 0.0,
        "total_pnl": 1733.03,
        "total_return_pct": 0.0174,
        "trade_count": 0.0,
        "win_rate": 0.037
      },
      "mid_weak": {
        "expected_value_score": 0.0495,
        "max_drawdown_pct": 0.0,
        "sharpe_daily": 0.03,
        "survival_rate": 0.0,
        "total_pnl": 716.87,
        "total_return_pct": 0.0072,
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
      "late_strong": 0.0004,
      "mid_weak": 0.0,
      "old_thin": 0.0
    },
    "max_drawdown_worse_max": 0.0004,
    "windows_ev_improved": 2,
    "windows_ev_regressed": 0,
    "windows_pnl_improved": 2,
    "windows_pnl_regressed": 0
  },
  "drawdown_guard_passed": true,
  "max_drawdown_worse_guardrail": 0.005,
  "max_drawdown_worse_max": 0.0004,
  "max_single_ticker_positive_share": 0.5,
  "minimum_selected_trades": 9,
  "passed": true,
  "sample_guard_passed": true,
  "selected_trade_count": 22,
  "single_ticker_positive_share": 0.29717,
  "windows_ev_improved": 2,
  "windows_ev_regressed": 0
}
```

## Production Impact

Replay-only alpha scout; no shared policy is changed unless Gate 4 passes and a separate shared default-off policy patch is applied.
