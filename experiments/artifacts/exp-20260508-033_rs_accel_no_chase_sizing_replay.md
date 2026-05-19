# exp-20260508-033 RS Accel No-Chase Sizing Replay

## Decision

Rejected.

This was an alpha-search capital-allocation experiment, not a bug fix. It
tested one causal variable: increasing post-existing-rule risk budget for
existing `trend_long` and `breakout_long` signals tagged
`rs_accel_no_chase`.

## Hypothesis

The previous shadow audit found that A/B candidates with positive 20-day
SPY-relative strength, improving relative strength versus the prior 20-day
window, and no 3% signal-day gap chase had better forward returns. This replay
tested whether that observation survives as a sizing rule for already-selected
signals.

## Result

Best variant: `mult_1_25`.

| Window | EV Before | EV After | EV Delta | PnL Delta | Sharpe Daily Delta | Max DD Delta | Win Rate Delta | Trades Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | 4.0674 | 4.2634 | +0.1960 | +$5,451.87 | -0.05 | +0.26 pp | 0.00 pp | 0 |
| `mid_weak` | 1.6195 | 1.6033 | -0.0162 | -$165.42 | -0.02 | 0.00 pp | 0.00 pp | 0 |
| `old_thin` | 0.3583 | 0.3341 | -0.0242 | -$1,039.82 | -0.04 | +0.30 pp | 0.00 pp | 0 |

Aggregate `EV +0.1556` (`+2.57%`) and aggregate `PnL +$4,246.63`
(`+2.39%`) did not clear Gate 4. More importantly, EV/PnL improved only in
`late_strong`; both validation windows regressed.

The wider `mult_1_50` variant increased aggregate PnL more (`+$5,413.55`) but
reduced aggregate EV improvement to `+1.41%` and worsened drawdown by up to
`+0.85 pp`, also only improving `late_strong`.

## Attribution

For `mult_1_25`, the temporary sizing rule touched:

| Window | Signals Seen | Trades | Trade Win Rate | Attributed Trade PnL |
| --- | ---: | ---: | ---: | ---: |
| `late_strong` | 17 | 14 | 85.71% | $80,366.59 |
| `mid_weak` | 14 | 10 | 70.00% | $38,263.57 |
| `old_thin` | 18 | 10 | 30.00% | $2,023.27 |

The tag identifies strong-tape winners, but its old-window trade win rate is
only 30%. That explains why raw sizing promotion is not robust.

## Production Parity

No production behavior changed. The script monkeypatches feature enrichment,
risk annotation, and sizing only during the experiment run. Promotion would
require a shared production/backtest implementation and parity tests before any
strategy change.

`production_impact`:

- `shared_policy_changed=false`
- `backtester_adapter_changed=false`
- `run_adapter_changed=false`
- `replay_only=true`
- `parity_test_added=false`

## Anti-Repeat

Do not retry nearby `rs_accel_no_chase` sizing multipliers on the same fixed
windows. A valid retry needs an orthogonal qualifier that explains the
`old_thin` failure, such as event/news confirmation, stronger candidate
replacement evidence, or a different regime-specific capital allocator.

Artifact:
`data/experiments/exp-20260508-033/exp-20260508-033_rs_accel_no_chase_sizing_replay.json`
