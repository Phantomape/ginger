# exp-20260524-012 Entry-Day Component Attribution

Decision: `accepted_measurement_repair_no_strategy_change`.

This is measurement repair, not a strategy promotion. It adds point-in-time
component attribution to `quant/entry_day_ranking_attribution.py` so future
component-aware ranking and sizing experiments do not depend on ad hoc replay
scripts.

## Trial Accounting

- lane: `measurement_repair`
- trial_family: `entry_day_component_attribution`
- changed_variable: `entry_day_ranking_component_attribution_surface`
- prior_trial_count: `0`
- multiple_testing_risk_bucket: `minimal`
- new_evidence_type: `pit_component_bucket_coverage`

## Gate Questions

1. Alpha hypothesis: component-aware ranking allocation may improve EV, but only
   if PIT component buckets show repeatable replacement value rather than the
   one-off behavior seen in recent component top-ups.
2. History check: `exp-20260524-003`, `exp-20260524-007`, and
   `exp-20260524-011` tested raw relative-strength, breadth-alignment, and
   trend component scalars and failed Gate 4. `exp-20260523-012` validated PIT
   ranking/vector coverage but did not summarize components.
3. Single causal variable: no trading variable changed; only the read-only
   attribution surface changed.
4. Acceptance standard: focused tests pass and canonical three-window reports
   preserve 100% PIT coverage with schema v2 component diagnostics.
5. Reproducibility: rerun the three commands listed below against the canonical
   result artifacts and matching OHLCV snapshots.

## Evidence

Focused verification:

```text
.\.venv\Scripts\python.exe -m pytest quant\test_entry_day_ranking_attribution.py
.\.venv\Scripts\python.exe -m py_compile quant\entry_day_ranking_attribution.py quant\test_entry_day_ranking_attribution.py
```

Canonical report regeneration:

```text
.\.venv\Scripts\python.exe quant\entry_day_ranking_attribution.py data\experiments\exp-20260518-004\canonical\late_strong_core_result.json data\ohlcv\ohlcv_snapshot_20251023_20260421.json --output data\experiments\exp-20260524-012\late_strong_entry_day_component_attribution.json
.\.venv\Scripts\python.exe quant\entry_day_ranking_attribution.py data\experiments\exp-20260518-004\canonical\mid_weak_core_result.json data\ohlcv\ohlcv_snapshot_20250423_20251022.json --output data\experiments\exp-20260524-012\mid_weak_entry_day_component_attribution.json
.\.venv\Scripts\python.exe quant\entry_day_ranking_attribution.py data\experiments\exp-20260518-004\canonical\old_thin_core_result.json data\ohlcv\ohlcv_snapshot_20241002_20250422.json --output data\experiments\exp-20260524-012\old_thin_entry_day_component_attribution.json
```

## Three-Window Coverage

| Window | Trades | PIT-safe | Alpha score coverage | Components |
|---|---:|---:|---:|---:|
| `late_strong` | 18 | 18 | 18 | 6 |
| `mid_weak` | 21 | 21 | 21 | 6 |
| `old_thin` | 22 | 22 | 22 | 6 |

Aggregate coverage: `61 / 61` point-in-time safe trades.

## Component Readout

| Component | Bucket | Trades | Total PnL |
|---|---:|---:|---:|
| `breadth_alignment` | high | 29 | `$91,426.03` |
| `breadth_alignment` | mid | 32 | `$143,424.96` |
| `expectation_revision` | mid | 61 | `$234,850.99` |
| `post_earnings_drift` | mid | 61 | `$234,850.99` |
| `relative_strength` | high | 10 | `$50,623.14` |
| `relative_strength` | mid | 51 | `$184,227.85` |
| `theme_participation` | mid | 52 | `$180,230.52` |
| `theme_participation` | low | 9 | `$54,620.47` |
| `trend` | high | 61 | `$234,850.99` |

`expectation_revision` and `post_earnings_drift` were constant `0.5` in all
three canonical windows. `trend` was always high. Those fields should not be
used for another raw scalar on the frozen canonical sample without new forward
evidence or a materially different interaction.

## Production Impact

```text
shared_policy_changed: false
backtester_adapter_changed: false
run_adapter_changed: false
production_orders_changed: false
```

No JavaScript was used.
