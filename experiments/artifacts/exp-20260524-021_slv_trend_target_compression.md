# exp-20260524-021 slv_trend_target_compression

## Hypothesis
Compressing targets for existing SLV Commodities trend_long signals may capture mean-reverting silver exits sooner than the current 7 ATR commodity target, while leaving GLD/IAU and the rest of the commodity sleeve unchanged.

## Gate Answers
- Type: alpha_search, exit/lifecycle.
- Prior evidence: accepted commodity/gold target split helped, while prior wider commodity tests noted SLV drag.
- Causal variable: SLV trend_long target ATR multiplier only.
- Evaluation: canonical three non-overlapping windows from docs/backtesting.md.
- Reproducibility: this artifact plus JSON payload record variants, windows, snapshots, and metrics.

## Variant Summary
| variant | agg EV | delta EV | agg PnL | delta PnL | EV windows +/- | gate |
|---|---:|---:|---:|---:|---:|---|
| baseline_current_policy | 7.878100 | 0.000000 | 234550.33 | 0.00 | 0/0 | control |
| slv_target_6_5_atr | 7.710800 | -0.167300 | 231814.69 | -2735.64 | 0/2 | reject |
| slv_target_6_0_atr | 7.662300 | -0.215800 | 230584.80 | -3965.53 | 0/2 | reject |
| slv_target_5_5_atr | 7.301900 | -0.576200 | 224062.50 | -10487.83 | 0/2 | reject |
| slv_target_5_0_atr | 6.816400 | -1.061700 | 214314.20 | -20236.13 | 0/2 | reject |

## Selected Variant: slv_target_6_5_atr
- Decision: reject
- Blockers: aggregate_expected_value_not_positive, aggregate_pnl_not_positive, one_or_more_windows_regressed_ev, fewer_than_two_windows_improved_ev
- Aggregate EV delta: -0.167300
- Aggregate PnL delta: -2735.64

## Window Detail
| window | EV delta | PnL delta | survival delta | trade delta | SLV PnL delta |
|---|---:|---:|---:|---:|---:|
| late_strong | -0.129600 | -1634.58 | 0.000000 | 0 | -1090.78 |
| mid_weak | -0.037700 | -1101.06 | 0.000000 | 0 | -1014.23 |
| old_thin | 0.000000 | 0.00 | 0.000000 | 0 | 0.00 |

## Production Parity
No production policy was changed. If a variant had passed, the shared risk_engine target policy would need the same ticker/strategy/sector condition before live use.
