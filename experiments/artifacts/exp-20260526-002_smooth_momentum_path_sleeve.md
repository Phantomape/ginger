# exp-20260526-002 Smooth Momentum Path Paper Sleeve

Decision: `rejected_smooth_momentum_path_sleeve`.

Single variable: a default-off paper sleeve admits at most one smooth daily-return-path momentum leader per day, enters at next open, and exits after ten trading days.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates | Days |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.1815 | -0.9813 | $117,072.92 | $106,128.84 | $-10,944.08 | +0.0079 | 99 | 242 | 103 |
| mid_weak | 2.1402 | 3.1173 | +0.9771 | $78,110.11 | $96,508.84 | $+18,398.73 | -0.0033 | 97 | 513 | 104 |
| old_thin | 0.5911 | 0.8760 | +0.2849 | $39,667.96 | $47,868.05 | $+8,200.09 | +0.1025 | 103 | 364 | 105 |

## Aggregate

- EV delta: `0.2807` (`0.035558`)
- PnL delta: `$15654.74` (`0.066658`)
- target trades: `299` across `3` windows
- max single positive share: `0.27661`
- positive PnL HHI: `0.14425`

## Smooth Path Audit

```json
{
  "late_strong": {
    "candidate_days": 103,
    "raw_ticker_days_considered": 4674,
    "rule_version": "smooth_momentum_path_v1",
    "smooth_momentum_candidates": 242
  },
  "mid_weak": {
    "candidate_days": 104,
    "raw_ticker_days_considered": 4826,
    "rule_version": "smooth_momentum_path_v1",
    "smooth_momentum_candidates": 513
  },
  "old_thin": {
    "candidate_days": 105,
    "raw_ticker_days_considered": 5244,
    "rule_version": "smooth_momentum_path_v1",
    "smooth_momentum_candidates": 364
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.1025,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.27661,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.14425,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 299,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 2,
  "windows_ev_regressed": 1,
  "windows_pnl_regressed": 1
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
