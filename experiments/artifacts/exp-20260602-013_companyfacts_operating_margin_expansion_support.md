# exp-20260602-013: Companyfacts Operating-Margin Expansion Support

- decision: `rejected_operating_margin_expansion_no_material_current_stack_lift`
- aggregate EV: `16.1444` -> `16.6222` (+0.4778)
- aggregate PnL: `$359,253.44` -> `$365,603.25` (+6,349.81)
- current-stack EV lift: `0.029595` (required `0.1`)
- incremental target trades: `237`
- max single positive share: `0.42861`
- positive PnL HHI: `0.259617`
- failed gates: `anti_repeat_material_current_stack_ev_lift_passed`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | adjusted trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 7.2995 | 7.3784 | +0.0789 | $+963.20 | 56 |
| mid_weak | 5.9392 | 6.1654 | +0.2262 | $+2,632.05 | 89 |
| old_thin | 2.9057 | 3.0784 | +0.1727 | $+2,754.56 | 92 |

## Prior Nearby Evidence

`exp-20260528-023` already tested non-declining operating margin versus the prior-year same quarter. It beat the old core baseline, but failed against the then-current accepted Companyfacts stack. This run uses the current accepted sector-residual stack as before-state and requires a 10% current-stack EV lift before reopening this field family.

## Production Parity

Replay-only and default-off paper only. The test uses SEC Companyfacts operating_income/revenue facts with `filed <= signal_date` and rows already selected by the accepted Companyfacts paper route. No live orders, shared production adapter, core ranking, sizing, exits, LLM, or news behavior changed.

## Conclusion

Operating-margin expansion was directionally positive but did not clear the 10% current-stack EV lift required to reopen this prior rejected nearby Companyfacts scalar family.

## Top Positive Incremental Contributors

| ticker | trades | incremental PnL | positive PnL share |
|---|---:|---:|---:|
| APP | 73 | $3,035.69 | 0.42861 |
| PLTR | 52 | $1,248.02 | 0.180077 |
| MU | 43 | $1,054.46 | 0.139717 |
| CRDO | 34 | $283.63 | 0.113261 |
| AMD | 15 | $796.41 | 0.103138 |
| AVGO | 3 | $146.18 | 0.018343 |
| NFLX | 9 | $-5.78 | 0.011384 |
| NOW | 3 | $9.50 | 0.005471 |
| META | 3 | $-162.56 | 0.0 |
| ISRG | 2 | $-55.74 | 0.0 |
