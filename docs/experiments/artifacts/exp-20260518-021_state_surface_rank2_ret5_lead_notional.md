# exp-20260518-021 State-Surface Rank-2 Ret5 Lead Notional

Decision: `rejected_state_surface_rank2_ret5_lead_notional`.

Single causal variable: `rank2_ret5_lead_rank_notional_profile` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Variant | Gate 4 | Ret5 Lead Min | Rank1 Ret5 Negative | Profile | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| accepted_rank2_ret20_lead_notional | FAIL | None | False | None | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 33.63% |
| rank2_ret5_lead_ge_000_rank2_lift | FAIL | 0.0 | False | [1.3, 1.55, 1.1, 0.675, 0.35] | +0.0450 | $+420.83 | 2 | 0 | 12 | +0.0000% | 35.05% |
| rank2_ret5_lead_ge_020_rank2_lift | FAIL | 0.02 | False | [1.3, 1.55, 1.1, 0.675, 0.35] | +0.0450 | $+420.83 | 2 | 0 | 12 | +0.0000% | 35.05% |
| rank2_ret5_lead_ge_050_rank2_lift | FAIL | 0.05 | False | [1.3, 1.55, 1.1, 0.675, 0.35] | +0.0030 | $-217.30 | 1 | 0 | 6 | +0.0000% | 33.76% |
| rank1_ret5_negative_rank2_lift | FAIL | 0.0 | True | [1.3, 1.55, 1.1, 0.675, 0.35] | +0.0667 | $+756.10 | 2 | 0 | 6 | +0.0000% | 34.69% |

## Best Non-Control Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Adjusted trades |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.8661 | 5.8691 | +0.0030 | $128,925.45 | $128,708.15 | $-217.30 | 3 |
| mid_weak | 3.4307 | 3.4944 | +0.0637 | $100,021.23 | $100,994.63 | $+973.40 | 3 |
| old_thin | 0.9874 | 0.9874 | +0.0000 | $53,958.08 | $53,958.08 | $+0.00 | 0 |

## Interpretation

Rank-2 short-term ret5 leadership is not a promotable follow-on to the accepted rank-2 ret20 leadership rule. The best non-control variant improved aggregate EV/PnL, but it failed the tail-aware promotion discipline because the adjusted sample is thin and single-ticker positive contribution concentration worsened versus the accepted baseline.

## Production Impact

```json
{
  "backtester_adapter_changed": false,
  "candidate_filter_changed": false,
  "candidate_ranking_changed": false,
  "live_default_orders_changed": false,
  "paper_notional_changed_if_rejected": false,
  "parity_test_added": false,
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

No JavaScript was used.
