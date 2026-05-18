# exp-20260518-005 State-Surface Regime Rank Notional

Decision: `accepted_shared_default_off_policy_regime_rank_notional`.

Single causal variable: `rank_notional_profile_by_regime` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Variant | Gate 4 | dEV | dPnL | EV Improved | EV Regressed | Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| accepted_all_regime_rank_notional | FAIL | +0.0000 | $+0.00 | 0 | 0 | 24 | +0.0000% | 32.22% |
| chop_mild_rank_plus | PASS | +0.1199 | $+2,111.20 | 3 | 0 | 24 | +0.0800% | 31.69% |
| chop_strong_rank_plus | PASS | +0.2176 | $+4,222.41 | 3 | 0 | 24 | +0.1800% | 31.21% |
| chop_max_rank_plus | PASS | +0.4369 | $+8,982.13 | 3 | 0 | 24 | +0.3700% | 30.92% |

## Best Variant

- Best: `chop_mild_rank_plus`
- Default profile: `[1.5, 1.25, 1.0, 0.75, 0.5]`
- Regime profiles: `{"chop": [1.625, 1.3, 1.0, 0.7, 0.375]}`
- Aggregate EV delta: `+0.1199`
- Aggregate PnL delta: `$+2,111.20`

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
  "production_impact": "If accepted, shared default-off paper policy changes only state-surface paper notional after queue ranking by using decision-date regime. The same state_surface_sleeve.py path is used by production; live/default orders remain disabled.",
  "production_signal_path_changed": false,
  "replay_only": false,
  "run_adapter_changed": true,
  "shared_policy_changed": true,
  "shared_policy_file": "quant/state_surface_sleeve.py"
}
```

No JavaScript was used.
