# exp-20260507-021 Event/Core Pressure Guard

Decision: `rejected`

Replay-only alpha search. Tests whether the default-off event bundle should stand down when the core book is already active.

## Best Guard Vs Full Bundle

| Window | Full EV | Guard EV | Delta EV | Full PnL | Guard PnL | Delta PnL | Guard trades | Skipped PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2452 | 4.2676 | +0.0224 | $90,131.87 | $90,223.93 | $+92.06 | 8 | $-92.06 |
| mid_weak | 2.0019 | 2.0019 | +0.0000 | $65,850.51 | $65,850.51 | $+0.00 | 11 | $+0.00 |
| old_thin | 0.3676 | 0.3926 | +0.0250 | $27,641.23 | $28,659.11 | $+1,017.88 | 5 | $-1,017.88 |

## Variant Summary

| Variant | EV Sum Vs Full | PnL Delta Vs Full | Windows EV Improved | Windows EV Regressed | Passed |
|---|---:|---:|---:|---:|---|
| no_same_ticker_core_overlap | +0.0474 | $+1,109.94 | 2 | 0 | False |
| core_active_le_1 | -0.9089 | $-14,303.35 | 0 | 3 | False |
| core_idle_only | -0.8023 | $-13,003.08 | 0 | 3 | False |

## Decision Rationale

Rejected: the best guard (no_same_ticker_core_overlap) did not beat the full frozen event bundle with enough stable EV improvement. Core pressure gating removed too many profitable event entries or failed materiality.

No production universe, ranking, sizing, exits, LLM, news, or order path changed.
