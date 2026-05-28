# exp-20260527-910 Kova Fixed Max-Loss Stop Shadow Replay

Decision: `rejected_kova_max_loss_stop_shadow_replay`.

The fixed maximum-loss stop failed Gate 4 because aggregate PnL or EV proxy did not improve. No Kova max-loss stop rule should be promoted from this shadow replay.

## Aggregate

- Before PnL: `37642.52`.
- After PnL: `29963.7722`.
- Delta PnL: `-7678.7478`.
- Delta EV proxy: `-0.05896`.
- Stopped trades: `9`.
- Beneficial stops: `1`.
- Harmful stops: `8`.
- Max single positive delta share: `1.0`.

## Windows

| window | stopped | before pnl | after pnl | delta pnl | delta EV proxy |
|---|---:|---:|---:|---:|---:|
| late_strong | 3 | 1466.65 | -2458.9012 | -3925.5512 | 0.165853 |
| mid_weak | 5 | 27846.68 | 24804.2547 | -3042.4253 | -0.027794 |
| old_thin | 1 | 8329.19 | 7618.4187 | -710.7713 | -0.018935 |

## Gate 4

```json
{
  "decision_evidence": {
    "aggregate_total_pnl_delta": -7678.7478,
    "expected_value_proxy_delta": -0.05896,
    "max_single_positive_delta_share": 1.0,
    "max_single_positive_delta_share_max": 0.4,
    "shadow_gate_passed": false,
    "triggered_count": 9,
    "triggered_count_min": 10,
    "windows_regressed": [
      "late_strong",
      "mid_weak",
      "old_thin"
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
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260527_910_kova_max_loss_stop_shadow_replay.py
```
