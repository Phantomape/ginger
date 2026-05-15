# exp-20260514-007 Legacy Target Review Visibility

## Decision

Accepted as measurement repair only.

The production advisory path now surfaces legacy-basis explicit target hits as
`LEGACY_TARGET_REVIEW`. This is deliberately non-executable: it does not map to
`SIGNAL_TARGET`, `TARGET_EXIT`, `HIGH_REDUCE`, sizing, ranking, entry, or any
backtest execution path.

## Why

`exp-20260513-005` showed 34 saved daily rows where an explicit target was hit
but hidden behind `legacy_basis=True`. `exp-20260513-008` then showed that
turning those rows into automatic exits was negative: the silent full-exit
variant lost `$2,332.93` versus hold, and the target-stop ratchet was inert.

So the right closeout is not "sell legacy targets"; it is "make them visible
for review without creating an order."

## Validation

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest quant\test_quant.py -q -k "legacy_signal_target or preflight_legacy_target_review or legacy_target_review_in_attention or signal_target_uses_daily_high or preflight_signal_target_maps"
```

Result: `6 passed, 310 deselected`.

Covered behavior:

- TSLA-like target hit emits `LEGACY_TARGET_REVIEW`, not `SIGNAL_TARGET`.
- AMD-like stale target is flagged with `stale_target_10pct_below_trigger=true`.
- `LEGACY_TARGET_REVIEW` stays `HOLD` in preflight.
- `LEGACY_TARGET_REVIEW` appears in `positions_requiring_attention`.
- Non-legacy `SIGNAL_TARGET` still maps to `TARGET_EXIT`.

## Production Impact

```json
{
  "shared_policy_changed": true,
  "backtester_adapter_changed": false,
  "run_adapter_changed": false,
  "replay_only": false,
  "parity_test_added": true,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_candidate_ranking": false,
  "alters_sizing": false,
  "alters_backtest_execution": false,
  "daily_prompt_visibility_changed": true
}
```
