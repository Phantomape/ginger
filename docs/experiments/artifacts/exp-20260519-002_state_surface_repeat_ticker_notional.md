# exp-20260519-002 State-Surface Recent Ticker Repeat Notional

Decision: `accepted_default_off_state_surface_recent_ticker_repeat_notional`.

Single causal variable: `recent_ticker_repeat_60d_notional_scalar` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Variant | Gate 4 | Scalar | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| accepted_score_expansion_notional | FAIL | n/a | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 38.01% |
| repeat_60d_dampen_0_50 | FAIL | 0.50 | -0.2513 | $-4,069.88 | 0 | 2 | 2 | +0.0000% | 34.24% |
| repeat_60d_dampen_0_75 | FAIL | 0.75 | -0.1278 | $-2,034.94 | 0 | 2 | 2 | +0.0000% | 36.19% |
| repeat_60d_topup_1_10 | PASS | 1.10 | +0.0505 | $+813.97 | 2 | 0 | 2 | +0.0000% | 38.70% |
| repeat_60d_topup_1_25 | PASS | 1.25 | +0.1398 | $+2,034.93 | 2 | 0 | 2 | +0.0000% | 39.70% |
| repeat_60d_topup_1_50 | PASS | 1.50 | +0.2685 | $+4,069.88 | 2 | 0 | 2 | +0.0000% | 41.28% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.8815 | 5.9166 | +0.0351 | $128,980.91 | $129,465.20 | $+484.29 | 6.53% | 6.53% | 1 |
| mid_weak | 3.6468 | 3.8802 | +0.2334 | $103,307.84 | $106,893.43 | $+3,585.59 | 10.63% | 10.63% | 1 |
| old_thin | 1.0304 | 1.0304 | +0.0000 | $55,397.40 | $55,397.40 | $+0.00 | 9.07% | 9.07% | 0 |

## Production Impact

```json
{
  "backtester_adapter_changed": false,
  "core_metrics_changed": false,
  "default_off_paper_only": true,
  "live_default_orders_changed": false,
  "parity_test_added": true,
  "replay_only": true,
  "run_adapter_changed": true,
  "shared_policy_changed": true
}
```

No JavaScript was used.
