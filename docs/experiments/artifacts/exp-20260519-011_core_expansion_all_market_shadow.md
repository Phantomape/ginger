# exp-20260519-011 Core Expansion All-Market Shadow

Decision: `rejected_available_history_core_expansion_shadow`.

Single variable family: candidate universe membership. No shared policy, sizing, ranking, exit, LLM/news, or live-order path changed.

## Coverage Boundary

- SEC reference tickers: `10341`.
- Canonical all-window non-core governed equities: `0`.
- Augmented all-window non-core governed equities tested: `14`.
- Missing current observation-universe history: `30`.

## Variant Scout

| Variant | Gate | Added | dEV | dPnL | Improved | Regressed | Candidate trades | Windows | Max DD worse |
|---|:---:|---|---:|---:|---|---|---:|---:|---:|
| add_all_history_covered_governed | FAIL | APLD, BE, CIFR, CORZ, DBRG, INTC, IREN, LITE, MARA, RIOT, SNDK, TLN, VST, WULF | +2.2543 | $+46,086.81 | late_strong, mid_weak | old_thin | 10 | 3 | +0.0189 |
| add_current_pilot_history_covered | FAIL | APLD, BE, INTC, LITE | +3.3189 | $+64,367.43 | late_strong, mid_weak | old_thin | 7 | 3 | +0.0132 |
| segment_ai_power_energy | FAIL | TLN, VST | -0.4431 | $-10,896.20 | late_strong | mid_weak, old_thin | 3 | 2 | +0.0190 |
| segment_btc_miner_hpc | FAIL | CIFR, CORZ, IREN, MARA, RIOT, WULF | -0.0380 | $+1,358.02 | late_strong | mid_weak, old_thin | 0 | 0 | +0.0102 |
| segment_power_datacenter_infra | FAIL | APLD, BE | +1.0719 | $+23,631.56 | mid_weak | old_thin | 2 | 2 | +0.0000 |

Selected variant: `add_current_pilot_history_covered`.

Production impact: replay-only shadow. Promotion would require a default-off forward paper sleeve or a separate shared universe policy experiment.
