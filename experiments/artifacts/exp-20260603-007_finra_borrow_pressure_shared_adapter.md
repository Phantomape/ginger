# exp-20260603-007 FINRA Borrow-Pressure Shared Adapter

Decision: `accepted_default_off_finra_borrow_pressure_shared_adapter`.

Single variable: move the accepted FINRA borrow-pressure admission field into the shared default-off FINRA/IWM paper adapter.

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Target trades |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.2882 | +0.1254 | $117,072.92 | $118,565.73 | $+1,492.81 | 6 |
| mid_weak | 2.1402 | 2.1718 | +0.0316 | $78,110.11 | $78,688.14 | $+578.03 | 8 |
| old_thin | 0.5911 | 0.6926 | +0.1015 | $39,667.96 | $43,285.24 | $+3,617.28 | 8 |

## Aggregate

- EV delta: `0.2585` (`0.032746`)
- PnL delta: `$5688.12` (`0.02422`)
- Gate 4 passed: `True`; target trades `22`; EV-regressed windows `0`.

## Production Parity

The adapter is shared production code and remains default-off paper only. `trade_enabled=false`; it does not change core signals, rankings, sizing, exits, watchlists, LLM/news, or orders.

No JavaScript was used.
