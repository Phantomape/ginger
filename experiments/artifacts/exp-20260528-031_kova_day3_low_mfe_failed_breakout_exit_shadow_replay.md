# exp-20260528-031 Kova Day-3 Low-MFE Failed-Breakout Exit Shadow Replay

Decision: `rejected_kova_day3_low_mfe_failed_breakout_exit_shadow_replay`.

The day-3 low-MFE failed-breakout exit failed Gate 4 because aggregate PnL or EV proxy did not improve. No Kova failed-breakout exit rule should be promoted from this shadow replay.

## Aggregate

- Before PnL: `37642.52`.
- After PnL: `30632.5016`.
- Delta PnL: `-7010.0184`.
- Delta EV proxy: `-0.051596`.
- Triggered exits: `11`.
- Beneficial exits: `2`.
- Harmful exits: `9`.
- Failed-low-MFE label share: `0.272727`.
- Top positive delta ticker share: `0.8999588941675899`.

## Window Metrics

| window | triggered | before pnl | after pnl | delta pnl | delta EV proxy |
|---|---:|---:|---:|---:|---:|
| late_strong | 2 | 1466.65 | -2652.5842 | -4119.2342 | 0.152936 |
| mid_weak | 9 | 27846.68 | 24955.8958 | -2890.7842 | -0.022851 |
| old_thin | 0 | 8329.19 | 8329.19 | 0.0 | 0.0 |

## Trigger Taxonomy Buckets

| taxonomy primary bucket | triggered trades |
|---|---:|
| failed_breakout_low_mfe | 1 |
| max_loss_stop_touch | 5 |
| orderly_or_unclassified_hold | 4 |
| strong_followthrough_no_warning | 1 |

## Related Files

- `quant/experiments/exp_20260528_031_kova_day3_low_mfe_failed_breakout_exit_shadow_replay.py`
- `data/experiments/exp-20260526-007/vcp_rank_notional_profile.json`
- `data/experiments/exp-20260528-014/kova_sell_side_lifecycle_taxonomy.json`
- `data/experiments/exp-20260528-031/kova_day3_low_mfe_failed_breakout_exit_shadow_replay.json`
- `experiments/artifacts/exp-20260528-031_kova_day3_low_mfe_failed_breakout_exit_shadow_replay.md`
- `experiments/logs/exp-20260528-031.json`
- `experiments/tickets/exp-20260528-031.json`
- `docs/experiments/tickets/exp-20260528-031.json`
- `docs/experiment_log.jsonl`
- `docs/experiment_registry.json`
