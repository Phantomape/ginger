# exp-20260605-001: FGRS Market-Regime Gate

- decision: `rejected_fgrs_market_regime_gate`
- single variable: `market_regime_admission_gate_on_fundamental_growth_rs_paper`
- aggregate EV: `12.3686` -> `8.5023` (-3.8663)
- aggregate PnL: `$304,414.61` -> `$246,670.67` (-57,743.94)
- target trades (after gate): `119`
- max single positive share: `0.395568`
- positive PnL HHI: `0.285019`
- failed gates: `aggregate_expected_value_positive, aggregate_pnl_positive, all_windows_expected_value_improved, all_windows_pnl_improved, drawdown_drift_passed, baseline_matches_docs_for_retention`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 6.4685 | 5.2239 | -1.2446 | $-14,024.91 | 70 | 39 |
| mid_weak | 3.7838 | 2.3393 | -1.4445 | $-20,439.48 | 90 | 44 |
| old_thin | 2.1163 | 0.9391 | -1.1772 | $-23,279.55 | 105 | 36 |

## Regime Gate Audit

| window | source | regime pass | regime fail |
|---|---:|---:|---:|
| late_strong | 70 | 39 | 31 |
| mid_weak | 90 | 44 | 46 |
| old_thin | 105 | 36 | 69 |

## Conclusion

Gate 4 alpha checks failed; no strategy behavior is retained.

- Regime gate: SPY close >= 50d MA AND IWM 20d return >= SPY 20d return (min 0.0)
- Source: exp-20260601-026 FGRS accepted trade rows
- No live/default orders, core ranking, sizing, exits, LLM, or news changed.
