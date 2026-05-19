# exp-20260507-907 Platform RS20 Leader Risk Replay

Decision: `rejected`
Best variant: `platform_rs20_2_00x_cap_aware`

## Hypothesis

Already-entered core-platform A/B trades with signal-date `rs20_leader` entry-state tags may deserve cap-aware add-on risk, while platform names without the leadership tag should keep baseline size.

## Aggregate Replay

| Variant | EV delta | EV delta % | PnL delta | PnL delta % | Windows EV +/- | Touched | Changed | DD worsening | Single ticker share | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| platform_rs20_1_25x_cap_aware | 0.1339 | 0.016508 | 3234.68 | 0.019508 | 2/0 | 9 | 6 | 0.0 | 0.7191 | FAIL |
| platform_rs20_1_50x_cap_aware | 0.2289 | 0.02822 | 5569.97 | 0.033591 | 2/0 | 9 | 7 | 0.0 | 0.8409 | FAIL |
| platform_rs20_2_00x_cap_aware | 0.3758 | 0.046331 | 9033.61 | 0.05448 | 2/0 | 9 | 7 | 0.0 | 0.9062 | FAIL |

## Window Deltas

| Variant | Window | EV delta | PnL delta | Sharpe delta | DD delta |
|---|---|---:|---:|---:|---:|
| platform_rs20_1_25x_cap_aware | late_strong | 0.0 | 0.0 | 0.0 | 0.0 |
| platform_rs20_1_25x_cap_aware | mid_weak | 0.0255 | 316.66 | 0.02 | 0.0 |
| platform_rs20_1_25x_cap_aware | old_thin | 0.1084 | 2918.02 | 0.12 | -0.002 |
| platform_rs20_1_50x_cap_aware | late_strong | 0.0 | 0.0 | 0.0 | 0.0 |
| platform_rs20_1_50x_cap_aware | mid_weak | 0.0488 | 612.76 | 0.03 | 0.0 |
| platform_rs20_1_50x_cap_aware | old_thin | 0.1801 | 4957.21 | 0.18 | -0.0033 |
| platform_rs20_2_00x_cap_aware | late_strong | 0.0 | 0.0 | 0.0 | 0.0 |
| platform_rs20_2_00x_cap_aware | mid_weak | 0.1101 | 1383.84 | 0.08 | 0.0 |
| platform_rs20_2_00x_cap_aware | old_thin | 0.2657 | 7649.77 | 0.23 | -0.005 |

## Rejection Reason

Best variant `platform_rs20_2_00x_cap_aware` failed Gate 4: EV delta 0.3758 (0.046331), PnL delta 9033.61 (0.05448), windows improved/regressed 2/0, changed trades 7 of 9 touched, max DD worsening 0.0, single ticker positive share 0.9062.

## Production Impact

Replay-only diagnostic. No production orders, shared policy, default backtest strategy, LLM/news boundary, or universe changed.
