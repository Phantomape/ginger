# exp-20260604-008 Lagged independent-source consensus

## Decision

- Decision: `positive_replay_lead_requires_lagged_consensus_shared_adapter`
- Rationale: Lagged independent-source timing improved core and the current accepted same-date consensus comparator across all three windows. Promotion would require a shared production/backtest adapter first.

## Three-window result

- Vs core: EV `+1.9949`, PnL `$+35,553.87`
- Vs accepted same-date consensus: EV `+0.6891`, PnL `$+12,156.11`
- Lagged independent selected trades: `25`

## Production impact

- Replay-only; no production code or live/default order behavior changed.
- Positive retention would require a shared lagged-consensus adapter and parity tests first.

No JavaScript was used.
