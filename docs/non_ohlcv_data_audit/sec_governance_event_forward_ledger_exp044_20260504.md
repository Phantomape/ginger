# SEC Governance Event Forward Ledger

Experiment: `exp-20260504-044`

Status: accepted observe-only.

## Why This Exists

`exp-20260504-039` was the strongest current alpha direction: a fixed SEC
governance/procedural 8-K sleeve improved EV in all three canonical windows.
It was not production-promotable because the event sleeve existed only as a
historical experiment. A live promotion without a daily frozen queue and paper
outcome ledger would create a production/backtest mismatch.

This run implements the default-off observation path. It does not change core
orders, candidate ranking, signal generation, sizing, exits, or default
backtest behavior.

## Frozen Cells

- `shareholder_vote|negative_excess_0_to_minus_2pct`
- `charter_or_securities_change|positive_excess_0_to_2pct`
- `exhibit_only|negative_excess_0_to_minus_2pct`
- `exhibit_only|positive_excess_0_to_2pct`

`2.02` earnings-result filings remain excluded.

## Validation

Focused tests:

`.\\.venv\\Scripts\\python.exe -m pytest quant\\test_sec_event_queue.py quant\\test_sec_event_sleeve.py`

Result: `12 passed`.

Canonical no-drift backtests:

| Window | EV Before | EV After | PnL Before | PnL After | Sharpe Daily | DD | Trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | 3.4191 | 3.4191 | $78,600.33 | $78,600.33 | 4.35 | 5.41% | 19 |
| mid_weak | 1.4415 | 1.4415 | $55,015.08 | $55,015.08 | 2.62 | 8.79% | 21 |
| old_thin | 0.3179 | 0.3179 | $24,642.07 | $24,642.07 | 1.29 | 8.05% | 22 |

## Next Evidence Needed

Before any live capital:

- closed forward paper outcomes;
- frozen same-day core-signal and cash alternatives;
- explicit shared trade-enabled sleeve adapter;
- another three-window parity check if any trade path is enabled.
