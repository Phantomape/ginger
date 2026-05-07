# exp-20260507-009: Mid-Dispersion Fragility Guard

Decision: `rejected`

## Variant Summary

| Variant | Gate 4 | EV Delta Sum | PnL Delta Sum | EV Windows + / - | Guarded Signals | Guarded Trades |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| no_tech_fragility_stack | False | -0.0065 | -156.45 | 1/1 | 16 | 9 |
| no_multi_fragility_stack | False | 0.0008 | 44.49 | 2/0 | 9 | 3 |
| no_any_fragility_stack | False | -0.0065 | -156.45 | 1/1 | 16 | 9 |

## Interpretation

Best variant `no_multi_fragility_stack` did not improve the north-star EV enough or across enough windows to justify complicating the accepted mid-dispersion trend allocation rule.

## Production Impact

- No production code was changed by this replay.
- If accepted later, the guard must live in shared portfolio sizing and be exposed to both run.py and backtester.py.
