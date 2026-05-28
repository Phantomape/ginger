# exp-20260528-023 Fundamental Growth + RS Operating-Margin Durability

Decision: `rejected_fundamental_growth_rs_operating_margin_durability_support`.

Single variable: apply a 1.05x paper-notional support scalar to already selected governed Companyfacts+RS paper candidates whose PIT operating margin is non-declining versus the prior-year same quarter.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Operating-margin supported |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 7.7701 | +2.6073 | $117,072.92 | $143,894.75 | $+26,821.83 | -0.0101 | 99 | 85 |
| mid_weak | 2.1402 | 6.2369 | +4.0967 | $78,110.11 | $135,882.90 | $+57,772.79 | -0.0220 | 116 | 104 |
| old_thin | 0.5911 | 1.8441 | +1.2530 | $39,667.96 | $71,196.98 | $+31,529.02 | +0.0024 | 121 | 108 |

## Aggregate

- EV delta: `7.957` (`1.007968`)
- PnL delta: `$116123.64` (`0.494457`)
- target trades: `336`
- max drawdown drift: `0.0024`
- max single positive share: `0.310582`
- positive PnL HHI: `0.220347`

## Operating-Margin Audit

```json
{
  "late_strong": {
    "daily_top1_filtered": 127,
    "filing_recency_supported": 67,
    "filtered_candidates": 161,
    "final_closed_pnl": 26821.83,
    "input_candidates": 260,
    "low_liability_supported": 81,
    "low_volume_supported": 38,
    "max_closed_drawdown_seen_usd": 7210.98,
    "min_operating_margin_yoy_delta": 0.0,
    "missing_trade_filtered": 31,
    "operating_margin_bucket_counts": {
      "improved_2_to_10pp": 4,
      "improved_gt_10pp": 72,
      "operating_margin_declined": 14,
      "stable_0_to_2pp": 9
    },
    "operating_margin_notional_scalar": 1.05,
    "operating_margin_status_counts": {
      "ok": 85,
      "operating_margin_declined": 14
    },
    "operating_margin_support_pnl_delta_by_ticker": {
      "AMD": 421.89,
      "APP": 11.92,
      "CRDO": -551.48,
      "MU": 1246.98,
      "RTX": 8.1
    },
    "operating_margin_supported": 85,
    "operating_margin_supported_ticker_counts": {
      "AMD": 4,
      "APP": 5,
      "CRDO": 4,
      "MU": 63,
      "RTX": 9
    },
    "rule_version": "fundamental_growth_rs_operating_margin_durability_support_v1",
    "same_ticker_core_overlap_filtered": 3,
    "selected_ticker_counts": {
      "AMD": 4,
      "APP": 5,
      "CRDO": 4,
      "GOOG": 14,
      "MU": 63,
      "RTX": 9
    },
    "selected_trades": 99,
    "selected_unique_tickers": 6,
    "ticker_profit_cap_scaled": 34
  },
  "mid_weak": {
    "daily_top1_filtered": 268,
    "filing_recency_supported": 84,
    "filtered_candidates": 283,
    "final_closed_pnl": 57772.79,
    "input_candidates": 399,
    "low_liability_supported": 61,
    "low_volume_supported": 54,
    "max_closed_drawdown_seen_usd": 4571.42,
    "min_operating_margin_yoy_delta": 0.0,
    "missing_trade_filtered": 11,
    "operating_margin_bucket_counts": {
      "improved_2_to_10pp": 22,
      "improved_gt_10pp": 82,
      "operating_margin_declined": 12
    },
    "operating_margin_notional_scalar": 1.05,
    "operating_margin_status_counts": {
      "ok": 104,
      "operating_margin_declined": 12
    },
    "operating_margin_support_pnl_delta_by_ticker": {
      "AMD": 266.08,
      "APP": 622.31,
      "AVGO": 126.27,
      "CRDO": 776.5,
      "MU": 291.72,
      "NFLX": 42.54,
      "PLTR": 488.11
    },
    "operating_margin_supported": 104,
    "operating_margin_supported_ticker_counts": {
      "AMD": 11,
      "APP": 18,
      "AVGO": 3,
      "CRDO": 30,
      "MU": 15,
      "NFLX": 2,
      "PLTR": 25
    },
    "rule_version": "fundamental_growth_rs_operating_margin_durability_support_v1",
    "same_ticker_core_overlap_filtered": 4,
    "selected_ticker_counts": {
      "AMD": 11,
      "APP": 18,
      "AVGO": 3,
      "COIN": 11,
      "CRDO": 30,
      "MU": 15,
      "NFLX": 2,
      "NVDA": 1,
      "PLTR": 25
    },
    "selected_trades": 116,
    "selected_unique_tickers": 9,
    "ticker_profit_cap_scaled": 33
  },
  "old_thin": {
    "both_governor_scalars_applied": 3,
    "daily_top1_filtered": 221,
    "filing_recency_supported": 69,
    "filtered_candidates": 238,
    "final_closed_pnl": 31529.02,
    "global_drawdown_scaled": 21,
    "input_candidates": 359,
    "low_liability_supported": 33,
    "low_volume_supported": 64,
    "max_closed_drawdown_seen_usd": 12265.51,
    "min_operating_margin_yoy_delta": 0.0,
    "missing_trade_filtered": 12,
    "operating_margin_bucket_counts": {
      "improved_2_to_10pp": 36,
      "improved_gt_10pp": 70,
      "operating_margin_declined": 13,
      "stable_0_to_2pp": 2
    },
    "operating_margin_notional_scalar": 1.05,
    "operating_margin_status_counts": {
      "ok": 108,
      "operating_margin_declined": 13
    },
    "operating_margin_support_pnl_delta_by_ticker": {
      "APP": 1182.13,
      "COIN": 156.46,
      "ISRG": -53.09,
      "META": -149.17,
      "MU": -17.81,
      "NFLX": -29.06,
      "NOW": 6.74,
      "PLTR": 650.12,
      "RTX": -2.4
    },
    "operating_margin_supported": 108,
    "operating_margin_supported_ticker_counts": {
      "APP": 50,
      "COIN": 1,
      "ISRG": 2,
      "META": 3,
      "MU": 1,
      "NFLX": 7,
      "NOW": 3,
      "PLTR": 27,
      "RTX": 14
    },
    "rule_version": "fundamental_growth_rs_operating_margin_durability_support_v1",
    "same_ticker_core_overlap_filtered": 5,
    "selected_ticker_counts": {
      "APP": 50,
      "AVGO": 13,
      "COIN": 1,
      "ISRG": 2,
      "META": 3,
      "MU": 1,
      "NFLX": 7,
      "NOW": 3,
      "PLTR": 27,
      "RTX": 14
    },
    "selected_trades": 121,
    "selected_unique_tickers": 10,
    "ticker_profit_cap_scaled": 55
  }
}
```

