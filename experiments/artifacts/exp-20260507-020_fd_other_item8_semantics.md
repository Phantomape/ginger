# exp-20260507-020 FD/Other Item 8.01 Semantics

Decision: `rejected_positive_immaterial`

## Hypothesis

Within the FD/Other negative-reaction SEC sleeve, item 8.01 Other Events may be a cleaner temporary-uncertainty alpha than item 7.01 FD/context packets. Keeping item 8.01 while excluding 7.01 should improve event-source quality without changing reaction thresholds, holding period, notional, or core A/B logic.

## Three-Window Result

| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL | Event trades | Event PnL | Full-source PnL delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.7435 | 3.9318 | +0.1883 | $83,562.53 | $86,794.69 | $+3,232.16 | 4 | $+2,576.24 | $+381.97 |
| mid_weak | 1.5478 | 1.6216 | +0.0738 | $57,542.74 | $59,184.04 | $+1,641.30 | 3 | $+1,413.72 | $+0.00 |
| old_thin | 0.3359 | 0.4014 | +0.0655 | $26,242.68 | $29,089.49 | $+2,846.81 | 3 | $+2,846.81 | $+1,320.63 |

## Aggregate

- Aggregate EV delta: `+0.3276` (+5.82%)
- Aggregate PnL delta: `$+7,720.27` (+4.61%)
- EV windows improved/regressed: `3` / `0`
- Event trades/PnL/win rate: `10` / `$+6,836.77` / `0.8`

## Decision

Positive but below materiality: item 8.01 semantics improved the FD/Other source directionally without enough Gate 4 lift.

No production universe, ranking, sizing, exits, LLM, news, or order path changed.
