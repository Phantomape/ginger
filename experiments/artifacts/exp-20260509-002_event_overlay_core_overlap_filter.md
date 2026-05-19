# exp-20260509-002 Event Overlay Core-Overlap Filter

Decision: `rejected_incremental_filter`

## Hypothesis

If the event overlay's alpha is truly independent candidate-pool alpha, then filtering out event rows that overlap same-day or same-window core A/B exposure should preserve or improve the frozen bundle's replacement value without source/notional/holding-period tuning.

## Baseline

| Window | Core EV | Full bundle EV | Full bundle PnL | Full event trades |
|---|---:|---:|---:|---:|
| late_strong | 4.0674 | 4.5771 | 97384.3 | 9 |
| mid_weak | 1.6195 | 2.083 | 67850.5 | 11 |
| old_thin | 0.3583 | 0.3938 | 28745.97 | 7 |

## Variant Comparison Versus Full Bundle

| Variant | EV sum | EV delta | PnL delta | Windows improved/regressed | Gate | Event trades | Event PnL |
|---|---:|---:|---:|---:|---|---:|---:|
| full_bundle | 7.0539 | 1.0087 | 16303.84 | 3/0 | core-baseline | 27 | 15856.23 |
| no_same_day_core_entry | 7.041 | -0.0129 | -198.79 | 0/1 | FAIL | 26 | 15657.44 |
| no_window_core_ticker | 7.0633 | 0.0094 | 433.37 | 2/1 | FAIL | 17 | 15825.54 |
| non_overlap_both | 7.0633 | 0.0094 | 433.37 | 2/1 | FAIL | 17 | 15825.54 |

## Decision Rationale

Rejected as an incremental filter. The best overlap-filtered variant (no_window_core_ticker) did not beat the full frozen event bundle with enough three-window stability and materiality. The full event bundle remains the better candidate-pool surface.

## Production Impact

Replay only. The default production and backtest order paths are unchanged. Any future positive version would require a shared event-candidate policy and run/backtester parity tests before capital impact.
