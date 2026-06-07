# exp-20260607-006 Macro Relief Sector-Confirmed Leadership

Status: `rejected`
Decision: `rejected_macro_relief_sector_confirmed_leadership_candidate_pool`

## Hypothesis

Official macro relief stock-leadership candidates may be cleaner when the candidate's broad-universe sector median also rallies and beats SPY on the event day.

## Gate 4

| Window | Before EV | After EV | dEV | EV vs exp020 | Before PnL | After PnL | dPnL | PnL vs exp020 | Sector-confirmed raw | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.2652 | +0.1024 | -0.0123 | $117,072.92 | $118,321.15 | $+1,248.23 | $-7.37 | 98 | 4 |
| mid_weak | 2.1402 | 2.1729 | +0.0327 | +0.0000 | $78,110.11 | $78,734.94 | $+624.83 | $+0.00 | 64 | 6 |
| old_thin | 0.5911 | 0.6847 | +0.0936 | +0.0597 | $39,667.96 | $43,056.09 | $+3,388.13 | $+2,205.78 | 134 | 10 |

- Aggregate EV delta vs core: `+0.2287`
- Aggregate PnL delta vs core: `$+5,261.19`
- Aggregate EV delta vs accepted exp020: `+0.0474`
- Aggregate PnL delta vs accepted exp020: `$+2,198.41`
- Target trades: `20`
- Failed reasons: `accepted_comparator_window_ev_regression_late_strong, accepted_comparator_window_pnl_regression_late_strong`

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
