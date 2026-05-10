# exp-20260510-006 Zero-position QQQ Overlay

Decision: `directionally_positive_replay_only`

## Hypothesis

When the refreshed accepted A/B stack has no active core positions, a fixed-notional QQQ overlay gated by prior-close QQQ 200-day trend and 20-day momentum may reduce idle-period opportunity cost without displacing stock alpha or scarce slots.

## Best variant

- Variant: `zero_position_qqq_100pct_notional`
- Aggregate EV delta: `0.3548`
- Aggregate PnL delta: `$6584.27`
- Windows improved/regressed: `3` / `0`
- Overlay days: `19` total, min `4` per window

## Three-window best-variant deltas

| Window | EV delta | PnL delta | Return delta | SharpeD delta | DD delta | Overlay days |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.2343 | $3339.13 | 0.0334 | 0.09 | -0.0005 | 8 |
| mid_weak | 0.0655 | $1072.46 | 0.0107 | 0.06 | -0.0010 | 4 |
| old_thin | 0.0550 | $2172.68 | 0.0217 | 0.09 | -0.0014 | 7 |

## Production impact

- Replay-only; no live/default orders changed.
- Any positive follow-up needs shared run/backtester cash/risk-budget semantics and parity tests.
- `cash_usd` is currently not populated in open positions, so this is fixed-notional research, not production cash sizing.

## Historical guardrail

This is not a retry of QQQ as a stock-style ATR sleeve. It changes the timing discriminator to zero active core positions only and keeps all A/B trades locked.
