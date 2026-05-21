# exp-20260520-034 historical_forward_outcome_backfill_v1

Decision: `blocked_historical_bucket_backtest_missing_phrase_provenance`.

## Hypothesis

The SEC financial-report queue has positive frozen forward drift, but fact-tone gap itself cannot be promoted until historical rows carry evidence spans.

## Trial Accounting

- mechanism_family: `sec_earnings_semantic_field`
- trial_family: `sec_fact_tone_gap_bucket`
- changed_variable: `fact_tone_gap_bucket`
- prior_trial_count: `33`
- multiple_testing_risk_bucket: `minimal`

## Metric Evidence

```json
{
  "candidate_count": 164,
  "deduped_10d_pnl_proxy": {
    "avg": 264.709299,
    "count": 157,
    "max": 7469.8,
    "min": -3031.92,
    "sum": 41559.36,
    "win_rate": 0.5414
  },
  "deduped_20d_pnl_proxy": {
    "avg": 402.216731,
    "count": 156,
    "max": 6607.61,
    "min": -2909.72,
    "sum": 62745.81,
    "win_rate": 0.5705
  },
  "deduped_candidate_rows": 164,
  "event_family_counts": [
    [
      "earnings_8k",
      90
    ],
    [
      "periodic_report",
      74
    ]
  ],
  "evidence_type": "frozen_forward_outcome_plus_prior_notional_replay",
  "fact_tone_gap_bucket_counts_on_historical_rows": {
    "unclassified_insufficient_evidence": 164
  },
  "fact_tone_gap_historical_limitation": "The frozen SEC forward rows do not carry language_bucket or phrase-hit provenance, so fact_tone_gap buckets are not yet backtestable by bucket.",
  "forward_source_artifact": "data/experiments/exp-20260511-100/exp_20260511_100_sec_financial_report_positive_t1_forward_outcome_refresh.json",
  "forward_source_experiment": "exp-20260511-100",
  "prior_scalar_decision": "rejected_sec_positive_language_low_reaction_notional",
  "prior_scalar_delta": {
    "aggregate": {
      "expected_value_score_sum_delta": 0.049637,
      "expected_value_score_sum_delta_pct": 0.004184,
      "max_drawdown_pct_max_delta": -0.000627,
      "max_drawdown_pct_max_delta_pct": -0.00536,
      "min_survival_rate_delta": 0.0,
      "min_survival_rate_delta_pct": 0.0,
      "sleeve_closed_trade_count_sum_delta": 0.0,
      "sleeve_closed_trade_count_sum_delta_pct": 0.0,
      "sleeve_total_pnl_sum_delta": 1315.95,
      "sleeve_total_pnl_sum_delta_pct": 0.015067,
      "total_pnl_sum_delta": 1315.95,
      "total_pnl_sum_delta_pct": 0.004059,
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
        "expected_value_score": 0.049637,
        "max_drawdown_pct": -0.000627,
        "sharpe_daily": 0.024912,
        "total_pnl": 1315.95
      }
    }
  },
  "prior_scalar_rejection_reason": "No positive-language low-reaction scalar cleared the three-window, tail-aware paper-sleeve gate.",
  "prior_scalar_source_artifact": "data/experiments/exp-20260520-008/exp_20260520_008_sec_positive_language_low_reaction_notional.json",
  "prior_scalar_source_experiment": "exp-20260520-008",
  "refreshed_forward_returns": {
    "refresh_fwd_10d_return": {
      "avg": 0.026471,
      "count": 157,
      "median": 0.014044,
      "p10": -0.077069,
      "p25": -0.029543,
      "p75": 0.061146,
      "p90": 0.149836,
      "win_rate": 0.5414
    },
    "refresh_fwd_1d_return": {
      "avg": 0.008333,
      "count": 159,
      "median": 0.00423,
      "p10": -0.015527,
      "p25": -0.006725,
      "p75": 0.020896,
      "p90": 0.044918,
      "win_rate": 0.5975
    },
    "refresh_fwd_20d_return": {
      "avg": 0.040222,
      "count": 156,
      "median": 0.013781,
      "p10": -0.09808,
      "p25": -0.048896,
      "p75": 0.07834,
      "p90": 0.228395,
      "win_rate": 0.5705
    },
    "refresh_fwd_5d_return": {
      "avg": 0.019428,
      "count": 158,
      "median": 0.013022,
      "p10": -0.056854,
      "p25": -0.025569,
      "p75": 0.053171,
      "p90": 0.088771,
      "win_rate": 0.5759
    }
  },
  "refreshed_pnl_proxy": {
    "refresh_fwd_10d_pnl_proxy": {
      "avg": 264.709299,
      "count": 157,
      "median": 140.44,
      "p10": -770.69,
      "p25": -295.43,
      "p75": 611.46,
      "p90": 1498.36,
      "win_rate": 0.5414
    },
    "refresh_fwd_1d_pnl_proxy": {
      "avg": 83.327987,
      "count": 159,
      "median": 42.3,
      "p10": -155.27,
      "p25": -67.25,
      "p75": 208.96,
      "p90": 449.18,
      "win_rate": 0.5975
    },
    "refresh_fwd_20d_pnl_proxy": {
      "avg": 402.216731,
      "count": 156,
      "median": 137.805,
      "p10": -980.8,
      "p25": -488.96,
      "p75": 783.4,
      "p90": 2283.95,
      "win_rate": 0.5705
    },
    "refresh_fwd_5d_pnl_proxy": {
      "avg": 194.278924,
      "count": 158,
      "median": 130.225,
      "p10": -568.54,
      "p25": -255.69,
      "p75": 531.71,
      "p90": 887.71,
      "win_rate": 0.5759
    }
  },
  "unique_tickers": 32
}
```

## Next Evidence Needed

Persist language_bucket, phrase-hit counts, and evidence spans on SEC candidates, then rerun bucketed forward attribution.
