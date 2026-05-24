# exp-20260524-007 core_breadth_alignment_component_topup

Decision: `rejected_failed_gate4`.

## Hypothesis
Entry-day breadth_alignment from the production-computable cross-sectional ranking surface may identify already-qualified core stock signals that are supported without being over-crowded. A small cap-aware top-up tests that allocation edge without changing entries, exits, ranking, universe, news, or LLM logic.

## Gate 1-4
- Baseline EV: `7.8941`
- After EV: `7.8992`
- EV delta: `0.0051`
- PnL delta: `$148.02`
- Adjusted signals: `6`
- Changed trades: `5`
- EV-regressed windows: `[]`
- Max single-ticker positive share: `0.991589`
- Gate 4 passed: `False`

## Window Deltas
| window | EV | PnL | DD | survival |
|---|---:|---:|---:|---:|
| late_strong | 0.0044 | 95.95 | 0.0 | 0.0 |
| mid_weak | 0.0 | -0.71 | 0.0 | 0.0 |
| old_thin | 0.0007 | 52.78 | 0.0 | 0.0 |

## Closeout
Best variant failed concentration guard: the positive incremental PnL was dominated by one ticker, so the component state is not production-promotable on this sample.
