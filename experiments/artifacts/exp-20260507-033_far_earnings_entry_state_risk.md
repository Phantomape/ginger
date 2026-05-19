# exp-20260507-033 Far-From-Earnings Entry-State Risk Replay

Decision: `rejected`
Best variant: `far_earnings_1_50x_cap_aware`

## Hypothesis

Accepted A/B trades whose signal-date entry state is at least 46 calendar days before next earnings have less near-event overhang and may deserve cap-aware risk add-on capital.

## Baseline

| EV sum | PnL sum | Trades |
|---:|---:|---:|
| 5.5094 | 165815.54 | 63 |

## Aggregate Replay

| Variant | EV delta | PnL delta | PnL delta % | Windows EV +/- | Touched | Changed | DD worsening | Single ticker share | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| far_earnings_1_25x_cap_aware | 0.1912 | 5148.79 | 0.031051 | 2/1 | 29 | 16 | 0.0122 | 0.3468 | FAIL |
| far_earnings_1_50x_cap_aware | 0.3173 | 8678.54 | 0.052339 | 2/1 | 29 | 18 | 0.0105 | 0.4244 | FAIL |

## Window Deltas

| Variant | Window | EV delta | PnL delta | Sharpe delta | DD delta |
|---|---|---:|---:|---:|---:|
| far_earnings_1_25x_cap_aware | late_strong | 0.1542 | 3096.47 | -0.03 | 0.0022 |
| far_earnings_1_25x_cap_aware | mid_weak | -0.0086 | -101.38 | -0.01 | 0.0 |
| far_earnings_1_25x_cap_aware | old_thin | 0.0456 | 2153.7 | -0.03 | 0.0122 |
| far_earnings_1_50x_cap_aware | late_strong | 0.2136 | 4523.46 | -0.06 | 0.0046 |
| far_earnings_1_50x_cap_aware | mid_weak | -0.0214 | -245.77 | -0.02 | 0.0 |
| far_earnings_1_50x_cap_aware | old_thin | 0.1251 | 4400.85 | 0.05 | 0.0105 |

## Rejection Reason

Best variant `far_earnings_1_50x_cap_aware` failed Gate 4: EV delta 0.3173 (0.039119), PnL delta 8678.54 (0.052339), windows improved/regressed 2/1, changed trades 18 of 29 touched, max DD worsening 0.0105, single ticker positive share 0.4244.

## Production Impact

No live or default-backtest strategy changed. Any future promotion would need a shared risk policy consumed by `run.py` and `backtester.py`, plus parity tests.
