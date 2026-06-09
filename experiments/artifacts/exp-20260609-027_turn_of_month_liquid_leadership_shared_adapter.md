# exp-20260609-027 Artifact

## Decision

`accepted_turn_of_month_liquid_leadership_shared_default_off_adapter`

## Fixed Policy Bundle

Last trading day through first three trading days, liquid sector-known stock universe, 20-day SPY-relative leadership, positive 60-day excess trend, signal-day return, high close location, volume and volatility guards, same-ticker selected core overlap exclusion, top-1/day, fixed $4,000 paper notional, next-open entry, 10-trading-day close exit, slippage, round-trip cost, and same-ticker cooldown.

## Three-Window Before/After

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Raw candidates | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.2813 | +0.1185 | $117,072.92 | $118,154.12 | $+1,081.20 | -0.0003 | 1328 | 23 |
| mid_weak | 2.1402 | 2.2389 | +0.0987 | $78,110.11 | $79,964.40 | $+1,854.29 | -0.0001 | 781 | 24 |
| old_thin | 0.5911 | 0.6513 | +0.0602 | $39,667.96 | $42,020.16 | $+2,352.20 | -0.0032 | 937 | 26 |

- Aggregate EV delta: `+0.2774`
- Aggregate PnL delta: `$+5,287.69`
- Target trades: `73`
- Gate failures: `none`

## Production Parity

Historical replay and daily observation share quant/turn_of_month_liquid_leadership_paper_sleeve.py. The helper is default-off and cannot alter orders, core ranking, sizing, exits, watchlists, LLM, or news behavior.

Historical replay passes the full loaded trading calendar into the shared helper. Daily snapshots must not infer last-trading-day labels from truncated OHLCV; month-end observation requires explicit calendar_dates or known_month_end_dates and otherwise fails closed.

## Reflection

The shared helper reproduced the private replay lead because it kept the exact calendar window, liquid sector-known universe, SPY-relative leadership, close/volume/volatility guards, same-ticker selected-core overlap exclusion, next-open entry, 10-day exit, cost, top-1, and cooldown semantics while adding daily pending/open/closed state handling with month-end fail-closed calendar parity.

No JavaScript was used.
