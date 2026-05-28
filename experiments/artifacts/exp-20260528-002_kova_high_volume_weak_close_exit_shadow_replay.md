# exp-20260528-002 Kova High-Volume Weak-Close Exit Shadow Replay

Decision: `rejected_kova_high_volume_weak_close_exit_shadow_replay`.

The Kova high-volume weak-close support-break exit failed Gate 4 because aggregate PnL or EV proxy did not improve. No Kova defensive-exit rule should be promoted from this shadow replay.

## Aggregate

- Before PnL: `37642.52`.
- After PnL: `36671.9792`.
- Delta PnL: `-970.5408`.
- Delta EV proxy: `-0.005483`.
- Triggered exits: `3`.
- Beneficial exits: `2`.
- Harmful exits: `1`.
- Max single positive delta share: `0.67033`.

## Windows

| window | triggered | before pnl | after pnl | delta pnl | delta EV proxy |
|---|---:|---:|---:|---:|---:|
| late_strong | 1 | 1466.65 | 70.8054 | -1395.8446 | -0.036633 |
| mid_weak | 1 | 27846.68 | 28131.7739 | 285.0939 | 0.003373 |
| old_thin | 1 | 8329.19 | 8469.3999 | 140.2099 | 0.00423 |

## Gate 4

```json
{
  "decision_evidence": {
    "aggregate_total_pnl_delta": -970.5408,
    "expected_value_proxy_delta": -0.005483,
    "max_single_positive_delta_share": 0.67033,
    "max_single_positive_delta_share_max": 0.4,
    "shadow_gate_passed": false,
    "triggered_count": 3,
    "triggered_count_min": 10,
    "windows_regressed": [
      "late_strong"
    ]
  },
  "passed": false,
  "promotion_grade": false,
  "reason": "Closed-trade shadow replay only; no production strategy rule changed.",
  "strategy_replacement_tested": false
}
```

## Repro

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260528_002_kova_high_volume_weak_close_exit_shadow_replay.py
```
