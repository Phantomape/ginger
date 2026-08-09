# exp-20260716-003: sign-preserving expected-value score

Decision: `accepted_measurement_repair`.

The canonical north-star score now uses:

```text
expected_value_score = strategy_total_return_pct * abs(sharpe_daily)
```

Total return owns the direction and Sharpe contributes magnitude. This removes
the negative-times-negative pathology without changing any positive-return,
positive-Sharpe score.

## Evidence

- All `314` tests in `quant/test_quant.py` passed. The focused subset covers
  all return/Sharpe sign quadrants and the backtester integration path.
- The active cash-feasible three-window baseline remains exactly `6.2057`
  (`4.1067 + 1.9908 + 0.1082`); PnL, trades, drawdown, signals and orders are
  untouched.
- The concrete `exp-20260716-002` losing fixture changes from legacy EV
  `+0.1674` to sign-preserving EV `-0.1640`, consistent with aggregate PnL
  `-$6,534.63`.
- Closed experiment runners that embedded the old formula remain unchanged for
  reproducibility. New canonical backtester results read the repaired helper in
  `quant/convergence.py`.

Detailed machine evidence:
`data/experiments/exp-20260716-003/expected_value_score_sign_repair.json`.

Production impact: measurement only. No signal, entry, exit, ranking, sizing,
cash, order, LLM or live behavior changed.
