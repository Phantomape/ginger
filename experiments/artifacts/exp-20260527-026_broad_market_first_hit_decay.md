# exp-20260527-026 Broad-Market First-Hit Leadership Decay

Decision: `rejected_broad_market_first_hit_decay`.

Single causal variable: skip repeat same-ticker broad-market paper candidates after the ticker's first selected hit in the same canonical replay window.

## Sweep

| Variant | Passed | EV delta | PnL delta | Windows EV +/- | Replaced | Trades | Tickers | Max DD drift |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| accepted_repeat_allowed | False | 0.0000 | $0.00 | 0/0 | 0 | 90 | 68 | 0.0000 |
| fresh_first_hit_only | False | -0.4602 | $-5,586.95 | 0/3 | 13 | 90 | 78 | 0.0000 |

## Gate 4

{
  "aggregate_ev_delta": -0.4602,
  "aggregate_pnl_delta": -5586.95,
  "concentration_guard_passed": true,
  "drawdown_guard_passed": true,
  "materiality_guard_passed": false,
  "max_drawdown_worse_guardrail": 0.005,
  "max_drawdown_worse_max": 0.0,
  "max_single_ticker_positive_share": 0.5,
  "max_top5_positive_share": 0.7,
  "minimum_ev_improved_windows": 3,
  "minimum_relative_ev_improvement": 0.1,
  "minimum_replaced_trades": 4,
  "minimum_replaced_windows": 2,
  "minimum_selected_trades": 30,
  "minimum_selected_windows": 3,
  "passed": false,
  "relative_ev_improvement": -0.027328,
  "replaced_trade_count": 13,
  "replaced_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "replacement_guard_passed": true,
  "sample_guard_passed": true,
  "selected_trade_count": 90,
  "selected_windows": 3,
  "single_ticker_positive_share": 0.151087,
  "top5_positive_share": 0.389687,
  "window_guard_passed": true,
  "windows_ev_improved": 0,
  "windows_ev_regressed": 3,
  "windows_pnl_improved": 0,
  "windows_pnl_regressed": 3
}

## Interpretation

First-hit freshness is retained only if it materially improves all three windows. A positive replay result remains non-promotable until the shared default-off broad-market adapter can expose the same append-only freshness state with warmup; this run changes no production or backtest behavior.

## Repro

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260527_026_broad_market_first_hit_decay.py
```
