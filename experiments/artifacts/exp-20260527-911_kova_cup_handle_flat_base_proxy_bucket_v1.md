# exp-20260527-911 Kova Cup/Flat Base Proxy Attribution

Decision: `observed_only_inverse_kova_base_shape_signal_requires_forward_evidence`.

The textbook Kova cup/flat-base proxy was not the useful bucket; the only material outperforming bucket was the non-textbook deep/loose base proxy. Treat this as an inverse diagnostic clue, not as a production ranking or entry rule.

## Source Aggregate

- Trades: `117`.
- Total PnL: `37642.52`.
- EV proxy: `0.148165`.
- Return on notional: `0.029294`.

## Buckets

| bucket | trades | total pnl | ev proxy | win rate | positive windows | max single positive share |
|---|---:|---:|---:|---:|---:|---:|
| cup_with_handle_proxy | 75 | 16505.74 | 0.076479 | 0.6 | 2 | 0.066209 |
| flat_base_proxy | 1 | -665.01 | -0.0 | 0.0 | 0 | None |
| deep_or_loose_base_proxy | 29 | 21502.16 | 0.283873 | 0.724138 | 3 | 0.11043 |
| no_clear_cup_or_flat_base_proxy | 12 | 299.63 | 0.000493 | 0.583333 | 2 | 0.389399 |
| insufficient_pre_signal_history | 0 | 0 | 0.0 | 0.0 | 0 | None |
| unavailable | 0 | 0 | 0.0 | 0.0 | 0 | None |

## Window PnL

| bucket | late_strong pnl | mid_weak pnl | old_thin pnl |
|---|---:|---:|---:|
| cup_with_handle_proxy | -6.37 | 12783.88 | 3728.23 |
| flat_base_proxy | 0 | 0 | -665.01 |
| deep_or_loose_base_proxy | 1144.61 | 15569.88 | 4787.67 |
| no_clear_cup_or_flat_base_proxy | 328.41 | -507.08 | 478.3 |
| insufficient_pre_signal_history | 0 | 0 | 0 |
| unavailable | 0 | 0 | 0 |

## Gate 4

```json
{
  "attribution_gate_passed": true,
  "decision_evidence": {
    "classification_counts": {
      "cup_with_handle_proxy": 75,
      "deep_or_loose_base_proxy": 29,
      "flat_base_proxy": 1,
      "no_clear_cup_or_flat_base_proxy": 12
    },
    "material_bucket_count": 2,
    "max_single_positive_pnl_share": 0.4,
    "min_material_bucket_trades": 20,
    "min_positive_windows": 2,
    "playbook_frozen_sample_guard": true,
    "promising_buckets": [
      "deep_or_loose_base_proxy"
    ],
    "promising_inverse_or_non_textbook_buckets": [
      "deep_or_loose_base_proxy"
    ],
    "promising_textbook_cup_flat_buckets": [],
    "promotion_grade": false,
    "source_expected_value_proxy": 0.148165,
    "source_total_pnl": 37642.52,
    "source_trade_count": 117
  },
  "passed": false,
  "promotion_grade": false,
  "reason": "Read-only frozen-sample base-shape attribution; no production strategy rule changed or promoted.",
  "strategy_replacement_tested": false
}
```

## Repro

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260527_911_kova_cup_handle_flat_base_proxy_bucket_v1.py
```
