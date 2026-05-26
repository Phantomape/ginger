# exp-20260526-015 Sector-Breadth Confirmed Breakout Paper Sleeve

Decision: `rejected_sector_breadth_breakout_sleeve`.

Single variable: a default-off paper sleeve admits at most one liquid breakout candidate per day only when same-sector up-volume breadth confirms participation.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates | Sector days | Tickers | Market-overlap cand. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.9918 | -0.1710 | $117,072.92 | $115,545.72 | $-1,527.20 | +0.0026 | 6 | 17 | 21 | 12 | 11 |
| mid_weak | 2.1402 | 2.2987 | +0.1585 | $78,110.11 | $82,386.62 | $+4,276.51 | -0.0001 | 35 | 94 | 52 | 22 | 49 |
| old_thin | 0.5911 | 0.7351 | +0.1440 | $39,667.96 | $44,548.58 | $+4,880.62 | -0.0083 | 32 | 72 | 44 | 24 | 49 |

## Aggregate

- EV delta: `0.1315` (`0.016658`)
- PnL delta: `$7629.93` (`0.032488`)
- target trades: `73` across `3` windows
- max single positive share: `0.270349`
- positive PnL HHI: `0.161544`

## Sector-Breadth Audit

```json
{
  "late_strong": {
    "candidate_days": 11,
    "candidate_source_tickers": 38,
    "market_breadth_overlap_candidates": 11,
    "raw_liquid_sector_breadth_breakout_hits": 17,
    "rule_version": "sector_breadth_confirmed_breakout_v1",
    "sector_breadth_pass_days": 21,
    "sector_breadth_pass_not_market_breadth_days": 11,
    "trading_days": 123,
    "unique_candidate_tickers": 12
  },
  "mid_weak": {
    "candidate_days": 35,
    "candidate_source_tickers": 38,
    "market_breadth_overlap_candidates": 49,
    "raw_liquid_sector_breadth_breakout_hits": 94,
    "rule_version": "sector_breadth_confirmed_breakout_v1",
    "sector_breadth_pass_days": 52,
    "sector_breadth_pass_not_market_breadth_days": 34,
    "trading_days": 127,
    "unique_candidate_tickers": 22
  },
  "old_thin": {
    "candidate_days": 33,
    "candidate_source_tickers": 38,
    "market_breadth_overlap_candidates": 49,
    "raw_liquid_sector_breadth_breakout_hits": 72,
    "rule_version": "sector_breadth_confirmed_breakout_v1",
    "sector_breadth_pass_days": 44,
    "sector_breadth_pass_not_market_breadth_days": 22,
    "trading_days": 138,
    "unique_candidate_tickers": 24
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0026,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.270349,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.161544,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 73,
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