## Current Accepted Baseline Comparison

```json
{
  "aggregate_delta_after_vs_accepted_low_liability": {
    "expected_value_score_delta_sum": -0.5849,
    "max_drawdown_pct_delta_max": 0.0081,
    "total_pnl_delta_sum": -11020.51
  },
  "available": true,
  "by_window_delta_after_vs_accepted_low_liability": {
    "late_strong": {
      "expected_value_score_delta": 0.0896,
      "max_drawdown_pct_delta": -0.0003,
      "total_pnl_delta": 1137.38
    },
    "mid_weak": {
      "expected_value_score_delta": 0.1658,
      "max_drawdown_pct_delta": -0.0003,
      "total_pnl_delta": 1863.6
    },
    "old_thin": {
      "expected_value_score_delta": -0.8403,
      "max_drawdown_pct_delta": 0.0081,
      "total_pnl_delta": -14021.49
    }
  },
  "reference_decision": "accepted_candidate_fundamental_growth_rs_low_liability_support",
  "reference_experiment_id": "exp-20260528-017"
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "core_gate4_passed": true,
  "current_accepted_stack_comparison_passed": false,
  "current_accepted_stack_failed_checks": [
    "aggregate_ev_not_above_current_accepted_exp017",
    "aggregate_pnl_not_above_current_accepted_exp017",
    "window_ev_regressed_vs_current_accepted_exp017",
    "window_pnl_regressed_vs_current_accepted_exp017"
  ],
  "max_drawdown_worse": 0.0024,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.310582,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.220347,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 336,
  "target_trade_count_min": 30,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 3,
  "windows_ev_regressed": 0,
  "windows_pnl_regressed": 0
}
```

## Production Impact

If accepted, this remains shared default-off paper only. Live/default orders, core universe, core ranking, sizing, exits, LLM/news, and trade-enabled behavior remain unchanged.

No JavaScript was used.
