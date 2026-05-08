# exp-20260508-001 Pre-Earnings 22-45 Risk Replay

Decision: `rejected`
Best variant: `pre_earnings_22_45_2_00x_cap_aware`

## Hypothesis

Accepted A/B trades 22-45 calendar days before the next earnings date may represent a stable pre-event continuation pocket that deserves modest cap-aware add-on risk, unlike the already-rejected far-earnings broad add-on and older narrow DTE overfit pockets.

## Baseline

| EV sum | PnL sum | Trades |
|---:|---:|---:|
| 5.5094 | 165815.54 | 63 |

## Aggregate Replay

| Variant | EV delta | EV delta % | PnL delta | PnL delta % | Windows EV +/- | Touched | Changed | DD worsening | Single ticker share | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| pre_earnings_22_45_1_25x_cap_aware | 0.2048 | 0.025249 | 3007.99 | 0.018141 | 2/1 | 8 | 8 | 0.0051 | 0.4855 | FAIL |
| pre_earnings_22_45_1_50x_cap_aware | 0.2512 | 0.03097 | 3560.11 | 0.02147 | 2/1 | 8 | 8 | 0.0055 | 0.4009 | FAIL |
| pre_earnings_22_45_2_00x_cap_aware | 0.3353 | 0.041338 | 4623.0 | 0.02788 | 2/1 | 8 | 8 | 0.0065 | 0.2991 | FAIL |

## Window Deltas

| Variant | Window | EV delta | PnL delta | Sharpe delta | DD delta |
|---|---|---:|---:|---:|---:|
| pre_earnings_22_45_1_25x_cap_aware | late_strong | 0.1079 | 1058.55 | 0.05 | 0.0 |
| pre_earnings_22_45_1_25x_cap_aware | mid_weak | 0.1028 | 2063.97 | 0.01 | 0.0051 |
| pre_earnings_22_45_1_25x_cap_aware | old_thin | -0.0059 | -114.53 | -0.01 | 0.0002 |
| pre_earnings_22_45_1_50x_cap_aware | late_strong | 0.1188 | 1165.94 | 0.06 | 0.0 |
| pre_earnings_22_45_1_50x_cap_aware | mid_weak | 0.1433 | 2606.12 | 0.04 | 0.0055 |
| pre_earnings_22_45_1_50x_cap_aware | old_thin | -0.0109 | -211.95 | -0.02 | 0.0003 |
| pre_earnings_22_45_2_00x_cap_aware | late_strong | 0.1188 | 1165.94 | 0.06 | 0.0 |
| pre_earnings_22_45_2_00x_cap_aware | mid_weak | 0.2379 | 3871.21 | 0.09 | 0.0065 |
| pre_earnings_22_45_2_00x_cap_aware | old_thin | -0.0214 | -414.15 | -0.05 | 0.0004 |

## Rejection Reason

Best variant `pre_earnings_22_45_2_00x_cap_aware` failed Gate 4: EV delta 0.3353 (0.041338), PnL delta 4623.0 (0.02788), windows improved/regressed 2/1, changed trades 8 of 8 touched, max DD worsening 0.0065, single ticker positive share 0.2991.

## Production Impact

Replay-only diagnostic. No production orders, shared policy, default backtest strategy, LLM/news boundary, or universe changed.
