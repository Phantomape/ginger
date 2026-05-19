# exp-20260517-012 SEC neutral moderate T1 excess

- decision: `rejected_concentration_limited_neutral_moderate_t1_excess`
- best_variant: `neutral_language_t1_excess_le_0.020`
- expected_value_score_delta: `0.717658`
- total_pnl_delta: `16836.09`
- gate_passed: `False`
- metric_gate_passed: `True`
- sample_guard_passed: `True`
- concentration_guard_passed: `False`

## Window Deltas

| window | EV delta | PnL delta | Max DD delta | adjusted trades |
|---|---:|---:|---:|---:|
| late_strong | 0.100858 | 1397.31 | 0.0 | 1 |
| mid_weak | 0.285638 | 4293.29 | -0.001748 | 2 |
| old_thin | 0.331162 | 11145.49 | 0.003957 | 4 |

## Selection

- adjusted trades: `7`
- windows present: `3`
- max single positive PnL share: `0.6323`

## Interpretation

The 2.0% T+1 excess cap produced a strong three-window paper alpha signal, but the positive PnL is too concentrated in one COIN earnings 8-K row. Treat this as a forward research queue, not a promoted paper allocation rule.
