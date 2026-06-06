# exp-20260606-001 Shared Low-Deployment ETF Cash Substitute

Decision: `accepted_shared_default_off_low_deployment_etf_cash_substitute_adapter`.

## Aggregate

- EV: `7.8941 -> 10.9233` (+3.0292)
- PnL: `$234,850.99 -> $279,157.90` ($+44,306.91)
- Target trades: `19`
- Max drawdown delta: `-0.0008`

## Window Deltas

| Window | EV delta | PnL delta | Trades |
| --- | ---: | ---: | ---: |
| `late_strong` | +2.3826 | $+23,434.05 | 7 |
| `mid_weak` | +0.1381 | $+2,968.12 | 5 |
| `old_thin` | +0.5085 | $+17,904.74 | 7 |

## Production Boundary

- Shared helper changed: `quant/low_deployment_etf_overlay.py`.
- Daily production remains default-off and `trade_enabled=false`.
- No live/default orders, ranking, sizing, exits, watchlists, LLM, or news path changed.
- No JavaScript was used.
