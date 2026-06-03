# exp-20260603-022 Post-Earnings Non-Core-Overlap Shared Support

Decision: `accepted_post_earnings_non_core_overlap_shared_support`.

Single variable: shared default-off adapter input `core_entry_tickers_by_date`; already-selected post-earnings candidates with no same-day core A/B overlap receive `1.05x` paper notional.

Baseline: `exp-20260603-004` accepted after metrics.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target trades | Supported trades | Non-core dPnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.5209 | 5.5416 | +0.0207 | $120,282.89 | $120,469.55 | $+186.66 | -0.0001 | 5 | 3 | $+186.65 |
| mid_weak | 2.1948 | 2.2038 | +0.0090 | $78,947.80 | $78,989.68 | $+41.88 | +0.0000 | 9 | 9 | $+41.88 |
| old_thin | 0.5982 | 0.5985 | +0.0003 | $39,878.58 | $39,897.97 | $+19.39 | -0.0001 | 6 | 4 | $+19.40 |

## Aggregate

- EV delta: `0.03` (`0.003608`)
- PnL delta: `$247.93` (`0.001037`)
- target trades: `20`
- supported trades: `16` across `['late_strong', 'mid_weak', 'old_thin']`
- target max single positive share: `0.311131`
- target positive PnL HHI: `0.195961`
- supported max single positive incremental share: `0.299212`
- supported positive incremental HHI: `0.206554`

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
    "max_single_positive_pnl_share": 0.311131,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": true,
    "positive_pnl_hhi": 0.195961,
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

Shared default-off adapter, run adapter, and report surface changed. This remains paper-only: `trade_enabled=false`; no live/default orders, core entries, ranking, sizing, exits, watchlists, LLM, or news behavior changed.

No JavaScript was used.
