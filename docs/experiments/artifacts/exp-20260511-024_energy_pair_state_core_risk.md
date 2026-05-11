# exp-20260511-024: Energy Pair-State Core Risk

Decision: `rejected`

## Baseline

| Window | EV | PnL | SharpeD | DD | Win rate | Trades | Survival |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | 4.234 | 94086.91 | 4.5 | 0.0548 | 0.7895 | 19 | 0.8039 |
| mid_weak | 1.6689 | 61813.4 | 2.7 | 0.0941 | 0.5238 | 21 | 0.7925 |
| old_thin | 0.3853 | 28544.11 | 1.35 | 0.0815 | 0.4091 | 22 | 0.9167 |

## Variant Summary

| Variant | Gate 4 | EV Delta Sum | PnL Delta Sum | EV Windows + / - | PnL Windows + / - | Resized Signals | Touched Trades |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| energy_pair_state_core_0_50x | False | -0.6417 | -13000.24 | 0/1 | 0/1 | 4 | 4 |
| energy_pair_state_core_0_75x | False | -0.206 | -4373.96 | 0/1 | 0/1 | 4 | 4 |
| energy_pair_state_core_1_25x | False | 0.0541 | 780.98 | 1/0 | 1/0 | 4 | 4 |
| energy_pair_state_core_1_50x | False | 0.0541 | 780.98 | 1/0 | 1/0 | 4 | 4 |

## Gate Answers

- Hypothesis: Existing Energy trend/breakout signals may deserve more or less risk only when Energy equities and oil both confirm continuation through XLE/USO 200-day and 10/20-day momentum state.
- Changed variable: risk multiplier for existing Energy trend/breakout signals only when the fixed XLE/USO pair-confirmed state is true.
- Prior near experiment: simple Energy breakout risk boosts and XLE/USO tradeable ETF expansion were rejected; this does not add ETF candidates and requires the documented state discriminator.
- Gate 2 fields: entry_date and target_price are present in open_positions; XLE/USO OHLCV is present in canonical snapshots for replay state only.
- Gate 3: no filter was added, so survival is unchanged except for normal replay path accounting.
- Production note: no production policy was promoted by this replay-only runner. Any positive candidate must add shared reference-feature plumbing to both run.py and backtester.py before orders change.
