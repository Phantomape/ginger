# exp-20260524-034 Compute-Memory/Storage Governed-Risk Admission

Decision: `rejected_compute_memory_storage_governed_risk_cap`.

Single variable: admit the governed compute-memory/storage cohort only with existing universe-state risk caps.

## Risk Caps

```json
{
  "INTC": 0.45,
  "STX": 0.0,
  "WDC": 0.3
}
```

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Target trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.9354 | 5.5129 | +0.5775 | $113,719.84 | $123,328.90 | $+9,609.06 | 0.8197 | 3 |
| mid_weak | 2.1386 | 2.1523 | +0.0137 | $78,050.31 | $77,700.56 | $-349.75 | 0.7910 | 2 |
| old_thin | 0.5805 | 0.5816 | +0.0011 | $40,307.27 | $40,386.78 | $+79.51 | 0.8769 | 0 |

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
    "max_single_positive_pnl_share": 0.695794,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": false,
    "positive_pnl_hhi": 0.576671,
    "positive_pnl_hhi_guardrail": 0.45
  },
  "target_trade_count": 5,
  "target_trade_count_min": 6,
  "target_window_count_min": 2,
  "target_windows": [
    "late_strong",
    "mid_weak"
  ]
}
```

## Production Impact

Replay-only. No production watchlist, shared policy, run adapter, or order path changed. Promotion would require shared universe governance, shared risk-cap logic, and parity tests.

No JavaScript was used.
