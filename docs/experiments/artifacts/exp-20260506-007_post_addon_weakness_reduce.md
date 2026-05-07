# exp-20260506-007: Post-Addon Weakness Reduce

- Status: `rejected`
- Lane: `alpha_search`
- Best tested variant: `POST_ADDON_WEAKNESS_DAYS=3`, `MIN_RS_VS_SPY=0.0`, require negative post-add-on return
- Aggregate EV delta: `-0.0016` (`-0.03%`)
- Aggregate PnL delta: `$-1,191.20`
- Executed partial-reduce events: `2`

## Three-Window Result

| Window | EV before | EV after | EV delta | PnL delta | Trades delta | Win-rate delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | 3.4191 | 3.4553 | +0.0362 | +649.15 | +1 | +0.0105 |
| `mid_weak` | 1.4415 | 1.4037 | -0.0378 | -1840.35 | +1 | -0.0238 |
| `old_thin` | 0.3179 | 0.3179 | 0.0000 | 0.00 | 0 | 0.0000 |

## Mechanism Read

The post-add-on deterioration idea is too sparse in the canonical windows. It
trimmed one AMZN add-on profitably in `late_strong`, but the AAPL trim in
`mid_weak` reduced overall portfolio quality and the old window had no touched
events. This does not justify a shared production lifecycle rule.

## Non-Repeat Guardrail

Do not retry nearby day-count, RS-vs-SPY, or negative-return threshold variants
on the same snapshots. A valid retry needs a larger touched cohort and an
orthogonal post-add-on quality discriminator with candidate-level replacement
evidence.

## Production Parity

No production order path changed. The tested behavior remained replay-only and
was rejected, so it should not be moved into shared run/backtester policy.
