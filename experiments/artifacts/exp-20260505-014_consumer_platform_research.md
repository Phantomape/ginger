# exp-20260505-014 Consumer Platform Research Basket

Decision: `accepted_observe_only`

## Hypothesis

`HOOD`, `RBLX`, and `SOFI` may represent a consumer digital platform alpha surface, but exp-20260505-011 showed direct tradeable promotion was unstable across the three canonical windows. The correct next step is production-aligned observation, not core or pilot order authority.

## Change

Added `HOOD`, `RBLX`, and `SOFI` to universe governance as `research` names only.

- No core universe promotion.
- No pilot sleeve promotion.
- No signal, ranking, sizing, exit, add-on, LLM, or news rule changed.
- Added an adapter test proving research names stay out of tradeable universes.

## Three-window before/after

| Window | EV before | EV after | PnL before | PnL after | SharpeD before | SharpeD after | DD before | DD after | Trades before | Trades after |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | 3.4191 | 3.4191 | 78600.33 | 78600.33 | 4.35 | 4.35 | 0.0541 | 0.0541 | 19 | 19 |
| `mid_weak` | 1.4415 | 1.4415 | 55015.08 | 55015.08 | 2.62 | 2.62 | 0.0879 | 0.0879 | 21 | 21 |
| `old_thin` | 0.3179 | 0.3179 | 24642.07 | 24642.07 | 1.29 | 1.29 | 0.0805 | 0.0805 | 22 | 22 |

## Parity

This is a shared universe-governance metadata change, but research names are excluded from `core_trade_universe` and `governance_tradeable_universe`. Production and backtest order paths therefore remain unchanged.

## Next evidence needed

Collect forward observation outcomes and evaluate replacement value before any pilot or core promotion.
