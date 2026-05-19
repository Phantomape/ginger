# exp-20260516-020 Technology Trend DTE Residual Risk

Decision: `accepted_shared_policy_promoted`.

Single variable: the existing `TREND_TECH_DTE_RISK_MULTIPLIER` for `trend_long` Technology signals with 44-64 `days_to_earnings`. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, slots, and all other sizing states were unchanged.

## Sweep

| Multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |
|---:|:---:|:---:|---:|---:|---|---|---:|---|---:|
| 0.000 | no | FAIL | -0.0720 | $-2,971.45 | late_strong, mid_weak | old_thin | 13 | late_strong, mid_weak, old_thin | +0.0000 |
| 0.125 | no | PASS | +0.0039 | $+151.61 | mid_weak, old_thin | - | 13 | late_strong, mid_weak, old_thin | +0.0000 |
| 0.250 | yes | FAIL | +0.0000 | $+0.00 | - | - | 13 | late_strong, mid_weak, old_thin | +0.0000 |

Selected non-control multiplier: `0.125`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Affected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1344 | 5.1344 | +0.0000 | $116,686.40 | $116,686.40 | $+0.00 | +0.0000 | 0.8039 | 3 |
| mid_weak | 2.1016 | 2.1054 | +0.0038 | $76,421.93 | $76,563.68 | $+141.75 | +0.0000 | 0.7925 | 4 |
| old_thin | 0.5294 | 0.5295 | +0.0001 | $37,282.59 | $37,292.45 | $+9.86 | +0.0000 | 0.8667 | 6 |

Production impact: promoted through the shared `TREND_TECH_DTE_RISK_MULTIPLIER` constant in `quant/constants.py`, which is consumed by `portfolio_engine.size_signals` in both `quant/backtester.py` and `quant/run.py`. Focused sizing coverage was updated in `quant/test_quant.py`, and the promoted code was rerun on all three canonical fixed snapshots.
