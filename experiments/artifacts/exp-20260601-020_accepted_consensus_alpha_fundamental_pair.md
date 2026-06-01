# exp-20260601-020: Accepted Consensus Alpha + Fundamental Pair

- decision: `rejected_accepted_consensus_alpha_fundamental_pair`
- aggregate EV: `6.3596` -> `7.1948` (+0.8352)
- aggregate PnL: `$192,538.61` -> `$206,468.19` (+13,929.58)
- target trades: `28`
- max single positive share: `0.47879153651549977`
- positive PnL HHI: `0.34233025762254343`
- alpha failed gates: `drawdown_drift_passed, concentration_guard_passed`
- retention failed gates: `drawdown_drift_passed, concentration_guard_passed, baseline_matches_docs_for_retention`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | target trades | source-pair candidates |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 4.1082 | 4.7677 | +0.6595 | $+7,181.38 | 7 | 14 |
| mid_weak | 2.1405 | 2.2505 | +0.1100 | $+1,974.71 | 14 | 17 |
| old_thin | 0.1109 | 0.1766 | +0.0657 | $+4,773.49 | 7 | 11 |

## Production / Backtest Consistency

Replay-only. No production order generation, shared ranking, sizing, exits, LLM, or live adapter changed. Any positive lead must be rebuilt as a shared live/backtest default-off adapter before promotion.

## Baseline Caveat

Current replay baseline differs from docs/backtesting.md accepted baseline. Positive replay results are observation-only until the clean baseline/parity decision is resolved.

## Conclusion

One or more Gate 4 alpha checks failed, so no strategy change is retained.
