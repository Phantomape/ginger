# exp-20260525-033 VCP Candidate Dossier / Catalyst Quality

Decision: `observed_only_vcp_candidate_dossier_counter_signal`.

Single variable: `vcp_catalyst_quality_bucket_v1`, a read-only candidate dossier bucket for the unchanged exp-022 VCP sleeve.

## Exp-022 Replay Parity

- selected-trade parity passed: `True`
- aggregate EV delta diff: `0.0`
- aggregate PnL delta diff: `$0.0`
- replay EV delta vs core: `1.2493`
- replay PnL delta vs core: `$23409.56`

## Selected-Trade Bucket Attribution

| Bucket | Trades | Total PnL | Avg PnL | Win Rate | Tickers |
|---|---:|---:|---:|---:|---:|
| A_positive_catalyst_plus_volume_support | 3 | $1,713.94 | $571.31 | 1.0 | 1 |
| B_positive_catalyst_only | 3 | $1,011.03 | $337.01 | 0.333333 | 2 |
| C_volume_support_only | 40 | $8,865.76 | $221.64 | 0.625 | 22 |
| D_negative_or_warning_catalyst | 2 | $1,340.94 | $670.47 | 1.0 | 1 |
| E_ambiguous_prior_context | 7 | $1,534.28 | $219.18 | 0.571429 | 7 |
| F_no_prior_catalyst_or_support | 16 | $8,943.61 | $558.98 | 0.6875 | 11 |

## Quality Separation

```json
{
  "best_eligible_bucket": "F_no_prior_catalyst_or_support",
  "best_worst_avg_pnl_separation": 339.8,
  "overall_avg_pnl": 329.71,
  "useful_quality_separation": true,
  "worst_eligible_bucket": "E_ambiguous_prior_context"
}
```

## Candidate Bucket Audit

```json
{
  "late_strong": {
    "candidate_dates_after_gate": 5,
    "candidate_dates_before_gate": 15,
    "qqq_candidate_bucket_attribution": {
      "C_volume_support_only": {
        "avg_fwd_10d": -0.000446,
        "candidate_count": 2,
        "candidate_date_count": 2,
        "fwd_10d_sample": 1,
        "fwd_10d_win_rate": 0.0,
        "ticker_count": 2
      },
      "E_ambiguous_prior_context": {
        "avg_fwd_10d": 0.074318,
        "candidate_count": 1,
        "candidate_date_count": 1,
        "fwd_10d_sample": 1,
        "fwd_10d_win_rate": 1.0,
        "ticker_count": 1
      },
      "F_no_prior_catalyst_or_support": {
        "avg_fwd_10d": 0.017883,
        "candidate_count": 3,
        "candidate_date_count": 2,
        "fwd_10d_sample": 2,
        "fwd_10d_win_rate": 0.5,
        "ticker_count": 3
      }
    },
    "qqq_confirmed_candidates": 6,
    "raw_volatility_candidates": 22,
    "rejected_missing_market_context": 0,
    "rejected_qqq_not_leading_spy": 16
  },
  "mid_weak": {
    "candidate_dates_after_gate": 51,
    "candidate_dates_before_gate": 58,
    "qqq_candidate_bucket_attribution": {
      "B_positive_catalyst_only": {
        "avg_fwd_10d": -0.001633,
        "candidate_count": 2,
        "candidate_date_count": 2,
        "fwd_10d_sample": 2,
        "fwd_10d_win_rate": 0.5,
        "ticker_count": 1
      },
      "C_volume_support_only": {
        "avg_fwd_10d": 0.025831,
        "candidate_count": 153,
        "candidate_date_count": 44,
        "fwd_10d_sample": 153,
        "fwd_10d_win_rate": 0.686275,
        "ticker_count": 33
      },
      "D_negative_or_warning_catalyst": {
        "avg_fwd_10d": 0.060106,
        "candidate_count": 5,
        "candidate_date_count": 5,
        "fwd_10d_sample": 5,
        "fwd_10d_win_rate": 1.0,
        "ticker_count": 2
      },
      "E_ambiguous_prior_context": {
        "avg_fwd_10d": 0.051874,
        "candidate_count": 21,
        "candidate_date_count": 16,
        "fwd_10d_sample": 21,
        "fwd_10d_win_rate": 0.714286,
        "ticker_count": 13
      },
      "F_no_prior_catalyst_or_support": {
        "avg_fwd_10d": 0.054919,
        "candidate_count": 26,
        "candidate_date_count": 20,
        "fwd_10d_sample": 26,
        "fwd_10d_win_rate": 0.769231,
        "ticker_count": 16
      }
    },
    "qqq_confirmed_candidates": 207,
    "raw_volatility_candidates": 215,
    "rejected_missing_market_context": 0,
    "rejected_qqq_not_leading_spy": 8
  },
  "old_thin": {
    "candidate_dates_after_gate": 17,
    "candidate_dates_before_gate": 22,
    "qqq_candidate_bucket_attribution": {
      "A_positive_catalyst_plus_volume_support": {
        "avg_fwd_10d": 0.065305,
        "candidate_count": 3,
        "candidate_date_count": 3,
        "fwd_10d_sample": 3,
        "fwd_10d_win_rate": 1.0,
        "ticker_count": 1
      },
      "B_positive_catalyst_only": {
        "avg_fwd_10d": 0.126723,
        "candidate_count": 1,
        "candidate_date_count": 1,
        "fwd_10d_sample": 1,
        "fwd_10d_win_rate": 1.0,
        "ticker_count": 1
      },
      "C_volume_support_only": {
        "avg_fwd_10d": 0.026267,
        "candidate_count": 14,
        "candidate_date_count": 7,
        "fwd_10d_sample": 14,
        "fwd_10d_win_rate": 0.785714,
        "ticker_count": 10
      },
      "E_ambiguous_prior_context": {
        "avg_fwd_10d": -0.0669,
        "candidate_count": 1,
        "candidate_date_count": 1,
        "fwd_10d_sample": 1,
        "fwd_10d_win_rate": 0.0,
        "ticker_count": 1
      },
      "F_no_prior_catalyst_or_support": {
        "avg_fwd_10d": 0.029785,
        "candidate_count": 22,
        "candidate_date_count": 11,
        "fwd_10d_sample": 22,
        "fwd_10d_win_rate": 0.636364,
        "ticker_count": 13
      }
    },
    "qqq_confirmed_candidates": 41,
    "raw_volatility_candidates": 46,
    "rejected_missing_market_context": 0,
    "rejected_qqq_not_leading_spy": 5
  }
}
```

## Gate

```json
{
  "best_eligible_bucket": "F_no_prior_catalyst_or_support",
  "best_worst_avg_pnl_separation": 339.8,
  "diagnostic_bucket_separation": true,
  "dossier_coverage_passed": true,
  "min_avg_pnl_separation": 100.0,
  "min_bucket_trades_for_separation": 5,
  "note": "This gate grades attribution usefulness only. It cannot promote a trade gate, sizing rule, ranking rule, or live/default order path.",
  "observed_only": true,
  "passed": false,
  "promotion_grade": false,
  "selected_trade_count": 71,
  "selected_trade_count_min": 20,
  "source_exp022_selection_parity_passed": true,
  "strategy_behavior_changed": false,
  "supportive_quality_buckets": [
    "A_positive_catalyst_plus_volume_support",
    "B_positive_catalyst_only",
    "C_volume_support_only"
  ],
  "supportive_quality_hypothesis_supported": false,
  "worst_eligible_bucket": "E_ambiguous_prior_context"
}
```

No JavaScript was used.
