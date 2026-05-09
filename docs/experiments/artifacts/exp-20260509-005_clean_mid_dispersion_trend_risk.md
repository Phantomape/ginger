# exp-20260509-005 Clean Mid-Dispersion Trend Risk

Decision: `rejected`

## Hypothesis

The accepted mid-sector-dispersion trend boost may be under-sized only for clean trend signals carrying no accepted risk haircut. This tests a drawdown discriminator before any further mid-dispersion risk increase.

## Gate 4

- passed: `False`
- best_variant: `clean_mid_dispersion_total_2_25x`
- EV delta sum: `+0.2938` (+4.86%)
- PnL delta sum: `$+8,382.32` (+4.72%)
- EV windows improved/regressed: `3` / `0`
- touched trades: `15`

## Three-Window Deltas

| Window | EV delta | PnL delta | SharpeD delta | DD delta | WR delta | Trades delta | Touched |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | +0.1723 | +2395.94 | +0.07 | +0.0000 | +0.0000 | +0 | 4 |
| `mid_weak` | +0.0415 | +863.25 | +0.03 | +0.0000 | +0.0000 | +0 | 3 |
| `old_thin` | +0.0800 | +5123.13 | +0.04 | +0.0087 | +0.0000 | +0 | 8 |

## Decision Rationale

The clean mid-dispersion top-up improved EV in all windows but did not clear materiality: the best effective variant was capped at 4.86% EV lift and 4.72% PnL lift, below the 10%/5% Gate 4 thresholds.

The direction was positive, but position caps absorbed higher variants and materiality stayed below Gate 4. No production rule was promoted.

## Production Impact

Replay only. Production and default backtest policy are unchanged.

