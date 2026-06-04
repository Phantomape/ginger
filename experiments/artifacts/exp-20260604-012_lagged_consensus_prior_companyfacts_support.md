# exp-20260604-012 Lagged Consensus Prior Companyfacts Support

## Decision

- Decision: `rejected_prior_companyfacts_support_incremental_concentration_failed`
- Rationale: The support variant improved all three windows, but incremental positive PnL was too concentrated: max single positive share 0.4281 and HHI 0.3007 breached the Gate 4 concentration guard.

## Three-Window Result

- Before comparator: `exp-20260604-009` accepted lagged free-data consensus.
- EV delta vs accepted adapter: `+0.0682`
- PnL delta vs accepted adapter: `$+1,198.42`
- Supported trades: `36` / `64` (0.5625)

| Window | EV Before | EV After | EV Delta | PnL Delta | Supported / Source Trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| late_strong | 6.2096 | 6.2552 | +0.0456 | $+409.29 | 12 / 17 |
| mid_weak | 2.6289 | 2.6343 | +0.0054 | $+179.45 | 13 / 24 |
| old_thin | 1.0505 | 1.0677 | +0.0172 | $+609.68 | 11 / 23 |

## Production Impact

- Replay-only; no shared adapter, production order, watchlist, ranking, sizing, exit, LLM, or news behavior changed.
- A positive result requires shared live/backtest adapter support and parity tests before promotion.

No JavaScript was used.
