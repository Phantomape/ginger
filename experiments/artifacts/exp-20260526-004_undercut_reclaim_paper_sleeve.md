# exp-20260526-004 Undercut-and-Reclaim Paper Sleeve

Decision: `rejected_undercut_reclaim_paper_sleeve`.

Single variable: a default-off paper sleeve admits at most one liquid undercut-and-reclaim reversal candidate per day, enters at next open, and exits after ten trading days.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates | Days |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1628 | +0.0000 | $117,072.92 | $117,072.92 | $+0.00 | +0.0000 | 0 | 0 | 0 |
| mid_weak | 2.1402 | 2.1402 | +0.0000 | $78,110.11 | $78,110.11 | $+0.00 | +0.0000 | 0 | 0 | 0 |
| old_thin | 0.5911 | 0.5468 | -0.0443 | $39,667.96 | $37,970.25 | $-1,697.71 | -0.0001 | 5 | 9 | 5 |

## Aggregate

- EV delta: `-0.0443` (`-0.005612`)
- PnL delta: `$-1697.71` (`-0.007229`)
- target trades: `5` across `1` windows
- max single positive share: `1.0`
- positive PnL HHI: `1.0`

## Pattern Audit

```json
{
  "late_strong": {
    "candidate_days": 0,
    "raw_ticker_days_considered": 4674,
    "rule_version": "undercut_reclaim_reversal_v1",
    "undercut_reclaim_candidates": 0
  },
  "mid_weak": {
    "candidate_days": 0,
    "raw_ticker_days_considered": 4826,
    "rule_version": "undercut_reclaim_reversal_v1",
    "undercut_reclaim_candidates": 0
  },
  "old_thin": {
    "candidate_days": 5,
    "raw_ticker_days_considered": 5244,
    "rule_version": "undercut_reclaim_reversal_v1",
    "undercut_reclaim_candidates": 9
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": false,
  "aggregate_pnl_delta_positive": false,
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
  "target_trade_count": 5,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "old_thin"
  ],
  "windows_ev_improved": 0,
  "windows_ev_regressed": 1,
  "windows_pnl_regressed": 1
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
