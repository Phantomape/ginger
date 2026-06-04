# exp-20260604-011 Lagged Consensus Cost/Liquidity Support

## Decision

- Decision: `rejected_cost_liquidity_support_incremental_concentration_failed`
- Rationale: The support variant improved all three windows, but incremental positive PnL was too concentrated: max single positive share 0.6258 and HHI 0.4342 breached the Gate 4 concentration guard.

## Three-Window Result

- Before comparator: `exp-20260604-009` accepted lagged free-data consensus.
- EV delta vs accepted adapter: `+0.0583`
- PnL delta vs accepted adapter: `$+1,020.49`
- Supported trades: `31` / `64` (0.484375)

| Window | EV Before | EV After | EV Delta | PnL Delta | Supported / Source Trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| late_strong | 6.2096 | 6.2365 | +0.0269 | $+283.63 | 9 / 17 |
| mid_weak | 2.6289 | 2.6458 | +0.0169 | $+272.87 | 12 / 24 |
| old_thin | 1.0505 | 1.0650 | +0.0145 | $+463.99 | 10 / 23 |

## Production Impact

- Replay-only; no shared adapter, production order, watchlist, ranking, sizing, exit, LLM, or news behavior changed.
- A positive result requires shared live/backtest adapter support and parity tests before promotion.

No JavaScript was used.
