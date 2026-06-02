# exp-20260602-027 Post-Earnings High-Liquidity Support

Decision: `accepted_post_earnings_underpriced_high_liquidity_support`.

Single variable: already-selected `POST_EARNINGS_UNDERPRICED_DRIFT_PAPER` candidates with `avg_dollar_volume_20d >= $1B` receive `1.10x` paper notional.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target trades | Supported trades | Support dPnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.5140 | +0.3512 | $117,072.92 | $120,128.53 | $+3,055.61 | -0.0017 | 5 | 3 | $+406.57 |
| mid_weak | 2.1402 | 2.1937 | +0.0535 | $78,110.11 | $78,912.25 | $+802.14 | -0.0017 | 9 | 6 | $+62.78 |
| old_thin | 0.5911 | 0.5980 | +0.0069 | $39,667.96 | $39,868.54 | $+200.58 | -0.0011 | 6 | 4 | $+31.83 |

## Aggregate

- EV delta: `0.4116` (`0.05214`)
- PnL delta: `$4058.33` (`0.01728`)
- target trades: `20`
- supported trades: `13` across `['late_strong', 'mid_weak', 'old_thin']`
- target max single positive share: `0.310893`
- target positive PnL HHI: `0.194626`
- supported max single positive share: `0.334154`
- supported positive PnL HHI: `0.219242`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [],
  "max_drawdown_worse": -0.0011,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": true,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.310893,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": true,
    "positive_pnl_hhi": 0.194626,
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

Shared default-off paper adapter increment. Production can surface the same paper notional support through the existing post-earnings sleeve/report/attribution path. Live/default orders, watchlists, core ranking/sizing/exits, and LLM/news behavior remain unchanged.

No JavaScript was used.
