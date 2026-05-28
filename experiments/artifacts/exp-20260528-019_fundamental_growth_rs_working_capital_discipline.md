# exp-20260528-019 Fundamental Growth + RS Working-Capital Discipline

Decision: `rejected_fundamental_growth_rs_working_capital_discipline_support`.

Single variable: apply a 1.05x paper-notional support scalar to already selected governed Companyfacts+RS paper candidates whose PIT receivables/revenue and inventory/revenue ratios do not deteriorate by more than 5 percentage points versus the prior-year same quarter.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Working-capital supported |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 7.6805 | +2.5177 | $117,072.92 | $142,757.37 | $+25,684.45 | -0.0098 | 99 | 0 |
| mid_weak | 2.1402 | 6.0711 | +3.9309 | $78,110.11 | $134,019.30 | $+55,909.19 | -0.0217 | 116 | 0 |
| old_thin | 0.5911 | 2.6844 | +2.0933 | $39,667.96 | $85,218.47 | $+45,550.51 | -0.0057 | 121 | 0 |

## Aggregate

- EV delta: `8.5419` (`1.082061`)
- PnL delta: `$127144.15` (`0.541382`)
- target trades: `336`
- max drawdown drift: `-0.0057`
- max single positive share: `0.391926`
- positive PnL HHI: `0.248733`

## Working-Capital Audit

```json
{
  "late_strong": {
    "daily_top1_filtered": 127,
    "filing_recency_supported": 67,
    "filtered_candidates": 161,
    "final_closed_pnl": 25684.45,
    "input_candidates": 260,
    "low_liability_supported": 81,
    "low_volume_supported": 38,
    "max_closed_drawdown_seen_usd": 6995.17,
    "max_working_capital_ratio_deterioration": 0.05,
    "missing_trade_filtered": 31,
    "rule_version": "fundamental_growth_rs_working_capital_discipline_support_v1",
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
    "ticker_profit_cap_scaled": 34,
    "working_capital_bucket_counts": {
      "missing_receivables_inventory_pairs": 99
    },
    "working_capital_notional_scalar": 1.05,
    "working_capital_status_counts": {
      "missing_receivables_inventory_pairs": 99
    },
    "working_capital_support_pnl_delta_by_ticker": {},
    "working_capital_supported": 0,
    "working_capital_supported_ticker_counts": {}
  },
  "mid_weak": {
    "daily_top1_filtered": 268,
    "filing_recency_supported": 84,
    "filtered_candidates": 283,
    "final_closed_pnl": 55909.19,
    "input_candidates": 399,
    "low_liability_supported": 61,
    "low_volume_supported": 54,
    "max_closed_drawdown_seen_usd": 4571.42,
    "max_working_capital_ratio_deterioration": 0.05,
    "missing_trade_filtered": 11,
    "rule_version": "fundamental_growth_rs_working_capital_discipline_support_v1",
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
    "ticker_profit_cap_scaled": 32,
    "working_capital_bucket_counts": {
      "missing_receivables_inventory_pairs": 116
    },
    "working_capital_notional_scalar": 1.05,
    "working_capital_status_counts": {
      "missing_receivables_inventory_pairs": 116
    },
    "working_capital_support_pnl_delta_by_ticker": {},
    "working_capital_supported": 0,
    "working_capital_supported_ticker_counts": {}
  },
  "old_thin": {
    "both_governor_scalars_applied": 3,
    "daily_top1_filtered": 221,
    "filing_recency_supported": 69,
    "filtered_candidates": 238,
    "final_closed_pnl": 45550.51,
    "global_drawdown_scaled": 20,
    "input_candidates": 359,
    "low_liability_supported": 33,
    "low_volume_supported": 64,
    "max_closed_drawdown_seen_usd": 12293.52,
    "max_working_capital_ratio_deterioration": 0.05,
    "missing_trade_filtered": 12,
    "rule_version": "fundamental_growth_rs_working_capital_discipline_support_v1",
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
    "ticker_profit_cap_scaled": 53,
    "working_capital_bucket_counts": {
      "missing_receivables_inventory_pairs": 121
    },
    "working_capital_notional_scalar": 1.05,
    "working_capital_status_counts": {
      "missing_receivables_inventory_pairs": 121
    },
    "working_capital_support_pnl_delta_by_ticker": {},
    "working_capital_supported": 0,
    "working_capital_supported_ticker_counts": {}
  }
}
```

## Current Accepted Baseline Comparison

```json
{
  "aggregate_delta_after_vs_accepted_low_liability": {
    "expected_value_score_delta_sum": 0.0,
    "max_drawdown_pct_delta_max": 0.0,
    "total_pnl_delta_sum": 0.0
  },
  "available": true,
  "by_window_delta_after_vs_accepted_low_liability": {
    "late_strong": {
      "expected_value_score_delta": 0.0,
      "max_drawdown_pct_delta": 0.0,
      "total_pnl_delta": 0.0
    },
    "mid_weak": {
      "expected_value_score_delta": 0.0,
      "max_drawdown_pct_delta": 0.0,
      "total_pnl_delta": 0.0
    },
    "old_thin": {
      "expected_value_score_delta": 0.0,
      "max_drawdown_pct_delta": 0.0,
      "total_pnl_delta": 0.0
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
    "aggregate_pnl_not_above_current_accepted_exp017"
  ],
  "max_drawdown_worse": -0.0057,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.391926,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.248733,
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
