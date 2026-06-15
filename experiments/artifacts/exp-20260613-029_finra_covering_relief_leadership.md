# exp-20260613-029 FINRA Covering-Relief Leadership

Decision: `rejected_finra_covering_relief_leadership`.

Single variable: require latest published FINRA days-to-cover >= 3.0 and short-interest change pct <= -5.0 before admitting the existing FINRA/IWM/liquid-breakout replay candidate.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates before | Relief rejects |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.2090 | +0.0462 | $117,072.92 | $117,853.19 | $+780.27 | +0.0000 | 1 | 13 | 12 |
| mid_weak | 2.1402 | 2.1223 | -0.0179 | $78,110.11 | $77,742.28 | $-367.83 | +0.0000 | 1 | 18 | 17 |
| old_thin | 0.5911 | 0.5911 | +0.0000 | $39,667.96 | $39,667.96 | $+0.00 | +0.0000 | 0 | 13 | 13 |

## Aggregate

- EV delta: `0.0283` (`0.003585`)
- PnL delta: `$412.44` (`0.001756`)
- target trades: `2` across `2` windows
- max single positive share: `1.0`
- positive PnL HHI: `1.0`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "window_ev_regression",
    "window_pnl_regression",
    "target_sample_too_small",
    "target_window_coverage_too_small",
    "target_concentration_failed"
  ],
  "max_drawdown_worse": 0.0,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 1.0,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 1.0,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 2,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak"
  ],
  "windows_ev_improved": 1,
  "windows_ev_regressed": 1,
  "windows_pnl_improved": 1,
  "windows_pnl_regressed": 1
}
```

## Production Impact

Replay-only scout. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, exits, LLM, or news behavior changed.

No JavaScript was used.
