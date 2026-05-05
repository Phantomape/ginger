# Form 4 Default-Off Paper Event Sleeve Harness

- experiment_id: `exp-20260504-013`
- timestamp: `2026-05-04T02:29:32+00:00`
- decision: `default_off_candidate`
- production impact: no order, sizing, ranking, signal-generation, or core slot changes

## Similar Experiments

- Exact Form 4 lineage: exp-20260503-017/020/025/026/030/033/037/040/042, exp-20260504-001/005/006/009.
- Reusable harness lineage: exp-20260427-019 scarce-slot default-off harness, exp-20260501-029/030 pilot sleeve attribution, exp-20260504-010/011/012 SEC event queue.
- Main constraint: prior Form 4 10d sleeve replay was positive, but slot replacement value is still inconclusive.

## Current Smoke

- as_of: `2026-05-04`
- queue candidate_count: `0`
- paper pending_count: `0`
- paper open_position_count: `0`
- paper realized_pnl_to_date: `$0.00`
- trade_enabled: `False`

## Validation

- `python -m pytest quant/test_form4_event_sleeve.py quant/test_form4_event_queue.py` -> 8 passed.
- `python -B` import/compile smoke passed for the new module, report generator, and run adapter.

## Next Minimum Action

Run the normal daily pipeline and let the default-off paper state accumulate closed Form 4 outcomes before considering paper-to-live promotion.
