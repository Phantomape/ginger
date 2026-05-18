# exp-20260518-018 State-Surface Rank-2 Ret20 Lead Notional

Decision: `accepted_shared_default_off_policy_rank2_ret20_lead_notional`.

Single causal variable: `rank2_ret20_lead_rank_notional_profile` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Variant | Gate 4 | Rank2 Ret20 Lead Min | Profile | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| accepted_score_compression_rank_notional | FAIL | None | None | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 31.28% |
| rank2_ret20_lead_ge_000_rank2_lift | FAIL | 0.0 | [1.35, 1.55, 1.0, 0.675, 0.35] | +0.0222 | $+535.08 | 2 | 1 | 9 | +0.0000% | 33.60% |
| rank2_ret20_lead_ge_005_rank2_lift | FAIL | 0.005 | [1.35, 1.55, 1.0, 0.675, 0.35] | +0.0222 | $+535.08 | 2 | 1 | 9 | +0.0000% | 33.60% |
| rank2_ret20_lead_ge_000_balanced_lift | PASS | 0.0 | [1.25, 1.55, 1.1, 0.675, 0.35] | +0.0237 | $+382.71 | 3 | 0 | 9 | +0.0000% | 33.76% |
| rank2_ret20_lead_ge_005_balanced_lift | PASS | 0.005 | [1.25, 1.55, 1.1, 0.675, 0.35] | +0.0237 | $+382.71 | 3 | 0 | 9 | +0.0000% | 33.76% |
| rank2_ret20_lead_ge_010_balanced_lift | PASS | 0.01 | [1.25, 1.55, 1.1, 0.675, 0.35] | +0.0227 | $+328.12 | 2 | 0 | 6 | +0.0000% | 31.14% |
| rank2_ret20_lead_ge_005_broad_lift | PASS | 0.005 | [1.3, 1.55, 1.1, 0.675, 0.35] | +0.0260 | $+544.72 | 3 | 0 | 9 | +0.0000% | 33.63% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.8620 | 5.8661 | +0.0041 | $128,834.52 | $128,925.45 | $+90.93 | 6.53% | 6.53% | 3 |
| mid_weak | 3.4129 | 3.4307 | +0.0178 | $99,792.71 | $100,021.23 | $+228.52 | 10.70% | 10.68% | 3 |
| old_thin | 0.9833 | 0.9874 | +0.0041 | $53,732.81 | $53,958.08 | $+225.27 | 9.16% | 9.15% | 3 |

## Production Impact

```json
{
  "alters_candidate_ranking": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_sizing": false,
  "backtester_adapter_changed": false,
  "parity_test_added": true,
  "parity_test_file": "quant/test_state_surface_sleeve.py",
  "production_impact": "If accepted, shared default-off paper policy changes only state-surface paper notional after queue ranking by using rank-2 ret20 excess leadership over rank 1. The same state_surface_sleeve.py path is used by production; live/default orders remain disabled.",
  "production_signal_path_changed": false,
  "replay_only": false,
  "run_adapter_changed": true,
  "shared_policy_changed": true,
  "shared_policy_file": "quant/state_surface_sleeve.py"
}
```

No JavaScript was used.
