# exp-20260511-003 Space Catalyst Shadow Surface

## Decision

Accepted as a default-off forward observation surface. This is not a live trade
promotion and not a core universe expansion.

## Hypothesis

The rejected static space catalyst pool from `exp-20260511-002` should be
converted into a production-visible shadow surface so future replacement value
can be measured without letting a hindsight-selected theme enter live trading.

## Single Variable

Expose `SPACE_CATALYST_SHADOW` records in daily run/report output with zero
live slots, explicit event fields, and promotion gates.

## Three-Window Check

| Window | EV Before | EV After | PnL Before | PnL After | Max DD Before | Max DD After | Trades | Survival |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2340 | 4.2340 | $94,086.91 | $94,086.91 | 5.48% | 5.48% | 19 | 80.39% |
| mid_weak | 1.6689 | 1.6689 | $61,813.40 | $61,813.40 | 9.41% | 9.41% | 21 | 79.25% |
| old_thin | 0.3853 | 0.3853 | $28,544.11 | $28,544.11 | 8.15% | 8.15% | 22 | 91.67% |

Aggregate EV delta: `0.0000`. Aggregate PnL delta: `$0.00`.

## Gate Results

- Gate 1: passed, using the accepted `exp-20260510-015` baseline.
- Gate 2: passed, `operator_inputs/open_positions.json` has `entry_date` and
  `target_price` for all 10 positions.
- Gate 3: passed, no core filter was added and survival stayed above 5%.
- Gate 4: passed for observe-only promotion because canonical core behavior did
  not drift.

## Production Impact

```text
production_impact:
  shared_policy_changed: true
  backtester_adapter_changed: false
  run_adapter_changed: true
  replay_only: false
  parity_test_added: true
  alters_orders: false
  alters_signal_generation: false
  alters_candidate_ranking: false
  alters_sizing: false
```

## Verification

- `.\\.venv\\Scripts\\python.exe -m pytest quant\\test_space_catalyst_sleeve.py quant\\test_pilot_sleeve.py`
  -> 17 passed.
- Canonical three-window backtests reran after the adapter and matched the
  accepted baseline.

## Next Evidence

Collect closed forward direct PnL, cash-relative PnL, core replacement value,
same-theme replacement value, and risk-adjusted replacement value. Do not retry
static space-pool promotion or adjacent ticker mining on the same frozen sample.
