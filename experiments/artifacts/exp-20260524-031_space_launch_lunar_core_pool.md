# exp-20260524-031 Space Launch/Lunar Core-Pool Scout

Decision: `rejected_space_launch_lunar_core_pool`.

Single variable: add the governed Space launch/lunar cohort to the core replay universe.

## Trial Accounting

- trial_family: `governed_space_launch_lunar_candidate_pool`
- changed_variable: `space_launch_lunar_core_universe_membership`
- prior_trial_count: `6`
- multiple_testing_risk_bucket: `high`
- new_evidence_type: `canonical_aligned_observation_universe_ohlcv_current_governed_space_launch_lunar_records`

## Target Cohort

`LUNR`, `RKLB`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Target trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.9354 | 4.3905 | -0.5449 | $113,719.84 | $106,054.41 | $-7,665.43 | 0.8214 | 1 |
| mid_weak | 2.1386 | 2.6219 | +0.4833 | $78,050.31 | $88,276.19 | $+10,225.88 | 0.8070 | 2 |
| old_thin | 0.5805 | 0.2384 | -0.3421 | $40,307.27 | $21,099.66 | $-19,207.61 | 0.6579 | 1 |

## Gate 4

```json
{
  "aggregate_ev_delta_positive": false,
  "aggregate_pnl_delta_positive": false,
  "improved_windows": [
    "mid_weak"
  ],
  "max_drawdown_worse": 0.0493,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "regressed_windows": [
    "late_strong",
    "old_thin"
  ],
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 1.0,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": false,
    "positive_pnl_hhi": 1.0,
    "positive_pnl_hhi_guardrail": 0.45
  },
  "target_trade_count": 4,
  "target_trade_count_min": 6,
  "target_window_count_min": 2,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ]
}
```

## Production Impact

Replay-only. No production watchlist, shared policy, run adapter, or order path changed. A positive replay would still need shared universe/taxonomy/risk constraints and parity tests before any live/default behavior changes.

No JavaScript was used.
