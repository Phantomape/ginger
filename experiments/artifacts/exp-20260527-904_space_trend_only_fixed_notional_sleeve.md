# exp-20260527-904 Space Trend-Only Fixed-Notional Sleeve

Decision: `rejected_space_trend_only_fixed_notional_sleeve`.

Single variable: route the governed full-history Space observation pool into an additive fixed-notional default-off paper sleeve only when the existing signal engine labels the discovery `trend_long`.

## Gate Questions

- alpha_hypothesis: entry/candidate_pool/risk allocation: governed full-history Space candidates may produce additive replacement value when the existing engine marks the discovery trend_long.
- single_causal_variable: `space_governed_trend_only_fixed_notional_paper_sleeve_routing_v1`
- reproducibility: `.venv\Scripts\python.exe quant\experiments\exp_20260527_904_space_trend_only_fixed_notional_sleeve.py`

## Trial Accounting

- trial_family: `governed_space_trend_only_fixed_notional_paper_sleeve`
- changed_variable: `space_governed_trend_only_fixed_notional_paper_sleeve_routing_v1`
- prior_trial_count: `10`
- multiple_testing_risk_bucket: `high`
- new_evidence_type: `production_visible_existing_strategy_family_on_governed_full_history_space_candidate_pool`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target trades | Filtered |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.5755 | 4.8881 | +0.3126 | $109,198.53 | $112,626.43 | $+3,427.90 | -0.0009 | 4 | 5 |
| mid_weak | 2.6219 | 3.2147 | +0.5928 | $88,276.19 | $98,612.40 | $+10,336.21 | -0.0021 | 5 | 2 |
| old_thin | 0.3787 | 0.3359 | -0.0428 | $28,472.77 | $26,655.82 | $-1,816.95 | +0.0052 | 3 | 1 |

## Aggregate

- EV delta: `0.8626` (`0.113858`)
- PnL delta: `$11947.16` (`0.052876`)
- target trades: `12` across `3` windows
- max single positive share: `0.369774`
- positive PnL HHI: `0.285619`

## Gate 4

```json
{
  "acceptance_rule": "positive aggregate EV/PnL; zero EV/PnL-regressed windows; >=8 target trades across >=2 windows; drawdown drift <=0.5pp; survival >=5%; concentration guard passes",
  "aggregate_ev_delta_positive": true,
  "aggregate_expected_value_score_delta": 0.8626,
  "aggregate_pnl_delta_positive": true,
  "aggregate_total_pnl_delta": 11947.16,
  "max_drawdown_worse": 0.0052,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.369774,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": true,
    "positive_pnl_hhi": 0.285619,
    "positive_pnl_hhi_guardrail": 0.45
  },
  "target_trade_count": 12,
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
