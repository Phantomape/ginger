# exp-20260607-019 Volatility Relief Shared Adapter

Decision: `accepted_volatility_relief_stock_leadership_shared_default_off_adapter`
Status: `accepted`

## Gate 4

- Aggregate EV delta: `+0.5732`
- Aggregate PnL delta: `$+11,934.79`
- Target trades: `88`
- Failed reasons: `none`

## Parity

- Historical replay uses `quant/volatility_relief_stock_leadership_paper_sleeve.py`.
- Daily run exposes the same helper as a default-off paper snapshot.
- `trade_enabled=False`; no live/default orders, ranking, sizing, exits, LLM/news, or watchlist behavior changed.

No JavaScript was used.
