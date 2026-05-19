# exp-20260518-020 State-Surface Rank-2 Ret20 Score-Gap Notional

Decision: `accepted_shared_default_off_policy_rank2_ret20_score_gap_notional`.

Single causal variable: `rank2_ret20_score_gap_rank_notional_profile` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Variant | Gate 4 | Score Gap Min | Profile | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| accepted_rank2_ret20_lead_notional | FAIL | None | None | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 33.63% |
| rank2_ret20_lead_score_gap_ge_020_mild | PASS | 0.2 | [1.2, 1.65, 1.1, 0.675, 0.35] | +0.0207 | $+430.96 | 2 | 0 | 6 | +0.0000% | 34.47% |
| rank2_ret20_lead_score_gap_ge_030_mild | PASS | 0.3 | [1.2, 1.65, 1.1, 0.675, 0.35] | +0.0207 | $+430.96 | 2 | 0 | 6 | +0.0000% | 34.47% |
| rank2_ret20_lead_score_gap_ge_030_balanced | PASS | 0.3 | [1.1, 1.75, 1.1, 0.675, 0.35] | +0.0313 | $+861.91 | 2 | 0 | 6 | +0.0000% | 35.30% |
| rank2_ret20_lead_score_gap_ge_030_strong | PASS | 0.3 | [1.0, 1.85, 1.1, 0.675, 0.35] | +0.0575 | $+1,292.85 | 2 | 0 | 6 | +0.0000% | 36.12% |
| rank2_ret20_lead_score_gap_ge_050_balanced | FAIL | 0.5 | [1.1, 1.75, 1.1, 0.675, 0.35] | +0.0096 | $+522.67 | 1 | 0 | 3 | +0.0000% | 35.53% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.8661 | 5.8661 | +0.0000 | $128,925.45 | $128,925.45 | $+0.00 | 6.53% | 6.53% | 0 |
| mid_weak | 3.4307 | 3.4683 | +0.0376 | $100,021.23 | $100,530.08 | $+508.85 | 10.68% | 10.63% | 3 |
| old_thin | 0.9874 | 1.0073 | +0.0199 | $53,958.08 | $54,742.08 | $+784.00 | 9.15% | 9.11% | 3 |

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
  "production_impact": "If accepted, shared default-off paper policy changes only state-surface paper notional after queue ranking by using score-gap-conditioned rank-2 ret20 leadership. The same state_surface_sleeve.py path is used by production; live/default orders remain disabled.",
  "production_signal_path_changed": false,
  "replay_only": false,
  "run_adapter_changed": true,
  "shared_policy_changed": true,
  "shared_policy_file": "quant/state_surface_sleeve.py"
}
```

No JavaScript was used.
