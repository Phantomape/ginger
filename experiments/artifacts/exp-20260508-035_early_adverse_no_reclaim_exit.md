# exp-20260508-035 Early-Adverse No-Reclaim Exit Replay

Decision: `rejected`

## Hypothesis

Already-open A/B trades that suffer a material early adverse move without a meaningful three-day reclaim may be lower-quality holds; exiting them at the next open could reduce tail losses without adding entry filters or weakening hard risk controls.

## Baseline

| EV sum | PnL sum | Trades |
|---:|---:|---:|
| 6.0452 | 177676.93 | 62 |

## Three-Window Replay

| Window | EV before | EV after | EV delta | PnL delta | Sharpe delta | Max DD delta | Triggers | Winner trunc. | Loser improved |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.2326 | 3.7457 | -1.4869 | -15539.57 | -0.78 | 0.004 | 2 | 2 | 0 |
| mid_weak | 2.8156 | 2.8156 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| old_thin | 0.6668 | 0.7697 | 0.1029 | 1846.58 | 0.2 | -0.0145 | 3 | 0 | 3 |

## Aggregate

- EV delta sum: `-1.384` (-0.158807)
- PnL delta sum: `$-13692.99` (-0.077067)
- Windows EV improved/regressed: `1/1`
- Triggers: `5`
- Winner truncations: `2`
- Loser improvements: `3`
- Max single-ticker positive share: `0.9932`
- Gate 4: `FAIL`

## Decision Rationale

Rejected. The early-adverse/no-reclaim exit did not satisfy the EV-first three-window Gate 4 robustness standard.

## Production Impact

Replay only. No production order path, shared policy, backtester default behavior, run adapter, universe, ranking, sizing, add-on, LLM, or news behavior changed.
