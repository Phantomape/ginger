# exp-20260526-005 Long-Base Breakout Paper Sleeve

Decision: `rejected_long_base_breakout_paper_sleeve`.

Single variable: a default-off paper sleeve admits at most one liquid long-base 63-day breakout candidate per day, enters at next open, and exits after ten trading days.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates | Days | Tickers |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.6931 | -0.4697 | $117,072.92 | $111,735.74 | $-5,337.18 | +0.0012 | 8 | 12 | 11 | 11 |
| mid_weak | 2.1402 | 2.3538 | +0.2136 | $78,110.11 | $82,301.99 | $+4,191.88 | -0.0001 | 10 | 10 | 10 | 10 |
| old_thin | 0.5911 | 0.7649 | +0.1738 | $39,667.96 | $45,529.02 | $+5,861.06 | -0.0027 | 15 | 18 | 16 | 16 |

## Aggregate

- EV delta: `-0.0823` (`-0.010426`)
- PnL delta: `$4715.76` (`0.02008`)
- target trades: `33` across `3` windows
- max single positive share: `0.34393`
- positive PnL HHI: `0.21325`

## Pattern Audit

```json
{
  "late_strong": {
    "candidate_days": 11,
    "long_base_breakout_candidates": 12,
    "raw_ticker_days_considered": 5102,
    "rule_version": "long_base_63d_breakout_v1",
    "source_tickers_considered": 42,
    "unique_candidate_tickers": 11
  },
  "mid_weak": {
    "candidate_days": 10,
    "long_base_breakout_candidates": 10,
    "raw_ticker_days_considered": 4826,
    "rule_version": "long_base_63d_breakout_v1",
    "source_tickers_considered": 38,
    "unique_candidate_tickers": 10
  },
  "old_thin": {
    "candidate_days": 16,
    "long_base_breakout_candidates": 18,
    "raw_ticker_days_considered": 5244,
    "rule_version": "long_base_63d_breakout_v1",
    "source_tickers_considered": 38,
    "unique_candidate_tickers": 16
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": false,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0012,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.34393,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.21325,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 33,
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
