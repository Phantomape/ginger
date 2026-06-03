# exp-20260603-015 Accepted Consensus Source-Family Adapter

## Decision

- Decision: `accepted_default_off_consensus_source_family_adapter`
- Adapter: `ACCEPTED_FREE_DATA_CROSS_SOURCE_CONSENSUS_PAPER`
- Rule version: `accepted_free_data_cross_source_consensus_shared_v1`
- Consensus rule: `accepted_free_data_cross_source_consensus_independent_source_family_v1`
- Source-family rule: `accepted_free_data_consensus_source_family_map_v1`
- Live orders: `false`

## Gate 4 Evidence

- Evidence source: `data/experiments/exp-20260603-014/accepted_consensus_independent_source_family.json`
- Aggregate EV delta: `1.3058`
- Aggregate PnL delta: `$23,397.76`
- Target trades: `47`
- FINRA-only selected trades: `0`
- Max positive share: `0.41044239003237454`
- Positive PnL HHI: `0.25195334502362565`

## Windows

| Window | EV Delta | PnL Delta | Target Trades |
| --- | ---: | ---: | ---: |
| late_strong | 0.7232 | $7,368.07 | 9 |
| mid_weak | 0.2731 | $4,817.45 | 22 |
| old_thin | 0.3095 | $11,212.24 | 16 |

## Production Parity

This is default-off paper observation only. The daily production path now passes a FINRA borrow-pressure alias into the shared consensus adapter, and the adapter collapses FINRA/IWM plus FINRA borrow-pressure into one source family before admission. This prevents FINRA+FINRA double counting.

No JavaScript was used.
