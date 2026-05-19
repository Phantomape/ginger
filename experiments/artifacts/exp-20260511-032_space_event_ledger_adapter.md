# exp-20260511-032 Space Event Ledger Adapter

Status: accepted observe-only measurement adapter.

This step moves the `exp-20260511-008` Space event-state harness into the daily
production-visible surface. It does not enable live Space slots, change core
signals, change ranking, change sizing, or route orders.

## What Changed

- Added a shared Space event ledger helper in `quant/space_catalyst_sleeve.py`.
- Added `data/space_catalyst_event_seeds.jsonl` as the manually reviewed seed
  event file.
- Wired `quant/run.py` to fetch only ledger-needed OHLCV, build the snapshot,
  persist `data/space_catalyst_event_state_shadow_ledger.jsonl`, and include
  the snapshot in `trend_signals` / `quant_signals`.
- Added a report section named `SPACE CATALYST EVENT LEDGER`.
- Updated parity documentation for the default-off Space catalyst surface.

## Validation

- AST parse passed for `space_catalyst_sleeve.py`, `run.py`,
  `report_generator.py`, and `test_space_catalyst_sleeve.py`.
- Focused tests: `20 passed`.
- Snapshot probe on the augmented late window at `2026-04-21` produced
  `2` active seed events, `2` event/ticker rows, `1` closed 10d decision, and
  a blocked promotion gate.

## Production Impact

```text
production_impact:
  shared_policy_changed: false
  shared_observation_helper_changed: true
  backtester_adapter_changed: false
  run_adapter_changed: true
  replay_only: false
  parity_test_added: true
  alters_orders: false
  alters_signal_generation: false
  alters_candidate_ranking: false
  alters_sizing: false
  live_slots: 0
```

## Decision

Accepted as observe-only evidence collection. The next valid promotion step is
not another static Space basket replay; it is at least `10` mature event
decisions with positive direct, same-theme, and benchmark-relative replacement
value, led by official catalyst buckets rather than attention-only rows.
