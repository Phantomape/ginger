# exp-20260527-013 RS-Line New-High Paper Sleeve

Decision: `rejected_rs_line_new_high_paper_sleeve`.

Single variable: a default-off paper sleeve admits at most one liquid candidate per day when its SPY-relative strength line makes a fresh 60-day high while price is near but not through its 20-day high.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates | Days | Tickers |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.2985 | -0.8643 | $117,072.92 | $109,099.90 | $-7,973.02 | +0.0018 | 61 | 112 | 63 | 22 |
| mid_weak | 2.1402 | 3.7685 | +1.6283 | $78,110.11 | $104,677.52 | $+26,567.41 | -0.0082 | 74 | 150 | 78 | 30 |
| old_thin | 0.5911 | 0.6999 | +0.1088 | $39,667.96 | $41,660.53 | $+1,992.57 | +0.1165 | 83 | 167 | 89 | 31 |

## Aggregate

- EV delta: `0.8728` (`0.110564`)
- PnL delta: `$20586.96` (`0.08766`)
- target trades: `218` across `3` windows
- max single positive share: `0.281102`
- positive PnL HHI: `0.141774`

## RS-Line Audit

```json
{
  "late_strong": {
    "candidate_days": 63,
    "candidate_source_tickers": 38,
    "context_checked": 4674,
    "near_price_high_passed": 126,
    "raw_rs_line_candidates": 112,
    "rs_line_new_high_hits": 297,
    "rule_version": "rs_line_new_high_near_price_high_v1",
    "trading_days": 123,
    "trend_passed": 297,
    "unique_candidate_tickers": 22
  },
  "mid_weak": {
    "candidate_days": 78,
    "candidate_source_tickers": 38,
    "context_checked": 4826,
    "near_price_high_passed": 169,
    "raw_rs_line_candidates": 150,
    "rs_line_new_high_hits": 446,
    "rule_version": "rs_line_new_high_near_price_high_v1",
    "trading_days": 127,
    "trend_passed": 446,
    "unique_candidate_tickers": 30
  },
  "old_thin": {
    "candidate_days": 89,
    "candidate_source_tickers": 38,
    "context_checked": 5244,
    "near_price_high_passed": 195,
    "raw_rs_line_candidates": 167,
    "rs_line_new_high_hits": 459,
    "rule_version": "rs_line_new_high_near_price_high_v1",
    "trading_days": 138,
    "trend_passed": 438,
    "unique_candidate_tickers": 31
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.1165,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.281102,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.141774,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 218,
  "target_trade_count_min": 30,
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
