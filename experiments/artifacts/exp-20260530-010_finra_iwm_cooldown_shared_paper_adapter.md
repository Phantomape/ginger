# exp-20260530-010 FINRA IWM Cooldown Shared Paper Adapter

Decision: `accepted_default_off_finra_iwm_shared_adapter`.

Single variable: move the accepted FINRA+IWM seven-day same-ticker cooldown paper source into a shared default-off production adapter.

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Target trades |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.2891 | +0.1263 | $117,072.92 | $118,592.97 | $+1,520.05 | 13 |
| mid_weak | 2.1402 | 2.1782 | +0.0380 | $78,110.11 | $78,921.41 | $+811.30 | 15 |
| old_thin | 0.5911 | 0.7576 | +0.1665 | $39,667.96 | $45,635.01 | $+5,967.05 | 10 |

## Aggregate

- EV delta: `0.3308` (`0.041905`)
- PnL delta: `$8298.4` (`0.035335`)
- Gate 4 from `exp-20260530-007` passed: 3/3 EV/PnL windows improved, 38 target trades, max drawdown drift +0.03pp, survival unchanged, concentration passed.

## Production Parity

The adapter is shared production code and is default-off paper only. `trade_enabled=false`; it does not change core signals, rankings, sizing, exits, watchlists, or orders.

No JavaScript was used.
