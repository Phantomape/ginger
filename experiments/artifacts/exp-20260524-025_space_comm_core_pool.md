# exp-20260524-025 Space Communications Core-Pool Scout

Decision: `rejected_space_comm_core_pool`.

Single variable: add the governed Space communications/satcom cohort to the core replay universe.

## Trial Accounting

- trial_family: `governed_space_comm_candidate_pool`
- changed_variable: `space_comm_core_universe_membership`
- prior_trial_count: `6`
- multiple_testing_risk_bucket: `high`
- new_evidence_type: `canonical_aligned_observation_universe_ohlcv_current_governed_space_communications_records`

## Target Cohort

`ASTS`, `GSAT`, `IRDM`, `SATS`, `VSAT`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Target trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.9354 | 5.3056 | +0.3702 | $113,719.84 | $115,340.97 | $+1,621.13 | 0.7941 | 7 |
| mid_weak | 2.1386 | 5.0744 | +2.9358 | $78,050.31 | $142,540.85 | $+64,490.54 | 0.8429 | 6 |
| old_thin | 0.5805 | 0.3595 | -0.2210 | $40,307.27 | $30,989.64 | $-9,317.63 | 0.9000 | 3 |

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "improved_windows": [
    "late_strong",
    "mid_weak"
  ],
  "max_drawdown_worse": 0.0049,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "regressed_windows": [
    "old_thin"
  ],
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.417548,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": true,
    "positive_pnl_hhi": 0.333395,
    "positive_pnl_hhi_guardrail": 0.45
  },
  "target_trade_count": 16,
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
