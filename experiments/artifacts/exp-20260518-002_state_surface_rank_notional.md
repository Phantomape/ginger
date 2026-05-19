# exp-20260518-002 State-Surface Rank Notional

Decision: `accepted_shared_default_off_policy_rank_notional`.

Single causal variable: `rank_notional_profile` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Profile | Gate 4 | dEV | dPnL | EV Improved | EV Regressed | Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| flat_100 | FAIL | +0.0000 | $+0.00 | 0 | 0 | 24 | +0.0000% | 34.04% |
| mild_top_heavy | PASS | +0.2458 | $+5,059.06 | 3 | 0 | 24 | +0.0300% | 33.01% |
| strong_top_heavy | PASS | +0.4905 | $+10,118.13 | 3 | 0 | 24 | +0.0700% | 32.22% |
| top2_heavy | PASS | +0.4419 | $+9,194.46 | 3 | 0 | 24 | +0.0200% | 34.35% |
| mild_tail_heavy | FAIL | -0.2509 | $-5,059.08 | 0 | 3 | 24 | +0.0900% | 35.48% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Sleeve trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.6541 | 5.7865 | +0.1324 | $125,367.73 | $127,738.19 | $+2,370.46 | 6.35% | 6.42% | 9 |
| mid_weak | 3.0489 | 3.3142 | +0.2653 | $93,811.54 | $98,345.58 | $+4,534.04 | 10.83% | 10.74% | 12 |
| old_thin | 0.8626 | 0.9554 | +0.0928 | $49,572.69 | $52,786.32 | $+3,213.63 | 9.40% | 9.22% | 3 |

## Gate 4

```json
{
  "aggregate_ev_delta": 0.4905,
  "aggregate_pnl_delta": 10118.13,
  "by_window": {
    "late_strong": {
      "drawdown_improvement_pct": -0.0007,
      "ev_delta_pct": 0.023417,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.018908,
      "sharpe_daily_delta": 0.02,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "mid_weak": {
      "drawdown_improvement_pct": 0.0009,
      "ev_delta_pct": 0.087015,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": true,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.048331,
      "sharpe_daily_delta": 0.12,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "old_thin": {
      "drawdown_improvement_pct": 0.0018,
      "ev_delta_pct": 0.107582,
      "passes_drawdown": false,
      "passes_material_ev": true,
      "passes_pnl": true,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.064827,
      "sharpe_daily_delta": 0.07,
      "trade_count_increased_with_win_rate_not_down": false
    }
  },
  "concentration_guard_passed": true,
  "delta_metrics": {
    "after_ev_sum": 10.0561,
    "after_pnl_sum": 278870.09,
    "aggregate_ev_delta": 0.4905,
    "aggregate_ev_delta_pct": 0.051277,
    "aggregate_pnl_delta": 10118.13,
    "aggregate_pnl_delta_pct": 0.037649,
    "baseline_ev_sum": 9.5656,
    "baseline_pnl_sum": 268751.96,
    "by_window": {
      "late_strong": {
        "expected_value_score": 0.1324,
        "max_drawdown_pct": 0.0007,
        "sharpe_daily": 0.02,
        "survival_rate": 0.0,
        "total_pnl": 2370.46,
        "total_return_pct": 0.0237,
        "trade_count": 0.0,
        "win_rate": 0.0
      },
      "mid_weak": {
        "expected_value_score": 0.2653,
        "max_drawdown_pct": -0.0009,
        "sharpe_daily": 0.12,
        "survival_rate": 0.0,
        "total_pnl": 4534.04,
        "total_return_pct": 0.0454,
        "trade_count": 0.0,
        "win_rate": 0.0
      },
      "old_thin": {
        "expected_value_score": 0.0928,
        "max_drawdown_pct": -0.0018,
        "sharpe_daily": 0.07,
        "survival_rate": 0.0,
        "total_pnl": 3213.63,
        "total_return_pct": 0.0322,
        "trade_count": 0.0,
        "win_rate": 0.0
      }
    },
    "by_window_max_drawdown_delta": {
      "late_strong": 0.0007,
      "mid_weak": -0.0009,
      "old_thin": -0.0018
    },
    "max_drawdown_worse_max": 0.0007,
    "windows_ev_improved": 3,
    "windows_ev_regressed": 0,
    "windows_pnl_improved": 3,
    "windows_pnl_regressed": 0
  },
  "drawdown_guard_passed": true,
  "max_drawdown_worse_guardrail": 0.005,
  "max_drawdown_worse_max": 0.0007,
  "max_single_ticker_positive_share": 0.5,
  "minimum_selected_trades": 9,
  "passed": true,
  "sample_guard_passed": true,
  "selected_trade_count": 24,
  "single_ticker_positive_share": 0.322212,
  "windows_ev_improved": 3,
  "windows_ev_regressed": 0
}
```

No JavaScript was used.
