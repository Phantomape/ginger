# exp-20260528-020 Fundamental Growth + RS Dual-Growth Support

Decision: `rejected_fundamental_growth_rs_dual_growth_support`.

Single variable: apply a 1.05x paper-notional support scalar to already selected governed Companyfacts+RS paper candidates whose filed-date-safe revenue-growth and EPS-growth checks both pass.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Dual-growth supported |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 7.8425 | +2.6797 | $117,072.92 | $144,426.23 | $+27,353.31 | -0.0102 | 99 | 67 |
| mid_weak | 2.1402 | 6.1343 | +3.9941 | $78,110.11 | $134,820.18 | $+56,710.07 | -0.0209 | 116 | 56 |
| old_thin | 0.5911 | 1.8368 | +1.2457 | $39,667.96 | $70,922.48 | $+31,254.52 | +0.0017 | 121 | 80 |

## Aggregate

- EV delta: `7.9195` (`1.003218`)
- PnL delta: `$115317.9` (`0.491026`)
- target trades: `336`
- max drawdown drift: `0.0017`
- max single positive share: `0.305367`
- positive PnL HHI: `0.219023`

## Dual-Growth Audit

```json
{
  "late_strong": {
    "daily_top1_filtered": 127,
    "dual_growth_notional_scalar": 1.05,
    "dual_growth_status_counts": {
      "dual_growth_pass": 67,
      "missing_or_single_growth_pass": 32
    },
    "dual_growth_support_pnl_delta_by_ticker": {
      "AMD": 421.89,
      "MU": 1246.98
    },
    "dual_growth_supported": 67,
    "dual_growth_supported_ticker_counts": {
      "AMD": 4,
      "MU": 63
    },
    "filing_recency_supported": 67,
    "filtered_candidates": 161,
    "final_closed_pnl": 27353.31,
    "input_candidates": 260,
    "low_liability_supported": 81,
    "low_volume_supported": 38,
    "max_closed_drawdown_seen_usd": 7009.8,
    "missing_trade_filtered": 31,
    "rule_version": "fundamental_growth_rs_dual_growth_support_v1",
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
    "dual_growth_notional_scalar": 1.05,
    "dual_growth_status_counts": {
      "dual_growth_pass": 56,
      "missing_or_single_growth_pass": 60
    },
    "dual_growth_support_pnl_delta_by_ticker": {
      "AMD": 266.08,
      "APP": -245.05,
      "MU": 291.72,
      "PLTR": 488.11
    },
    "dual_growth_supported": 56,
    "dual_growth_supported_ticker_counts": {
      "AMD": 11,
      "APP": 5,
      "MU": 15,
      "PLTR": 25
    },
    "filing_recency_supported": 84,
    "filtered_candidates": 283,
    "final_closed_pnl": 56710.07,
    "input_candidates": 399,
    "low_liability_supported": 61,
    "low_volume_supported": 54,
    "max_closed_drawdown_seen_usd": 4571.42,
    "missing_trade_filtered": 11,
    "rule_version": "fundamental_growth_rs_dual_growth_support_v1",
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
    "dual_growth_notional_scalar": 1.05,
    "dual_growth_status_counts": {
      "dual_growth_pass": 80,
      "missing_or_single_growth_pass": 41
    },
    "dual_growth_support_pnl_delta_by_ticker": {
      "APP": 1182.13,
      "NOW": 6.74,
      "PLTR": 650.12
    },
    "dual_growth_supported": 80,
    "dual_growth_supported_ticker_counts": {
      "APP": 50,
      "NOW": 3,
      "PLTR": 27
    },
    "filing_recency_supported": 69,
    "filtered_candidates": 238,
    "final_closed_pnl": 31254.52,
    "global_drawdown_scaled": 20,
    "input_candidates": 359,
    "low_liability_supported": 33,
    "low_volume_supported": 64,
    "max_closed_drawdown_seen_usd": 12381.25,
    "missing_trade_filtered": 12,
    "rule_version": "fundamental_growth_rs_dual_growth_support_v1",
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
    "expected_value_score_delta_sum": -0.6224,
    "max_drawdown_pct_delta_max": 0.0074,
    "total_pnl_delta_sum": -11826.25
  },
  "available": true,
  "by_window_delta_after_vs_accepted_low_liability": {
    "late_strong": {
      "expected_value_score_delta": 0.162,
      "max_drawdown_pct_delta": -0.0004,
      "total_pnl_delta": 1668.86
    },
    "mid_weak": {
      "expected_value_score_delta": 0.0632,
      "max_drawdown_pct_delta": 0.0008,
      "total_pnl_delta": 800.88
    },
    "old_thin": {
      "expected_value_score_delta": -0.8476,
      "max_drawdown_pct_delta": 0.0074,
      "total_pnl_delta": -14295.99
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
    "max_single_positive_pnl_share": 0.305367,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.219023,
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
