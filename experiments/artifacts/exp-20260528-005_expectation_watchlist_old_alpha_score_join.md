# exp-20260528-005 Expectation Watchlist Old Alpha Score Join

- status: `observed_only`
- decision: `measurement_repair_passed_next_true_ranking_test`
- changed_variable: `old_alpha_score_join_v1`
- gate_reason: `old_alpha_score_join_ready_for_true_replacement_test`

## Summary

Read-only measurement repair that rebuilds the existing cross-sectional ranking surface by feature_context_date and joins old_alpha_score/rank/bucket onto expectation watchlist rows. No production behavior changed.

## Gate

```json
{
  "data_gap_reasons": [],
  "decision": "measurement_repair_passed_next_true_ranking_test",
  "join_coverage_ratio": 1.0,
  "measurement_gate_passed": true,
  "old_alpha_score_rows": 751,
  "primary_positive_joined_rows": 53,
  "promotion_gate_passed": false,
  "reason": "old_alpha_score_join_ready_for_true_replacement_test",
  "surface_rebuild_failure_count": 0,
  "thresholds": {
    "min_join_coverage_ratio": 0.8,
    "min_old_alpha_score_rows": 100,
    "min_primary_joined_rows": 30
  }
}
```

## Coverage

```json
{
  "closed_forward_outcomes": {
    "10d": 394,
    "20d": 0,
    "5d": 547
  },
  "feature_surface_date_count": 49,
  "field_coverage": {
    "combined_alpha_score": {
      "coverage_ratio": 1.0,
      "missing_rows": 0,
      "present_rows": 751
    },
    "combined_watchlist_alpha_score_rank": {
      "coverage_ratio": 1.0,
      "missing_rows": 0,
      "present_rows": 751
    },
    "combined_watchlist_alpha_score_rank_bucket": {
      "coverage_ratio": 1.0,
      "missing_rows": 0,
      "present_rows": 751
    },
    "feature_context_date": {
      "coverage_ratio": 1.0,
      "missing_rows": 0,
      "present_rows": 751
    },
    "forward_outcomes": {
      "coverage_ratio": 1.0,
      "missing_rows": 0,
      "present_rows": 751
    },
    "old_alpha_score": {
      "coverage_ratio": 1.0,
      "missing_rows": 0,
      "present_rows": 751
    },
    "old_alpha_score_rank": {
      "coverage_ratio": 1.0,
      "missing_rows": 0,
      "present_rows": 751
    },
    "old_alpha_score_rank_bucket": {
      "coverage_ratio": 1.0,
      "missing_rows": 0,
      "present_rows": 751
    },
    "old_watchlist_alpha_score_rank": {
      "coverage_ratio": 1.0,
      "missing_rows": 0,
      "present_rows": 751
    },
    "old_watchlist_alpha_score_rank_bucket": {
      "coverage_ratio": 1.0,
      "missing_rows": 0,
      "present_rows": 751
    }
  },
  "join_coverage_ratio": 1.0,
  "join_status_counts": {
    "joined": 751
  },
  "old_alpha_score_rows": 751,
  "primary_positive_7d_rows": 53,
  "primary_positive_joined_rows": 53,
  "rank_bucket_counts": {
    "combined_watchlist_alpha_score": {
      "bottom_quartile": 188,
      "lower_mid": 188,
      "top_decile": 75,
      "top_quartile": 112,
      "upper_mid": 188
    },
    "old_surface_alpha_score": {
      "bottom_quartile": 220,
      "lower_mid": 143,
      "top_decile": 72,
      "top_quartile": 131,
      "upper_mid": 185
    },
    "old_watchlist_alpha_score": {
      "bottom_quartile": 188,
      "lower_mid": 188,
      "top_decile": 75,
      "top_quartile": 112,
      "upper_mid": 188
    }
  },
  "rows_total": 751,
  "score_summary": {
    "combined_alpha_score": {
      "avg": 0.748573,
      "count": 751,
      "max": 2.401835,
      "min": 0.097
    },
    "expectation_residual_component_score": {
      "avg": 0.240879,
      "count": 751,
      "max": 1.5,
      "min": 0.0
    },
    "old_alpha_score": {
      "avg": 0.507694,
      "count": 751,
      "max": 0.901835,
      "min": 0.097
    }
  },
  "surface_date_summaries_sample": {
    "2026-05-18": {
      "distribution": {
        "avg_alpha_score": 0.484615,
        "max_alpha_score": 0.777235,
        "min_alpha_score": 0.1109
      },
      "feature_ticker_count": 57,
      "ranking_universe_count": 57
    },
    "2026-05-19": {
      "distribution": {
        "avg_alpha_score": 0.485576,
        "max_alpha_score": 0.88333,
        "min_alpha_score": 0.129075
      },
      "feature_ticker_count": 57,
      "ranking_universe_count": 57
    },
    "2026-05-20": {
      "distribution": {
        "avg_alpha_score": 0.477504,
        "max_alpha_score": 0.7768,
        "min_alpha_score": 0.12525
      },
      "feature_ticker_count": 57,
      "ranking_universe_count": 57
    },
    "2026-05-21": {
      "distribution": {
        "avg_alpha_score": 0.496595,
        "max_alpha_score": 0.85162,
        "min_alpha_score": 0.15475
      },
      "feature_ticker_count": 57,
      "ranking_universe_count": 57
    },
    "2026-05-22": {
      "distribution": {
        "avg_alpha_score": 0.503933,
        "max_alpha_score": 0.85641,
        "min_alpha_score": 0.11165
      },
      "feature_ticker_count": 57,
      "ranking_universe_count": 57
    },
    "2026-05-23": {
      "distribution": {
        "avg_alpha_score": 0.501803,
        "max_alpha_score": 0.85641,
        "min_alpha_score": 0.11165
      },
      "feature_ticker_count": 57,
      "ranking_universe_count": 57
    },
    "2026-05-24": {
      "distribution": {
        "avg_alpha_score": 0.503268,
        "max_alpha_score": 0.85641,
        "min_alpha_score": 0.11165
      },
      "feature_ticker_count": 57,
      "ranking_universe_count": 57
    },
    "2026-05-25": {
      "distribution": {
        "avg_alpha_score": 0.506547,
        "max_alpha_score": 0.88421,
        "min_alpha_score": 0.11165
      },
      "feature_ticker_count": 57,
      "ranking_universe_count": 57
    },
    "2026-05-26": {
      "distribution": {
        "avg_alpha_score": 0.526104,
        "max_alpha_score": 0.901835,
        "min_alpha_score": 0.1091
      },
      "feature_ticker_count": 59,
      "ranking_universe_count": 59
    },
    "2026-05-27": {
      "distribution": {
        "avg_alpha_score": 0.517875,
        "max_alpha_score": 0.880685,
        "min_alpha_score": 0.097
      },
      "feature_ticker_count": 59,
      "ranking_universe_count": 59
    }
  },
  "surface_rebuild_failures": {},
  "watchlist_feature_context_dates": [
    "2026-05-08",
    "2026-05-09",
    "2026-05-10",
    "2026-05-11",
    "2026-05-12",
    "2026-05-13",
    "2026-05-14",
    "2026-05-15",
    "2026-05-18",
    "2026-05-19",
    "2026-05-20",
    "2026-05-24",
    "2026-05-25",
    "2026-05-26",
    "2026-05-27"
  ]
}
```

