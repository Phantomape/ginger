# exp-20260609-006 Fundamental Growth RS Quality-Gated Top-1 Replacement

Decision: `rejected_fundamental_growth_rs_quality_gated_top1_replacement`.

Single decision hypothesis: prefilter the accepted Fundamental Growth RS candidate rows to candidates passing both filed-date-safe filing recency and low-liability gates before the existing top-1/day selector.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Quality candidates | Replacement days |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.0858 | -1.0770 | $117,072.92 | $106,679.54 | $-10,393.38 | 82 | 118 | 24 |
| mid_weak | 2.1402 | 3.7143 | +1.5741 | $78,110.11 | $102,041.40 | $+23,931.29 | 86 | 129 | 54 |
| old_thin | 0.5911 | 1.9207 | +1.3296 | $39,667.96 | $74,156.24 | $+34,488.28 | 63 | 85 | 46 |

## Aggregate

- EV delta vs core baseline: `1.8267` (`0.231401`)
- PnL delta vs core baseline: `$48026.19` (`0.204496`)
- target trades: `231`
- max drawdown drift: `0.0038`
- max single positive share: `0.888934`
- positive PnL HHI: `0.802539`

## Accepted Comparator

```json
{
  "aggregate_delta_after_vs_accepted_low_liability": {
    "expected_value_score_delta_sum": -6.7152,
    "max_drawdown_pct_delta_max": -0.0087,
    "total_pnl_delta_sum": -79117.96
  },
  "available": true,
  "by_window_delta_after_vs_accepted_low_liability": {
    "late_strong": {
      "expected_value_score_delta": -3.5947,
      "max_drawdown_pct_delta": 0.0136,
      "total_pnl_delta": -36077.83
    },
    "mid_weak": {
      "expected_value_score_delta": -2.3568,
      "max_drawdown_pct_delta": -0.0045,
      "total_pnl_delta": -31977.9
    },
    "old_thin": {
      "expected_value_score_delta": -0.7637,
      "max_drawdown_pct_delta": -0.0116,
      "total_pnl_delta": -11062.23
    }
  },
  "reference_decision": "accepted_candidate_fundamental_growth_rs_low_liability_support",
  "reference_experiment_id": "exp-20260528-017"
}
```

## Quality Selection Audit

```json
{
  "late_strong": {
    "downstream_filtered_candidates": 36,
    "filing_recency_passed_candidates": 185,
    "input_candidates": 260,
    "low_liability_passed_candidates": 146,
    "missing_both_quality_gates": 47,
    "missing_filing_recency_gate": 28,
    "missing_low_liability_gate": 67,
    "no_quality_candidate_days": 20,
    "quality_candidate_days": 89,
    "quality_filtered_candidates": 142,
    "quality_passed_candidates": 118,
    "replacement_day_count": 24,
    "rule_version": "fundamental_growth_rs_quality_gated_top1_replacement_v1",
    "selected_ticker_counts": {
      "CRDO": 14,
      "GOOG": 24,
      "MU": 43,
      "PLTR": 1
    },
    "selected_trades": 82,
    "selected_unique_tickers": 4
  },
  "mid_weak": {
    "downstream_filtered_candidates": 43,
    "filing_recency_passed_candidates": 331,
    "input_candidates": 399,
    "low_liability_passed_candidates": 192,
    "missing_both_quality_gates": 5,
    "missing_filing_recency_gate": 63,
    "missing_low_liability_gate": 202,
    "no_quality_candidate_days": 35,
    "quality_candidate_days": 88,
    "quality_filtered_candidates": 270,
    "quality_passed_candidates": 129,
    "replacement_day_count": 54,
    "rule_version": "fundamental_growth_rs_quality_gated_top1_replacement_v1",
    "selected_ticker_counts": {
      "CRDO": 19,
      "META": 1,
      "MU": 3,
      "NVDA": 9,
      "PLTR": 54
    },
    "selected_trades": 86,
    "selected_unique_tickers": 5
  },
  "old_thin": {
    "downstream_filtered_candidates": 22,
    "filing_recency_passed_candidates": 247,
    "input_candidates": 359,
    "low_liability_passed_candidates": 119,
    "missing_both_quality_gates": 78,
    "missing_filing_recency_gate": 34,
    "missing_low_liability_gate": 162,
    "no_quality_candidate_days": 64,
    "quality_candidate_days": 63,
    "quality_filtered_candidates": 274,
    "quality_passed_candidates": 85,
    "replacement_day_count": 46,
    "rule_version": "fundamental_growth_rs_quality_gated_top1_replacement_v1",
    "selected_ticker_counts": {
      "ISRG": 3,
      "MU": 2,
      "NVDA": 3,
      "PLTR": 55
    },
    "selected_trades": 63,
    "selected_unique_tickers": 4
  }
}
```

## Gate 4

```json
{
  "accepted_low_liability_comparison_passed": false,
  "accepted_low_liability_failed_checks": [
    "aggregate_ev_not_above_accepted_exp017",
    "aggregate_pnl_not_above_accepted_exp017",
    "window_ev_regressed_vs_accepted_exp017",
    "window_pnl_regressed_vs_accepted_exp017"
  ],
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "core_gate4_passed": false,
  "decision": "rejected_fundamental_growth_rs_quality_gated_top1_replacement",
  "max_drawdown_worse": 0.0038,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.888934,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.802539,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 231,
  "target_trade_count_min": 30,
  "target_window_count_min": 3,
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

## Reflection

The quality-gated replacement selector did not clear Gate 4. The likely mechanism is that filing recency and low liabilities are useful as small support scalars but too blunt as a hard replacement selector, removing top-ranked winners or making the source too sparse.

No JavaScript was used.
