# exp-20260529-026 SEC Fact-Improvement Neutral-Tone Top-Up

Decision: `rejected_sec_fact_improvement_neutral_tone_topup`.

## Hypothesis

SEC financial-report T+1 rows with explicit improving facts but neutral or mixed tone may be underreacted continuation candidates. A bounded paper-notional scalar tests that semantic quality bucket without changing eligibility, exits, live orders, or LLM authority.

## Trial Accounting

- trial_family: `sec_fact_tone_gap_semantic_allocation`
- changed_variable: `sec_fact_improvement_neutral_tone_notional_scalar`
- prior_trial_count: `5`
- multiple_testing_risk_bucket: `moderate`
- new_evidence_type: `previously_untested_production_visible_fact_tone_bucket`

## Best Variant

- best_variant: `fact_improvement_neutral_tone_scalar_0_75`
- target_scalar: `0.75`
- EV delta: `0.0`
- PnL delta: `$0.0`
- gate_passed: `False`

## Three-Window Deltas

| Window | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|
| late_strong | +0.0000 | $+0.00 | +0.0000 |
| mid_weak | +0.0000 | $+0.00 | +0.0000 |
| old_thin | +0.0000 | $+0.00 | +0.0000 |

## Gate

```json
{
  "aggregate_delta": {
    "expected_value_score_sum_delta": 0.0,
    "expected_value_score_sum_delta_pct": 0.0,
    "max_drawdown_pct_max_delta": 0.0,
    "max_drawdown_pct_max_delta_pct": 0.0,
    "min_survival_rate_delta": 0.0,
    "min_survival_rate_delta_pct": 0.0,
    "sleeve_closed_trade_count_sum_delta": 0.0,
    "sleeve_closed_trade_count_sum_delta_pct": 0.0,
    "sleeve_total_pnl_sum_delta": 0.0,
    "sleeve_total_pnl_sum_delta_pct": 0.0,
    "total_pnl_sum_delta": 0.0,
    "total_pnl_sum_delta_pct": 0.0,
    "trade_count_sum_delta": 0.0,
    "trade_count_sum_delta_pct": 0.0
  },
  "by_window": {
    "late_strong": {
      "expected_value_score": 0.0,
      "max_drawdown_pct": 0.0,
      "sharpe_daily": 0.0,
      "total_pnl": 0.0
    },
    "mid_weak": {
      "expected_value_score": 0.0,
      "max_drawdown_pct": 0.0,
      "sharpe_daily": 0.0,
      "total_pnl": 0.0
    },
    "old_thin": {
      "expected_value_score": 0.0,
      "max_drawdown_pct": 0.0,
      "sharpe_daily": 0.0,
      "total_pnl": 0.0
    }
  },
  "checks": {
    "adjusted_trade_sample": false,
    "adjusted_window_coverage": false,
    "drawdown_worse_guard": true,
    "ev_improved_window_coverage": false,
    "hhi_concentration_cap": true,
    "no_ev_regressed_windows": true,
    "positive_aggregate_ev": false,
    "positive_aggregate_pnl": false,
    "single_ticker_positive_share_cap": true,
    "top5_contribution_cap": true
  },
  "metrics": {
    "adjusted_trade_count": 0,
    "adjusted_windows": [],
    "max_drawdown_worse": 0.0,
    "max_single_positive_pnl_share": null,
    "pnl_hhi_concentration": null,
    "pnl_top_5_contribution_pct": null,
    "windows_ev_improved": 0,
    "windows_ev_regressed": 0
  },
  "passed": false,
  "rules": {
    "metric_gate": "aggregate EV/PnL positive, at least two EV-improved windows, zero EV-regressed windows, and max drawdown worsening <= 0.5pp",
    "sample_guard": {
      "min_adjusted_trades": 6,
      "min_adjusted_windows": 2
    },
    "tail_guard": {
      "max_hhi_concentration": 0.35,
      "max_single_ticker_positive_share": 0.5,
      "max_top5_contribution": 0.6
    }
  }
}
```

## Target Coverage

```json
{
  "bucket_counts": {
    "fact_improvement_positive_tone": 7,
    "fact_negative_or_guidance_cut": 10,
    "fact_tone_divergence": 18,
    "unclassified_insufficient_evidence": 73
  },
  "by_window": {
    "late_strong": {
      "bucket_counts": {
        "fact_improvement_positive_tone": 2,
        "fact_negative_or_guidance_cut": 1,
        "fact_tone_divergence": 7,
        "unclassified_insufficient_evidence": 29
      },
      "candidate_rows": 39,
      "target_accessions": [],
      "target_rows": 0,
      "target_tickers": []
    },
    "mid_weak": {
      "bucket_counts": {
        "fact_improvement_positive_tone": 3,
        "fact_negative_or_guidance_cut": 4,
        "fact_tone_divergence": 5,
        "unclassified_insufficient_evidence": 17
      },
      "candidate_rows": 29,
      "target_accessions": [],
      "target_rows": 0,
      "target_tickers": []
    },
    "old_thin": {
      "bucket_counts": {
        "fact_improvement_positive_tone": 2,
        "fact_negative_or_guidance_cut": 5,
        "fact_tone_divergence": 6,
        "unclassified_insufficient_evidence": 27
      },
      "candidate_rows": 40,
      "target_accessions": [],
      "target_rows": 0,
      "target_tickers": []
    }
  },
  "target_bucket": "fact_improvement_neutral_tone",
  "target_candidate_rows": 0,
  "target_share": 0.0,
  "target_tickers": {},
  "total_candidate_rows": 108
}
```

## Production Impact

No shared policy, production adapter, live/default order path, or LLM boundary changed. This is an offline default-off paper-sleeve scout.

No JavaScript was used.
