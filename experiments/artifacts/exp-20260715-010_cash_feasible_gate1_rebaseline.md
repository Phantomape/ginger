# exp-20260715-010 — Cash-feasible Gate-1 rebaseline

## Decision

Accepted measurement repair; `accepted_alpha=false` and `live_ready=false`.

The already validated `exp-20260715-008` execution-date cash-admission policy
is now the canonical backtester default. No scale/skip/release rule, cash
buffer, order cap, entry/exit rule, ranking rule, sizing rule, cost, window, or
frozen behavior input changed.

## Identity evidence

- Frozen behavior SHA-256:
  `ff0f232a2c075a7f330b28ddff8661d25108e45eeb9f4322c3f99574e338ffa6`
  (the exact `exp-20260712-015` input bundle).
- Explicit `CASH_LEDGER_ENFORCED=True` and default-config replays matched
  exactly in all three windows, including full metrics, trade rows, dated
  return series, and complete cash-ledger hashes.
- Default-config results exactly matched the `exp-20260715-008` enforced
  reference in every headline field.
- Explicit `CASH_LEDGER_ENFORCED=False` still reproduced the complete prior
  unenforced anchor in every window (trade rows, dated returns, EV, PnL, and
  trade count).
- Source and input identities stayed stable across all nine window runs; the
  source bundle hash verified after publication.

## Active baseline

| Window | EV | PnL | Trades | Max DD | Survival | Min cash | Negative-cash events |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | 4.1067 | $70,075.18 | 13 | 3.94% | 88.89% | $11.95 | 0 |
| mid_weak | 1.9908 | $51,976.41 | 13 | 6.61% | 81.16% | $0.44 | 0 |
| old_thin | 0.1082 | $8,940.77 | 23 | 8.89% | 92.31% | $5.12 | 0 |

Aggregate EV is `6.2057`, aggregate PnL is `$130,992.36`, and total trades
are `49`. Cash conservation error is zero in every window. The canonical
summary is
`data/backtests/backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json`.

## Interpretation

The change from the historical unenforced anchor is EV `-6.0641`, PnL
`-$106,859.91`, and `-13` trades. This is the removal of unfinanceable fills,
not an alpha regression: the prior `12.2698` EV / `$237,852.27` PnL result is
now retained only as an explicit-False, leverage-inflated historical upper
bound.

Future capital-allocation experiments must compare both sides against the new
cash-feasible anchor. Do not retune cash admission or mechanically rerun a
rejected allocation policy merely because the hurdle fell; a new ticket must
predeclare a genuinely new allocator/covariance hypothesis.

## Production boundary

The backtester default now changes core order admission, but `run.py` and live
orders were not changed. A live-ready claim requires a shared, auditable
settled-cash/buying-power reservation contract (including outstanding-order
reservations) across backtester, production runner, and broker adapters.

## Reproduction

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260715_010_cash_feasible_gate1_rebaseline.py
.\.venv\Scripts\python.exe -B -m pytest quant\test_backtester_cash_ledger.py -q
.\.venv\Scripts\python.exe -B scripts\experiment.py audit --lean-strict
```
