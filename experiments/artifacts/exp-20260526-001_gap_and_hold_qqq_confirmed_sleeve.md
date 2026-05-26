# exp-20260526-001 Gap-and-Hold QQQ-Confirmed Paper Sleeve

Decision: `rejected_gap_and_hold_qqq_confirmed_sleeve`.

Single variable: a default-off paper sleeve admits at most one daily gap-and-hold candidate per day when QQQ's 20-day return is greater than SPY's 20-day return, enters at next open, and exits after ten trading days.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | QQQ-confirmed | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 3.9289 | -1.2339 | $117,072.92 | $103,942.09 | $-13,130.83 | +0.0083 | 26 | 84 | 159 |
| mid_weak | 2.1402 | 2.4835 | +0.3433 | $78,110.11 | $84,758.27 | $+6,648.16 | -0.0122 | 44 | 113 | 131 |
| old_thin | 0.5911 | 0.7703 | +0.1792 | $39,667.96 | $45,305.36 | $+5,637.40 | +0.0175 | 30 | 72 | 163 |

## Aggregate

- EV delta: `-0.7114` (`-0.090118`)
- PnL delta: `$-845.27` (`-0.003599`)
- target trades: `100` across `3` windows
- max single positive share: `0.308626`
- positive PnL HHI: `0.181136`

## Market Gate Audit

```json
{
  "late_strong": {
    "candidate_days_after_confirmation": 32,
    "market_rule": "QQQ 20d close-to-close return > SPY 20d close-to-close return",
    "missing_market_context": 0,
    "qqq_confirmed_candidates": 84,
    "qqq_not_stronger_than_spy_rejected": 75,
    "raw_gap_and_hold_candidates": 159
  },
  "mid_weak": {
    "candidate_days_after_confirmation": 47,
    "market_rule": "QQQ 20d close-to-close return > SPY 20d close-to-close return",
    "missing_market_context": 0,
    "qqq_confirmed_candidates": 113,
    "qqq_not_stronger_than_spy_rejected": 18,
    "raw_gap_and_hold_candidates": 131
  },
  "old_thin": {
    "candidate_days_after_confirmation": 30,
    "market_rule": "QQQ 20d close-to-close return > SPY 20d close-to-close return",
    "missing_market_context": 0,
    "qqq_confirmed_candidates": 72,
    "qqq_not_stronger_than_spy_rejected": 91,
    "raw_gap_and_hold_candidates": 163
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": false,
  "aggregate_pnl_delta_positive": false,
  "max_drawdown_worse": 0.0175,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.308626,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.181136,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 100,
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
