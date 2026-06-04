# exp-20260604-016 Lagged Consensus Density Monotonicity

- Decision: `rejected_lagged_density_no_positive_monotonic_ladder`
- Source replay: `data/experiments/exp-20260604-008/lagged_independent_source_consensus.json`
- Target trades: `64`
- Production impact: observed-only; no shared policy, adapter, ranking, sizing, exit, order, LLM, or news change.

## Gate Answers

1. Hypothesis: ranking/capital allocation attribution: stronger lagged independent source-confirmation density should identify cleaner accepted lagged consensus trades.
2. History: exp-20260604-008 found the positive lagged source-timing lead; exp-20260604-009 promoted the shared default-off adapter; exp-20260604-010 through 015 rejected nearby rank/support/source retunes versus the accepted lagged comparator.
3. Single causal variable: `prior_independent_source_confirmation_density_bucket_v1`.
4. Standard: Observed-only pass requires aggregate return monotonicity by density bucket, aggregate bucket sample >= 8, and stable monotonicity across at least two evaluable standard windows.
5. Reproducibility: `.venv\Scripts\python.exe -B quant\experiments\exp_20260604_016_lagged_consensus_density_monotonicity.py`

## Aggregate Buckets

| Bucket | Count | Avg PnL % | Avg PnL $ | Total PnL $ | Win rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| `same_day_only` | 17 | 0.041175 | 411.7488 | 6999.73 | 0.764706 |
| `prior_1_family` | 36 | 0.076516 | 765.1647 | 27545.93 | 0.722222 |
| `prior_2plus_families` | 11 | 0.009166 | 91.6555 | 1008.21 | 0.454545 |

## Monotonic Validation

- Aggregate monotonic increasing: `False`
- Aggregate sample gate passed: `True`
- Evaluable windows: `2`
- Increasing evaluable windows: `0`

## Window Checks

| Window | Evaluable | Same-day avg % | Prior 1 avg % | Prior 2+ avg % | Increasing |
| --- | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | False | 0.009334 | 0.068013 | 0.07425 | False |
| `mid_weak` | True | 0.03917 | 0.050878 | -0.007661 | False |
| `old_thin` | True | 0.052563 | 0.108696 | -0.082482 | False |

## Conclusion

Average net return does not increase from same-day-only to higher prior-confirmation density.

No JavaScript was used.
