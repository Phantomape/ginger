# exp-20260509-009 Event Bundle Trade Adapter Parity

Decision: `accepted_default_off_parity_adapter`

Alpha direction selected: event candidate-pool allocation. The active lead remains the non-generic positive state-surface event add-on from `exp-20260509-007`, because it improved EV in all three canonical windows versus the full event bundle.

## What Changed

- Added `event_bundle_forward_gated_trade_plan_v1` in `quant/event_sleeve_bundle.py`.
- The trade plan is blocked unless `trade_enabled=true`, the forward paper gate passes, the kill switch is clear, the candidate schema is valid, and the paper snapshot is enabled.
- Default snapshots now expose a blocked `trade_plan` audit surface, but default live orders and default core backtests remain unchanged.
- Added focused parity tests for default-blocked and forward-gated executable states.

## Three-Window Alpha Evidence

Source: `exp-20260509-007`.

| Window | Full EV | Variant EV | Delta EV | Full PnL | Variant PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 4.5771 | 4.8980 | +0.3209 | $97,384.30 | $101,828.78 | +$4,444.48 |
| mid_weak | 2.0830 | 2.3533 | +0.2703 | $67,850.50 | $72,186.99 | +$4,336.49 |
| old_thin | 0.3938 | 0.4231 | +0.0293 | $28,745.97 | $30,005.02 | +$1,259.05 |

Aggregate EV delta versus full bundle: +0.6205 (+8.80%). Aggregate PnL delta: +$10,040.02 (+5.18%). EV improved/regressed: 3/0.

## Default Core Check After Adapter

The adapter is default-off, so it should not move default core metrics.

| Window | EV | PnL | Sharpe Daily | Max DD | Win Rate | Trades |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 4.0674 | $90,788.88 | 4.48 | 5.39% | 79.0% | 19 |
| mid_weak | 1.6195 | $59,540.63 | 2.72 | 8.79% | 52.4% | 21 |
| old_thin | 0.3583 | $27,347.42 | 1.31 | 9.03% | 40.9% | 22 |

These match the accepted default core stack after the add-on heat parity repair.

## Production Impact

```json
{
  "shared_policy_changed": true,
  "backtester_adapter_changed": false,
  "run_adapter_changed": true,
  "replay_only": false,
  "parity_test_added": true,
  "alters_orders": false,
  "default_live_orders_changed": false
}
```

No live event orders were enabled. Promotion is still blocked until closed forward paper replacement-value outcomes pass the shared gate.

## Verification

- `.\.venv\Scripts\python.exe -m pytest quant\test_event_sleeve_bundle.py -q` -> 10 passed.
- Fixed windows from `docs/backtesting.md` were rerun for default core invariance.

## Why Not Other Alpha Surfaces

LLM soft-ranking and earnings/revisions remain data-limited. Generic heat reserve, event source pruning, clean mid-dispersion top-up, raw universe growth, and nearby core retunes have recent rejected or below-materiality records. This run keeps focus on the only current three-window positive event-allocation surface while removing the promotion parity blocker.
