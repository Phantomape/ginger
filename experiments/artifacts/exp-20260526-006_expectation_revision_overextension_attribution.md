# exp-20260526-006 Expectation Revision Overextension Attribution

Decision: `observed_only_promising_but_concentration_or_maturity_blocked`.

Observed-only alpha search. No entries, exits, ranking, sizing, paper sleeves, LLM/news, or orders changed.

## Coverage

```json
{
  "aggregate_bucket_counts": {
    "non_overextended": 23,
    "overextended_residual_leader": 18
  },
  "candidate_hit_counts_all_usable_rows": {
    "10td": 22,
    "3td": 15
  },
  "candidate_hit_counts_primary_bucket_a_rows": {
    "10td": 0,
    "3td": 0
  },
  "candidate_hit_counts_primary_positive_rows": {
    "10td": 0,
    "3td": 0
  },
  "candidate_hit_counts_wide_bucket_a_rows": {
    "10td": 0,
    "3td": 0
  },
  "candidate_hit_counts_wide_positive_rows": {
    "10td": 1,
    "3td": 1
  },
  "closed_forward_outcomes": {
    "10d": 394,
    "20d": 0,
    "5d": 547
  },
  "effective_date_source_counts": {
    "known_ohlcv_calendar": 649
  },
  "expectation_status_counts": {
    "non_positive_eps_estimate_delta_7d": 298,
    "pit_usable_missing_7d_delta": 310,
    "positive_eps_estimate_delta_7d": 41
  },
  "ledger_rows_total": 2074,
  "pead_status_counts": {
    "missing_last_earnings_date": 649
  },
  "pit_unusable_revision_rows": 1425,
  "pit_usable_revision_rows": 649,
  "primary_positive_7d_rows": 41,
  "primary_positive_7d_ticker_count": 16,
  "primary_positive_7d_tickers": [
    "AAPL",
    "AMD",
    "APP",
    "CAT",
    "COHR",
    "CVX",
    "DDOG",
    "DIS",
    "LLY",
    "MTSI",
    "MU",
    "NVDA",
    "NVO",
    "RBLX",
    "SOFI",
    "V"
  ],
  "primary_rows_used_in_this_experiment": 41,
  "residual_context_status_counts": {
    "ok": 649
  },
  "residual_leader_rows": 209,
  "residual_state_counts": {
    "beta_lagging": 318,
    "neutral": 122,
    "residual_leader": 51,
    "strong_residual_leader": 158
  },
  "scout_prev_positive_rows": 22,
  "source_decision": "rejected_or_scout_only_revision_watchlist",
  "source_experiment_id": "exp-20260525-034",
  "state_bucket_counts": {
    "beta_lagging_non_overextended": 9,
    "neutral_non_overextended": 14,
    "overextended_residual_leader": 18
  },
  "support_30d_positive_rows": 0,
  "watchlist_signal_basis_counts": {
    "none": 594,
    "primary_7d": 33,
    "primary_7d+scout_prev": 8,
    "scout_prev": 14
  },
  "wide_watchlist_positive_rows": 55,
  "wide_watchlist_positive_ticker_count": 19,
  "wide_watchlist_positive_tickers": [
    "AAPL",
    "AMD",
    "APP",
    "CAT",
    "COHR",
    "COIN",
    "CVX",
    "DDOG",
    "DIS",
    "LLY",
    "MTSI",
    "MU",
    "NVDA",
    "NVO",
    "RBLX",
    "SOFI",
    "SPOT",
    "V",
    "XOM"
  ]
}
```

## Aggregate Buckets

| Bucket | Rows | 5d Closed | 5d Avg Return | 10d Closed | 10d Avg Return | 20d Closed | 20d Avg Return |
|---|---:|---:|---:|---:|---:|---:|---:|
| non_overextended | 23 | 17 | 0.8502% | 6 | 0.9756% | 0 |  |
| overextended_residual_leader | 18 | 16 | -0.7459% | 10 | 0.7018% | 0 |  |
| missing_residual_context | 0 | 0 |  | 0 |  | 0 |  |

## State Buckets

| Bucket | Rows | 5d Closed | 5d Avg Return | 10d Closed | 10d Avg Return |
|---|---:|---:|---:|---:|---:|
| neutral_non_overextended | 14 | 12 | 0.4626% | 5 | 1.3142% |
| beta_lagging_non_overextended | 9 | 5 | 1.7806% | 1 | -0.7173% |
| overextended_residual_leader | 18 | 16 | -0.7459% | 10 | 0.7018% |
| missing_residual_context | 0 | 0 |  | 0 |  |

## Gate

```json
{
  "comparisons": [
    {
      "horizon": "5d",
      "non_overextended_avg_return": 0.008502,
      "non_overextended_closed_outcomes": 17,
      "overextended_closed_outcomes": 16,
      "overextended_residual_leader_avg_return": -0.007459,
      "passed": true
    },
    {
      "horizon": "10d",
      "non_overextended_avg_return": 0.009756,
      "non_overextended_closed_outcomes": 6,
      "overextended_closed_outcomes": 10,
      "overextended_residual_leader_avg_return": 0.007018,
      "passed": true
    }
  ],
  "concentration": {
    "max_single_ticker_positive_guardrail": 0.5,
    "max_single_ticker_positive_share": 0.568618,
    "passed": false,
    "top5_positive_contribution_guardrail": 0.6,
    "top5_positive_contribution_share": 0.779192
  },
  "decision": "observed_only_promising_but_concentration_or_maturity_blocked",
  "directional_passed": true,
  "non_overextended_closed_5d_outcomes": 17,
  "overextended_closed_5d_outcomes": 16,
  "promotion_gate_passed": false,
  "reason": "directional_readout_positive_but_not_promotable",
  "total_primary_positive_7d_rows": 41,
  "warnings": [
    "non_overextended_10d_closed_outcomes_thin",
    "non_overextended_20d_no_closed_outcomes",
    "overextended_residual_leader_20d_no_closed_outcomes"
  ]
}
```

No JavaScript was used.
