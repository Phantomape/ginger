# exp-20260604-017 AI optical lagged-prior consensus

## Decision

- Decision: `rejected_ai_optical_lagged_prior_no_selected_prior_rows`
- Rationale: The AI optical prior-confirmation rule produced no selected AI-optical-prior trades.

## Three-window result

- Vs core: EV `+1.9949`, PnL `$+35,553.87`
- Vs accepted lagged adapter: EV `+0.0000`, PnL `$+0.00`
- AI optical prior selected trades: `0`

## Production impact

- Replay-only; no production code or live/default order behavior changed.
- Positive retention would require a shared AI-optical-lagged consensus adapter and parity tests first.

No JavaScript was used.
