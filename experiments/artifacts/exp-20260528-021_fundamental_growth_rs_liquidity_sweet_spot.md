# exp-20260528-021 Fundamental Growth + RS Liquidity Sweet-Spot Support

Decision: `rejected_fundamental_growth_rs_liquidity_sweet_spot_support`.

Single variable: apply a 1.05x paper-notional support scalar to already selected governed Companyfacts+RS paper candidates whose 20-day average dollar volume is >= $250M and < $10B.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Liquidity supported |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 7.7942 | +2.6314 | $117,072.92 | $144,074.52 | $+27,001.60 | -0.0102 | 99 | 71 |
| mid_weak | 2.1402 | 6.2293 | +4.0891 | $78,110.11 | $136,014.41 | $+57,904.30 | -0.0215 | 116 | 93 |
| old_thin | 0.5911 | 1.8443 | +1.2532 | $39,667.96 | $71,205.85 | $+31,537.89 | +0.0017 | 121 | 112 |

## Aggregate

- EV delta: `7.9737` (`1.010083`)
- PnL delta: `$116443.79` (`0.49582`)
- target trades: `336`
- max drawdown drift: `0.0017`
- max single positive share: `0.30979`
- positive PnL HHI: `0.218527`

## Liquidity Audit

```json
{
  "late_strong": {
    "daily_top1_filtered": 127,
    "filing_recency_supported": 67,
    "filtered_candidates": 161,
    "final_closed_pnl": 27001.6,
    "input_candidates": 260,
    "liquidity_bucket_counts": {
      "mega_gte_10b": 28,
      "sweet_spot_250m_to_10b": 71
    },
    "liquidity_sweet_spot_max_avg_dollar_volume_20": 10000000000.0,
    "liquidity_sweet_spot_min_avg_dollar_volume_20": 250000000.0,
    "liquidity_sweet_spot_notional_scalar": 1.05,
    "liquidity_sweet_spot_support_pnl_delta_by_ticker": {
      "AMD": 421.89,
      "APP": 11.92,
      "CRDO": -551.48,
      "GOOG": 146.81,
      "MU": 1279.97,
      "RTX": 8.1
    },
    "liquidity_sweet_spot_supported": 71,
    "liquidity_sweet_spot_supported_ticker_counts": {
      "AMD": 4,
      "APP": 5,
      "CRDO": 4,
      "GOOG": 14,
      "MU": 35,
      "RTX": 9
    },
    "low_liability_supported": 81,
    "low_volume_supported": 38,
    "max_closed_drawdown_seen_usd": 7311.96,
    "missing_trade_filtered": 31,
    "rule_version": "fundamental_growth_rs_liquidity_sweet_spot_support_v1",
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
    "final_closed_pnl": 57904.3,
    "input_candidates": 399,
    "liquidity_bucket_counts": {
      "below_250m": 4,
      "mega_gte_10b": 19,
      "sweet_spot_250m_to_10b": 93
    },
    "liquidity_sweet_spot_max_avg_dollar_volume_20": 10000000000.0,
    "liquidity_sweet_spot_min_avg_dollar_volume_20": 250000000.0,
    "liquidity_sweet_spot_notional_scalar": 1.05,
    "liquidity_sweet_spot_support_pnl_delta_by_ticker": {
      "AMD": 266.08,
      "APP": 622.31,
      "AVGO": 126.27,
      "COIN": 141.24,
      "CRDO": 425.59,
      "MU": 291.72,
      "NFLX": 42.54,
      "PLTR": 79.38
    },
    "liquidity_sweet_spot_supported": 93,
    "liquidity_sweet_spot_supported_ticker_counts": {
      "AMD": 11,
      "APP": 18,
      "AVGO": 3,
      "COIN": 11,
      "CRDO": 26,
      "MU": 15,
      "NFLX": 2,
      "PLTR": 7
    },
    "low_liability_supported": 61,
    "low_volume_supported": 54,
    "max_closed_drawdown_seen_usd": 4800.0,
    "missing_trade_filtered": 11,
    "rule_version": "fundamental_growth_rs_liquidity_sweet_spot_support_v1",
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
    "filing_recency_supported": 69,
    "filtered_candidates": 238,
    "final_closed_pnl": 31537.89,
    "global_drawdown_scaled": 21,
    "input_candidates": 359,
    "liquidity_bucket_counts": {
      "mega_gte_10b": 9,
      "sweet_spot_250m_to_10b": 112
    },
    "liquidity_sweet_spot_max_avg_dollar_volume_20": 10000000000.0,
    "liquidity_sweet_spot_min_avg_dollar_volume_20": 250000000.0,
    "liquidity_sweet_spot_notional_scalar": 1.05,
    "liquidity_sweet_spot_support_pnl_delta_by_ticker": {
      "APP": 1182.13,
      "AVGO": -143.01,
      "COIN": 156.46,
      "ISRG": -53.09,
      "MU": -17.81,
      "NFLX": -29.06,
      "NOW": 6.74,
      "PLTR": 652.84,
      "RTX": -2.4
    },
    "liquidity_sweet_spot_supported": 112,
    "liquidity_sweet_spot_supported_ticker_counts": {
      "APP": 50,
      "AVGO": 8,
      "COIN": 1,
      "ISRG": 2,
      "MU": 1,
      "NFLX": 7,
      "NOW": 3,
      "PLTR": 26,
      "RTX": 14
    },
    "low_liability_supported": 33,
    "low_volume_supported": 64,
    "max_closed_drawdown_seen_usd": 12256.64,
    "missing_trade_filtered": 12,
    "rule_version": "fundamental_growth_rs_liquidity_sweet_spot_support_v1",
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
    "expected_value_score_delta_sum": -0.5682,
    "max_drawdown_pct_delta_max": 0.0074,
    "total_pnl_delta_sum": -10700.36
  },
  "available": true,
  "by_window_delta_after_vs_accepted_low_liability": {
    "late_strong": {
      "expected_value_score_delta": 0.1137,
      "max_drawdown_pct_delta": -0.0004,
      "total_pnl_delta": 1317.15
    },
    "mid_weak": {
      "expected_value_score_delta": 0.1582,
      "max_drawdown_pct_delta": 0.0002,
      "total_pnl_delta": 1995.11
    },
    "old_thin": {
      "expected_value_score_delta": -0.8401,
      "max_drawdown_pct_delta": 0.0074,
      "total_pnl_delta": -14012.62
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
  "max_drawdown_worse": 0.0017,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.30979,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.218527,
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
