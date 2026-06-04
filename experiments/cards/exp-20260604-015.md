# exp-20260604-015 VCP lagged-prior consensus

## Decision

- Decision: `rejected_vcp_lagged_prior_did_not_beat_accepted_lagged_adapter`
- Rationale: The VCP prior-confirmation variant did not beat exp-20260604-009 accepted lagged adapter across aggregate EV/PnL and all three per-window EV/PnL comparisons.

## Three-window result

- Vs core: EV `+2.1064`, PnL `$+37,918.48`
- Vs accepted lagged adapter: EV `+0.1115`, PnL `$+2,364.61`
- VCP prior selected trades: `10`

## Production impact

- Replay-only; no production code or live/default order behavior changed.
- Positive retention would require a shared VCP-lagged consensus adapter and parity tests first.

No JavaScript was used.
