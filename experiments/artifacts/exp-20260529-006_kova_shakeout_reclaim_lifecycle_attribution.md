# exp-20260529-006 Kova Shakeout/Reclaim Lifecycle Attribution

Decision: `observed_only_no_promotable_edge`.

The early shakeout/reclaim bucket is not promotable from this closed paper attribution. Failed checks: sample_ok.

## Evidence

- Reclaim trades: `7`.
- Reclaim total PnL: `4039.29`.
- Reclaim avg PnL: `577.0414`.
- No-reclaim avg PnL: `-107.417`.
- Avg PnL edge vs no-reclaim: `684.4584`.
- Reclaim top positive ticker share: `0.44358377829476997`.
- Gate checks: sample `False`, positive `True`, comparator `True`, concentration `True`.

## Bucket Metrics

| bucket | trades | total pnl | avg pnl | return on notional | win rate | top positive ticker share |
|---|---:|---:|---:|---:|---:|---:|
| early_shakeout_reclaim | 7 | 4039.29 | 577.0414 | 0.05212 | 0.857143 | 0.44358377829476997 |
| early_shakeout_no_reclaim | 20 | -2148.34 | -107.417 | -0.009992 | 0.3 | 0.3524305983200729 |
| no_early_shakeout | 90 | 35751.57 | 397.2397 | 0.036022 | 0.677778 | 0.16297783735432536 |
| unavailable | 0 | 0 | 0.0 | 0.0 | 0.0 | None |

## Window Buckets

| window | reclaim trades | reclaim pnl | no-reclaim trades | no-reclaim pnl | no-shakeout trades | no-shakeout pnl |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0 | 0 | 4 | 1466.65 | 0 | 0 |
| mid_weak | 6 | 3892.26 | 14 | -2870.77 | 68 | 26825.19 |
| old_thin | 1 | 147.03 | 2 | -744.22 | 22 | 8926.38 |

## Related Files

- `quant/experiments/exp_20260529_006_kova_shakeout_reclaim_lifecycle_attribution.py`
- `data/experiments/exp-20260529-006/kova_shakeout_reclaim_lifecycle_attribution.json`
- `experiments/logs/exp-20260529-006.json`
- `experiments/tickets/exp-20260529-006.json`
- `docs/experiments/tickets/exp-20260529-006.json`
- `experiments/cards/exp-20260529-006.md`
- `experiments/artifacts/exp-20260529-006_kova_shakeout_reclaim_lifecycle_attribution.md`
- `data/experiments/exp-20260526-007/vcp_rank_notional_profile.json`
