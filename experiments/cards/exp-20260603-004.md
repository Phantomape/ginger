# exp-20260603-004 Post-Earnings Sector-Residual Support

Decision: `accepted_post_earnings_sector_residual_support`.

Single variable: already-selected `POST_EARNINGS_UNDERPRICED_DRIFT_PAPER` candidates whose signal-date 20-day return beats their broad sector median receive `1.05x` paper notional.

Baseline: `exp-20260602-027` accepted after metrics.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target trades | Supported trades | Sector dPnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.5140 | 5.5209 | +0.0069 | $120,128.53 | $120,282.89 | $+154.36 | -0.0001 | 5 | 4 | $+154.36 |
| mid_weak | 2.1937 | 2.1948 | +0.0011 | $78,912.25 | $78,947.80 | $+35.55 | -0.0001 | 9 | 6 | $+35.56 |
| old_thin | 0.5980 | 0.5982 | +0.0002 | $39,868.54 | $39,878.58 | $+10.04 | +0.0000 | 6 | 6 | $+10.03 |

## Aggregate

- EV delta: `0.0082` (`0.000987`)
- PnL delta: `$199.95` (`0.000837`)
- target trades: `20`
- supported trades: `16` across `['late_strong', 'mid_weak', 'old_thin']`
- target max single positive share: `0.311752`
- target positive PnL HHI: `0.195532`
- supported max single positive incremental share: `0.324197`
- supported positive incremental HHI: `0.209952`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [],
  "max_drawdown_worse": 0.0,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": true,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.311752,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": true,
    "positive_pnl_hhi": 0.195532,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 20,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 3,
  "windows_ev_regressed": 0,
  "windows_pnl_regressed": 0
}
```

## Production Impact

Shared default-off paper adapter increment. Production can surface the same sector-residual paper notional support through the existing post-earnings sleeve/report/attribution path. Live/default orders, watchlists, core ranking/sizing/exits, and LLM/news behavior remain unchanged.

No JavaScript was used.
