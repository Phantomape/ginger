# exp-20260528-016 Fundamental Growth + RS Filing-Recency Support

Decision: `accepted_candidate_fundamental_growth_rs_filing_recency_support`.

Single variable: apply a 1.05x paper-notional support scalar to already selected governed Companyfacts+RS paper candidates whose latest operating-income filing age is at most 90 calendar days.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Filing-recency supported |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 7.6091 | +2.4463 | $117,072.92 | $141,955.13 | $+24,882.21 | -0.0094 | 99 | 67 |
| mid_weak | 2.1402 | 5.9463 | +3.8061 | $78,110.11 | $132,731.80 | $+54,621.69 | -0.0205 | 116 | 84 |
| old_thin | 0.5911 | 2.6586 | +2.0675 | $39,667.96 | $84,671.19 | $+45,003.23 | -0.0063 | 121 | 69 |

## Aggregate

- EV delta: `8.3199` (`1.053939`)
- PnL delta: `$124507.13` (`0.530154`)
- target trades: `336`
- max drawdown drift: `-0.0063`
- max single positive share: `0.399969`
- positive PnL HHI: `0.251841`

## Filing-Recency Audit

```json
{
  "late_strong": {
    "daily_top1_filtered": 127,
    "filing_age_bucket_counts": {
      "fresh_0_45d": 40,
      "recent_46_90d": 27,
      "stale_91_180d": 32
    },
    "filing_recency_max_days": 90,
    "filing_recency_notional_scalar": 1.05,
    "filing_recency_support_pnl_delta_by_ticker": {
      "APP": 11.35,
      "CRDO": -500.21,
      "GOOG": 235.7,
      "MU": 867.72,
      "RTX": 88.78
    },
    "filing_recency_supported": 67,
    "filing_recency_supported_ticker_counts": {
      "APP": 5,
      "CRDO": 4,
      "GOOG": 12,
      "MU": 43,
      "RTX": 3
    },
    "filtered_candidates": 161,
    "final_closed_pnl": 24882.21,
    "input_candidates": 260,
    "low_volume_supported": 38,
    "max_closed_drawdown_seen_usd": 6743.13,
    "missing_trade_filtered": 31,
    "rule_version": "fundamental_growth_rs_filing_recency_support_v1",
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
    "filing_age_bucket_counts": {
      "fresh_0_45d": 38,
      "recent_46_90d": 46,
      "stale_91_180d": 31,
      "very_stale_gt180d": 1
    },
    "filing_recency_max_days": 90,
    "filing_recency_notional_scalar": 1.05,
    "filing_recency_support_pnl_delta_by_ticker": {
      "AMD": 253.41,
      "APP": 592.68,
      "AVGO": 120.26,
      "COIN": 134.52,
      "CRDO": 475.51,
      "MU": 107.97,
      "NFLX": 40.51,
      "NVDA": 2.89,
      "PLTR": 138.5
    },
    "filing_recency_supported": 84,
    "filing_recency_supported_ticker_counts": {
      "AMD": 11,
      "APP": 18,
      "AVGO": 3,
      "COIN": 11,
      "CRDO": 13,
      "MU": 8,
      "NFLX": 2,
      "NVDA": 1,
      "PLTR": 17
    },
    "filtered_candidates": 283,
    "final_closed_pnl": 54621.69,
    "input_candidates": 399,
    "low_volume_supported": 54,
    "max_closed_drawdown_seen_usd": 4571.42,
    "missing_trade_filtered": 11,
    "rule_version": "fundamental_growth_rs_filing_recency_support_v1",
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
    "ticker_profit_cap_scaled": 32
  },
  "old_thin": {
    "both_governor_scalars_applied": 3,
    "daily_top1_filtered": 221,
    "filing_age_bucket_counts": {
      "fresh_0_45d": 29,
      "recent_46_90d": 40,
      "stale_91_180d": 52
    },
    "filing_recency_max_days": 90,
    "filing_recency_notional_scalar": 1.05,
    "filing_recency_support_pnl_delta_by_ticker": {
      "APP": 1920.09,
      "COIN": 149.01,
      "ISRG": -23.81,
      "MU": -16.16,
      "NOW": 6.42,
      "PLTR": 627.3
    },
    "filing_recency_supported": 69,
    "filing_recency_supported_ticker_counts": {
      "APP": 47,
      "COIN": 1,
      "ISRG": 1,
      "MU": 1,
      "NOW": 3,
      "PLTR": 16
    },
    "filtered_candidates": 238,
    "final_closed_pnl": 45003.23,
    "global_drawdown_scaled": 19,
    "input_candidates": 359,
    "low_volume_supported": 64,
    "max_closed_drawdown_seen_usd": 12180.1,
    "missing_trade_filtered": 12,
    "rule_version": "fundamental_growth_rs_filing_recency_support_v1",
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
    "ticker_profit_cap_scaled": 53
  }
}
```

## Current Accepted Baseline Comparison

```json
{
  "aggregate_delta_after_vs_accepted_low_volume_participation": {
    "expected_value_score_delta_sum": 0.3643,
    "max_drawdown_pct_delta_max": -0.0013,
    "total_pnl_delta_sum": 5232.47
  },
  "available": true,
  "by_window_delta_after_vs_accepted_low_volume_participation": {
    "late_strong": {
      "expected_value_score_delta": 0.0664,
      "max_drawdown_pct_delta": -0.0003,
      "total_pnl_delta": 703.33
    },
    "mid_weak": {
      "expected_value_score_delta": 0.1488,
      "max_drawdown_pct_delta": 0.0,
      "total_pnl_delta": 1866.28
    },
    "old_thin": {
      "expected_value_score_delta": 0.1491,
      "max_drawdown_pct_delta": -0.0013,
      "total_pnl_delta": 2662.86
    }
  },
  "reference_decision": "accepted_candidate_fundamental_growth_rs_low_volume_participation_support",
  "reference_experiment_id": "exp-20260528-015"
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "core_gate4_passed": true,
  "current_accepted_stack_comparison_passed": true,
  "current_accepted_stack_failed_checks": [],
  "max_drawdown_worse": -0.0063,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": true,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.399969,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.251841,
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
