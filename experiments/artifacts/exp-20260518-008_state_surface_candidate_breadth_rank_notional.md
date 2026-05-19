# exp-20260518-008 State-Surface Candidate-Breadth Rank Notional

Decision: `accepted_shared_default_off_policy_candidate_breadth_rank_notional`.

Single causal variable: `candidate_breadth_rank_notional_profile` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Variant | Gate 4 | Profile | dEV | dPnL | EV Improved | EV Regressed | Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| accepted_regime_rank_notional | FAIL | None | +0.0000 | $+0.00 | 0 | 0 | 24 | +0.0000% | 31.69% |
| breadth_ge4_chop_profile | FAIL | [1.625, 1.3, 1.0, 0.7, 0.375] | +0.0077 | $+225.83 | 1 | 0 | 24 | +0.0000% | 31.55% |
| breadth_ge4_mid1 | PASS | [1.6625, 1.315, 1.0, 0.675, 0.35] | +0.0400 | $+926.94 | 3 | 0 | 24 | +0.0300% | 31.37% |
| breadth_ge4_mid2 | PASS | [1.6875, 1.325, 1.0, 0.65, 0.3375] | +0.0704 | $+1,394.35 | 3 | 0 | 24 | +0.0500% | 31.25% |
| breadth_ge4_strong | PASS | [1.75, 1.35, 1.0, 0.6, 0.3] | +0.1332 | $+2,562.87 | 3 | 0 | 24 | +0.1000% | 30.95% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Sleeve trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.8255 | 5.8333 | +0.0078 | $128,314.41 | $128,487.28 | $+172.87 | 6.50% | 6.53% | 9 |
| mid_weak | 3.3712 | 3.3994 | +0.0282 | $99,152.49 | $99,688.14 | $+535.65 | 10.74% | 10.71% | 12 |
| old_thin | 0.9793 | 0.9833 | +0.0040 | $53,514.39 | $53,732.81 | $+218.42 | 9.18% | 9.16% | 3 |

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
  "production_impact": "If accepted, shared default-off paper policy changes only state-surface paper notional after queue ranking by using same-day candidate breadth. The same state_surface_sleeve.py path is used by production; live/default orders remain disabled.",
  "production_signal_path_changed": false,
  "replay_only": false,
  "run_adapter_changed": true,
  "shared_policy_changed": true,
  "shared_policy_file": "quant/state_surface_sleeve.py"
}
```

No JavaScript was used.
