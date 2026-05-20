# exp-20260520-020 Space short-extension trend risk

## Hypothesis
Within source-diverse dual-catalyst Space trend signals, lower 10d extension may represent cleaner post-catalyst absorption than already-heated moves; a small risk scalar gated by signal momentum_10d_pct could improve EV without changing the candidate pool or production/LLM boundaries.

## Single Changed Variable
`space_dual_catalyst_short_extension_trend_risk_scalar` gated by `momentum_10d_pct`.

## Gate 1 Baseline
- current accepted experiment: `exp-20260519-027`
- current benchmark-breadth scalar: `1.021875`
- current aggregate EV: `29.0599`
- current aggregate PnL: `741041.42`

## Gate 2 Field Check
- open position field check passed: `True`
- dual catalyst profile field check passed: `True`
- short-extension field check passed: `True`
- candidate signals: `6`
- missing momentum_10d_pct: `0`

## Gate 3 Survival Audit
- min survival before: `0.6267`
- min survival after: `0.6267`
- no filter was added; this is a sizing-only scalar.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.762700 | 8.762700 | 0.000000 | 0.00 | 0.000000 | 17 | 17 |
| mid_weak | 19.058800 | 19.598400 | 0.539600 | 13893.69 | -0.000100 | 23 | 23 |
| old_thin | 1.238400 | 1.238400 | 0.000000 | 0.00 | 0.000000 | 23 | 23 |

## Best Variant
- momentum_10d_max: `0.3`
- scalar: `1.05`
- candidate signals: `6`
- eligible signals: `4`
- changed signals: `4`
- changed tickers: `['ASTS', 'LUNR', 'RKLB']`
- changed windows: `['mid_weak']`
- aggregate EV delta vs current: `0.5396`
- aggregate PnL delta vs current: `13893.69`
- max drawdown delta vs current: `0.0`

## Decision
- decision: `reject`
- Gate 4 passed: `False`
- improved windows: `{'mid_weak': 0.5396}`
- regressed windows: `{}`

## Production Impact
```text
production_impact:
  shared_policy_changed: false
  backtester_adapter_changed: false
  run_adapter_changed: false
  replay_only: true
  parity_test_added: false
  live_slots: 0
```
