# exp-20260524-026 Space Communications IWM-Gated Core-Pool Scout

Decision: `rejected_space_comm_iwm_gate_core_pool`.

Single variable: allow the governed Space comm/satcom cohort into replay candidate generation only when IWM 20d momentum leads SPY.

## Trial Accounting

- trial_family: `governed_space_comm_iwm_gate_candidate_pool`
- changed_variable: `space_comm_iwm_leader_core_universe_membership`
- prior_trial_count: `7`
- multiple_testing_risk_bucket: `high`
- new_evidence_type: `materially_different_production_visible_small_cap_risk_appetite_gate_on_governed_space_comm_candidate_pool`

## Target Cohort

`ASTS`, `GSAT`, `IRDM`, `SATS`, `VSAT`

## IWM Gate

```json
{
  "by_window": {
    "late_strong": {
      "days_with_target_features": 120,
      "gate_closed_days": 46,
      "gate_open_days": 74,
      "missing_iwm_or_spy_momentum_days": 0,
      "sample_gate_closed_dates": [],
      "sample_gate_open_dates": [],
      "target_feature_rows_removed": 230
    },
    "mid_weak": {
      "days_with_target_features": 112,
      "gate_closed_days": 53,
      "gate_open_days": 59,
      "missing_iwm_or_spy_momentum_days": 0,
      "sample_gate_closed_dates": [],
      "sample_gate_open_dates": [],
      "target_feature_rows_removed": 265
    },
    "old_thin": {
      "days_with_target_features": 122,
      "gate_closed_days": 92,
      "gate_open_days": 30,
      "missing_iwm_or_spy_momentum_days": 0,
      "sample_gate_closed_dates": [],
      "sample_gate_open_dates": [],
      "target_feature_rows_removed": 460
    }
  },
  "passed": true
}
```

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Target trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.9354 | 4.9502 | +0.0148 | $113,719.84 | $110,252.24 | $-3,467.60 | 0.7846 | 5 |
| mid_weak | 2.1386 | 2.7389 | +0.6003 | $78,050.31 | $96,776.45 | $+18,726.14 | 0.8413 | 4 |
| old_thin | 0.5805 | 0.5072 | -0.0733 | $40,307.27 | $37,845.17 | $-2,462.10 | 0.8971 | 1 |

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "improved_windows": [
    "late_strong",
    "mid_weak"
  ],
  "max_drawdown_worse": 0.0102,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "regressed_windows": [
    "old_thin"
  ],
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.590091,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": false,
    "positive_pnl_hhi": 0.516233,
    "positive_pnl_hhi_guardrail": 0.45
  },
  "target_trade_count": 10,
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

Replay-only. No production watchlist, shared policy, run adapter, or order path changed. A positive replay still requires shared Space universe/taxonomy/IWM-gate constraints and parity tests before any live/default behavior changes.

No JavaScript was used.
