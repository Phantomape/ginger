# exp-20260508-026 Add-on Volume Confirmation

## Hypothesis

Day-2 follow-through add-ons with checkpoint-day volume below their 20-session
average may be lower-quality capital-allocation opportunities. A minimum
checkpoint volume ratio could conserve scarce heat without weakening the hard
portfolio heat cap.

## Setup

- Lane: `alpha_search`
- Category: capital allocation / follow-through add-on quality
- Feature: `checkpoint_volume_ratio = Volume[checkpoint] / avg(Volume[checkpoint-19:checkpoint])`
- Variants: `>= 1.0`, `>= 1.2`
- Locked variables: signal generation, entry gates, candidate order, sizing,
  hard portfolio heat cap, add-on checkpoint day, add-on fraction, exits,
  universe, LLM/news replay settings.
- Production parity: the temporary implementation used the same helper in
  `backtester.py` and `production_parity.py`, then was rolled back because the
  experiment failed Gate 4.

## Three-Window Results

| Window | Variant | EV | PnL | Sharpe daily | Max DD | Win rate | Add-ons |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | baseline | 4.0674 | $90,788.88 | 4.48 | 5.39% | 78.95% | 7 |
| late_strong | vol >= 1.0 | 4.0239 | $89,823.19 | 4.48 | 5.39% | 78.95% | 6 |
| late_strong | vol >= 1.2 | 4.0239 | $89,823.19 | 4.48 | 5.39% | 78.95% | 6 |
| mid_weak | baseline | 1.6195 | $59,540.63 | 2.72 | 8.79% | 52.38% | 7 |
| mid_weak | vol >= 1.0 | 1.5736 | $58,281.10 | 2.70 | 8.79% | 52.38% | 5 |
| mid_weak | vol >= 1.2 | 1.5268 | $56,342.92 | 2.71 | 8.79% | 52.38% | 2 |
| old_thin | baseline | 0.3583 | $27,347.42 | 1.31 | 9.03% | 40.91% | 4 |
| old_thin | vol >= 1.0 | 0.3583 | $27,347.42 | 1.31 | 9.03% | 40.91% | 4 |
| old_thin | vol >= 1.2 | 0.3583 | $27,347.42 | 1.31 | 9.03% | 40.91% | 4 |

Aggregate:

- Baseline: EV `6.0452`, PnL `$177,676.93`
- Volume >= 1.0: EV `5.9558` (`-1.48%`), PnL `$175,451.71` (`-1.25%`)
- Volume >= 1.2: EV `5.9090` (`-2.25%`), PnL `$173,513.53` (`-2.34%`)

## Interpretation

The volume floor rejected profitable add-ons rather than bad add-ons. At `1.0`,
it cut XOM in late_strong and GS/LLY in mid_weak. At `1.2`, it additionally
cut PLTR/AAPL/APP in mid_weak. Drawdown did not improve, trade count did not
increase, and no window's EV improved.

## Decision

Rejected. Do not promote, and do not retry nearby simple checkpoint volume-ratio
floors on these frozen windows. The add-on alpha surface remains budget
reservation or lifecycle-staged heat allocation, not volume confirmation.
