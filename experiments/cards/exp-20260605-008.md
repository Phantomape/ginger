# exp-20260605-008 SEC Negative Lagged Consensus Source

## Decision

- Decision: `rejected_sec_negative_lagged_consensus_did_not_beat_accepted_lagged_comparator`
- Rationale: The variant did not beat the current accepted lagged consensus comparator across all three canonical windows.

## Three-Window Result

- Vs core EV delta: `+2.1396`
- Vs core PnL delta: `$+37,245.94`
- Vs accepted lagged consensus EV delta: `+0.1447`
- Vs accepted lagged consensus PnL delta: `$+1,692.07`
- Selected trades with SEC negative source: `3`

| Window | EV Delta Vs Lagged | PnL Delta Vs Lagged | EV Delta Vs Core | Target Trades |
| --- | ---: | ---: | ---: | ---: |
| late_strong | +0.0152 | $+51.36 | +1.0620 | 18 |
| mid_weak | +0.1295 | $+1,640.71 | +0.6182 | 25 |
| old_thin | +0.0000 | $+0.00 | +0.4594 | 23 |

## Source Diagnostics

- SEC source rows by window: `{'late_strong': 5, 'mid_weak': 7, 'old_thin': 4}`
- Current SEC confirmations selected: `2`
- Prior SEC confirmations selected: `1`

## Production Boundary

Replay-only. No shared adapter, production path, live/default orders, ranking, sizing, exits, watchlists, LLM, or news behavior changed.

No JavaScript was used.
