# exp-20260523-009 AI Power Datacenter Infrastructure Core-Pool Scout

Decision: `rejected_ai_power_datacenter_core_pool`.

Single variable: add the governed AI power/datacenter infrastructure cohort to the core replay universe.

## Trial Accounting

- trial_family: `governed_ai_power_candidate_pool`
- changed_variable: `ai_power_datacenter_core_universe_membership`
- prior_trial_count: `5`
- multiple_testing_risk_bucket: `moderate_high`
- new_evidence_type: `canonical_aligned_observation_universe_ohlcv_current_governed_records`

## Target Cohort

`BE`, `CEG`, `ETN`, `GEV`, `PWR`, `VRT`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Target trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.9354 | 4.4024 | -0.5330 | $113,719.84 | $108,974.91 | $-4,744.93 | 0.7895 | 1 |
| mid_weak | 2.1386 | 2.1386 | +0.0000 | $78,050.31 | $78,050.31 | $+0.00 | 0.7833 | 0 |
| old_thin | 0.5805 | 0.3949 | -0.1856 | $40,307.27 | $32,910.47 | $-7,396.80 | 0.8732 | 2 |

## Gate 4

```json
{
  "aggregate_ev_delta_positive": false,
  "aggregate_pnl_delta_positive": false,
  "improved_windows": [],
  "max_drawdown_worse": 0.0094,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "regressed_windows": [
    "late_strong",
    "old_thin"
  ],
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": null,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": false,
    "positive_pnl_hhi": null,
    "positive_pnl_hhi_guardrail": 0.45
  },
  "target_trade_count": 3,
  "target_trade_count_min": 6,
  "target_window_count_min": 2,
  "target_windows": [
    "late_strong",
    "old_thin"
  ]
}
```

## Production Impact

No production watchlist, shared policy, run adapter, or order path changed. A positive replay requires shared universe/taxonomy implementation and parity tests before any live/default behavior changes.

No JavaScript was used.
