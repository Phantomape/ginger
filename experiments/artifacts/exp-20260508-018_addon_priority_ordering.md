# exp-20260508-018 add-on priority ordering replay

Run at: `2026-05-08T12:13:19.0729852Z`

## Hypothesis

If multiple scheduled follow-through add-ons compete for scarce portfolio heat
on the same fill date, executing the strongest checkpoint candidates first by
`rs_vs_spy`, `unrealized_pct`, and SPY-relative leader status may redirect the
fixed risk budget toward better confirmed winners without relaxing the hard
portfolio heat cap.

## Decision

`rejected_no_effect`.

The tested ordering produced no metric changes in any canonical window. The
add-on heat bottleneck is not caused by lower-priority same-day add-ons
consuming scarce heat room; most missed add-ons had zero available heat before
ordering mattered.

## Three-window result

| window | EV before | EV after | EV delta | PnL before | PnL after | PnL delta | Sharpe delta | Max DD delta | Trades delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.7435 | 3.7435 | 0.0000 | 83562.53 | 83562.53 | 0.00 | 0.00 | 0.0000 | 0 |
| mid_weak | 1.5478 | 1.5478 | 0.0000 | 57542.74 | 57542.74 | 0.00 | 0.00 | 0.0000 | 0 |
| old_thin | 0.3359 | 0.3359 | 0.0000 | 26242.68 | 26242.68 | 0.00 | 0.00 | 0.0000 | 0 |

## Production parity

No production or backtest strategy code was retained. A production version
would need a shared helper and action ordering test, but this replay does not
justify that work.

## Do not repeat

Do not retry nearby same-day add-on ordering keys on the same fixed windows
without evidence that same-day add-on competition, rather than absolute lack of
heat room, is the binding constraint.
