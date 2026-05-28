# exp-20260528-001 Broad-Market Repeat-Leadership Support

Decision: `rejected_broad_market_repeat_leadership_support`.

Single causal variable: paper-notional scalar for selected broad-market candidates whose ticker already had a prior selected hit in the same canonical replay window.

## Sweep

| Variant | Gate 4 | Scalar | Adjusted | dEV | dPnL | Rel EV | EV +/- | PnL Regr | Max DD Drift |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|
| repeat_scalar_1p00_baseline_replay | FAIL | 1.000 | 0 | +0.0000 | $+0.00 | +0.00% | 0/0 | 0 | +0.0000% |
| repeat_scalar_1p025 | FAIL | 1.025 | 10 | +0.0090 | $-0.81 | +0.05% | 2/1 | 1 | +0.0100% |
| repeat_scalar_1p05 | FAIL | 1.050 | 10 | +0.0116 | $-1.62 | +0.07% | 2/1 | 1 | +0.0200% |
| repeat_scalar_1p075 | FAIL | 1.075 | 10 | +0.0141 | $-2.43 | +0.08% | 2/1 | 1 | +0.0300% |
| repeat_scalar_1p1 | FAIL | 1.100 | 10 | +0.0167 | $-3.25 | +0.10% | 2/1 | 1 | +0.0400% |
| repeat_scalar_1p15 | FAIL | 1.150 | 10 | +0.0123 | $-4.87 | +0.07% | 2/1 | 1 | +0.0600% |
| repeat_scalar_1p25 | FAIL | 1.250 | 10 | +0.0224 | $-8.11 | +0.13% | 2/1 | 1 | +0.1000% |
| repeat_scalar_1p5 | FAIL | 1.500 | 10 | +0.0454 | $-16.25 | +0.27% | 2/1 | 1 | +0.2000% |

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 7.4190 | 7.4921 | +0.0731 | $159,891.81 | $160,773.78 | $+881.97 |
| mid_weak | 7.3451 | 7.4005 | +0.0554 | $160,023.22 | $161,230.81 | $+1,207.59 |
| old_thin | 2.0757 | 1.9926 | -0.0831 | $94,782.99 | $92,677.18 | $-2,105.81 |

## Gate 4

```json
{
  "adjusted_guard_passed": true,
  "adjusted_trade_count": 10,
  "adjusted_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "aggregate_ev_delta": 0.0454,
  "aggregate_pnl_delta": -16.25,
  "baseline_replay_parity_passed": true,
  "concentration_guard_passed": true,
  "drawdown_guard_passed": true,
  "materiality_guard_passed": false,
  "max_drawdown_worse_guardrail": 0.005,
  "max_drawdown_worse_max": 0.002,
  "max_single_ticker_positive_share": 0.5,
  "max_top5_positive_share": 0.7,
  "minimum_adjusted_trades": 8,
  "minimum_adjusted_windows": 3,
  "minimum_ev_improved_windows": 3,
  "minimum_relative_ev_improvement": 0.1,
  "minimum_selected_trades": 30,
  "minimum_selected_windows": 3,
  "passed": false,
  "promotion_blocked_without_shared_adapter": false,
  "relative_ev_improvement": 0.002696,
  "sample_guard_passed": true,
  "selected_trade_count": 90,
  "selected_windows": 3,
  "single_ticker_positive_share": 0.1362,
  "top5_positive_share": 0.46318,
  "window_guard_passed": true,
  "windows_ev_improved": 2,
  "windows_ev_regressed": 1,
  "windows_pnl_improved": 2,
  "windows_pnl_regressed": 1
}
```

## Production Impact

```json
{
  "alters_candidate_ranking": false,
  "alters_exits": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_sizing": false,
  "backtester_adapter_changed": false,
  "default_off_paper_only": true,
  "live_order_path_changed": false,
  "production_signal_path_changed": false,
  "promotion_requirement": "Positive evidence is not retained until the shared broad-market paper adapter can expose identical append-only repeat-hit state and parity checks.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false,
  "trade_enabled": false
}
```

## Interpretation

Repeat-hit support is retainable only if it clears the stricter state-surface scalar bar. A positive replay result remains non-promotable until shared adapter parity is implemented; this run changes no production or backtest behavior.

## Repro

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260528_001_broad_market_repeat_leadership_support.py
```

No JavaScript was used.
