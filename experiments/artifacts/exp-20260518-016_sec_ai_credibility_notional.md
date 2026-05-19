# SEC AI Disclosure Credibility Notional

- Experiment ID: `exp-20260518-016`
- Decision: `rejected_sec_ai_credibility_notional`
- Hypothesis: Within the accepted SEC financial-report default-off paper stack, AI-themed filings should only deserve extra notional when the filing contains specific product/customer/capex evidence rather than generic AI promotion. A bounded paper scalar on that credible bucket may improve replacement value without changing queue eligibility, hold days, capacity, or live orders.
- Changed variable: `sec_ai_disclosure_credibility_notional_scalar`

## Gate 1-4

- Gate 1 baseline: accepted `exp-20260518-014` default-off SEC paper stack over the canonical three fixed windows.
- Gate 2 fields passed: `True`
- Gate 3 survival unchanged: min survival rate delta `0.0`.
- Gate 4 passed: `False`

## Aggregate

| Metric | Before | After | Delta |
| --- | ---: | ---: | ---: |
| EV sum | 11.675045 | 11.719645 | 0.0446 |
| Total PnL | 318771.69 | 321945.21 | 3173.52 |
| Max DD max | 0.115591 | 0.120276 | 0.004685 |

## Window Deltas

| Window | EV delta | PnL delta | Max DD delta | Credible AI trades | Credible AI PnL delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| late_strong | -0.159178 | -170.66 | -0.000301 | 5 | -89.51 |
| mid_weak | 0.255011 | 4561.3 | -0.001694 | 5 | 4561.31 |
| old_thin | -0.051233 | -1217.12 | 0.004685 | 6 | -1217.12 |

## Interpretation

The AI credibility bucket is replayable and not sample-empty, but its historical incremental value is not robust across the canonical windows. The slice helped `mid_weak`, yet the same extra notional harmed `late_strong` and `old_thin`, so this field is not ready for promotion into the shared SEC paper sleeve.

## Next Evidence

Do not promote this heuristic bucket. Revisit AI disclosure fields only after a narrower evidence taxonomy widens honestly or after closed forward replacement-value evidence shows a stable cross-window edge.
