# exp-20260507-018 State Surface Paper Adapter

## Decision

Accepted as a default-off observation harness, not as a live trading strategy.

## Alpha Hypothesis

The strongest current alpha lead is still the full state-surface satellite from
`exp-20260507-016`: production-universe candidates scored by market state,
breadth, relative strength, proximity to highs, and volume. It improved all
three canonical windows in replay, while `exp-20260507-017` showed that pruning
the balanced surface was weaker. The next alpha step is therefore not another
threshold sweep. It is to make the full surface production-visible as paper
attribution so forward replacement value can be measured without changing
orders.

## What Changed

- Added `quant/state_surface_sleeve.py`.
- Wired `run.py` to emit `state_surface_queue` and `state_surface_sleeve`.
- Added a report section for the default-off paper sleeve.
- Added tests that assert `trade_enabled=false` and `alters_orders=false`.
- Updated production/backtest parity disclosure.

The sleeve never changes signal generation, ranking, sizing, slots, exits, or
orders. It records candidates, pending paper entries, open paper positions,
closed paper outcomes, and a forward gate.

## Three-Window Core Check

| Window | Before EV | After EV | Before PnL | After PnL | Notes |
|---|---:|---:|---:|---:|---|
| `late_strong` | 3.7435 | 3.7435 | 83562.53 | 83562.53 | unchanged |
| `mid_weak` | 1.5478 | 1.5312 | 57542.74 | 57776.56 | earnings-calendar coverage drifted 38/45 -> 37/45 |
| `old_thin` | 0.3359 | 0.3359 | 26242.68 | 26242.68 | unchanged |

The mid-window drift is attributed to existing live earnings-calendar
nondeterminism because this patch does not touch `backtester.py`, signal
generation, risk, sizing, fills, or exits. The state-surface sleeve is not
traded by default backtests.

## Production Parity

`production_impact`:

- `shared_policy_changed=true`
- `run_adapter_changed=true`
- `backtester_adapter_changed=false`
- `parity_test_added=true`
- `alters_orders=false`
- `alters_signal_generation=false`
- `alters_candidate_ranking=false`
- `alters_sizing=false`

This is parity-safe for observation because production emits the paper sleeve
and default backtests do not trade it. A future live promotion is still blocked
until a shared backtester trade adapter consumes `state_surface_sleeve.py` and
forward paper outcomes clear the gate.

## Verification

`.\.venv\Scripts\python.exe -m pytest quant\test_state_surface_sleeve.py quant\test_event_sleeve_bundle.py quant\test_sec_event_queue.py -q`

Result: `24 passed in 1.93s`.

## Next Valid Step

Wait for at least 15 closed forward paper observations, then compare the
state-surface paper sleeve against cash and the frozen same-day core
alternatives. Do not retry balanced-surface pruning or nearby state-surface
threshold variants without new forward evidence.
