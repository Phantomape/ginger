# exp-20260508-023 Add-on Heat Parity

## Direction

Best current alpha direction remains follow-through add-on capital allocation.
Prior experiments showed add-on marginal expectancy, but exp-20260508-019
found a blocker: production used effective-stop portfolio heat while backtester
execution used local `Position.stop_price` heat. That made further add-on
parameter searches unreliable.

## Change

- Exposed `cap_followthrough_addon_shares()` in `quant/production_parity.py`.
- Reused it from `quant/backtester.py` for add-on execution cap checks.
- Backtester add-on heat now comes from `portfolio_engine.compute_portfolio_heat`
  with effective stops, matching the production policy.
- No add-on thresholds, fractions, caps, ranking, universe, LLM, or news logic
  changed.

## Fixed-Window Result

| Window | EV Before | EV After | PnL Before | PnL After | Sharpe Daily Before | Sharpe Daily After | Win Rate Before | Win Rate After | Trades Before | Trades After |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | 3.7435 | 4.0674 | $83,562.53 | $90,788.88 | 4.48 | 4.48 | 78.95% | 78.95% | 19 | 19 |
| mid_weak | 1.5478 | 1.6195 | $57,542.74 | $59,540.63 | 2.69 | 2.72 | 52.38% | 52.38% | 21 | 21 |
| old_thin | 0.3359 | 0.2892 | $26,242.68 | $24,512.21 | 1.28 | 1.18 | 40.91% | 37.50% | 22 | 24 |

Aggregate EV improved by 0.3489 (+6.20%). Aggregate PnL improved by
$7,493.77 (+4.48%). This does not pass alpha-promotion Gate 4 because the
required thresholds are +10% EV or +5% PnL, and old_thin regressed.

## Decision

Accepted as a production/backtest parity repair. Rejected as an alpha
promotion. The old_thin regression means this should not be interpreted as
permission to loosen add-on capacity further.

## Next Alpha

The next valid add-on alpha search is a state-specific quality discriminator
or reserve mechanism that keeps the hard heat cap intact and specifically
prevents old_thin-style downstream capital exposure. Do not retry raw add-on
capacity, same-day priority ordering, or heat-cap relaxation.
