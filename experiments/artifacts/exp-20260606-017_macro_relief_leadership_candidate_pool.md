# exp-20260606-017 Macro Relief Leadership Candidate Pool

Status: `rejected`
Decision: `rejected_macro_relief_leadership_candidate_pool`

## Hypothesis

Official CPI/FOMC/NFP relief days where SPY and QQQ both rally and close strong may identify stock leaders with cleaner 10-trading-day next-open replacement value than broad daily momentum.

## Gate 4

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Macro relief days | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.2325 | +0.0697 | $117,072.92 | $117,854.81 | $+781.89 | +0.0000 | 2 | 2 |
| mid_weak | 2.1402 | 2.1541 | +0.0139 | $78,110.11 | $78,331.38 | $+221.27 | +0.0000 | 3 | 3 |
| old_thin | 0.5911 | 0.6153 | +0.0242 | $39,667.96 | $40,484.51 | $+816.55 | -0.0005 | 5 | 5 |

- Aggregate EV delta: `+0.1078`
- Aggregate PnL delta: `$+1,819.71`
- Target trades: `10`
- Failed reasons: `target_sample_too_small`

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
