# exp-20260518-013 State-Surface Score-Dispersion Notional

Decision: `accepted_shared_default_off_policy_score_dispersion_notional`.

Single causal variable: `score_dispersion_rank_notional_profile` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Variant | Gate 4 | Max Top3 Spread | Profile | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| accepted_candidate_breadth_rank_notional | FAIL | None | None | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 31.37% |
| top3_spread_le_030_rank2_lift | FAIL | 0.3 | [1.35, 1.45, 1.05, 0.675, 0.35] | +0.0287 | $+347.24 | 1 | 0 | 3 | +0.0000% | 31.34% |
| top3_spread_le_040_flat | FAIL | 0.4 | [1.45, 1.35, 1.05, 0.675, 0.35] | +0.0091 | $+186.32 | 1 | 1 | 6 | +0.0100% | 31.38% |
| top3_spread_le_040_rank2_lift | PASS | 0.4 | [1.35, 1.45, 1.05, 0.675, 0.35] | +0.0422 | $+451.81 | 2 | 0 | 6 | +0.0000% | 31.28% |
| top3_spread_le_040_rank2_strong | PASS | 0.4 | [1.25, 1.55, 1.1, 0.675, 0.35] | +0.0649 | $+779.93 | 2 | 0 | 6 | +0.0000% | 31.14% |
| top3_spread_le_050_rank2_lift | FAIL | 0.5 | [1.35, 1.45, 1.05, 0.675, 0.35] | -0.0052 | $-356.18 | 1 | 1 | 9 | +0.0000% | 32.85% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.8333 | 5.8620 | +0.0287 | $128,487.28 | $128,834.52 | $+347.24 | 6.53% | 6.53% | 3 |
| mid_weak | 3.3994 | 3.4129 | +0.0135 | $99,688.14 | $99,792.71 | $+104.57 | 10.71% | 10.70% | 3 |
| old_thin | 0.9833 | 0.9833 | +0.0000 | $53,732.81 | $53,732.81 | $+0.00 | 9.16% | 9.16% | 0 |

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
  "production_impact": "If accepted, shared default-off paper policy changes only state-surface paper notional after queue ranking by using top-three score spread. The same state_surface_sleeve.py path is used by production; live/default orders remain disabled.",
  "production_signal_path_changed": false,
  "replay_only": false,
  "run_adapter_changed": true,
  "shared_policy_changed": true,
  "shared_policy_file": "quant/state_surface_sleeve.py"
}
```

No JavaScript was used.
