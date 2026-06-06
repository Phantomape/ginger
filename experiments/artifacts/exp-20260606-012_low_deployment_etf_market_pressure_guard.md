# exp-20260606-012 Low-Deployment ETF Market-Pressure Guard

Decision: `rejected_low_deployment_etf_market_pressure_guard`.

## Preflight Answers

1. Hypothesis: risk allocation / capital allocation: add a fixed production-visible SPY/QQQ pressure guard to the accepted default-off ETF cash substitute so low-deployment replacement value does not add new equity ETF risk during acute broad market pressure.
2. History: exp-20260606-001 accepted the shared ETF adapter; exp-20260606-011 rejected prior-loss-streak cooldown; exp-20260522-004 rejected ETF volatility cap; exp-20260605-028 found forward activation still blocked.
3. Single variable: `low_deployment_etf_market_pressure_volatility_guard_v1`.
4. Acceptance: three canonical windows versus accepted ETF comparator; positive aggregate EV/PnL, no window regressions, no drawdown worsening, enough trades, survival/concentration pass.
5. Reproduce: `.venv\Scripts\python.exe -B quant\experiments\exp_20260606_012_low_deployment_etf_market_pressure_guard.py`.

## Aggregate vs Accepted ETF Comparator

- EV: `10.9233 -> 10.9233` (+0.0000)
- PnL: `$279,157.90 -> $279,157.90` ($+0.00)
- Variant trades: `19` (accepted `19`)
- Max drawdown delta vs accepted: `0.0`

## Window Deltas

| Window | EV delta | PnL delta | Accepted trades | Variant trades | Guarded entries |
| --- | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | +0.0000 | $+0.00 | 7 | 7 | 0 |
| `mid_weak` | +0.0000 | $+0.00 | 5 | 5 | 0 |
| `old_thin` | +0.0000 | $+0.00 | 7 | 7 | 0 |

## Production Boundary

- Experiment-only, default-off paper replay; no production orders changed.
- Positive retention would require shared-helper promotion and parity tests.
- No JavaScript was used.

## Reflection

If rejected with no_signal_coverage, the fixed pressure guard did not overlap any accepted ETF paper entry in the three canonical windows, so it cannot express alpha under the current replay surface. If a looser version is considered, it must come from new forward replacement rows or a materially different free data edge; do not retune SPY/QQQ pressure thresholds on the same frozen windows.
