# exp-20260602-003: Explicit Post-Earnings Continuation

- Decision: `accepted_explicit_post_earnings_continuation_policy`
- Changed variable: `post_earnings_continuation_confirmed_v1`
- Baseline: `exp-20260601-025` PIT earnings snapshot DTE canonical baseline
- Prior lead: `exp-20260602-002` observed-only post-earnings reset continuation
- JavaScript: not used

## Gate 4 Summary

| Metric | Before | After | Delta |
|---|---:|---:|---:|
| Aggregate EV | 6.3596 | 7.8941 | +1.5345 (+24.13%) |
| Aggregate PnL | $192,538.61 | $234,850.99 | +$42,312.38 (+21.98%) |
| Trade count | 58 | 61 | +3 |
| Max drawdown ceiling | 14.09% | 11.19% | -2.90% |
| Min survival rate | 79.17% | 79.25% | +0.08% |

## Three Windows

| Window | EV before | EV after | EV delta | PnL before | PnL after | Trades | Survival after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.1082 | 5.1628 | +1.0546 | $100,203.06 | $117,072.92 | 18 | 80.39% |
| mid_weak | 2.1405 | 2.1402 | -0.0003 | $78,119.38 | $78,110.11 | 21 | 79.25% |
| old_thin | 0.1109 | 0.5911 | +0.4802 | $14,216.17 | $39,667.96 | 22 | 86.67% |

## Production Parity

The accepted implementation is shared across production and backtest: `data_layer.py` and `backtester.py` both expose `last_earnings_date`, `days_since_last_earnings`, `post_earnings_continuation_confirmed`, and `post_earnings_event_date`. The continuation flag is true only when same-day actual EPS is known and a later future earnings date exists.

## Acceptance

Accepted. Aggregate EV improved by more than 10%, max drawdown improved, trade count increased, and survival stayed well above the Gate 3 floor. The only regressed canonical window was `mid_weak`, with a negligible `-0.0003` EV / `-$9.27` PnL drift.
