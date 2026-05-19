# exp-20260507-009: Core Platform Exit Capture Diagnostic

Decision: `shadow_only`
Next action: `pre_register_core_platform_runner_exit_replay`

## Official Baseline

| EV sum | PnL sum | Trades |
|---:|---:|---:|
| 5.6272 | 167347.95 | 62 |

## Aggregate Capture

| Cohort | Trades | PnL | Win rate | Median capture 40d MFE | Runner candidates | Exit before 40d MFE |
|---|---:|---:|---:|---:|---:|---:|
| treatment | 11 | 27692.68 | 0.5455 | 0.410675 | 5 | 5 |
| control | 6 | 6288.28 | 0.3333 | -0.406788 | 1 | 4 |

## Diagnostic Gate

Runner-exit replay needs at least 8 treatment trades, at least 3 runner candidates, and median 40d MFE capture below 0.65.

## Production Parity

No production policy changed. This is observed-only attribution.
