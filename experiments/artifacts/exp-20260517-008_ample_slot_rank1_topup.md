# exp-20260517-008 Ample-Slot Rank-1 Top-Up

Decision: `rejected_ample_slot_rank1_topup`.

Single variable: cap-aware post-selection top-up on the already-selected rank-1 signal when the shared entry planner has at least four available slots. Entries, filters, candidate pool, ranking, exits, targets, LLM/news, event sleeves, and portfolio heat were unchanged.

## Sweep

| Multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |
|---:|:---:|:---:|---:|---:|---|---|---:|---|---:|
| 1.0000 | yes | FAIL | +0.0000 | $+0.00 | - | - | 0 | - | +0.0000 |
| 1.0125 | no | FAIL | +0.0291 | $+447.46 | late_strong, mid_weak | old_thin | 7 | late_strong, mid_weak, old_thin | +0.0004 |
| 1.0250 | no | FAIL | +0.0580 | $+1,121.30 | late_strong, mid_weak | old_thin | 7 | late_strong, mid_weak, old_thin | +0.0016 |
| 1.0500 | no | FAIL | +0.0919 | $+2,205.88 | late_strong, mid_weak | old_thin | 8 | late_strong, mid_weak, old_thin | +0.0036 |

Selected non-control multiplier: `1.05`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Affected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1361 | 5.2200 | +0.0839 | $116,727.26 | $118,101.09 | $+1,373.83 | +0.0004 | 0.8039 | 5 |
| mid_weak | 2.1313 | 2.1402 | +0.0089 | $77,222.87 | $78,110.11 | $+887.24 | +0.0036 | 0.7925 | 2 |
| old_thin | 0.5911 | 0.5902 | -0.0009 | $39,667.96 | $39,612.77 | $-55.19 | +0.0000 | 0.8667 | 1 |

Production impact: replay-only scout. A positive promotion must implement this in shared `production_parity.py`, add parity tests, then rerun the canonical three-window backtest before live/default behavior changes.
