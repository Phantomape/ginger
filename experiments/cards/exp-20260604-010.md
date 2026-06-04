# exp-20260604-010 Lagged Consensus Rank Priority

## Decision

- Decision: `rejected_lagged_rank_priority_did_not_beat_accepted_adapter`
- Rationale: The rank-priority variant did not beat the current accepted lagged consensus adapter across all three windows.

## Three-Window Result

- Vs core: EV `+2.0114`, PnL `$+35,271.22`
- Vs accepted lagged adapter: EV `+0.0165`, PnL `$-282.65`
- Lagged-priority selected trades: `27`

| Window | EV Delta | PnL Delta | Target Trades | Lagged-Priority Trades |
| --- | ---: | ---: | ---: | ---: |
| late_strong | +1.0468 | $+10,700.53 | 17 | 10 |
| mid_weak | +0.4887 | $+9,517.86 | 24 | 6 |
| old_thin | +0.4759 | $+15,052.83 | 23 | 11 |

## Production Impact

- Replay-only; no shared adapter, production order, watchlist, ranking, sizing, exit, LLM, or news behavior changed.
- A positive result would require shared adapter ordering and parity tests before promotion.

No JavaScript was used.
