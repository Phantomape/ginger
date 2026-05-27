# exp-20260526-022 VCP Base Geometry / Higher-Low Attribution

Decision: `observed_only_no_actionable_base_geometry_split`.

The pre-signal higher-low base geometry bucket did not clear the observed-only attribution bar. Keep the VCP top-2 rank-notional sleeve unchanged and avoid turning this frozen-sample split into a gate.

## Source

- Source population: `exp-20260526-007` `rank2_125` selected paper trades.
- Core, VCP definition, QQQ/SPY gate, top-2 selection, rank-notional profile, exits, LLM/news, universe, and live/default orders unchanged.
- Tested field: `pre_signal_base_geometry_bucket_v1`.

## Aggregate Buckets

| bucket | trades | total pnl | avg pnl | win rate | avg risk-to-pivot |
|---|---:|---:|---:|---:|---:|
| constructive_higher_low_base | 84 | 26534.93 | 315.89 | 0.630952 | 0.061328 |
| nonconstructive_or_lower_low_base | 33 | 11107.59 | 336.59 | 0.606061 | 0.077893 |
| insufficient_swing_low_structure | 0 | 0.0 | None | None | None |
| unavailable | 0 | 0.0 | None | None | None |

## Window Buckets

| window | bucket | trades | total pnl | avg pnl | win rate |
|---|---|---:|---:|---:|---:|
| late_strong | constructive_higher_low_base | 3 | 322.04 | 107.35 | 0.333333 |
| late_strong | nonconstructive_or_lower_low_base | 1 | 1144.61 | 1144.61 | 1.0 |
| mid_weak | constructive_higher_low_base | 66 | 21230.3 | 321.67 | 0.636364 |
| mid_weak | nonconstructive_or_lower_low_base | 22 | 6616.38 | 300.74 | 0.590909 |
| old_thin | constructive_higher_low_base | 15 | 4982.59 | 332.17 | 0.666667 |
| old_thin | nonconstructive_or_lower_low_base | 10 | 3346.6 | 334.66 | 0.6 |

## Constructive Bucket Readout

- Constructive bucket trades: `84`.
- Constructive bucket total PnL: `26534.93`.
- Constructive bucket average PnL: `315.89`.
- Max single positive PnL share: `0.213184`.
- Positive PnL HHI: `0.121329`.

## Gate 4

No strategy promotion was possible in this experiment because this is read-only attribution.

```json
{
  "decision_evidence": {
    "constructive_avg_pnl": 315.89,
    "constructive_beats_nonconstructive_avg_pnl": false,
    "constructive_concentration_passed": true,
    "constructive_max_single_positive_pnl_share": 0.213184,
    "constructive_positive_aggregate": true,
    "constructive_positive_pnl_hhi": 0.121329,
    "constructive_positive_windows": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ],
    "constructive_trade_count_min_20": true,
    "constructive_trade_counts_by_window": {
      "late_strong": 3,
      "mid_weak": 66,
      "old_thin": 15
    },
    "nonconstructive_or_unavailable_avg_pnl": 336.59
  },
  "passed": false,
  "promotion_grade": false,
  "reason": "Observed-only metadata attribution. A later closed forward or Gate 1-4 replacement test is required before any strategy change.",
  "strategy_replacement_tested": false
}
```

## Repro

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260526_022_vcp_base_geometry_higher_low_attribution.py
```
