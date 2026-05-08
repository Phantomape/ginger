# exp-20260508-019 - Add-on entry heat reserve

## Decision

Rejected. Reserving entry heat for future follow-through add-ons did not change
add-on execution or improve the expected-value score in any of the three fixed
windows from `docs/backtesting.md`.

## Hypothesis

Confirmed day-2 follow-through winners have positive marginal expectancy. A
small entry heat reserve might preserve capacity for those add-ons while keeping
the hard portfolio heat cap at 8%.

## Results

| Window | Baseline EV | Reserve 0.5% EV | Reserve 1.0% EV | PnL impact | Add-on execution impact |
| --- | ---: | ---: | ---: | ---: | --- |
| late_strong | 3.7435 | 3.7435 | 3.7435 | $0.00 | none |
| mid_weak | 1.5478 | 1.5478 | 1.5478 | $0.00 | none |
| old_thin | 0.3359 | 0.3359 | 0.3359 | $0.00 | none |

The 1.0% reserve removed one survived signal in `old_thin`, but it did not
change trades, PnL, or add-on execution.

## Mechanism Read

This falsifies the narrow idea that missed add-ons are mainly caused by new
entries consuming heat before the add-on fill date. The next add-on alpha test
should not retry entry-reserve variants.

The sweep exposed a more important measurement blocker: production add-on
actions are capped through `production_parity.py` and `portfolio_engine` using
effective-stop heat, while the backtester executes add-ons through a local
initial-stop heat calculation. Until that path is shared, add-on
capital-allocation experiments are measuring a replay rule production does not
actually use.
