# exp-20260524-020 Residual AI Infra Core-Pool Scout

Decision: `rejected_residual_ai_infra_core_pool`.

Single variable: add the governed residual AI-infra pilot cohort to the core replay universe.

## Trial Accounting

- trial_family: `governed_residual_ai_infra_candidate_pool`
- changed_variable: `residual_ai_infra_core_universe_membership`
- prior_trial_count: `5`
- multiple_testing_risk_bucket: `high`
- new_evidence_type: `canonical_aligned_observation_universe_ohlcv_current_governed_residual_ai_infra_records`

## Target Cohort

`APLD`, `INTC`, `WDC`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Target trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.9354 | 4.2069 | -0.7285 | $113,719.84 | $109,838.70 | $-3,881.14 | 0.8103 | 4 |
| mid_weak | 2.1386 | 2.3632 | +0.2246 | $78,050.31 | $88,510.25 | $+10,459.94 | 0.8310 | 2 |
| old_thin | 0.5805 | 0.5792 | -0.0013 | $40,307.27 | $40,218.26 | $-89.01 | 0.8730 | 0 |

## Gate 4

```json
{
  "aggregate_ev_delta_positive": false,
  "aggregate_pnl_delta_positive": true,
  "improved_windows": [
    "mid_weak"
  ],
  "max_drawdown_worse": 0.0131,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "regressed_windows": [
    "late_strong",
    "old_thin"
  ],
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.677154,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": false,
    "positive_pnl_hhi": 0.562767,
    "positive_pnl_hhi_guardrail": 0.45
  },
  "target_trade_count": 6,
  "target_trade_count_min": 6,
  "target_window_count_min": 2,
  "target_windows": [
    "late_strong",
    "mid_weak"
  ]
}
```

## Production Impact

Replay-only. No production watchlist, shared policy, run adapter, or order path changed. A positive replay would still need shared pilot universe, sector taxonomy, risk constraints, and parity tests before any live/default behavior changes.

No JavaScript was used.
