# exp-20260517-006 Two-Slot Rank-2 Top-Up

Decision: `rejected_two_slot_rank2_topup`.

Single variable: cap-aware risk top-up on the already-selected rank-2 signal when `available_slots == 2`. The accepted one-slot rank-1 top-up remains unchanged in both baseline and variants. Entries, filters, candidate pool, ranking, exits, targets, LLM/news, event sleeves, and portfolio heat were unchanged.

## Sweep

| Multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |
|---:|:---:|:---:|---:|---:|---|---|---:|---|---:|
| 1.000 | yes | FAIL | +0.0000 | $+0.00 | - | - | 0 | - | +0.0000 |
| 1.025 | no | FAIL | +0.0019 | $-0.55 | late_strong | old_thin | 2 | late_strong, old_thin | +0.0008 |
| 1.050 | no | FAIL | -0.0100 | $+38.46 | - | late_strong, old_thin | 2 | late_strong, old_thin | +0.0015 |
| 1.075 | no | FAIL | -0.0069 | $+63.94 | late_strong | old_thin | 2 | late_strong, old_thin | +0.0022 |

Selected non-control multiplier: `1.025`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Affected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1361 | 5.1392 | +0.0031 | $116,727.26 | $116,799.71 | $+72.45 | -0.0001 | 0.8039 | 1 |
| mid_weak | 2.1313 | 2.1313 | +0.0000 | $77,222.87 | $77,222.87 | $+0.00 | +0.0000 | 0.7925 | 0 |
| old_thin | 0.5911 | 0.5899 | -0.0012 | $39,667.96 | $39,594.96 | $-73.00 | +0.0008 | 0.8667 | 1 |

Production impact: replay-only scout. A positive promotion must implement this in shared `production_parity.py`, add parity tests, then rerun the canonical three-window backtest before live/default behavior changes.
