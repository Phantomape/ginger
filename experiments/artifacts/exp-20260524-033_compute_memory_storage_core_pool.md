# exp-20260524-033 Compute-Memory/Storage Core-Pool Scout

Decision: `rejected_compute_memory_storage_core_pool`.

Single variable: add the governed compute-memory/storage cohort to the core replay universe.

## Trial Accounting

- trial_family: `governed_compute_memory_storage_candidate_pool`
- changed_variable: `compute_memory_storage_core_universe_membership`
- prior_trial_count: `5`
- multiple_testing_risk_bucket: `high`
- new_evidence_type: `canonical_aligned_observation_universe_ohlcv_current_governed_compute_memory_semis_records_with_new_stx_peer`

## Target Cohort

`INTC`, `WDC`, `STX`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Target trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.9354 | 6.2412 | +1.3058 | $113,719.84 | $134,798.01 | $+21,078.17 | 0.8197 | 3 |
| mid_weak | 2.1386 | 2.2231 | +0.0845 | $78,050.31 | $80,840.50 | $+2,790.19 | 0.7971 | 2 |
| old_thin | 0.5805 | 0.6020 | +0.0215 | $40,307.27 | $42,101.26 | $+1,793.99 | 0.8824 | 1 |

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "improved_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "max_drawdown_worse": 0.0132,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "regressed_windows": [],
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.587303,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": false,
    "positive_pnl_hhi": 0.515244,
    "positive_pnl_hhi_guardrail": 0.45
  },
  "target_trade_count": 6,
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
