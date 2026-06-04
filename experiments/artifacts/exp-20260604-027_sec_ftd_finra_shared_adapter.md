# exp-20260604-027 SEC FTD + FINRA Shared Adapter

Decision: `accepted_default_off_sec_ftd_finra_shared_adapter`.

Single variable: move the accepted SEC FTD + FINRA confirmation candidate source into a shared default-off paper adapter.

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Target trades |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.3853 | +0.2225 | $117,072.92 | $119,940.25 | $+2,867.33 | 39 |
| mid_weak | 2.1402 | 2.1884 | +0.0482 | $78,110.11 | $80,162.83 | $+2,052.72 | 40 |
| old_thin | 0.5911 | 0.7624 | +0.1713 | $39,667.96 | $44,848.40 | $+5,180.44 | 42 |

## Aggregate

- EV delta: `0.442` (`0.055991`)
- PnL delta: `$10100.49` (`0.043008`)
- Windows improved: EV `3/3`, PnL `3/3`.
- Target trades: `121`.
- Gate 4 passed: `True`; failed gates `[]`.

## Production Consistency

The adapter is shared production code and remains default-off paper only. `trade_enabled=false`; it does not change core signals, rankings, sizing, exits, watchlists, LLM/news, or orders.

Live activation is still blocked until forward paper rows close and are compared against replay outputs.

No JavaScript was used.
