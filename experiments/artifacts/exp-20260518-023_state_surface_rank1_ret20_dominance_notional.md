# exp-20260518-023 State-Surface Rank-1 Ret20 Dominance Notional

Decision: `accepted_shared_default_off_policy_rank1_ret20_dominance_notional`.

Single causal variable: `rank1_ret20_dominance_rank_notional_profile` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Variant | Gate 4 | Profile | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| accepted_rank2_ret20_score_gap_notional | FAIL | None | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 36.12% |
| rank1_ret20_dominance_ge_015_score_gap_ge_045_balanced | PASS | [1.6, 1.4, 1.0, 0.675, 0.35] | +0.0098 | $+287.87 | 2 | 0 | 6 | +0.0000% | 36.55% |
| rank1_ret20_dominance_ge_015_score_gap_ge_045_less_rank1 | FAIL | [1.55, 1.4, 1.0, 0.675, 0.35] | +0.0169 | $+246.19 | 1 | 1 | 6 | +0.0000% | 36.62% |
| rank1_ret20_dominance_ge_015_score_gap_ge_045_rank2_heavy | FAIL | [1.45, 1.5, 1.1, 0.675, 0.35] | +0.0419 | $+677.50 | 1 | 1 | 6 | +0.0000% | 36.86% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.8661 | 5.8667 | +0.0006 | $128,925.45 | $128,938.31 | $+12.86 | 6.53% | 6.53% | 3 |
| mid_weak | 3.2004 | 3.2096 | +0.0092 | $95,821.82 | $96,096.83 | $+275.01 | 10.63% | 10.63% | 3 |
| old_thin | 0.9033 | 0.9033 | +0.0000 | $51,615.59 | $51,615.59 | $+0.00 | 9.09% | 9.09% | 0 |

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
  "production_impact": "If accepted, shared default-off paper policy changes only state-surface paper notional after queue ranking by using rank-1 ret20 dominance plus score gap. The same state_surface_sleeve.py path is used by production; live/default orders remain disabled.",
  "production_signal_path_changed": false,
  "replay_only": false,
  "run_adapter_changed": true,
  "shared_policy_changed": true,
  "shared_policy_file": "quant/state_surface_sleeve.py"
}
```

No JavaScript was used.
