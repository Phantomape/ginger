# exp-20260526-020 Space Volume-Breadth Fixed-Notional Sleeve

Decision: `rejected_space_volume_breadth_fixed_notional_sleeve`.

Single variable: route the governed full-history Space observation pool into an additive fixed-notional default-off paper sleeve only when exp-20260526-013 market volume-breadth thrust is true on the signal date.

## Trial Accounting

- trial_family: `governed_space_volume_breadth_fixed_notional_paper_sleeve`
- changed_variable: `space_governed_volume_breadth_fixed_notional_paper_sleeve_routing_v1`
- prior_trial_count: `9`
- multiple_testing_risk_bucket: `high`
- new_evidence_type: `free_ohlcv_market_volume_breadth_internal_structure_field_on_governed_full_history_space_candidate_pool`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target trades | Filtered |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.9354 | 4.7672 | -0.1682 | $113,719.84 | $112,167.09 | $-1,552.75 | +0.0008 | 4 | 5 |
| mid_weak | 2.1386 | 2.3231 | +0.1845 | $78,050.31 | $81,795.96 | $+3,745.65 | -0.0013 | 3 | 4 |
| old_thin | 0.5805 | 0.6366 | +0.0561 | $40,307.27 | $42,160.08 | $+1,852.81 | +0.0021 | 3 | 1 |

## Aggregate

- EV delta: `0.0724` (`0.009458`)
- PnL delta: `$4045.71` (`0.017433`)
- target trades: `10` across `3` windows
- max single positive share: `0.675381`
- positive PnL HHI: `0.560454`

## Gate 4

```json
{
  "acceptance_rule": "positive aggregate EV/PnL; zero EV/PnL-regressed windows; >=8 target trades across >=2 windows; drawdown drift <=0.5pp; survival >=5%; concentration guard passes",
  "aggregate_ev_delta_positive": true,
  "aggregate_expected_value_score_delta": 0.0724,
  "aggregate_pnl_delta_positive": true,
  "aggregate_total_pnl_delta": 4045.71,
  "max_drawdown_worse": 0.0021,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.675381,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": false,
    "positive_pnl_hhi": 0.560454,
    "positive_pnl_hhi_guardrail": 0.45
  },
  "target_trade_count": 10,
  "target_trade_count_min": 8,
  "target_window_count_min": 2,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 2,
  "windows_ev_regressed": 1,
  "windows_pnl_regressed": 1
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
