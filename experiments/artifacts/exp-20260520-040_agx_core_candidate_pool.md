# exp-20260520-040 AGX Core Candidate-Pool Scout

Decision: `rejected_agx_core_candidate_pool`.

Single variable: AGX membership in the core replay universe, with required Industrials taxonomy applied for correct risk classification.

## Trial Accounting

- trial_family: `broad_market_candidate_pool_governance`
- prior_trial_count: `3`
- multiple_testing_risk_bucket: `moderate`
- new_evidence_type: `single_ticker_correct_sector_replay`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | AGX trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1628 | +0.0000 | $117,072.92 | $117,072.92 | $+0.00 | 0.8113 | 0 |
| mid_weak | 2.1402 | 2.1402 | +0.0000 | $78,110.11 | $78,110.11 | $+0.00 | 0.7963 | 0 |
| old_thin | 0.5911 | 0.5894 | -0.0017 | $39,667.96 | $40,645.43 | $+977.47 | 0.8594 | 0 |

## Gate 4

```json
{
  "aggregate_ev_delta_positive": false,
  "aggregate_pnl_delta_positive": true,
  "improved_windows": [],
  "max_drawdown_worse": 0.0105,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "regressed_windows": [
    "old_thin"
  ],
  "survival_guard_passed": true,
  "target_trade_count": 0,
  "target_trade_count_min": 3,
  "target_window_count_min": 2,
  "target_windows": []
}
```

## Production Impact

No production watchlist, shared policy, run adapter, or order path changed. A positive result would require a shared watchlist and sector-map promotion plus another canonical replay.

No JavaScript was used.
