# exp-20260616-015 SBC Burden Improvement Shared Adapter

Status: `accepted`
Decision: `accepted_paper_pending_forward_sbc_burden_improvement_shared_adapter`
Full-stack verdict: `accepted_paper_pending_forward`

## Hypothesis

candidate_pool/shared_adapter: raw SEC Companyfacts annual stock-based compensation burden falling versus revenue, with positive revenue/gross-profit context and liquid SPY-relative leadership, may identify growth-quality candidates whose shareholder dilution cost is improving before a 10-trading-day continuation leg.

## Gate 4

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Raw candidates | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.6366 | +0.4738 | $117,072.92 | $123,342.85 | $+6,269.93 | -0.0003 | 177 | 40 |
| mid_weak | 2.1402 | 2.5777 | +0.4375 | $78,110.11 | $86,498.54 | $+8,388.43 | -0.0022 | 248 | 46 |
| old_thin | 0.5911 | 0.6236 | +0.0325 | $39,667.96 | $40,757.79 | $+1,089.83 | +0.0048 | 112 | 22 |

- Aggregate EV delta: `+0.9438`
- Aggregate PnL delta: `$+15,748.19`
- Target trades: `108`
- Failed reasons: `none`
- Lead reproduction EV drift: `+0.000000`
- Lead reproduction PnL drift: `$+0.00`
- Accepted compression comparator EV/PnL: `+0.1608` / `$+2,248.98`
- Accepted distribution comparator EV/PnL: `+0.5286` / `$+10,432.91`

## Production Impact

Shared default-off paper helper and daily snapshot only. `trade_enabled=false`; live/default orders, ranking, sizing, exits, LLM/news, and watchlists are unchanged.

No JavaScript was used.
