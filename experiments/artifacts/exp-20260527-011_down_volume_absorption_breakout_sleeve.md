# exp-20260527-011 Down-Volume Absorption Breakout Paper Sleeve

Decision: `rejected_down_volume_absorption_breakout_sleeve`.

Single variable: a default-off paper sleeve admits at most one liquid breakout candidate per day when the prior 10 trading days show upside volume dominance and limited downside volume.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates | Passes | Tickers |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 3.9601 | -1.2027 | $117,072.92 | $101,540.99 | $-15,531.93 | +0.0022 | 56 | 162 | 125 | 31 |
| mid_weak | 2.1402 | 2.3898 | +0.2496 | $78,110.11 | $83,562.00 | $+5,451.89 | -0.0020 | 82 | 270 | 205 | 36 |
| old_thin | 0.5911 | 0.4998 | -0.0913 | $39,667.96 | $34,954.95 | $-4,713.01 | +0.0528 | 68 | 206 | 159 | 37 |

## Aggregate

- EV delta: `-1.0444` (`-0.132301`)
- PnL delta: `$-14793.05` (`-0.062989`)
- target trades: `206` across `3` windows
- max single positive share: `0.148327`
- positive PnL HHI: `0.093266`

## Absorption Audit

```json
{
  "late_strong": {
    "absorption_context_checked": 162,
    "absorption_context_passed": 125,
    "candidate_days": 66,
    "candidate_source_tickers": 39,
    "raw_liquid_breakout_hits": 162,
    "rule_version": "down_volume_absorption_breakout_v1",
    "trading_days": 123,
    "unique_candidate_tickers": 31
  },
  "mid_weak": {
    "absorption_context_checked": 270,
    "absorption_context_passed": 205,
    "candidate_days": 86,
    "candidate_source_tickers": 38,
    "raw_liquid_breakout_hits": 270,
    "rule_version": "down_volume_absorption_breakout_v1",
    "trading_days": 127,
    "unique_candidate_tickers": 36
  },
  "old_thin": {
    "absorption_context_checked": 206,
    "absorption_context_passed": 159,
    "candidate_days": 70,
    "candidate_source_tickers": 38,
    "raw_liquid_breakout_hits": 206,
    "rule_version": "down_volume_absorption_breakout_v1",
    "trading_days": 138,
    "unique_candidate_tickers": 37
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": false,
  "aggregate_pnl_delta_positive": false,
  "max_drawdown_worse": 0.0528,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.148327,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.093266,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 206,
  "target_trade_count_min": 30,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 1,
  "windows_ev_regressed": 2,
  "windows_pnl_regressed": 2
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
