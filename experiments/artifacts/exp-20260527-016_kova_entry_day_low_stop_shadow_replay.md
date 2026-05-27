# exp-20260527-016 Kova Entry-Day-Low Stop Shadow Replay

Decision: `rejected_entry_day_low_stop_shadow_replay`.

The Kova entry-day-low stop failed the shadow replay gate. Keep the fixed 10-day VCP top-2 paper exit unchanged.

## Source

- Source population: `exp-20260526-007` `rank2_125` selected paper trades.
- Core, VCP definition, QQQ/SPY gate, top-2 selection, rank-notional profile, ranking, LLM/news, universe, and live/default orders unchanged.
- Tested exit field: `entry_day_low_minus_2pct_stop_v1`.

## PnL Comparison

| window | trades | triggers | source pnl | stop pnl | delta |
|---|---:|---:|---:|---:|---:|
| late_strong | 4 | 4 | 1466.65 | -2490.35 | -3957.0 |
| mid_weak | 88 | 40 | 27846.68 | 13473.88 | -14372.8 |
| old_thin | 25 | 8 | 8329.19 | 4790.5 | -3538.69 |
| aggregate | 117 | 52 | 37642.52 | 15774.03 | -21868.49 |

## Triggered Stop Readout

- Triggered trades: `52`.
- Triggered stop total PnL: `-22252.08`.
- Triggered stop average PnL: `-427.92`.
- Triggered stop win rate: `0.0`.

## Gate 4

No strategy promotion was possible in this experiment because this is a read-only exit replay.

```json
{
  "decision_evidence": {
    "aggregate_delta_positive": false,
    "aggregate_stop_pnl_delta_vs_source": -21868.49,
    "no_window_pnl_regression": false,
    "triggered_sample_passed": true,
    "triggered_trade_count": 52,
    "triggered_trade_count_min": 20,
    "windows_pnl_improved": 0,
    "windows_pnl_regressed": 3
  },
  "passed": false,
  "promotion_grade": false,
  "reason": "Observed-only frozen paper exit replay. No strategy exit rule is kept without a later closed Gate 1-4 replay.",
  "strategy_replacement_tested": false
}
```

## Repro

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260527_016_kova_entry_day_low_stop_shadow_replay.py
```