## Movement Summary

```json
{
  "combined_watchlist_top_decile_rows": 75,
  "comparable_rows": 751,
  "new_combined_top_decile_rows": 49,
  "old_top_decile_dropped_rows": 49,
  "old_watchlist_top_decile_rows": 75,
  "rank_scope": "watchlist_rows_only_not_full_daily_candidate_surface",
  "top_decile_retained_rows": 26,
  "top_rank_decliners_sample": [
    {
      "as_of_date": "2026-05-25",
      "combined_alpha_score": 0.79749,
      "combined_watchlist_alpha_score_rank": 280,
      "combined_watchlist_alpha_score_rank_bucket": "upper_mid",
      "expectation_residual_component_score": 0.0,
      "feature_context_date": "2026-05-25",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_10d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_5d_forward_price",
          "pnl_proxy": null,
          "return": null
        }
      },
      "old_alpha_score": 0.79749,
      "old_alpha_score_components": {
        "breadth_alignment": 0.6842,
        "expectation_revision": 1.0,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.7198,
        "theme_participation": 0.3333,
        "trend": 0.9
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 2,
      "old_alpha_score_rank_bucket": "top_decile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 29,
      "old_watchlist_alpha_score_rank_bucket": "top_decile",
      "primary_bucket": "D_neither",
      "primary_expectation_positive": false,
      "residual_state": "neutral",
      "ticker": "CRDO",
      "watchlist_rank_improvement": -251
    },
    {
      "as_of_date": "2026-05-24",
      "combined_alpha_score": 0.79749,
      "combined_watchlist_alpha_score_rank": 279,
      "combined_watchlist_alpha_score_rank_bucket": "upper_mid",
      "expectation_residual_component_score": 0.0,
      "feature_context_date": "2026-05-24",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_10d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_5d_forward_price",
          "pnl_proxy": null,
          "return": null
        }
      },
      "old_alpha_score": 0.79749,
      "old_alpha_score_components": {
        "breadth_alignment": 0.6842,
        "expectation_revision": 1.0,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.7198,
        "theme_participation": 0.3333,
        "trend": 0.9
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 2,
      "old_alpha_score_rank_bucket": "top_decile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 28,
      "old_watchlist_alpha_score_rank_bucket": "top_decile",
      "primary_bucket": "D_neither",
      "primary_expectation_positive": false,
      "residual_state": "neutral",
      "ticker": "CRDO",
      "watchlist_rank_improvement": -251
    },
    {
      "as_of_date": "2026-05-13",
      "combined_alpha_score": 0.734065,
      "combined_watchlist_alpha_score_rank": 283,
      "combined_watchlist_alpha_score_rank_bucket": "upper_mid",
      "expectation_residual_component_score": 0.0,
      "feature_context_date": "2026-05-13",
      "forward_outcomes": {
        "10d": {
          "closed": true,
          "future_date": "2026-05-23",
          "gap_reason": null,
          "pnl_proxy": 484.86,
          "return": 0.048486
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": true,
          "future_date": "2026-05-18",
          "gap_reason": null,
          "pnl_proxy": -272.31,
          "return": -0.027231
        }
      },
      "old_alpha_score": 0.734065,
      "old_alpha_score_components": {
        "breadth_alignment": 0.7198,
        "expectation_revision": 0.929,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.4491,
        "theme_participation": 0.5,
        "trend": 0.9
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 9,
      "old_alpha_score_rank_bucket": "top_quartile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 73,
      "old_watchlist_alpha_score_rank_bucket": "top_decile",
      "primary_bucket": "D_neither",
      "primary_expectation_positive": false,
      "residual_state": "neutral",
      "ticker": "LLY",
      "watchlist_rank_improvement": -210
    },
    {
      "as_of_date": "2026-05-18",
      "combined_alpha_score": 0.715335,
      "combined_watchlist_alpha_score_rank": 284,
      "combined_watchlist_alpha_score_rank_bucket": "upper_mid",
      "expectation_residual_component_score": 0.0,
      "feature_context_date": "2026-05-18",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_10d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": true,
          "future_date": "2026-05-23",
          "gap_reason": null,
          "pnl_proxy": -239.14,
          "return": -0.023914
        }
      },
      "old_alpha_score": 0.715335,
      "old_alpha_score_components": {
        "breadth_alignment": 0.6579,
        "expectation_revision": 0.8802,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.4256,
        "theme_participation": 0.5,
        "trend": 0.9
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 3,
      "old_alpha_score_rank_bucket": "top_decile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 91,
      "old_watchlist_alpha_score_rank_bucket": "top_quartile",
      "primary_bucket": "D_neither",
      "primary_expectation_positive": false,
      "residual_state": "neutral",
      "ticker": "CVX",
      "watchlist_rank_improvement": -193
    },
    {
      "as_of_date": "2026-05-19",
      "combined_alpha_score": 0.71342,
      "combined_watchlist_alpha_score_rank": 285,
      "combined_watchlist_alpha_score_rank_bucket": "upper_mid",
      "expectation_residual_component_score": 0.0,
      "feature_context_date": "2026-05-19",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_10d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": true,
          "future_date": "2026-05-24",
          "gap_reason": null,
          "pnl_proxy": -295.06,
          "return": -0.029506
        }
      },
      "old_alpha_score": 0.71342,
      "old_alpha_score_components": {
        "breadth_alignment": 0.6666,
        "expectation_revision": 0.8802,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.4162,
        "theme_participation": 0.5,
        "trend": 0.9
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 5,
      "old_alpha_score_rank_bucket": "top_decile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 95,
      "old_watchlist_alpha_score_rank_bucket": "top_quartile",
      "primary_bucket": "D_neither",
      "primary_expectation_positive": false,
      "residual_state": "neutral",
      "ticker": "CVX",
      "watchlist_rank_improvement": -190
    },
    {
      "as_of_date": "2026-05-26",
      "combined_alpha_score": 0.70762,
      "combined_watchlist_alpha_score_rank": 286,
      "combined_watchlist_alpha_score_rank_bucket": "upper_mid",
      "expectation_residual_component_score": 0.0,
      "feature_context_date": "2026-05-26",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_10d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_5d_forward_price",
          "pnl_proxy": null,
          "return": null
        }
      },
      "old_alpha_score": 0.70762,
      "old_alpha_score_components": {
        "breadth_alignment": 0.7161,
        "expectation_revision": 0.8442,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.4119,
        "theme_participation": 0.5,
        "trend": 0.9
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 12,
      "old_alpha_score_rank_bucket": "top_quartile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 108,
      "old_watchlist_alpha_score_rank_bucket": "top_quartile",
      "primary_bucket": "D_neither",
      "primary_expectation_positive": false,
      "residual_state": "neutral",
      "ticker": "GE",
      "watchlist_rank_improvement": -178
    },
    {
      "as_of_date": "2026-05-27",
      "combined_alpha_score": 0.704175,
      "combined_watchlist_alpha_score_rank": 287,
      "combined_watchlist_alpha_score_rank_bucket": "upper_mid",
      "expectation_residual_component_score": 0.0,
      "feature_context_date": "2026-05-27",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_10d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_5d_forward_price",
          "pnl_proxy": null,
          "return": null
        }
      },
      "old_alpha_score": 0.704175,
      "old_alpha_score_components": {
        "breadth_alignment": 0.6907,
        "expectation_revision": 0.8442,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.4032,
        "theme_participation": 0.5,
        "trend": 0.9
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 11,
      "old_alpha_score_rank_bucket": "top_quartile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 112,
      "old_watchlist_alpha_score_rank_bucket": "top_quartile",
      "primary_bucket": "D_neither",
      "primary_expectation_positive": false,
      "residual_state": "neutral",
      "ticker": "GE",
      "watchlist_rank_improvement": -175
    },
    {
      "as_of_date": "2026-05-14",
      "combined_alpha_score": 0.704135,
      "combined_watchlist_alpha_score_rank": 288,
      "combined_watchlist_alpha_score_rank_bucket": "upper_mid",
      "expectation_residual_component_score": 0.0,
      "feature_context_date": "2026-05-14",
      "forward_outcomes": {
        "10d": {
          "closed": true,
          "future_date": "2026-05-24",
          "gap_reason": null,
          "pnl_proxy": 286.6,
          "return": 0.02866
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": true,
          "future_date": "2026-05-19",
          "gap_reason": null,
          "pnl_proxy": -415.08,
          "return": -0.041508
        }
      },
      "old_alpha_score": 0.704135,
      "old_alpha_score_components": {
        "breadth_alignment": 0.694,
        "expectation_revision": 0.8168,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.4243,
        "theme_participation": 0.5,
        "trend": 0.9
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 10,
      "old_alpha_score_rank_bucket": "top_quartile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 113,
      "old_watchlist_alpha_score_rank_bucket": "top_quartile",
      "primary_bucket": "D_neither",
      "primary_expectation_positive": false,
      "residual_state": "neutral",
      "ticker": "GS",
      "watchlist_rank_improvement": -175
    },
    {
      "as_of_date": "2026-05-20",
      "combined_alpha_score": 0.70108,
      "combined_watchlist_alpha_score_rank": 290,
      "combined_watchlist_alpha_score_rank_bucket": "upper_mid",
      "expectation_residual_component_score": 0.0,
      "feature_context_date": "2026-05-20",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_10d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": true,
          "future_date": "2026-05-25",
          "gap_reason": null,
          "pnl_proxy": 148.76,
          "return": 0.014876
        }
      },
      "old_alpha_score": 0.70108,
      "old_alpha_score_components": {
        "breadth_alignment": 0.6403,
        "expectation_revision": 0.8262,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.4153,
        "theme_participation": 0.5,
        "trend": 0.9
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 4,
      "old_alpha_score_rank_bucket": "top_decile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 116,
      "old_watchlist_alpha_score_rank_bucket": "top_quartile",
      "primary_bucket": "D_neither",
      "primary_expectation_positive": false,
      "residual_state": "neutral",
      "ticker": "GS",
      "watchlist_rank_improvement": -174
    },
    {
      "as_of_date": "2026-05-13",
      "combined_alpha_score": 0.702275,
      "combined_watchlist_alpha_score_rank": 289,
      "combined_watchlist_alpha_score_rank_bucket": "upper_mid",
      "expectation_residual_component_score": 0.0,
      "feature_context_date": "2026-05-13",
      "forward_outcomes": {
        "10d": {
          "closed": true,
          "future_date": "2026-05-23",
          "gap_reason": null,
          "pnl_proxy": 432.38,
          "return": 0.043238
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": true,
          "future_date": "2026-05-18",
          "gap_reason": null,
          "pnl_proxy": -94.83,
          "return": -0.009483
        }
      },
      "old_alpha_score": 0.702275,
      "old_alpha_score_components": {
        "breadth_alignment": 0.7198,
        "expectation_revision": 0.8168,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.4117,
        "theme_participation": 0.5,
        "trend": 0.9
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 14,
      "old_alpha_score_rank_bucket": "top_quartile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 115,
      "old_watchlist_alpha_score_rank_bucket": "top_quartile",
      "primary_bucket": "D_neither",
      "primary_expectation_positive": false,
      "residual_state": "neutral",
      "ticker": "GS",
      "watchlist_rank_improvement": -174
    },
    {
      "as_of_date": "2026-05-13",
      "combined_alpha_score": 0.691705,
      "combined_watchlist_alpha_score_rank": 291,
      "combined_watchlist_alpha_score_rank_bucket": "upper_mid",
      "expectation_residual_component_score": 0.0,
      "feature_context_date": "2026-05-13",
      "forward_outcomes": {
        "10d": {
          "closed": true,
          "future_date": "2026-05-23",
          "gap_reason": null,
          "pnl_proxy": 332.92,
          "return": 0.033292
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": true,
          "future_date": "2026-05-18",
          "gap_reason": null,
          "pnl_proxy": -34.46,
          "return": -0.003446
        }
      },
      "old_alpha_score": 0.691705,
      "old_alpha_score_components": {
        "breadth_alignment": 0.7198,
        "expectation_revision": 0.6527,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.5007,
        "theme_participation": 0.5,
        "trend": 0.9
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 16,
      "old_alpha_score_rank_bucket": "upper_mid",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 123,
      "old_watchlist_alpha_score_rank_bucket": "top_quartile",
      "primary_bucket": "D_neither",
      "primary_expectation_positive": false,
      "residual_state": "neutral",
      "ticker": "AAPL",
      "watchlist_rank_improvement": -168
    },
    {
      "as_of_date": "2026-05-14",
      "combined_alpha_score": 0.688475,
      "combined_watchlist_alpha_score_rank": 292,
      "combined_watchlist_alpha_score_rank_bucket": "upper_mid",
      "expectation_residual_component_score": 0.0,
      "feature_context_date": "2026-05-14",
      "forward_outcomes": {
        "10d": {
          "closed": true,
          "future_date": "2026-05-24",
          "gap_reason": null,
          "pnl_proxy": 1835.37,
          "return": 0.183537
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": true,
          "future_date": "2026-05-19",
          "gap_reason": null,
          "pnl_proxy": -842.64,
          "return": -0.084264
        }
      },
      "old_alpha_score": 0.688475,
      "old_alpha_score_components": {
        "breadth_alignment": 0.6595,
        "expectation_revision": 1.0,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.642,
        "theme_participation": 0.5,
        "trend": 0.55
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 12,
      "old_alpha_score_rank_bucket": "top_quartile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 127,
      "old_watchlist_alpha_score_rank_bucket": "top_quartile",
      "primary_bucket": "D_neither",
      "primary_expectation_positive": false,
      "residual_state": "neutral",
      "ticker": "CRDO",
      "watchlist_rank_improvement": -165
    },
    {
      "as_of_date": "2026-05-13",
      "combined_alpha_score": 0.68584,
      "combined_watchlist_alpha_score_rank": 293,
      "combined_watchlist_alpha_score_rank_bucket": "upper_mid",
      "expectation_residual_component_score": 0.0,
      "feature_context_date": "2026-05-13",
      "forward_outcomes": {
        "10d": {
          "closed": true,
          "future_date": "2026-05-23",
          "gap_reason": null,
          "pnl_proxy": 1534.11,
          "return": 0.153411
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": true,
          "future_date": "2026-05-18",
          "gap_reason": null,
          "pnl_proxy": -1747.47,
          "return": -0.174747
        }
      },
      "old_alpha_score": 0.68584,
      "old_alpha_score_components": {
        "breadth_alignment": 0.6638,
        "expectation_revision": 1.0,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.6306,
        "theme_participation": 0.5,
        "trend": 0.55
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 18,
      "old_alpha_score_rank_bucket": "upper_mid",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 132,
      "old_watchlist_alpha_score_rank_bucket": "top_quartile",
      "primary_bucket": "D_neither",
      "primary_expectation_positive": false,
      "residual_state": "neutral",
      "ticker": "CRDO",
      "watchlist_rank_improvement": -161
    },
    {
      "as_of_date": "2026-05-19",
      "combined_alpha_score": 0.679795,
      "combined_watchlist_alpha_score_rank": 295,
      "combined_watchlist_alpha_score_rank_bucket": "upper_mid",
      "expectation_residual_component_score": 0.0,
      "feature_context_date": "2026-05-19",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_10d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": true,
          "future_date": "2026-05-24",
          "gap_reason": null,
          "pnl_proxy": -469.39,
          "return": -0.046939
        }
      },
      "old_alpha_score": 0.679795,
      "old_alpha_score_components": {
        "breadth_alignment": 0.6666,
        "expectation_revision": 0.6512,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.4649,
        "theme_participation": 0.5,
        "trend": 0.9
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 6,
      "old_alpha_score_rank_bucket": "top_quartile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 141,
      "old_watchlist_alpha_score_rank_bucket": "top_quartile",
      "primary_bucket": "D_neither",
      "primary_expectation_positive": false,
      "residual_state": "neutral",
      "ticker": "XOM",
      "watchlist_rank_improvement": -154
    },
    {
      "as_of_date": "2026-05-14",
      "combined_alpha_score": 0.68061,
      "combined_watchlist_alpha_score_rank": 294,
      "combined_watchlist_alpha_score_rank_bucket": "upper_mid",
      "expectation_residual_component_score": 0.0,
      "feature_context_date": "2026-05-14",
      "forward_outcomes": {
        "10d": {
          "closed": true,
          "future_date": "2026-05-24",
          "gap_reason": null,
          "pnl_proxy": -583.23,
          "return": -0.058323
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": true,
          "future_date": "2026-05-19",
          "gap_reason": null,
          "pnl_proxy": -653.04,
          "return": -0.065304
        }
      },
      "old_alpha_score": 0.68061,
      "old_alpha_score_components": {
        "breadth_alignment": 0.694,
        "expectation_revision": 0.5493,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.5442,
        "theme_participation": 0.5,
        "trend": 0.9
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 13,
      "old_alpha_score_rank_bucket": "top_quartile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 140,
      "old_watchlist_alpha_score_rank_bucket": "top_quartile",
      "primary_bucket": "D_neither",
      "primary_expectation_positive": false,
      "residual_state": "beta_lagging",
      "ticker": "AVGO",
      "watchlist_rank_improvement": -154
    },
    {
      "as_of_date": "2026-05-18",
      "combined_alpha_score": 0.678085,
      "combined_watchlist_alpha_score_rank": 296,
      "combined_watchlist_alpha_score_rank_bucket": "upper_mid",
      "expectation_residual_component_score": 0.0,
      "feature_context_date": "2026-05-18",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_10d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": true,
          "future_date": "2026-05-23",
          "gap_reason": null,
          "pnl_proxy": -347.06,
          "return": -0.034706
        }
      },
      "old_alpha_score": 0.678085,
      "old_alpha_score_components": {
        "breadth_alignment": 0.6579,
        "expectation_revision": 0.6512,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.4598,
        "theme_participation": 0.5,
        "trend": 0.9
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 8,
      "old_alpha_score_rank_bucket": "top_quartile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 144,
      "old_watchlist_alpha_score_rank_bucket": "top_quartile",
      "primary_bucket": "D_neither",
      "primary_expectation_positive": false,
      "residual_state": "neutral",
      "ticker": "XOM",
      "watchlist_rank_improvement": -152
    },
    {
      "as_of_date": "2026-05-27",
      "combined_alpha_score": 0.66824,
      "combined_watchlist_alpha_score_rank": 297,
      "combined_watchlist_alpha_score_rank_bucket": "upper_mid",
      "expectation_residual_component_score": 0.0,
      "feature_context_date": "2026-05-27",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_10d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_5d_forward_price",
          "pnl_proxy": null,
          "return": null
        }
      },
      "old_alpha_score": 0.66824,
      "old_alpha_score_components": {
        "breadth_alignment": 0.6907,
        "expectation_revision": 0.6765,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.4603,
        "theme_participation": 0.3333,
        "trend": 0.9
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 14,
      "old_alpha_score_rank_bucket": "top_quartile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 151,
      "old_watchlist_alpha_score_rank_bucket": "top_quartile",
      "primary_bucket": "D_neither",
      "primary_expectation_positive": false,
      "residual_state": "beta_lagging",
      "ticker": "TSM",
      "watchlist_rank_improvement": -146
    },
    {
      "as_of_date": "2026-05-14",
      "combined_alpha_score": 0.667875,
      "combined_watchlist_alpha_score_rank": 298,
      "combined_watchlist_alpha_score_rank_bucket": "upper_mid",
      "expectation_residual_component_score": 0.0,
      "feature_context_date": "2026-05-14",
      "forward_outcomes": {
        "10d": {
          "closed": true,
          "future_date": "2026-05-24",
          "gap_reason": null,
          "pnl_proxy": -474.91,
          "return": -0.047491
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": true,
          "future_date": "2026-05-19",
          "gap_reason": null,
          "pnl_proxy": -721.94,
          "return": -0.072194
        }
      },
      "old_alpha_score": 0.667875,
      "old_alpha_score_components": {
        "breadth_alignment": 0.6595,
        "expectation_revision": 1.0,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.5596,
        "theme_participation": 0.5,
        "trend": 0.55
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 15,
      "old_alpha_score_rank_bucket": "upper_mid",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 152,
      "old_watchlist_alpha_score_rank_bucket": "top_quartile",
      "primary_bucket": "D_neither",
      "primary_expectation_positive": false,
      "residual_state": "neutral",
      "ticker": "GEV",
      "watchlist_rank_improvement": -146
    },
    {
      "as_of_date": "2026-05-10",
      "combined_alpha_score": 0.664715,
      "combined_watchlist_alpha_score_rank": 301,
      "combined_watchlist_alpha_score_rank_bucket": "upper_mid",
      "expectation_residual_component_score": 0.0,
      "feature_context_date": "2026-05-10",
      "forward_outcomes": {
        "10d": {
          "closed": true,
          "future_date": "2026-05-21",
          "gap_reason": null,
          "pnl_proxy": 420.6,
          "return": 0.04206
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": true,
          "future_date": "2026-05-16",
          "gap_reason": null,
          "pnl_proxy": 257.96,
          "return": 0.025796
        }
      },
      "old_alpha_score": 0.664715,
      "old_alpha_score_components": {
        "breadth_alignment": 0.7199,
        "expectation_revision": 0.6527,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.4594,
        "theme_participation": 0.3333,
        "trend": 0.9
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 11,
      "old_alpha_score_rank_bucket": "top_quartile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 160,
      "old_watchlist_alpha_score_rank_bucket": "top_quartile",
      "primary_bucket": "D_neither",
      "primary_expectation_positive": false,
      "residual_state": "neutral",
      "ticker": "AAPL",
      "watchlist_rank_improvement": -141
    },
    {
      "as_of_date": "2026-05-09",
      "combined_alpha_score": 0.664715,
      "combined_watchlist_alpha_score_rank": 300,
      "combined_watchlist_alpha_score_rank_bucket": "upper_mid",
      "expectation_residual_component_score": 0.0,
      "feature_context_date": "2026-05-09",
      "forward_outcomes": {
        "10d": {
          "closed": true,
          "future_date": "2026-05-21",
          "gap_reason": null,
          "pnl_proxy": 420.6,
          "return": 0.04206
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": true,
          "future_date": "2026-05-16",
          "gap_reason": null,
          "pnl_proxy": 257.96,
          "return": 0.025796
        }
      },
      "old_alpha_score": 0.664715,
      "old_alpha_score_components": {
        "breadth_alignment": 0.7199,
        "expectation_revision": 0.6527,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.4594,
        "theme_participation": 0.3333,
        "trend": 0.9
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 12,
      "old_alpha_score_rank_bucket": "top_quartile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 159,
      "old_watchlist_alpha_score_rank_bucket": "top_quartile",
      "primary_bucket": "D_neither",
      "primary_expectation_positive": false,
      "residual_state": "neutral",
      "ticker": "AAPL",
      "watchlist_rank_improvement": -141
    }
  ],
  "top_rank_improvers_sample": [
    {
      "as_of_date": "2026-05-26",
      "combined_alpha_score": 1.296925,
      "combined_watchlist_alpha_score_rank": 83,
      "combined_watchlist_alpha_score_rank_bucket": "top_quartile",
      "expectation_residual_component_score": 1.0,
      "feature_context_date": "2026-05-26",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_10d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_5d_forward_price",
          "pnl_proxy": null,
          "return": null
        }
      },
      "old_alpha_score": 0.296925,
      "old_alpha_score_components": {
        "breadth_alignment": 0.5,
        "expectation_revision": 0.6805,
        "post_earnings_drift": 0.5,
        "relative_strength": 0.0233,
        "theme_participation": 0.5,
        "trend": 0.1
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 55,
      "old_alpha_score_rank_bucket": "bottom_quartile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 668,
      "old_watchlist_alpha_score_rank_bucket": "bottom_quartile",
      "primary_bucket": "B_positive_expectation_only",
      "primary_expectation_positive": true,
      "residual_state": "beta_lagging",
      "ticker": "RBLX",
      "watchlist_rank_improvement": 585
    },
    {
      "as_of_date": "2026-05-27",
      "combined_alpha_score": 1.300775,
      "combined_watchlist_alpha_score_rank": 80,
      "combined_watchlist_alpha_score_rank_bucket": "top_quartile",
      "expectation_residual_component_score": 1.0,
      "feature_context_date": "2026-05-27",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_10d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_5d_forward_price",
          "pnl_proxy": null,
          "return": null
        }
      },
      "old_alpha_score": 0.300775,
      "old_alpha_score_components": {
        "breadth_alignment": 0.5,
        "expectation_revision": 0.6805,
        "post_earnings_drift": 0.5,
        "relative_strength": 0.0387,
        "theme_participation": 0.5,
        "trend": 0.1
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 55,
      "old_alpha_score_rank_bucket": "bottom_quartile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 660,
      "old_watchlist_alpha_score_rank_bucket": "bottom_quartile",
      "primary_bucket": "B_positive_expectation_only",
      "primary_expectation_positive": true,
      "residual_state": "beta_lagging",
      "ticker": "RBLX",
      "watchlist_rank_improvement": 580
    },
    {
      "as_of_date": "2026-05-25",
      "combined_alpha_score": 1.31195,
      "combined_watchlist_alpha_score_rank": 76,
      "combined_watchlist_alpha_score_rank_bucket": "top_quartile",
      "expectation_residual_component_score": 1.0,
      "feature_context_date": "2026-05-25",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_10d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_5d_forward_price",
          "pnl_proxy": null,
          "return": null
        }
      },
      "old_alpha_score": 0.31195,
      "old_alpha_score_components": {
        "breadth_alignment": 0.5,
        "expectation_revision": 0.6805,
        "post_earnings_drift": 0.5,
        "relative_strength": 0.0834,
        "theme_participation": 0.5,
        "trend": 0.1
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 52,
      "old_alpha_score_rank_bucket": "bottom_quartile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 651,
      "old_watchlist_alpha_score_rank_bucket": "bottom_quartile",
      "primary_bucket": "B_positive_expectation_only",
      "primary_expectation_positive": true,
      "residual_state": "beta_lagging",
      "ticker": "RBLX",
      "watchlist_rank_improvement": 575
    },
    {
      "as_of_date": "2026-05-24",
      "combined_alpha_score": 1.31885,
      "combined_watchlist_alpha_score_rank": 75,
      "combined_watchlist_alpha_score_rank_bucket": "top_decile",
      "expectation_residual_component_score": 1.0,
      "feature_context_date": "2026-05-24",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_10d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_5d_forward_price",
          "pnl_proxy": null,
          "return": null
        }
      },
      "old_alpha_score": 0.31885,
      "old_alpha_score_components": {
        "breadth_alignment": 0.5,
        "expectation_revision": 0.715,
        "post_earnings_drift": 0.5,
        "relative_strength": 0.0834,
        "theme_participation": 0.5,
        "trend": 0.1
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 51,
      "old_alpha_score_rank_bucket": "bottom_quartile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 641,
      "old_watchlist_alpha_score_rank_bucket": "bottom_quartile",
      "primary_bucket": "B_positive_expectation_only",
      "primary_expectation_positive": true,
      "residual_state": "beta_lagging",
      "ticker": "RBLX",
      "watchlist_rank_improvement": 566
    },
    {
      "as_of_date": "2026-05-20",
      "combined_alpha_score": 1.3402,
      "combined_watchlist_alpha_score_rank": 66,
      "combined_watchlist_alpha_score_rank_bucket": "top_decile",
      "expectation_residual_component_score": 1.0,
      "feature_context_date": "2026-05-20",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_10d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": true,
          "future_date": "2026-05-25",
          "gap_reason": null,
          "pnl_proxy": -103.77,
          "return": -0.010377
        }
      },
      "old_alpha_score": 0.3402,
      "old_alpha_score_components": {
        "breadth_alignment": 0.5,
        "expectation_revision": 0.676,
        "post_earnings_drift": 0.5,
        "relative_strength": 0.32,
        "theme_participation": 0.5,
        "trend": 0.0
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 46,
      "old_alpha_score_rank_bucket": "bottom_quartile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 604,
      "old_watchlist_alpha_score_rank_bucket": "bottom_quartile",
      "primary_bucket": "B_positive_expectation_only",
      "primary_expectation_positive": true,
      "residual_state": "beta_lagging",
      "ticker": "DIS",
      "watchlist_rank_improvement": 538
    },
    {
      "as_of_date": "2026-05-20",
      "combined_alpha_score": 1.341115,
      "combined_watchlist_alpha_score_rank": 65,
      "combined_watchlist_alpha_score_rank_bucket": "top_decile",
      "expectation_residual_component_score": 1.0,
      "feature_context_date": "2026-05-20",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_10d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": true,
          "future_date": "2026-05-25",
          "gap_reason": null,
          "pnl_proxy": -44.61,
          "return": -0.004461
        }
      },
      "old_alpha_score": 0.341115,
      "old_alpha_score_components": {
        "breadth_alignment": 0.5,
        "expectation_revision": 0.9512,
        "post_earnings_drift": 0.5,
        "relative_strength": 0.1035,
        "theme_participation": 0.5,
        "trend": 0.0
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 45,
      "old_alpha_score_rank_bucket": "bottom_quartile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 602,
      "old_watchlist_alpha_score_rank_bucket": "bottom_quartile",
      "primary_bucket": "B_positive_expectation_only",
      "primary_expectation_positive": true,
      "residual_state": "beta_lagging",
      "ticker": "SOFI",
      "watchlist_rank_improvement": 537
    },
    {
      "as_of_date": "2026-05-25",
      "combined_alpha_score": 1.380615,
      "combined_watchlist_alpha_score_rank": 57,
      "combined_watchlist_alpha_score_rank_bucket": "top_decile",
      "expectation_residual_component_score": 1.0,
      "feature_context_date": "2026-05-25",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_10d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_5d_forward_price",
          "pnl_proxy": null,
          "return": null
        }
      },
      "old_alpha_score": 0.380615,
      "old_alpha_score_components": {
        "breadth_alignment": 0.6623,
        "expectation_revision": 0.676,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.3292,
        "theme_participation": 0.5,
        "trend": 0.0
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 45,
      "old_alpha_score_rank_bucket": "bottom_quartile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 543,
      "old_watchlist_alpha_score_rank_bucket": "lower_mid",
      "primary_bucket": "B_positive_expectation_only",
      "primary_expectation_positive": true,
      "residual_state": "beta_lagging",
      "ticker": "DIS",
      "watchlist_rank_improvement": 486
    },
    {
      "as_of_date": "2026-05-24",
      "combined_alpha_score": 1.380615,
      "combined_watchlist_alpha_score_rank": 56,
      "combined_watchlist_alpha_score_rank_bucket": "top_decile",
      "expectation_residual_component_score": 1.0,
      "feature_context_date": "2026-05-24",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_10d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_5d_forward_price",
          "pnl_proxy": null,
          "return": null
        }
      },
      "old_alpha_score": 0.380615,
      "old_alpha_score_components": {
        "breadth_alignment": 0.6623,
        "expectation_revision": 0.676,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.3292,
        "theme_participation": 0.5,
        "trend": 0.0
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 45,
      "old_alpha_score_rank_bucket": "bottom_quartile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 542,
      "old_watchlist_alpha_score_rank_bucket": "lower_mid",
      "primary_bucket": "B_positive_expectation_only",
      "primary_expectation_positive": true,
      "residual_state": "beta_lagging",
      "ticker": "DIS",
      "watchlist_rank_improvement": 486
    },
    {
      "as_of_date": "2026-05-26",
      "combined_alpha_score": 1.382125,
      "combined_watchlist_alpha_score_rank": 54,
      "combined_watchlist_alpha_score_rank_bucket": "top_decile",
      "expectation_residual_component_score": 1.0,
      "feature_context_date": "2026-05-26",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_10d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_5d_forward_price",
          "pnl_proxy": null,
          "return": null
        }
      },
      "old_alpha_score": 0.382125,
      "old_alpha_score_components": {
        "breadth_alignment": 0.6695,
        "expectation_revision": 0.676,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.3338,
        "theme_participation": 0.5,
        "trend": 0.0
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 47,
      "old_alpha_score_rank_bucket": "bottom_quartile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 539,
      "old_watchlist_alpha_score_rank_bucket": "lower_mid",
      "primary_bucket": "B_positive_expectation_only",
      "primary_expectation_positive": true,
      "residual_state": "beta_lagging",
      "ticker": "DIS",
      "watchlist_rank_improvement": 485
    },
    {
      "as_of_date": "2026-05-15",
      "combined_alpha_score": 1.401945,
      "combined_watchlist_alpha_score_rank": 50,
      "combined_watchlist_alpha_score_rank_bucket": "top_decile",
      "expectation_residual_component_score": 1.0,
      "feature_context_date": "2026-05-15",
      "forward_outcomes": {
        "10d": {
          "closed": true,
          "future_date": "2026-05-25",
          "gap_reason": null,
          "pnl_proxy": 49.17,
          "return": 0.004917
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": true,
          "future_date": "2026-05-20",
          "gap_reason": null,
          "pnl_proxy": 73.76,
          "return": 0.007376
        }
      },
      "old_alpha_score": 0.401945,
      "old_alpha_score_components": {
        "breadth_alignment": 0.6509,
        "expectation_revision": 0.518,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.4232,
        "theme_participation": 0.5,
        "trend": 0.1
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 38,
      "old_alpha_score_rank_bucket": "lower_mid",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 508,
      "old_watchlist_alpha_score_rank_bucket": "lower_mid",
      "primary_bucket": "B_positive_expectation_only",
      "primary_expectation_positive": true,
      "residual_state": "neutral",
      "ticker": "NVO",
      "watchlist_rank_improvement": 458
    },
    {
      "as_of_date": "2026-05-14",
      "combined_alpha_score": 1.4067,
      "combined_watchlist_alpha_score_rank": 49,
      "combined_watchlist_alpha_score_rank_bucket": "top_decile",
      "expectation_residual_component_score": 1.0,
      "feature_context_date": "2026-05-14",
      "forward_outcomes": {
        "10d": {
          "closed": true,
          "future_date": "2026-05-24",
          "gap_reason": null,
          "pnl_proxy": -183.41,
          "return": -0.018341
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": true,
          "future_date": "2026-05-19",
          "gap_reason": null,
          "pnl_proxy": -331.88,
          "return": -0.033188
        }
      },
      "old_alpha_score": 0.4067,
      "old_alpha_score_components": {
        "breadth_alignment": 0.6595,
        "expectation_revision": 0.518,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.4405,
        "theme_participation": 0.5,
        "trend": 0.1
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 40,
      "old_alpha_score_rank_bucket": "lower_mid",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 495,
      "old_watchlist_alpha_score_rank_bucket": "lower_mid",
      "primary_bucket": "B_positive_expectation_only",
      "primary_expectation_positive": true,
      "residual_state": "neutral",
      "ticker": "NVO",
      "watchlist_rank_improvement": 446
    },
    {
      "as_of_date": "2026-05-10",
      "combined_alpha_score": 0.74657,
      "combined_watchlist_alpha_score_rank": 282,
      "combined_watchlist_alpha_score_rank_bucket": "upper_mid",
      "expectation_residual_component_score": 0.5,
      "feature_context_date": "2026-05-10",
      "forward_outcomes": {
        "10d": {
          "closed": true,
          "future_date": "2026-05-21",
          "gap_reason": null,
          "pnl_proxy": -1063.71,
          "return": -0.106371
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": true,
          "future_date": "2026-05-16",
          "gap_reason": null,
          "pnl_proxy": -977.38,
          "return": -0.097738
        }
      },
      "old_alpha_score": 0.24657,
      "old_alpha_score_components": {
        "breadth_alignment": 0.6724,
        "expectation_revision": 0.0,
        "post_earnings_drift": 0.5,
        "relative_strength": 0.5318,
        "theme_participation": 0.0,
        "trend": 0.1
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 56,
      "old_alpha_score_rank_bucket": "bottom_quartile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 713,
      "old_watchlist_alpha_score_rank_bucket": "bottom_quartile",
      "primary_bucket": "C_residual_leader_only",
      "primary_expectation_positive": false,
      "residual_state": "residual_leader",
      "ticker": "COIN",
      "watchlist_rank_improvement": 431
    },
    {
      "as_of_date": "2026-05-09",
      "combined_alpha_score": 0.74657,
      "combined_watchlist_alpha_score_rank": 281,
      "combined_watchlist_alpha_score_rank_bucket": "upper_mid",
      "expectation_residual_component_score": 0.5,
      "feature_context_date": "2026-05-09",
      "forward_outcomes": {
        "10d": {
          "closed": true,
          "future_date": "2026-05-21",
          "gap_reason": null,
          "pnl_proxy": -1063.71,
          "return": -0.106371
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": true,
          "future_date": "2026-05-16",
          "gap_reason": null,
          "pnl_proxy": -977.38,
          "return": -0.097738
        }
      },
      "old_alpha_score": 0.24657,
      "old_alpha_score_components": {
        "breadth_alignment": 0.6724,
        "expectation_revision": 0.0,
        "post_earnings_drift": 0.5,
        "relative_strength": 0.5318,
        "theme_participation": 0.0,
        "trend": 0.1
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 56,
      "old_alpha_score_rank_bucket": "bottom_quartile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 712,
      "old_watchlist_alpha_score_rank_bucket": "bottom_quartile",
      "primary_bucket": "C_residual_leader_only",
      "primary_expectation_positive": false,
      "residual_state": "residual_leader",
      "ticker": "COIN",
      "watchlist_rank_improvement": 431
    },
    {
      "as_of_date": "2026-05-14",
      "combined_alpha_score": 1.448215,
      "combined_watchlist_alpha_score_rank": 48,
      "combined_watchlist_alpha_score_rank_bucket": "top_decile",
      "expectation_residual_component_score": 1.0,
      "feature_context_date": "2026-05-14",
      "forward_outcomes": {
        "10d": {
          "closed": true,
          "future_date": "2026-05-24",
          "gap_reason": null,
          "pnl_proxy": -71.73,
          "return": -0.007173
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": true,
          "future_date": "2026-05-19",
          "gap_reason": null,
          "pnl_proxy": -170.25,
          "return": -0.017025
        }
      },
      "old_alpha_score": 0.448215,
      "old_alpha_score_components": {
        "breadth_alignment": 0.6595,
        "expectation_revision": 0.7252,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.4408,
        "theme_participation": 0.5,
        "trend": 0.1
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 37,
      "old_alpha_score_rank_bucket": "lower_mid",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 445,
      "old_watchlist_alpha_score_rank_bucket": "lower_mid",
      "primary_bucket": "B_positive_expectation_only",
      "primary_expectation_positive": true,
      "residual_state": "beta_lagging",
      "ticker": "APP",
      "watchlist_rank_improvement": 397
    },
    {
      "as_of_date": "2026-05-15",
      "combined_alpha_score": 1.451385,
      "combined_watchlist_alpha_score_rank": 47,
      "combined_watchlist_alpha_score_rank_bucket": "top_decile",
      "expectation_residual_component_score": 1.0,
      "feature_context_date": "2026-05-15",
      "forward_outcomes": {
        "10d": {
          "closed": true,
          "future_date": "2026-05-25",
          "gap_reason": null,
          "pnl_proxy": -385.63,
          "return": -0.038563
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": true,
          "future_date": "2026-05-20",
          "gap_reason": null,
          "pnl_proxy": -373.65,
          "return": -0.037365
        }
      },
      "old_alpha_score": 0.451385,
      "old_alpha_score_components": {
        "breadth_alignment": 0.6509,
        "expectation_revision": 0.7252,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.4552,
        "theme_participation": 0.5,
        "trend": 0.1
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 35,
      "old_alpha_score_rank_bucket": "lower_mid",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 440,
      "old_watchlist_alpha_score_rank_bucket": "lower_mid",
      "primary_bucket": "B_positive_expectation_only",
      "primary_expectation_positive": true,
      "residual_state": "neutral",
      "ticker": "APP",
      "watchlist_rank_improvement": 393
    },
    {
      "as_of_date": "2026-05-27",
      "combined_alpha_score": 1.46794,
      "combined_watchlist_alpha_score_rank": 45,
      "combined_watchlist_alpha_score_rank_bucket": "top_decile",
      "expectation_residual_component_score": 1.0,
      "feature_context_date": "2026-05-27",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_10d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_5d_forward_price",
          "pnl_proxy": null,
          "return": null
        }
      },
      "old_alpha_score": 0.46794,
      "old_alpha_score_components": {
        "breadth_alignment": 0.5,
        "expectation_revision": 0.6512,
        "post_earnings_drift": 0.5,
        "relative_strength": 0.3108,
        "theme_participation": 0.5,
        "trend": 0.45
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 34,
      "old_alpha_score_rank_bucket": "lower_mid",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 424,
      "old_watchlist_alpha_score_rank_bucket": "lower_mid",
      "primary_bucket": "B_positive_expectation_only",
      "primary_expectation_positive": true,
      "residual_state": "beta_lagging",
      "ticker": "XOM",
      "watchlist_rank_improvement": 379
    },
    {
      "as_of_date": "2026-05-09",
      "combined_alpha_score": 1.28752,
      "combined_watchlist_alpha_score_rank": 86,
      "combined_watchlist_alpha_score_rank_bucket": "top_quartile",
      "expectation_residual_component_score": 0.85,
      "feature_context_date": "2026-05-09",
      "forward_outcomes": {
        "10d": {
          "closed": true,
          "future_date": "2026-05-21",
          "gap_reason": null,
          "pnl_proxy": -433.19,
          "return": -0.043319
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": true,
          "future_date": "2026-05-16",
          "gap_reason": null,
          "pnl_proxy": -357.76,
          "return": -0.035776
        }
      },
      "old_alpha_score": 0.43752,
      "old_alpha_score_components": {
        "breadth_alignment": 0.6724,
        "expectation_revision": 0.518,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.5612,
        "theme_participation": 0.5,
        "trend": 0.1
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 41,
      "old_alpha_score_rank_bucket": "lower_mid",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 462,
      "old_watchlist_alpha_score_rank_bucket": "lower_mid",
      "primary_bucket": "C_residual_leader_only",
      "primary_expectation_positive": false,
      "residual_state": "strong_residual_leader",
      "ticker": "NVO",
      "watchlist_rank_improvement": 376
    },
    {
      "as_of_date": "2026-05-13",
      "combined_alpha_score": 0.572015,
      "combined_watchlist_alpha_score_rank": 367,
      "combined_watchlist_alpha_score_rank_bucket": "upper_mid",
      "expectation_residual_component_score": 0.35,
      "feature_context_date": "2026-05-13",
      "forward_outcomes": {
        "10d": {
          "closed": true,
          "future_date": "2026-05-23",
          "gap_reason": null,
          "pnl_proxy": -833.0,
          "return": -0.0833
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": true,
          "future_date": "2026-05-18",
          "gap_reason": null,
          "pnl_proxy": -612.49,
          "return": -0.061249
        }
      },
      "old_alpha_score": 0.222015,
      "old_alpha_score_components": {
        "breadth_alignment": 0.6638,
        "expectation_revision": 0.0,
        "post_earnings_drift": 0.5,
        "relative_strength": 0.4353,
        "theme_participation": 0.0,
        "trend": 0.1
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 57,
      "old_alpha_score_rank_bucket": "bottom_quartile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 724,
      "old_watchlist_alpha_score_rank_bucket": "bottom_quartile",
      "primary_bucket": "D_neither",
      "primary_expectation_positive": false,
      "residual_state": "beta_lagging",
      "ticker": "COIN",
      "watchlist_rank_improvement": 357
    },
    {
      "as_of_date": "2026-05-20",
      "combined_alpha_score": 0.651585,
      "combined_watchlist_alpha_score_rank": 303,
      "combined_watchlist_alpha_score_rank_bucket": "upper_mid",
      "expectation_residual_component_score": 0.35,
      "feature_context_date": "2026-05-20",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_10d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": true,
          "future_date": "2026-05-25",
          "gap_reason": null,
          "pnl_proxy": 1997.14,
          "return": 0.199714
        }
      },
      "old_alpha_score": 0.301585,
      "old_alpha_score_components": {
        "breadth_alignment": 0.5,
        "expectation_revision": 0.5593,
        "post_earnings_drift": 0.5,
        "relative_strength": 0.1389,
        "theme_participation": 0.5,
        "trend": 0.1
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 50,
      "old_alpha_score_rank_bucket": "bottom_quartile",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 659,
      "old_watchlist_alpha_score_rank_bucket": "bottom_quartile",
      "primary_bucket": "D_neither",
      "primary_expectation_positive": false,
      "residual_state": "beta_lagging",
      "ticker": "SPOT",
      "watchlist_rank_improvement": 356
    },
    {
      "as_of_date": "2026-05-20",
      "combined_alpha_score": 2.022275,
      "combined_watchlist_alpha_score_rank": 23,
      "combined_watchlist_alpha_score_rank_bucket": "top_decile",
      "expectation_residual_component_score": 1.5,
      "feature_context_date": "2026-05-20",
      "forward_outcomes": {
        "10d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_10d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "20d": {
          "closed": false,
          "future_date": null,
          "gap_reason": "missing_20d_forward_price",
          "pnl_proxy": null,
          "return": null
        },
        "5d": {
          "closed": true,
          "future_date": "2026-05-25",
          "gap_reason": null,
          "pnl_proxy": -364.25,
          "return": -0.036425
        }
      },
      "old_alpha_score": 0.522275,
      "old_alpha_score_components": {
        "breadth_alignment": 0.636,
        "expectation_revision": 0.615,
        "post_earnings_drift": 0.8,
        "relative_strength": 0.4899,
        "theme_participation": 0.0,
        "trend": 0.55
      },
      "old_alpha_score_join_status": "joined",
      "old_alpha_score_rank": 23,
      "old_alpha_score_rank_bucket": "upper_mid",
      "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
      "old_watchlist_alpha_score_rank": 377,
      "old_watchlist_alpha_score_rank_bucket": "lower_mid",
      "primary_bucket": "A_positive_expectation_and_residual_leader",
      "primary_expectation_positive": true,
      "residual_state": "residual_leader",
      "ticker": "NVDA",
      "watchlist_rank_improvement": 354
    }
  ],
  "watchlist_rank_improvement_summary": {
    "avg": 0.0,
    "count": 751,
    "max": 585.0,
    "min": -251.0
  }
}
```

## Next Evidence Needed

Run a true observed-only ranking replacement experiment that compares old_alpha_score buckets against old_alpha_score + expectation_residual_component_score buckets on the full per-date ranking surface, then require a separate Gate 1-4 strategy experiment before any production ranking change.

No JavaScript was used.
