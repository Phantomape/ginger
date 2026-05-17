# exp-20260517-014 State-Surface Rotation-Only Replay

Decision: `accepted_for_shared_default_off_policy_review`.

Single causal variable: state-surface satellite candidate eligibility is restricted to `rotation_breakout_leadership`. Core strategy logic, event bundle notional/scalars, exits, ranking, sizing, LLM/news, and production orders are unchanged.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Sleeve trades | Sleeve PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.2798 | +0.1170 | $117,072.92 | $121,654.95 | $+4,582.03 | -0.0047 | 9 | $+3,664.49 |
| mid_weak | 2.1402 | 2.8003 | +0.6601 | $78,110.11 | $89,752.93 | $+11,642.82 | -0.0036 | 10 | $+13,468.07 |
| old_thin | 0.5911 | 0.8626 | +0.2715 | $39,667.96 | $49,572.69 | $+9,904.73 | -0.0061 | 3 | $+9,904.73 |

## Gate 4

```json
{
  "aggregate_ev_delta": 1.0486,
  "aggregate_pnl_delta": 26129.58,
  "by_window": {
    "late_strong": {
      "drawdown_improvement_pct": 0.0047,
      "ev_delta_pct": 0.022662,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.039138,
      "sharpe_daily_delta": -0.07,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "mid_weak": {
      "drawdown_improvement_pct": 0.0036,
      "ev_delta_pct": 0.308429,
      "passes_drawdown": false,
      "passes_material_ev": true,
      "passes_pnl": true,
      "passes_sharpe": true,
      "passes_trade_count": true,
      "pnl_delta_pct": 0.149057,
      "sharpe_daily_delta": 0.38,
      "trade_count_increased_with_win_rate_not_down": true
    },
    "old_thin": {
      "drawdown_improvement_pct": 0.0061,
      "ev_delta_pct": 0.459313,
      "passes_drawdown": false,
      "passes_material_ev": true,
      "passes_pnl": true,
      "passes_sharpe": true,
      "passes_trade_count": true,
      "pnl_delta_pct": 0.249691,
      "sharpe_daily_delta": 0.25,
      "trade_count_increased_with_win_rate_not_down": true
    }
  },
  "concentration_guard_passed": true,
  "max_drawdown_worse_max": -0.0036,
  "max_single_ticker_positive_share": 0.5,
  "minimum_selected_trades": 9,
  "passed": true,
  "sample_guard_passed": true,
  "selected_trade_count": 22,
  "single_ticker_positive_share": 0.311727,
  "windows_ev_improved": 3,
  "windows_ev_regressed": 0
}
```

## Production Impact

Promoted only to shared default-off paper policy in `state_surface_sleeve.py`: candidate eligibility is `rotation_breakout_leadership` only, full `scored_candidates` audit remains available, and live/default orders remain disabled.
