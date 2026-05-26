# exp-20260525-034 Expectation Revision Watchlist Attribution

Decision: `rejected_or_scout_only_revision_watchlist`.

Observed-only alpha search. No entries, exits, ranking, sizing, paper sleeves, LLM/news, or orders changed.

## Coverage

```json
{
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
    "10d": 343,
    "20d": 0,
    "5d": 496
  },
  "effective_date_source_counts": {
    "known_ohlcv_calendar": 547,
    "pending_future_trading_calendar": 51
  },
  "expectation_status_counts": {
    "non_positive_eps_estimate_delta_7d": 253,
    "pit_usable_missing_7d_delta": 308,
    "positive_eps_estimate_delta_7d": 37
  },
  "ledger_rows_total": 2017,
  "pead_status_counts": {
    "missing_effective_trade_date": 51,
    "missing_last_earnings_date": 547
  },
  "pit_unusable_revision_rows": 1419,
  "pit_usable_revision_rows": 598,
  "primary_positive_7d_rows": 37,
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
  "residual_context_status_counts": {
    "ok": 598
  },
  "residual_leader_rows": 193,
  "residual_state_counts": {
    "beta_lagging": 295,
    "neutral": 110,
    "residual_leader": 46,
    "strong_residual_leader": 147
  },
  "scout_prev_positive_rows": 22,
  "support_30d_positive_rows": 0,
  "watchlist_signal_basis_counts": {
    "none": 547,
    "primary_7d": 29,
    "primary_7d+scout_prev": 8,
    "scout_prev": 14
  },
  "wide_watchlist_positive_rows": 51,
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

## Latest Watchlist

```json
{
  "latest_as_of_date": "2026-05-24",
  "primary_positive_7d": [
    {
      "as_of_date": "2026-05-24",
      "candidate_hit_10td": false,
      "candidate_hit_3td": false,
      "effective_date_source": "pending_future_trading_calendar",
      "eps_estimate_delta_30d": null,
      "eps_estimate_delta_7d": 0.18,
      "eps_estimate_delta_prev": 0.0,
      "feature_context_date": "2026-05-24",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_effective_trade_date",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_effective_trade_date",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_effective_trade_date",
          "pnl_proxy": null,
          "return": null
        }
      },
      "pead_status": "missing_effective_trade_date",
      "primary_bucket": "A_positive_expectation_and_residual_leader",
      "primary_expectation_positive": true,
      "residual_leader": true,
      "residual_state": "strong_residual_leader",
      "residual_strength_score": 0.429657,
      "ret20_excess_qqq": 0.4311,
      "ret20_excess_spy": 0.4675,
      "scout_prev_positive": false,
      "support_30d_positive": false,
      "ticker": "MU",
      "watchlist_effective_trade_date": null,
      "watchlist_signal_basis": [
        "primary_7d"
      ],
      "wide_watchlist_bucket": "A_positive_expectation_and_residual_leader",
      "wide_watchlist_positive": true
    },
    {
      "as_of_date": "2026-05-24",
      "candidate_hit_10td": false,
      "candidate_hit_3td": false,
      "effective_date_source": "pending_future_trading_calendar",
      "eps_estimate_delta_30d": null,
      "eps_estimate_delta_7d": 0.05,
      "eps_estimate_delta_prev": 0.0,
      "feature_context_date": "2026-05-24",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_effective_trade_date",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_effective_trade_date",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_effective_trade_date",
          "pnl_proxy": null,
          "return": null
        }
      },
      "pead_status": "missing_effective_trade_date",
      "primary_bucket": "B_positive_expectation_only",
      "primary_expectation_positive": true,
      "residual_leader": false,
      "residual_state": "neutral",
      "residual_strength_score": -0.01768,
      "ret20_excess_qqq": -0.0377,
      "ret20_excess_spy": -0.0013,
      "scout_prev_positive": false,
      "support_30d_positive": false,
      "ticker": "CVX",
      "watchlist_effective_trade_date": null,
      "watchlist_signal_basis": [
        "primary_7d"
      ],
      "wide_watchlist_bucket": "B_positive_expectation_only",
      "wide_watchlist_positive": true
    },
    {
      "as_of_date": "2026-05-24",
      "candidate_hit_10td": false,
      "candidate_hit_3td": false,
      "effective_date_source": "pending_future_trading_calendar",
      "eps_estimate_delta_30d": null,
      "eps_estimate_delta_7d": 0.01,
      "eps_estimate_delta_prev": 0.0,
      "feature_context_date": "2026-05-24",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_effective_trade_date",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_effective_trade_date",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_effective_trade_date",
          "pnl_proxy": null,
          "return": null
        }
      },
      "pead_status": "missing_effective_trade_date",
      "primary_bucket": "B_positive_expectation_only",
      "primary_expectation_positive": true,
      "residual_leader": false,
      "residual_state": "beta_lagging",
      "residual_strength_score": -0.05688,
      "ret20_excess_qqq": -0.0769,
      "ret20_excess_spy": -0.0405,
      "scout_prev_positive": false,
      "support_30d_positive": false,
      "ticker": "DIS",
      "watchlist_effective_trade_date": null,
      "watchlist_signal_basis": [
        "primary_7d"
      ],
      "wide_watchlist_bucket": "B_positive_expectation_only",
      "wide_watchlist_positive": true
    },
    {
      "as_of_date": "2026-05-24",
      "candidate_hit_10td": false,
      "candidate_hit_3td": false,
      "effective_date_source": "pending_future_trading_calendar",
      "eps_estimate_delta_30d": null,
      "eps_estimate_delta_7d": 0.01,
      "eps_estimate_delta_prev": 0.0,
      "feature_context_date": "2026-05-24",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_effective_trade_date",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_effective_trade_date",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_effective_trade_date",
          "pnl_proxy": null,
          "return": null
        }
      },
      "pead_status": "missing_effective_trade_date",
      "primary_bucket": "B_positive_expectation_only",
      "primary_expectation_positive": true,
      "residual_leader": false,
      "residual_state": "beta_lagging",
      "residual_strength_score": -0.20218,
      "ret20_excess_qqq": -0.2222,
      "ret20_excess_spy": -0.1858,
      "scout_prev_positive": false,
      "support_30d_positive": false,
      "ticker": "RBLX",
      "watchlist_effective_trade_date": null,
      "watchlist_signal_basis": [
        "primary_7d"
      ],
      "wide_watchlist_bucket": "B_positive_expectation_only",
      "wide_watchlist_positive": true
    }
  ],
  "primary_positive_7d_count": 4,
  "wide_positive": [
    {
      "as_of_date": "2026-05-24",
      "candidate_hit_10td": false,
      "candidate_hit_3td": false,
      "effective_date_source": "pending_future_trading_calendar",
      "eps_estimate_delta_30d": null,
      "eps_estimate_delta_7d": 0.18,
      "eps_estimate_delta_prev": 0.0,
      "feature_context_date": "2026-05-24",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_effective_trade_date",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_effective_trade_date",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_effective_trade_date",
          "pnl_proxy": null,
          "return": null
        }
      },
      "pead_status": "missing_effective_trade_date",
      "primary_bucket": "A_positive_expectation_and_residual_leader",
      "primary_expectation_positive": true,
      "residual_leader": true,
      "residual_state": "strong_residual_leader",
      "residual_strength_score": 0.429657,
      "ret20_excess_qqq": 0.4311,
      "ret20_excess_spy": 0.4675,
      "scout_prev_positive": false,
      "support_30d_positive": false,
      "ticker": "MU",
      "watchlist_effective_trade_date": null,
      "watchlist_signal_basis": [
        "primary_7d"
      ],
      "wide_watchlist_bucket": "A_positive_expectation_and_residual_leader",
      "wide_watchlist_positive": true
    },
    {
      "as_of_date": "2026-05-24",
      "candidate_hit_10td": false,
      "candidate_hit_3td": false,
      "effective_date_source": "pending_future_trading_calendar",
      "eps_estimate_delta_30d": null,
      "eps_estimate_delta_7d": 0.05,
      "eps_estimate_delta_prev": 0.0,
      "feature_context_date": "2026-05-24",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_effective_trade_date",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_effective_trade_date",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_effective_trade_date",
          "pnl_proxy": null,
          "return": null
        }
      },
      "pead_status": "missing_effective_trade_date",
      "primary_bucket": "B_positive_expectation_only",
      "primary_expectation_positive": true,
      "residual_leader": false,
      "residual_state": "neutral",
      "residual_strength_score": -0.01768,
      "ret20_excess_qqq": -0.0377,
      "ret20_excess_spy": -0.0013,
      "scout_prev_positive": false,
      "support_30d_positive": false,
      "ticker": "CVX",
      "watchlist_effective_trade_date": null,
      "watchlist_signal_basis": [
        "primary_7d"
      ],
      "wide_watchlist_bucket": "B_positive_expectation_only",
      "wide_watchlist_positive": true
    },
    {
      "as_of_date": "2026-05-24",
      "candidate_hit_10td": false,
      "candidate_hit_3td": false,
      "effective_date_source": "pending_future_trading_calendar",
      "eps_estimate_delta_30d": null,
      "eps_estimate_delta_7d": 0.01,
      "eps_estimate_delta_prev": 0.0,
      "feature_context_date": "2026-05-24",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_effective_trade_date",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_effective_trade_date",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_effective_trade_date",
          "pnl_proxy": null,
          "return": null
        }
      },
      "pead_status": "missing_effective_trade_date",
      "primary_bucket": "B_positive_expectation_only",
      "primary_expectation_positive": true,
      "residual_leader": false,
      "residual_state": "beta_lagging",
      "residual_strength_score": -0.05688,
      "ret20_excess_qqq": -0.0769,
      "ret20_excess_spy": -0.0405,
      "scout_prev_positive": false,
      "support_30d_positive": false,
      "ticker": "DIS",
      "watchlist_effective_trade_date": null,
      "watchlist_signal_basis": [
        "primary_7d"
      ],
      "wide_watchlist_bucket": "B_positive_expectation_only",
      "wide_watchlist_positive": true
    },
    {
      "as_of_date": "2026-05-24",
      "candidate_hit_10td": false,
      "candidate_hit_3td": false,
      "effective_date_source": "pending_future_trading_calendar",
      "eps_estimate_delta_30d": null,
      "eps_estimate_delta_7d": 0.01,
      "eps_estimate_delta_prev": 0.0,
      "feature_context_date": "2026-05-24",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_effective_trade_date",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_effective_trade_date",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_effective_trade_date",
          "pnl_proxy": null,
          "return": null
        }
      },
      "pead_status": "missing_effective_trade_date",
      "primary_bucket": "B_positive_expectation_only",
      "primary_expectation_positive": true,
      "residual_leader": false,
      "residual_state": "beta_lagging",
      "residual_strength_score": -0.20218,
      "ret20_excess_qqq": -0.2222,
      "ret20_excess_spy": -0.1858,
      "scout_prev_positive": false,
      "support_30d_positive": false,
      "ticker": "RBLX",
      "watchlist_effective_trade_date": null,
      "watchlist_signal_basis": [
        "primary_7d"
      ],
      "wide_watchlist_bucket": "B_positive_expectation_only",
      "wide_watchlist_positive": true
    }
  ],
  "wide_positive_count": 4
}
```

## Primary Bucket Summary

| Bucket | Rows | 5d Closed | 5d Avg Return | 10d Closed | 10d Avg Return | 20d Closed | 20d Avg Return |
|---|---:|---:|---:|---:|---:|---:|---:|
| A_positive_expectation_and_residual_leader | 17 | 13 | -1.0048% | 3 | -3.0267% | 0 |  |
| B_positive_expectation_only | 20 | 12 | 0.8620% | 3 | 1.0799% | 0 |  |
| C_residual_leader_only | 176 | 150 | -1.6949% | 117 | -0.7400% | 0 |  |
| D_neither | 385 | 321 | 0.6853% | 220 | 1.7550% | 0 |  |

## Wide Watchlist Bucket Summary

| Bucket | Rows | 5d Closed | 5d Avg Return | 10d Closed | 10d Avg Return | 20d Closed | 20d Avg Return |
|---|---:|---:|---:|---:|---:|---:|---:|
| A_positive_expectation_and_residual_leader | 25 | 20 | -0.9916% | 10 | -0.9237% | 0 |  |
| B_positive_expectation_only | 26 | 17 | 0.6631% | 7 | 0.7971% | 0 |  |
| C_residual_leader_only | 168 | 143 | -1.7305% | 110 | -0.7857% | 0 |  |
| D_neither | 379 | 316 | 0.6932% | 216 | 1.7767% | 0 |  |

## Current Position Overlap

```json
{
  "current_position_count": 11,
  "entry_watchlist_match_count": 1,
  "entry_watchlist_matches": [
    {
      "avg_cost": 383.009,
      "entry_date": "2026-05-11",
      "entry_effective_trade_date": "2026-05-11",
      "entry_lag_trading_days": 0,
      "eps_estimate_delta_30d": null,
      "eps_estimate_delta_7d": null,
      "eps_estimate_delta_prev": 0.06,
      "opened_by_strategy": "pilot_breakout_long",
      "position_source": "positions",
      "primary_expectation_positive": false,
      "residual_state": "beta_lagging",
      "revision_as_of_date": "2026-05-09",
      "shares": 16,
      "ticker": "COHR",
      "watchlist_effective_trade_date": "2026-05-11",
      "watchlist_signal_basis": [
        "scout_prev"
      ],
      "wide_watchlist_positive": true
    }
  ],
  "ticker_overlap_count": 4,
  "ticker_overlap_with_positive_watchlist": [
    "AMD",
    "APP",
    "COHR",
    "NVDA"
  ]
}
```

## Gate

```json
{
  "primary_7d_gate": {
    "bucket_a_closed_5d_outcomes": 13,
    "comparisons": [
      {
        "bucket_a_avg_return": -0.010048,
        "comparison_bucket": "B_positive_expectation_only",
        "horizon": "5d",
        "other_avg_return": 0.00862,
        "passed": false
      },
      {
        "bucket_a_avg_return": -0.010048,
        "comparison_bucket": "C_residual_leader_only",
        "horizon": "5d",
        "other_avg_return": -0.016949,
        "passed": true
      },
      {
        "bucket_a_avg_return": -0.010048,
        "comparison_bucket": "D_neither",
        "horizon": "5d",
        "other_avg_return": 0.006853,
        "passed": false
      },
      {
        "bucket_a_avg_return": -0.030267,
        "comparison_bucket": "B_positive_expectation_only",
        "horizon": "10d",
        "other_avg_return": 0.010799,
        "passed": false
      },
      {
        "bucket_a_avg_return": -0.030267,
        "comparison_bucket": "C_residual_leader_only",
        "horizon": "10d",
        "other_avg_return": -0.0074,
        "passed": false
      },
      {
        "bucket_a_avg_return": -0.030267,
        "comparison_bucket": "D_neither",
        "horizon": "10d",
        "other_avg_return": 0.01755,
        "passed": false
      }
    ],
    "concentration": {
      "max_single_ticker_positive_guardrail": 0.5,
      "max_single_ticker_positive_share": 0.392391,
      "passed": false,
      "top5_positive_contribution_guardrail": 0.6,
      "top5_positive_contribution_share": 0.998463
    },
    "decision": "rejected_or_scout_only_revision_watchlist",
    "decision_scope": "primary_7d_promotable_readout",
    "passed": false,
    "positive_expectation_rows": 37,
    "promotable": true,
    "reason": "bucket_a_failed_outperformance_concentration_or_scope",
    "total_closed_5d_outcomes": 496
  },
  "wide_watchlist_scout_gate": {
    "bucket_a_closed_5d_outcomes": 20,
    "comparisons": [
      {
        "bucket_a_avg_return": -0.009916,
        "comparison_bucket": "B_positive_expectation_only",
        "horizon": "5d",
        "other_avg_return": 0.006631,
        "passed": false
      },
      {
        "bucket_a_avg_return": -0.009916,
        "comparison_bucket": "C_residual_leader_only",
        "horizon": "5d",
        "other_avg_return": -0.017305,
        "passed": true
      },
      {
        "bucket_a_avg_return": -0.009916,
        "comparison_bucket": "D_neither",
        "horizon": "5d",
        "other_avg_return": 0.006932,
        "passed": false
      },
      {
        "bucket_a_avg_return": -0.009237,
        "comparison_bucket": "B_positive_expectation_only",
        "horizon": "10d",
        "other_avg_return": 0.007971,
        "passed": false
      },
      {
        "bucket_a_avg_return": -0.009237,
        "comparison_bucket": "C_residual_leader_only",
        "horizon": "10d",
        "other_avg_return": -0.007857,
        "passed": false
      },
      {
        "bucket_a_avg_return": -0.009237,
        "comparison_bucket": "D_neither",
        "horizon": "10d",
        "other_avg_return": 0.017767,
        "passed": false
      }
    ],
    "concentration": {
      "max_single_ticker_positive_guardrail": 0.5,
      "max_single_ticker_positive_share": 0.255836,
      "passed": false,
      "top5_positive_contribution_guardrail": 0.6,
      "top5_positive_contribution_share": 0.815047
    },
    "decision": "rejected_or_scout_only_revision_watchlist",
    "decision_scope": "wide_watchlist_scout_not_promotable",
    "passed": false,
    "positive_expectation_rows": 51,
    "promotable": false,
    "reason": "bucket_a_failed_outperformance_concentration_or_scope",
    "total_closed_5d_outcomes": 496
  }
}
```

No JavaScript was used.
