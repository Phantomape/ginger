# exp-20260510-026 Form4 meaningful-purchase shadow attribution

## Hypothesis

Form4 open-market insider purchases below the existing `>= $500k` paper queue threshold may be useful candidate-pool alpha, but the threshold should not be lowered on the frozen sample. The safe next step is forward observation: surface `meaningful_purchase_v1` events that are below the forward queue threshold, while keeping queue candidates and all trading behavior unchanged.

## Change

Added `shadow_attribution` to `FORM4_MEANINGFUL_PURCHASE_FORWARD_QUEUE`:

```text
base_meaningful_purchase_event_count
below_forward_threshold_event_count
forward_queue_candidate_count
below_forward_threshold_events
```

This is observe-only. It does not alter `candidate_count`, candidate qualification, ranking, sizing, slots, or orders.

Current forward check:

| As of | Candidate count | Base meaningful | Below threshold | Symbols |
| --- | ---: | ---: | ---: | --- |
| 2026-05-06 | 0 | 1 | 1 | CAT ($219,210) |

## Gate 4

Canonical three-window fixed-snapshot backtests stayed unchanged versus the accepted core baseline:

| Window | EV | PnL | Return | Max DD | Trades | Survival |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | 4.2340 | $94,086.91 | 94.09% | 5.48% | 19 | 80.39% |
| mid_weak | 1.6689 | $61,813.40 | 61.81% | 9.41% | 21 | 79.25% |
| old_thin | 0.3853 | $28,544.11 | 28.54% | 8.15% | 22 | 91.67% |

Aggregate EV delta: `0.0000`. Aggregate PnL delta: `$0.00`.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest quant\test_form4_event_queue.py quant\test_form4_event_sleeve.py -q
.\.venv\Scripts\python.exe quant\backtester.py --start 2025-10-23 --end 2026-04-21 --ohlcv-snapshot data\ohlcv_snapshot_20251023_20260421.json
.\.venv\Scripts\python.exe quant\backtester.py --start 2025-04-23 --end 2025-10-22 --ohlcv-snapshot data\ohlcv_snapshot_20250423_20251022.json
.\.venv\Scripts\python.exe quant\backtester.py --start 2024-10-02 --end 2025-04-22 --ohlcv-snapshot data\ohlcv_snapshot_20241002_20250422.json
```

Result: `10 passed`; all three core windows unchanged.

## Production impact

```text
production_impact:
  shared_policy_changed: false
  shared_observation_module_changed: true
  backtester_adapter_changed: false
  run_adapter_changed: false
  replay_only: false
  parity_test_added: true
  alters_signal_generation: false
  alters_candidate_ranking: false
  alters_sizing: false
  alters_orders: false
```

Decision: accepted for forward observation only. Do not lower the existing `>= $500k` paper queue threshold until below-threshold events have closed forward outcomes with adequate count and concentration control.
