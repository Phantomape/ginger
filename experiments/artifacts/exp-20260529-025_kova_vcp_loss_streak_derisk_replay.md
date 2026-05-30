# exp-20260529-025 Kova VCP Loss-Streak De-Risking Replay

Decision: `rejected_kova_vcp_loss_streak_derisk_replay`.

The Kova VCP closed-ledger loss-streak de-risking replay failed Gate 4 (failed checks: aggregate_pnl_improved). Do not promote this notional scalar from the closed paper ledger.

## Aggregate

- Before PnL: `37642.52`.
- After PnL: `36786.19`.
- Delta PnL: `-856.33`.
- Delta EV proxy: `0.003721`.
- Drawdown delta: `-254.185`.
- Scaled trades: `11`.
- Beneficial scaled trades: `5`.
- Harmful scaled trades: `6`.
- Top positive delta ticker share: `0.300233`.

## Windows

| window | scaled | before pnl | after pnl | delta pnl | delta EV proxy | drawdown delta | regressed |
|---|---:|---:|---:|---:|---:|---:|---|
| late_strong | 0 | 1466.65 | 1466.65 | 0.0 | 0.0 | 0.0 | False |
| mid_weak | 11 | 27846.68 | 26990.35 | -856.33 | 0.003842 | -254.185 | True |
| old_thin | 0 | 8329.19 | 8329.19 | 0.0 | 0.0 | 0.0 | False |

## Largest Scaled Trades

| ticker | window | entry | exit | base pnl | scalar | delta pnl | prior loss streak |
|---|---|---|---|---:|---:|---:|---:|
| GS | mid_weak | 2025-06-12 | 2025-06-26 | 1019.32 | 0.5 | -509.66 | 2 |
| AVGO | mid_weak | 2025-05-30 | 2025-06-12 | 712.51 | 0.5 | -356.255 | 3 |
| CAT | mid_weak | 2025-06-12 | 2025-06-26 | 708.24 | 0.5 | -354.12 | 2 |
| META | mid_weak | 2025-07-01 | 2025-07-15 | -505.15 | 0.5 | 252.575 | 2 |
| NVDA | mid_weak | 2025-07-14 | 2025-07-25 | 446.14 | 0.5 | -223.07 | 2 |
| DIS | mid_weak | 2025-07-01 | 2025-07-15 | -410.63 | 0.5 | 205.315 | 2 |
| NVDA | mid_weak | 2025-05-30 | 2025-06-12 | 407.98 | 0.5 | -203.99 | 3 |
| UNH | mid_weak | 2025-10-09 | 2025-10-22 | -340.79 | 0.5 | 170.395 | 2 |
| SPOT | mid_weak | 2025-06-24 | 2025-07-08 | -269.1 | 0.5 | 134.55 | 2 |
| UNH | mid_weak | 2025-10-06 | 2025-10-17 | -167.58 | 0.5 | 83.79 | 2 |

## Gate 4

```json
{
  "aggregate_drawdown_delta_pnl": -254.185,
  "aggregate_ev_improved": true,
  "aggregate_pnl_improved": false,
  "beneficial_scaled_count": 5,
  "concentration_ok": true,
  "drawdown_ok": true,
  "harmful_scaled_count": 6,
  "max_single_positive_delta_share_limit": 0.5,
  "scaled_count": 11,
  "scaled_count_min": 10,
  "scaled_count_ok": true,
  "shadow_gate_passed": false,
  "top_ticker_positive_delta_share": 0.300233,
  "window_regression_ok": true,
  "window_regressions": [
    "mid_weak"
  ],
  "window_regressions_max": 1
}
```

## Repro

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260529_025_kova_vcp_loss_streak_derisk_replay.py
```

## Related Files

- `quant/experiments/exp_20260529_025_kova_vcp_loss_streak_derisk_replay.py`
- `data/experiments/exp-20260529-025/kova_vcp_loss_streak_derisk_replay.json`
- `experiments/logs/exp-20260529-025.json`
- `experiments/tickets/exp-20260529-025.json`
- `docs/experiments/tickets/exp-20260529-025.json`
- `experiments/cards/exp-20260529-025.md`
- `experiments/manifests/exp-20260529-025.json`
- `experiments/artifacts/exp-20260529-025_kova_vcp_loss_streak_derisk_replay.md`
- `data/experiments/exp-20260526-007/vcp_rank_notional_profile.json`
