# exp-20260508-016 precious-metals state target replay

Run at: `2026-05-08T10:14:06.484566+00:00`

## Hypothesis

SLV trend winners should be allowed to run to the gold-like 8 ATR target only when silver is leading gold on 20-day momentum; otherwise the current 7 ATR target avoids repeating broad commodity target overextension.

## Decision

`rejected` - All variants failed majority-window EV/Gate 4 robustness.

## Baseline

| window | EV | sharpe_daily | max_dd | pnl | win_rate | trades | survival |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.7435 | 4.48 | 0.0539 | 83562.53 | 0.7895 | 19 | 0.8039 |
| mid_weak | 1.5478 | 2.69 | 0.0879 | 57542.74 | 0.5238 | 21 | 0.7925 |
| old_thin | 0.3359 | 1.28 | 0.0905 | 26242.68 | 0.4091 | 22 | 0.9167 |

## Variants

### slv_ret20_gt_gld_ret20

SLV trend target = 8 ATR when SLV 20d momentum is greater than GLD 20d momentum.

| window | retargets | EV delta | sharpe delta | max_dd delta | pnl delta | win delta | trades delta | Gate4 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| late_strong | 3 | 0.0576 | 0.02 | 0.0 | 910.47 | 0.0 | 0.0 | FAIL |
| mid_weak | 5 | -0.3248 | -0.24 | 0.0 | -7625.95 | -0.0455 | 2.0 | FAIL |
| old_thin | 2 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | FAIL |

Decision: `rejected` - did not produce robust majority-window EV/Gate 4 improvement

### slv_ret20_gt_gld_ret20_by_2pp

SLV trend target = 8 ATR when SLV 20d momentum beats GLD by at least 2pp.

| window | retargets | EV delta | sharpe delta | max_dd delta | pnl delta | win delta | trades delta | Gate4 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| late_strong | 3 | 0.0576 | 0.02 | 0.0 | 910.47 | 0.0 | 0.0 | FAIL |
| mid_weak | 5 | -0.3248 | -0.24 | 0.0 | -7625.95 | -0.0455 | 2.0 | FAIL |
| old_thin | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | FAIL |

Decision: `rejected` - did not produce robust majority-window EV/Gate 4 improvement

### slv_and_gld_positive_slv_leads

SLV trend target = 8 ATR when both SLV and GLD 20d momentum are positive and SLV leads.

| window | retargets | EV delta | sharpe delta | max_dd delta | pnl delta | win delta | trades delta | Gate4 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| late_strong | 3 | 0.0576 | 0.02 | 0.0 | 910.47 | 0.0 | 0.0 | FAIL |
| mid_weak | 4 | -0.3248 | -0.24 | 0.0 | -7625.95 | -0.0455 | 2.0 | FAIL |
| old_thin | 2 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | FAIL |

Decision: `rejected` - did not produce robust majority-window EV/Gate 4 improvement

## Production parity

Replay only. No production policy, backtester adapter, run adapter, candidate universe, ranking, sizing, stop, LLM, or news behavior changed.

If a variant is later promoted, it must be implemented in shared `risk_engine.enrich_signals()` and covered by parity tests before enabling.

