# exp-20260519-003 State-Surface Rank-1 Score Isolation Notional

Decision: `accepted_default_off_state_surface_rank1_score_isolation_notional`.

Single causal variable: `rank1_score_isolation_rank_notional_profile` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Variant | Gate 4 | Score Gap | Profile | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| accepted_score_expansion_repeat_notional | FAIL | n/a | n/a | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 40.70% |
| rank1_score_gap020_200_110_080 | PASS | 0.2 | [2.0, 1.1, 0.8, 0.675, 0.35] | +0.0438 | $+714.49 | 2 | 0 | 6 | +0.1100% | 40.26% |
| rank1_score_gap020_210_105_075 | PASS | 0.2 | [2.1, 1.05, 0.75, 0.675, 0.35] | +0.0727 | $+1,125.57 | 2 | 0 | 6 | +0.1800% | 39.97% |
| rank1_score_gap020_220_100_070 | PASS | 0.2 | [2.2, 1.0, 0.7, 0.675, 0.35] | +0.1039 | $+1,536.65 | 2 | 0 | 6 | +0.2500% | 39.68% |
| rank1_score_gap030_220_100_070 | FAIL | 0.3 | [2.2, 1.0, 0.7, 0.675, 0.35] | +0.0790 | $+1,148.61 | 1 | 0 | 3 | +0.2500% | 40.01% |
| rank1_score_gap045_220_100_070 | FAIL | 0.45 | [2.2, 1.0, 0.7, 0.675, 0.35] | +0.0790 | $+1,148.61 | 1 | 0 | 3 | +0.2500% | 40.01% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.9704 | 6.0494 | +0.0790 | $130,074.54 | $131,223.15 | $+1,148.61 | 6.67% | 6.92% | 3 |
| mid_weak | 3.8844 | 3.9093 | +0.0249 | $107,009.42 | $107,397.46 | $+388.04 | 10.63% | 10.63% | 3 |
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
