# exp-20260717-005: TSA checkpoint throughput PIT preflight

## Decision

Rejected before any price or return data was read.

## Machine-checked evidence

- Hash-bound FOIA PDF weekly total: 17,351,496.
- Current TSA annual-table total for the same dates: 17,884,180.
- Difference: 532,684 (3.070%).
- PDF cover date: 2025-10-27; metadata modification date: 2025-11-17.
- Reading-room indexed / raw-structure-ready counts: old_thin=25/19, mid_weak=24/22, late_strong=22/12.
- Exact-364-day comparator sentinel parse: RuntimeError:expected one cover date, got [].
- Four late-window filename exceptions are official but were batch-modified on 2025-11-17, so stale reports are missed rather than retroactively entered.
- OHLCV and returns read: no.

## Reopen condition

Reopen only when an authorized immutable/versioned TSA weekly release archive supplies publication timestamps and original bytes for enough current, preceding-week, and exact-364-day reports to yield >=10 locked signal events in every canonical window; the mutable annual table and current post-modified PDFs do not qualify.
