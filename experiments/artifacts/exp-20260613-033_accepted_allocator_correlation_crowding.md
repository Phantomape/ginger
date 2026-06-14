# exp-20260613-033 Accepted Allocator Correlation Crowding

Status: `rejected`

## Hypothesis

Same-day accepted-helper candidates may improve when the chosen row has lower
PIT OHLCV correlation crowding versus competing candidates, avoiding crowded
beta without changing source families, sizing, exits, or trade-enabled defaults.

## Gate 4 Three-Window Readout

| Window | Core EV | Accepted EV | Crowding EV | Direct dEV | Changed |
|---|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 6.1042 | 6.1042 | +0.0000 | 0 |
| mid_weak | 1.9517 | 2.5602 | 2.5602 | +0.0000 | 0 |
| old_thin | 0.5911 | 1.2316 | 1.2316 | +0.0000 | 0 |

- Direct PnL delta vs accepted allocator: `$+0.00`
- Aggregate EV delta vs core: `+2.1904`
- Aggregate PnL delta vs core: `$+41,060.03`
- Gate 4 failed reasons: `direct_ev_vs_accepted_allocator_not_positive`,
  `direct_pnl_vs_accepted_allocator_not_positive`,
  `changed_selection_sample_too_small`

## Conclusion

The variant selected exactly the same rows as the same-run accepted allocator
control. This is not accepted alpha because there was no attributable selection
change to evaluate.

## Reflection

Low same-day peer correlation did not create actionable replacements under the
fixed margin and accepted execution envelope. The source-choice oracle gap is
unlikely to be solved by a simple low-correlation arbitration rule on frozen
historical windows. A retry needs a materially richer PIT relation field or
closed forward replacement rows, not threshold or weight sweeps of this rule.

No production/shared helper changed. No JavaScript was used.
