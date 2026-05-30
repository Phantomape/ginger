# exp-20260530-016 Catalyst-Qualified Pre-Breakout Entry

- Decision: `rejected_prebreakout_catalyst_qualified_entry`
- Aggregate EV delta: `0.0211`
- Aggregate PnL delta: `216.23`
- Gate 4 passed: `False`

| Window | EV before | EV after | EV delta | PnL delta | Max DD delta | Trades delta | Signals survived delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | 5.1628 | 5.1628 | 0.0000 | $0.00 | 0.0000 | 0.0 | 2.0 |
| mid_weak | 2.1402 | 2.1776 | 0.0374 | $785.05 | 0.0000 | 2.0 | 3.0 |
| old_thin | 0.5911 | 0.5748 | -0.0163 | $-568.82 | 0.0016 | 2.0 | 3.0 |

This runner is replay-only. It temporarily injects the entry source inside signal generation and does not alter production code. A positive replay is not production-retained unless the same catalyst requirement is moved to a shared path in a separate change.
