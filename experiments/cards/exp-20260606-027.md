# exp-20260606-027 Macro Stress Resilient Leadership Candidate Pool

Status: `rejected`
Decision: `rejected_macro_stress_resilient_leadership_candidate_pool`

## Hypothesis

Official CPI/FOMC/NFP stress days where SPY and QQQ both sell off and close weak may identify resilient liquid stock leaders with cleaner next-open continuation than generic broad-pressure OHLCV filters.

## Gate 4

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Macro stress days | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1317 | -0.0311 | $117,072.92 | $116,632.25 | $-440.67 | +0.0000 | 2 | 4 |
| mid_weak | 2.1402 | 2.1377 | -0.0025 | $78,110.11 | $78,019.51 | $-90.60 | +0.0000 | 1 | 2 |
| old_thin | 0.5911 | 0.5390 | -0.0521 | $39,667.96 | $37,686.55 | $-1,981.41 | +0.0042 | 4 | 6 |

- Aggregate EV delta: `-0.0857`
- Aggregate PnL delta: `$-2,512.68`
- Target trades: `12`
- Failed reasons: `aggregate_ev_not_positive, aggregate_pnl_not_positive, window_ev_regression, window_pnl_regression, fewer_than_two_ev_improved_windows, target_concentration_failed, target_sample_too_small`

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
