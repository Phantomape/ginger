# exp-20260527-909 Kova Confirmation Pyramid Shadow Replay

Decision: `rejected_pnl_positive_but_ev_proxy_regressed_kova_confirmation_pyramid`.

The confirmation add-on increased closed-trade PnL, but the risk-adjusted EV proxy and/or return on deployed notional regressed. No Kova pyramiding rule should be promoted from this capital-only lift.

## Aggregate

- Before PnL: `37642.52`.
- After PnL: `43997.0555`.
- Delta PnL: `6354.5355`.
- Delta PnL pct: `0.168813`.
- Delta EV proxy: `-0.019154`.
- Delta return on deployed notional: `-0.000467`.
- Triggered add-ons: `44`.
- Add-on win rate: `0.704545`.
- Max single positive add-on share: `0.1077`.

## Windows

| window | triggered | before pnl | after pnl | delta pnl |
|---|---:|---:|---:|---:|
| late_strong | 0 | 1466.65 | 1466.65 | 0.0 |
| mid_weak | 33 | 27846.68 | 33386.0097 | 5539.3297 |
| old_thin | 11 | 8329.19 | 9144.3958 | 815.2058 |

## Gate 4

```json
{
  "decision_evidence": {
    "aggregate_total_pnl_delta_pct": 0.168813,
    "aggregate_total_pnl_delta_pct_min": 0.1,
    "expected_value_proxy_delta": -0.019154,
    "max_single_positive_addon_share": 0.1077,
    "max_single_positive_addon_share_max": 0.4,
    "return_on_deployed_notional_delta": -0.000467,
    "risk_adjusted_proxy_non_regression_required": true,
    "shadow_gate_passed": false,
    "triggered_count": 44,
    "triggered_count_min": 20,
    "windows_regressed": []
  },
  "passed": false,
  "promotion_grade": false,
  "reason": "Closed-trade shadow replay only; no production strategy rule changed.",
  "strategy_replacement_tested": false
}
```

## Repro

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260527_909_kova_confirmation_pyramid_shadow_replay.py
```
