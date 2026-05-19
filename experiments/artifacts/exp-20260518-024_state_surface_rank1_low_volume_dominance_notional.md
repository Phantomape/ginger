# exp-20260518-024 State-Surface Rank-1 Low-Volume Dominance Notional

Decision: `rejected_state_surface_rank1_low_volume_dominance_notional`.

Single causal variable: `rank1_low_volume_dominance_rank_notional_profile` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Variant | Gate 4 | Volume Max | Profile | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| accepted_rank1_ret20_dominance_notional | FAIL | None | None | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 36.55% |
| rank1_volume_lt_050_rank2_shift | FAIL | 0.5 | [1.0, 1.85, 1.1, 0.675, 0.35] | +0.1229 | $+1,774.52 | 1 | 0 | 3 | +0.0000% | 37.83% |
| rank1_volume_lt_065_small_shift | FAIL | 0.65 | [1.55, 1.45, 1.0, 0.675, 0.35] | +0.0054 | $+161.96 | 1 | 1 | 6 | +0.0000% | 36.71% |
| rank1_volume_lt_065_balanced | FAIL | 0.65 | [1.5, 1.5, 1.0, 0.675, 0.35] | +0.0209 | $+323.91 | 1 | 1 | 6 | +0.0000% | 36.87% |
| rank1_volume_lt_065_rank2_shift | FAIL | 0.65 | [1.0, 1.85, 1.1, 0.675, 0.35] | +0.1205 | $+1,439.96 | 1 | 1 | 6 | +0.0000% | 38.06% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.8667 | 5.8667 | +0.0000 | $128,938.31 | $128,938.31 | $+0.00 | 6.53% | 6.53% | 0 |
| mid_weak | 3.4879 | 3.6108 | +0.1229 | $100,805.09 | $102,579.61 | $+1,774.52 | 10.63% | 10.63% | 3 |
| old_thin | 1.0073 | 1.0073 | +0.0000 | $54,742.08 | $54,742.08 | $+0.00 | 9.11% | 9.11% | 0 |

## Production Impact

```json
{
  "alters_candidate_ranking": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_sizing": false,
  "backtester_adapter_changed": false,
  "parity_test_added": false,
  "parity_test_file": "quant/test_state_surface_sleeve.py",
  "production_impact": "If accepted, shared default-off paper policy would change only state-surface paper notional after queue ranking by using rank-1 low-volume participation inside accepted rank-1 dominance days. The same state_surface_sleeve.py path is used by production; live/default orders remain disabled.",
  "production_signal_path_changed": false,
  "replay_only": false,
  "run_adapter_changed": false,
  "shared_policy_changed": false,
  "shared_policy_file": "quant/state_surface_sleeve.py"
}
```

No JavaScript was used.
