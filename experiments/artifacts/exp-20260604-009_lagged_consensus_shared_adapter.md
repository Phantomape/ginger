# exp-20260604-009 Lagged Consensus Shared Adapter

## Decision

- Decision: `accepted_lagged_consensus_shared_default_off_adapter`
- Adapter: `ACCEPTED_FREE_DATA_CROSS_SOURCE_CONSENSUS_PAPER`
- Rule version: `accepted_free_data_cross_source_consensus_shared_v1`
- Lagged rule: `accepted_free_data_cross_source_consensus_lagged_independent_source_family_v1`
- Live orders: `false`

## Three-Window Evidence

- Evidence source: `data/experiments/exp-20260604-008/lagged_independent_source_consensus.json`
- Vs core EV delta: `+1.9949`
- Vs core PnL delta: `$+35,553.87`
- Vs accepted same-day consensus EV delta: `+0.6891`
- Vs accepted same-day consensus PnL delta: `$+12,156.11`
- Lagged independent selected trades: `25`
- Max single positive share: `0.406701`
- Positive PnL HHI: `0.242387`

| Window | EV Delta | PnL Delta | Target Trades | Lagged Trades |
| --- | ---: | ---: | ---: | ---: |
| late_strong | +1.0468 | $+10,700.53 | 17 | 10 |
| mid_weak | +0.4887 | $+9,517.86 | 24 | 6 |
| old_thin | +0.4594 | $+15,335.48 | 23 | 9 |

## Production Boundary

The shared adapter now computes current plus prior-three-trading-day independent source-family confirmation from the default-off source snapshot logs. It remains paper-only with `trade_enabled=false`; orders, core universe, ranking, sizing, exits, watchlists, LLM, and news are unchanged.

No JavaScript was used.
