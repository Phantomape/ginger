# exp-20260606-020 Macro Relief Top-2 Shared Paper Adapter

Status: `accepted`
Decision: `accepted_macro_relief_top2_shared_default_off_paper_adapter`

## Hypothesis

The positive exp-20260606-019 macro relief top-2 stock leadership source can be implemented as one shared default-off paper adapter without changing the three-window evidence or creating a production/backtest mismatch.

## Gate 4

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Macro relief days | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.2775 | +0.1147 | $117,072.92 | $118,328.52 | $+1,255.60 | +0.0000 | 2 | 4 |
| mid_weak | 2.1402 | 2.1729 | +0.0327 | $78,110.11 | $78,734.94 | $+624.83 | -0.0005 | 3 | 6 |
| old_thin | 0.5911 | 0.6250 | +0.0339 | $39,667.96 | $40,850.31 | $+1,182.35 | -0.0008 | 5 | 10 |

- Aggregate EV delta: `+0.1813`
- Aggregate PnL delta: `$+3,062.78`
- Target trades: `20`
- Failed reasons: `none`

## Production Impact

Shared default-off paper adapter only. Daily production can observe the surface, but trade_enabled remains false and no production watchlist, order path, core entry, ranking, sizing, or exit behavior changes.

No JavaScript was used.
