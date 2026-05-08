# exp-20260507-908 Gap-Up Entry-State Risk Replay

Decision: `rejected`
Best variant: `gap_up_1_50x_cap_aware`

## Hypothesis

Accepted A/B trades with a signal-day open gap of at least 3% may have a different payoff distribution than normal entries; a bounded risk multiplier could improve expected value without changing entries.

## Baseline

| EV sum | PnL sum | Trades |
|---:|---:|---:|
| 5.5094 | 165815.54 | 63 |

## Aggregate Replay

| Variant | EV delta | EV delta % | PnL delta | PnL delta % | Windows EV +/- | Touched | Changed | DD worsening | Single ticker share | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| gap_up_0_50x | -0.6907 | -0.085154 | -24564.88 | -0.148146 | 0/3 | 22 | 19 | 0.0 | 0.4685 | FAIL |
| gap_up_0_75x | -0.2954 | -0.036419 | -12433.28 | -0.074983 | 0/3 | 22 | 19 | 0.0 | 0.4578 | FAIL |
| gap_up_1_25x_cap_aware | 0.1308 | 0.016126 | 4018.15 | 0.024233 | 2/0 | 22 | 13 | 0.0112 | 0.5495 | FAIL |
| gap_up_1_50x_cap_aware | 0.2218 | 0.027345 | 6413.32 | 0.038677 | 2/0 | 22 | 15 | 0.0095 | 0.693 | FAIL |

## Window Deltas

| Variant | Window | EV delta | PnL delta | Sharpe delta | DD delta |
|---|---|---:|---:|---:|---:|
| gap_up_0_50x | late_strong | -0.0568 | -2621.8 | 0.12 | -0.0066 |
| gap_up_0_50x | mid_weak | -0.2699 | -9964.19 | 0.41 | -0.0056 |
| gap_up_0_50x | old_thin | -0.364 | -11978.89 | -0.49 | -0.0188 |
| gap_up_0_75x | late_strong | -0.0109 | -1331.95 | 0.08 | -0.0037 |
| gap_up_0_75x | mid_weak | -0.099 | -5078.71 | 0.26 | -0.0071 |
| gap_up_0_75x | old_thin | -0.1855 | -6022.62 | -0.19 | -0.0089 |
| gap_up_1_25x_cap_aware | late_strong | 0.0 | 0.0 | 0.0 | 0.0 |
| gap_up_1_25x_cap_aware | mid_weak | 0.079 | 1737.08 | 0.0 | 0.0046 |
| gap_up_1_25x_cap_aware | old_thin | 0.0518 | 2281.07 | -0.02 | 0.0112 |
| gap_up_1_50x_cap_aware | late_strong | 0.0 | 0.0 | 0.0 | 0.0 |
| gap_up_1_50x_cap_aware | mid_weak | 0.0916 | 1909.34 | 0.0 | 0.0046 |
| gap_up_1_50x_cap_aware | old_thin | 0.1302 | 4503.98 | 0.06 | 0.0095 |

## Rejection Reason

Best variant `gap_up_1_50x_cap_aware` failed Gate 4: EV delta 0.2218 (0.027345), PnL delta 6413.32 (0.038677), windows improved/regressed 2/0, changed trades 15 of 22 touched, max DD worsening 0.0095, single ticker positive share 0.693.

## Production Impact

Replay-only diagnostic. No production orders, shared policy, default backtest strategy, LLM/news boundary, or universe changed.
