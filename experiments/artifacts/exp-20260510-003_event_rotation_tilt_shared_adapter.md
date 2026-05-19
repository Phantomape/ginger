# exp-20260510-003 Event Rotation-Tilt Shared Adapter

Decision: `accepted_default_off_paper_adapter`

Alpha search follow-through. The strongest current event-overlay allocation lead
is the `rotation_breakout_leadership` subset inside the default-off event bundle.
`exp-20260510-001` showed the 3.0x paper-notional tilt improved EV in all three
canonical windows versus the current 2.0x non-generic state-surface event add-on.

## Replay Evidence Used

| Window | Current EV | 3.0x EV | Delta EV | Current PnL | 3.0x PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 4.8980 | 5.2074 | +0.3094 | $101,828.78 | $106,273.27 | +$4,444.49 |
| mid_weak | 2.3533 | 2.5742 | +0.2209 | $72,186.99 | $75,490.20 | +$3,303.21 |
| old_thin | 0.4231 | 0.4295 | +0.0064 | $30,005.02 | $30,245.22 | +$240.20 |

Aggregate delta versus current event lead: EV `+0.5367`, PnL `+$7,987.90`.

## Code Change

`quant/event_sleeve_bundle.py` now keeps the existing 2.0x paper scalar for
positive non-generic state-surface event rows, but applies 3.0x when the matched
state surface is `rotation_breakout_leadership`. The daily report now exposes the
rotation-tilt candidate count.

This remains default-off paper attribution:

- live/default orders unchanged
- core A/B ranking unchanged
- core sizing and exits unchanged
- event trade plan remains blocked unless the explicit forward gate and trade
  adapter are enabled

## Canonical Core No-Drift Check

| Window | EV | PnL | Sharpe daily | Max DD | Win rate | Trades |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 4.0674 | $90,788.88 | 4.48 | 5.39% | 78.95% | 19 |
| mid_weak | 1.6195 | $59,540.63 | 2.72 | 8.79% | 52.38% | 21 |
| old_thin | 0.3583 | $27,347.42 | 1.31 | 9.03% | 40.91% | 22 |

These match the accepted core baseline, as expected for a default-off paper
adapter.

## Validation

- `.\\.venv\\Scripts\\python.exe -m pytest quant\\test_event_sleeve_bundle.py`
  -> `10 passed`
- Three canonical `backtesting.md` fixed windows rerun with snapshots.

## Next Step

Collect forward paper replacement-value outcomes under the exact shared
rotation-tilt annotation. Do not route this to live/default orders until closed
forward outcomes and the explicit trade adapter gate pass.
