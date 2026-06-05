# exp-20260605-021 Lagged Consensus Fill-Delay Gap Guard

## Decision

- Decision: `rejected_fill_delay_gap_guard_did_not_beat_accepted_adapter`
- Rationale: The fill-delay gap guard did not beat the current accepted lagged consensus adapter across all three windows.

## Three-Window Result

- Before comparator: `exp-20260604-009` accepted lagged free-data consensus.
- EV delta vs accepted adapter: `-0.3708`
- PnL delta vs accepted adapter: `$-3,698.24`
- Blocked trades: `10` / `64` (0.15625)

| Window | EV Before | EV After | EV Delta | PnL Delta | Blocked / Source Trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| late_strong | 6.2096 | 5.7558 | -0.4538 | $-3,997.60 | 3 / 17 |
| mid_weak | 2.6289 | 2.7470 | +0.1181 | $+2,145.35 | 3 / 24 |
| old_thin | 1.0505 | 1.0154 | -0.0351 | $-1,845.99 | 4 / 23 |

## Production Impact

- Replay-only; no shared adapter, production order, watchlist, ranking, sizing, exit, LLM, or news behavior changed.
- A positive result requires shared live/backtest adapter support and parity tests before promotion.

No JavaScript was used.
