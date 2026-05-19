# exp-20260517-005 Two-Slot Rank-1 Top-Up

Decision: `rejected_two_slot_rank1_topup`.

Single variable: cap-aware risk top-up on the already-selected rank-1 signal when `available_slots == 2`. The accepted one-slot rank-1 top-up remains unchanged in both baseline and variants. Entries, filters, candidate pool, ranking, exits, targets, LLM/news, event sleeves, and portfolio heat were unchanged.

## Sweep

| Multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |
|---:|:---:|:---:|---:|---:|---|---|---:|---|---:|
| 1.000 | yes | FAIL | +0.0000 | $+0.00 | - | - | 0 | - | +0.0000 |
| 1.025 | no | FAIL | -0.0034 | $+459.48 | mid_weak | late_strong | 5 | late_strong, mid_weak | +0.0009 |
| 1.050 | no | FAIL | -0.0091 | $+876.10 | mid_weak | late_strong | 5 | late_strong, mid_weak | +0.0019 |
| 1.075 | no | FAIL | -0.0182 | $+1,222.31 | mid_weak | late_strong | 5 | late_strong, mid_weak | +0.0029 |

Selected non-control multiplier: `1.025`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Affected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1361 | 5.1325 | -0.0036 | $116,727.26 | $117,175.44 | $+448.18 | +0.0009 | 0.8039 | 2 |
| mid_weak | 2.1313 | 2.1315 | +0.0002 | $77,222.87 | $77,234.17 | $+11.30 | +0.0000 | 0.7925 | 3 |
| old_thin | 0.5911 | 0.5911 | +0.0000 | $39,667.96 | $39,667.96 | $+0.00 | +0.0000 | 0.8667 | 0 |

Production impact: replay-only scout. A positive promotion must implement this in shared `production_parity.py`, add parity tests, then rerun the canonical three-window backtest before live/default behavior changes.
