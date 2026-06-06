# exp-20260606-011 Low-Deployment ETF Loss-Streak Kill Switch

Decision: `rejected_low_deployment_etf_loss_streak_kill_switch`.

## Preflight Answers

1. Hypothesis: risk allocation / capital allocation: add a production-visible loss-streak cooldown to the accepted default-off ETF cash substitute so low-deployment replacement value survives weak ETF sleeve regimes.
2. History: exp-20260606-001 accepted the shared ETF adapter; exp-20260522-004 rejected ETF volatility cap; exp-20260605-028 found forward activation still blocked.
3. Single variable: `low_deployment_etf_prior_closed_loss_streak_kill_switch_v1`.
4. Acceptance: three canonical windows versus accepted ETF comparator; positive aggregate EV/PnL, no window regressions, no drawdown worsening, enough trades, survival/concentration pass.
5. Reproduce: `.venv\Scripts\python.exe -B quant\experiments\exp_20260606_011_low_deployment_etf_loss_streak_kill_switch.py`.

## Aggregate vs Accepted ETF Comparator

- EV: `10.9233 -> 10.0887` (-0.8346)
- PnL: `$279,157.90 -> $269,212.62` ($-9,945.28)
- Variant trades: `18` (accepted `19`)
- Max drawdown delta vs accepted: `0.0`

## Window Deltas

| Window | EV delta | PnL delta | Accepted trades | Variant trades |
| --- | ---: | ---: | ---: | ---: |
| `late_strong` | -0.8346 | $-9,945.28 | 7 | 6 |
| `mid_weak` | +0.0000 | $+0.00 | 5 | 5 |
| `old_thin` | +0.0000 | $+0.00 | 7 | 7 |

## Production Boundary

- Experiment-only, default-off paper replay; no production orders changed.
- Positive retention would require shared-helper promotion and parity tests.
- No JavaScript was used.

## Reflection

If rejected, the loss-streak rule probably cuts profitable recovery entries after ordinary ETF pullbacks. The accepted ETF edge is likely driven by persistent broad-market replacement exposure during low core deployment, so realized sleeve loss streak is too slow and too blunt as a state variable. Do not retry adjacent loss-streak/cooldown thresholds without new forward replacement rows or a materially different free data edge.
