# exp-20260523-010 BTC Miner/HPC Specialist Core-Pool Scout

Decision: `rejected_btc_miner_hpc_core_pool`.

Single variable: add the governed BTC miner/HPC specialist cohort to the core replay universe.

## Trial Accounting

- trial_family: `governed_btc_miner_hpc_candidate_pool`
- changed_variable: `btc_miner_hpc_core_universe_membership`
- prior_trial_count: `2`
- multiple_testing_risk_bucket: `high`
- new_evidence_type: `canonical_aligned_observation_universe_ohlcv_current_governed_specialist_records`

## Target Cohort

`CIFR`, `CORZ`, `IREN`, `MARA`, `RIOT`, `WULF`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Target trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.9354 | 4.9391 | +0.0037 | $113,719.84 | $115,133.57 | $+1,413.73 | 0.8148 | 0 |
| mid_weak | 2.1386 | 2.1224 | -0.0162 | $78,050.31 | $79,490.41 | $+1,440.10 | 0.8136 | 0 |
| old_thin | 0.5805 | 0.5550 | -0.0255 | $40,307.27 | $38,811.46 | $-1,495.81 | 0.8571 | 0 |

## Gate 4

```json
{
  "aggregate_ev_delta_positive": false,
  "aggregate_pnl_delta_positive": true,
  "improved_windows": [
    "late_strong"
  ],
  "max_drawdown_worse": 0.0102,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "regressed_windows": [
    "mid_weak",
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
  "target_trade_count": 0,
  "target_trade_count_min": 6,
  "target_window_count_min": 2,
  "target_windows": []
}
```

## Production Impact

Replay-only. No production watchlist, shared policy, run adapter, or order path changed. A positive replay would still need shared specialist universe, sector taxonomy, risk constraints, and parity tests before any live/default behavior changes.

No JavaScript was used.
