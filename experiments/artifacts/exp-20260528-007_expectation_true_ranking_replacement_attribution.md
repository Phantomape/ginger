# exp-20260528-007 Expectation True Ranking Replacement Attribution

- status: `observed_only`
- decision: `observed_only_no_promotable_edge`
- changed_variable: `old_alpha_score_plus_expectation_residual_component_v1`
- gate_reason: `combined_score_failed_directional_or_concentration_gate`

## Summary

Observed-only true ranking replacement attribution. For each feature_context_date with expectation watchlist coverage, the script ranks the full daily surface by old_alpha_score and by old_alpha_score + expectation_residual_component_score, then compares top-decile and new-vs-dropped replacement buckets.

## Gate

```json
{
  "comparisons": [
    {
      "combined_top_avg_return": -0.01286,
      "combined_top_total_pnl_proxy": -7072.93,
      "dropped_old_avg_return": -0.004628,
      "dropped_old_total_pnl_proxy": -1203.18,
      "horizon": "5d",
      "new_combined_avg_return": 0.004382,
      "new_combined_total_pnl_proxy": 1139.38,
      "old_top_avg_return": -0.017119,
      "old_top_total_pnl_proxy": -9415.49,
      "replacement_passed": true,
      "top_decile_passed": true
    },
    {
      "combined_top_avg_return": -0.002359,
      "combined_top_total_pnl_proxy": -943.64,
      "dropped_old_avg_return": 0.015522,
      "dropped_old_total_pnl_proxy": 2173.06,
      "horizon": "10d",
      "new_combined_avg_return": -0.002841,
      "new_combined_total_pnl_proxy": -397.74,
      "old_top_avg_return": 0.004068,
      "old_top_total_pnl_proxy": 1627.16,
      "replacement_passed": false,
      "top_decile_passed": false
    }
  ],
  "concentration": {
    "combined_top_decile": {
      "10d": {
        "avg_pnl_proxy": -23.59,
        "avg_return": -0.002359,
        "closed_outcomes": 40,
        "max_single_ticker_positive_share": 0.487878,
        "positive_pnl_by_ticker": {
          "AMD": 1419.62,
          "APLD": 1210.84,
          "APP": 156.14,
          "BE": 776.66,
          "DDOG": 4968.3,
          "LLY": 579.12,
          "MTSI": 1072.8
        },
        "tail_loss": -0.134086,
        "top5_positive_contribution_share": 0.444386,
        "total_pnl_proxy": -943.64,
        "win_rate": 0.4,
        "worst_row": {
          "combined_alpha_score": 1.31932,
          "combined_daily_alpha_score_rank": 1,
          "combined_daily_alpha_score_rank_bucket": "top_decile",
          "daily_rank_improvement": 0,
          "expectation_residual_component_score": 0.5,
          "expectation_watchlist_join_status": "joined",
          "feature_context_date": "2026-05-08",
          "forward_return": -0.134086,
          "future_date": "2026-05-18",
          "gap_reason": null,
          "old_alpha_score": 0.81932,
          "old_daily_alpha_score_rank": 1,
          "old_daily_alpha_score_rank_bucket": "top_decile",
          "pnl_proxy": -1340.86,
          "primary_bucket": "C_residual_leader_only",
          "replacement_bucket": "retained_top_decile",
          "residual_state": "strong_residual_leader",
          "signal_effective_trade_date": "2026-05-08",
          "ticker": "INTC",
          "watchlist_signal_basis": [
            "none"
          ]
        }
      },
      "5d": {
        "avg_pnl_proxy": -128.6,
        "avg_return": -0.01286,
        "closed_outcomes": 55,
        "max_single_ticker_positive_share": 0.220577,
        "positive_pnl_by_ticker": {
          "AAPL": 915.48,
          "AMD": 553.64,
          "APP": 471.97,
          "BE": 1100.64,
          "CAT": 498.0,
          "COHR": 1615.17,
          "DDOG": 2263.65,
          "LLY": 146.12,
          "MTSI": 534.25,
          "MU": 1768.46,
          "TSLA": 395.0
        },
        "tail_loss": -0.181001,
        "top5_positive_contribution_share": 0.383232,
        "total_pnl_proxy": -7072.93,
        "win_rate": 0.490909,
        "worst_row": {
          "combined_alpha_score": 1.37061,
          "combined_daily_alpha_score_rank": 1,
          "combined_daily_alpha_score_rank_bucket": "top_decile",
          "daily_rank_improvement": 0,
          "expectation_residual_component_score": 0.5,
          "expectation_watchlist_join_status": "joined",
          "feature_context_date": "2026-05-11",
          "forward_return": -0.181001,
          "future_date": "2026-05-16",
          "gap_reason": null,
          "old_alpha_score": 0.87061,
          "old_daily_alpha_score_rank": 1,
          "old_daily_alpha_score_rank_bucket": "top_decile",
          "pnl_proxy": -1810.01,
          "primary_bucket": "C_residual_leader_only",
          "replacement_bucket": "retained_top_decile",
          "residual_state": "strong_residual_leader",
          "signal_effective_trade_date": "2026-05-11",
          "ticker": "CRDO",
          "watchlist_signal_basis": [
            "none"
          ]
        }
      }
    },
    "max_single_ticker_positive_share": 0.5,
    "max_top5_positive_share": 0.6,
    "passed": true
  },
  "data_gap_reasons": [],
  "decision": "observed_only_no_promotable_edge",
  "promotion_gate_passed": false,
  "ranking_replacement_attribution_passed": false,
  "reason": "combined_score_failed_directional_or_concentration_gate",
  "thresholds": {
    "max_single_ticker_positive_share": 0.5,
    "max_top5_positive_share": 0.6,
    "min_replacement_closed_10d": 8,
    "min_replacement_closed_5d": 10,
    "min_top_closed_10d": 20,
    "min_top_closed_5d": 30
  }
}
```

## Coverage

```json
{
  "closed_forward_outcomes": {
    "10d": 457,
    "20d": 0,
    "5d": 634
  },
  "combined_rank_bucket_counts": {
    "bottom_quartile": 225,
    "lower_mid": 212,
    "top_decile": 75,
    "top_quartile": 135,
    "upper_mid": 220
  },
  "evaluated_feature_dates": [
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
  ],
  "field_coverage": {
    "combined_alpha_score": {
      "coverage_ratio": 1.0,
      "missing_rows": 0,
      "present_rows": 867
    },
    "combined_daily_alpha_score_rank": {
      "coverage_ratio": 1.0,
      "missing_rows": 0,
      "present_rows": 867
    },
    "expectation_residual_component_score": {
      "coverage_ratio": 1.0,
      "missing_rows": 0,
      "present_rows": 867
    },
    "feature_context_date": {
      "coverage_ratio": 1.0,
      "missing_rows": 0,
      "present_rows": 867
    },
    "forward_outcomes": {
      "coverage_ratio": 1.0,
      "missing_rows": 0,
      "present_rows": 867
    },
    "old_alpha_score": {
      "coverage_ratio": 1.0,
      "missing_rows": 0,
      "present_rows": 867
    },
    "old_daily_alpha_score_rank": {
      "coverage_ratio": 1.0,
      "missing_rows": 0,
      "present_rows": 867
    },
    "replacement_bucket": {
      "coverage_ratio": 1.0,
      "missing_rows": 0,
      "present_rows": 867
    },
    "signal_effective_trade_date": {
      "coverage_ratio": 1.0,
      "missing_rows": 0,
      "present_rows": 867
    }
  },
  "join_status_counts": {
    "joined": 751,
    "missing_watchlist_row": 116
  },
  "old_rank_bucket_counts": {
    "bottom_quartile": 225,
    "lower_mid": 212,
    "top_decile": 75,
    "top_quartile": 135,
    "upper_mid": 220
  },
  "ranking_surface_feature_date_count": 49,
  "replacement_bucket_counts": {
    "neither_top_decile": 753,
    "new_combined_top_decile": 39,
    "old_top_decile_dropped": 39,
    "retained_top_decile": 36
  },
  "surface_rebuild_failures": {},
  "surface_rows_total": 867,
  "watchlist_date_count": 15,
  "watchlist_rows_total": 751
}
```

## Selection Summary

```json
{
  "combined_top_decile": {
    "date_count": 15,
    "horizons": {
      "10d": {
        "avg_pnl_proxy": -23.59,
        "avg_return": -0.002359,
        "closed_outcomes": 40,
        "max_single_ticker_positive_share": 0.487878,
        "positive_pnl_by_ticker": {
          "AMD": 1419.62,
          "APLD": 1210.84,
          "APP": 156.14,
          "BE": 776.66,
          "DDOG": 4968.3,
          "LLY": 579.12,
          "MTSI": 1072.8
        },
        "tail_loss": -0.134086,
        "top5_positive_contribution_share": 0.444386,
        "total_pnl_proxy": -943.64,
        "win_rate": 0.4,
        "worst_row": {
          "combined_alpha_score": 1.31932,
          "combined_daily_alpha_score_rank": 1,
          "combined_daily_alpha_score_rank_bucket": "top_decile",
          "daily_rank_improvement": 0,
          "expectation_residual_component_score": 0.5,
          "expectation_watchlist_join_status": "joined",
          "feature_context_date": "2026-05-08",
          "forward_return": -0.134086,
          "future_date": "2026-05-18",
          "gap_reason": null,
          "old_alpha_score": 0.81932,
          "old_daily_alpha_score_rank": 1,
          "old_daily_alpha_score_rank_bucket": "top_decile",
          "pnl_proxy": -1340.86,
          "primary_bucket": "C_residual_leader_only",
          "replacement_bucket": "retained_top_decile",
          "residual_state": "strong_residual_leader",
          "signal_effective_trade_date": "2026-05-08",
          "ticker": "INTC",
          "watchlist_signal_basis": [
            "none"
          ]
        }
      },
      "20d": {
        "avg_pnl_proxy": null,
        "avg_return": null,
        "closed_outcomes": 0,
        "max_single_ticker_positive_share": null,
        "positive_pnl_by_ticker": {},
        "tail_loss": null,
        "top5_positive_contribution_share": null,
        "total_pnl_proxy": null,
        "win_rate": null,
        "worst_row": null
      },
      "5d": {
        "avg_pnl_proxy": -128.6,
        "avg_return": -0.01286,
        "closed_outcomes": 55,
        "max_single_ticker_positive_share": 0.220577,
        "positive_pnl_by_ticker": {
          "AAPL": 915.48,
          "AMD": 553.64,
          "APP": 471.97,
          "BE": 1100.64,
          "CAT": 498.0,
          "COHR": 1615.17,
          "DDOG": 2263.65,
          "LLY": 146.12,
          "MTSI": 534.25,
          "MU": 1768.46,
          "TSLA": 395.0
        },
        "tail_loss": -0.181001,
        "top5_positive_contribution_share": 0.383232,
        "total_pnl_proxy": -7072.93,
        "win_rate": 0.490909,
        "worst_row": {
          "combined_alpha_score": 1.37061,
          "combined_daily_alpha_score_rank": 1,
          "combined_daily_alpha_score_rank_bucket": "top_decile",
          "daily_rank_improvement": 0,
          "expectation_residual_component_score": 0.5,
          "expectation_watchlist_join_status": "joined",
          "feature_context_date": "2026-05-11",
          "forward_return": -0.181001,
          "future_date": "2026-05-16",
          "gap_reason": null,
          "old_alpha_score": 0.87061,
          "old_daily_alpha_score_rank": 1,
          "old_daily_alpha_score_rank_bucket": "top_decile",
          "pnl_proxy": -1810.01,
          "primary_bucket": "C_residual_leader_only",
          "replacement_bucket": "retained_top_decile",
          "residual_state": "strong_residual_leader",
          "signal_effective_trade_date": "2026-05-11",
          "ticker": "CRDO",
          "watchlist_signal_basis": [
            "none"
          ]
        }
      }
    },
    "join_status_counts": {
      "joined": 75
    },
    "primary_bucket_counts": {
      "A_positive_expectation_and_residual_leader": 21,
      "B_positive_expectation_only": 21,
      "C_residual_leader_only": 33
    },
    "replacement_bucket_counts": {
      "new_combined_top_decile": 39,
      "retained_top_decile": 36
    },
    "row_count": 75,
    "ticker_count": 23,
    "tickers": [
      "AAPL",
      "AMD",
      "APLD",
      "APP",
      "BE",
      "CAT",
      "COHR",
      "CRDO",
      "CVX",
      "DDOG",
      "DIS",
      "GOOG",
      "INTC",
      "LLY",
      "MRVL",
      "MTSI",
      "MU",
      "NVDA",
      "RBLX",
      "SNOW",
      "TSLA",
      "UNH",
      "XOM"
    ]
  },
  "new_combined_top_decile": {
    "date_count": 12,
    "horizons": {
      "10d": {
        "avg_pnl_proxy": -28.41,
        "avg_return": -0.002841,
        "closed_outcomes": 14,
        "max_single_ticker_positive_share": 0.583908,
        "positive_pnl_by_ticker": {
          "AMD": 1419.62,
          "APP": 156.14,
          "LLY": 579.12,
          "MTSI": 276.36
        },
        "tail_loss": -0.086578,
        "top5_positive_contribution_share": 1.0,
        "total_pnl_proxy": -397.74,
        "win_rate": 0.357143,
        "worst_row": {
          "combined_alpha_score": 2.195755,
          "combined_daily_alpha_score_rank": 2,
          "combined_daily_alpha_score_rank_bucket": "top_decile",
          "daily_rank_improvement": 9,
          "expectation_residual_component_score": 1.5,
          "expectation_watchlist_join_status": "joined",
          "feature_context_date": "2026-05-14",
          "forward_return": -0.086578,
          "future_date": "2026-05-24",
          "gap_reason": null,
          "old_alpha_score": 0.695755,
          "old_daily_alpha_score_rank": 11,
          "old_daily_alpha_score_rank_bucket": "top_quartile",
          "pnl_proxy": -865.78,
          "primary_bucket": "A_positive_expectation_and_residual_leader",
          "replacement_bucket": "new_combined_top_decile",
          "residual_state": "residual_leader",
          "signal_effective_trade_date": "2026-05-14",
          "ticker": "NVDA",
          "watchlist_signal_basis": [
            "primary_7d"
          ]
        }
      },
      "20d": {
        "avg_pnl_proxy": null,
        "avg_return": null,
        "closed_outcomes": 0,
        "max_single_ticker_positive_share": null,
        "positive_pnl_by_ticker": {},
        "tail_loss": null,
        "top5_positive_contribution_share": null,
        "total_pnl_proxy": null,
        "win_rate": null,
        "worst_row": null
      },
      "5d": {
        "avg_pnl_proxy": 43.82,
        "avg_return": 0.004382,
        "closed_outcomes": 26,
        "max_single_ticker_positive_share": 0.283415,
        "positive_pnl_by_ticker": {
          "AAPL": 915.48,
          "AMD": 553.64,
          "APP": 471.97,
          "BE": 1100.64,
          "CAT": 498.0,
          "COHR": 1615.17,
          "LLY": 146.12,
          "MTSI": 2.93,
          "TSLA": 395.0
        },
        "tail_loss": -0.079275,
        "top5_positive_contribution_share": 0.585225,
        "total_pnl_proxy": 1139.38,
        "win_rate": 0.576923,
        "worst_row": {
          "combined_alpha_score": 2.207615,
          "combined_daily_alpha_score_rank": 1,
          "combined_daily_alpha_score_rank_bucket": "top_decile",
          "daily_rank_improvement": 7,
          "expectation_residual_component_score": 1.5,
          "expectation_watchlist_join_status": "joined",
          "feature_context_date": "2026-05-14",
          "forward_return": -0.079275,
          "future_date": "2026-05-19",
          "gap_reason": null,
          "old_alpha_score": 0.707615,
          "old_daily_alpha_score_rank": 8,
          "old_daily_alpha_score_rank_bucket": "top_quartile",
          "pnl_proxy": -792.75,
          "primary_bucket": "A_positive_expectation_and_residual_leader",
          "replacement_bucket": "new_combined_top_decile",
          "residual_state": "strong_residual_leader",
          "signal_effective_trade_date": "2026-05-14",
          "ticker": "AMD",
          "watchlist_signal_basis": [
            "primary_7d"
          ]
        }
      }
    },
    "join_status_counts": {
      "joined": 39
    },
    "primary_bucket_counts": {
      "A_positive_expectation_and_residual_leader": 13,
      "B_positive_expectation_only": 21,
      "C_residual_leader_only": 5
    },
    "replacement_bucket_counts": {
      "new_combined_top_decile": 39
    },
    "row_count": 39,
    "ticker_count": 16,
    "tickers": [
      "AAPL",
      "AMD",
      "APP",
      "BE",
      "CAT",
      "COHR",
      "CVX",
      "DIS",
      "LLY",
      "MRVL",
      "MTSI",
      "NVDA",
      "RBLX",
      "SNOW",
      "TSLA",
      "XOM"
    ]
  },
  "old_top_decile": {
    "date_count": 15,
    "horizons": {
      "10d": {
        "avg_pnl_proxy": 40.68,
        "avg_return": 0.004068,
        "closed_outcomes": 40,
        "max_single_ticker_positive_share": 0.447121,
        "positive_pnl_by_ticker": {
          "APLD": 1988.57,
          "BE": 1738.43,
          "DDOG": 5400.95,
          "INTC": 1355.01,
          "MRVL": 753.09,
          "MTSI": 796.44,
          "WDC": 46.89
        },
        "tail_loss": -0.134086,
        "top5_positive_contribution_share": 0.389513,
        "total_pnl_proxy": 1627.16,
        "win_rate": 0.45,
        "worst_row": {
          "combined_alpha_score": 1.31932,
          "combined_daily_alpha_score_rank": 1,
          "combined_daily_alpha_score_rank_bucket": "top_decile",
          "daily_rank_improvement": 0,
          "expectation_residual_component_score": 0.5,
          "expectation_watchlist_join_status": "joined",
          "feature_context_date": "2026-05-08",
          "forward_return": -0.134086,
          "future_date": "2026-05-18",
          "gap_reason": null,
          "old_alpha_score": 0.81932,
          "old_daily_alpha_score_rank": 1,
          "old_daily_alpha_score_rank_bucket": "top_decile",
          "pnl_proxy": -1340.86,
          "primary_bucket": "C_residual_leader_only",
          "replacement_bucket": "retained_top_decile",
          "residual_state": "strong_residual_leader",
          "signal_effective_trade_date": "2026-05-08",
          "ticker": "INTC",
          "watchlist_signal_basis": [
            "none"
          ]
        }
      },
      "20d": {
        "avg_pnl_proxy": null,
        "avg_return": null,
        "closed_outcomes": 0,
        "max_single_ticker_positive_share": null,
        "positive_pnl_by_ticker": {},
        "tail_loss": null,
        "top5_positive_contribution_share": null,
        "total_pnl_proxy": null,
        "win_rate": null,
        "worst_row": null
      },
      "5d": {
        "avg_pnl_proxy": -171.19,
        "avg_return": -0.017119,
        "closed_outcomes": 55,
        "max_single_ticker_positive_share": 0.240903,
        "positive_pnl_by_ticker": {
          "APLD": 2744.92,
          "BE": 945.3,
          "DDOG": 3329.13,
          "GS": 148.76,
          "INTC": 2905.55,
          "LLY": 426.76,
          "MTSI": 531.32,
          "MU": 2787.62
        },
        "tail_loss": -0.216014,
        "top5_positive_contribution_share": 0.418238,
        "total_pnl_proxy": -9415.49,
        "win_rate": 0.472727,
        "worst_row": {
          "combined_alpha_score": 1.356675,
          "combined_daily_alpha_score_rank": 8,
          "combined_daily_alpha_score_rank_bucket": "top_quartile",
          "daily_rank_improvement": -6,
          "expectation_residual_component_score": 0.5,
          "expectation_watchlist_join_status": "joined",
          "feature_context_date": "2026-05-14",
          "forward_return": -0.216014,
          "future_date": "2026-05-19",
          "gap_reason": null,
          "old_alpha_score": 0.856675,
          "old_daily_alpha_score_rank": 2,
          "old_daily_alpha_score_rank_bucket": "top_decile",
          "pnl_proxy": -2160.14,
          "primary_bucket": "C_residual_leader_only",
          "replacement_bucket": "old_top_decile_dropped",
          "residual_state": "strong_residual_leader",
          "signal_effective_trade_date": "2026-05-14",
          "ticker": "APLD",
          "watchlist_signal_basis": [
            "none"
          ]
        }
      }
    },
    "join_status_counts": {
      "joined": 72,
      "missing_watchlist_row": 3
    },
    "primary_bucket_counts": {
      "A_positive_expectation_and_residual_leader": 8,
      "C_residual_leader_only": 59,
      "D_neither": 5,
      "missing_watchlist_row": 3
    },
    "replacement_bucket_counts": {
      "old_top_decile_dropped": 39,
      "retained_top_decile": 36
    },
    "row_count": 75,
    "ticker_count": 17,
    "tickers": [
      "AMD",
      "APLD",
      "BE",
      "COHR",
      "CRDO",
      "CVX",
      "DDOG",
      "GOOG",
      "GS",
      "INTC",
      "LLY",
      "MRVL",
      "MTSI",
      "MU",
      "RKLB",
      "UNH",
      "WDC"
    ]
  },
  "old_top_decile_dropped": {
    "date_count": 12,
    "horizons": {
      "10d": {
        "avg_pnl_proxy": 155.22,
        "avg_return": 0.015522,
        "closed_outcomes": 14,
        "max_single_ticker_positive_share": 0.313142,
        "positive_pnl_by_ticker": {
          "APLD": 777.73,
          "BE": 961.77,
          "DDOG": 432.65,
          "INTC": 1355.01,
          "MRVL": 753.09,
          "WDC": 46.89
        },
        "tail_loss": -0.06549,
        "top5_positive_contribution_share": 0.911221,
        "total_pnl_proxy": 2173.06,
        "win_rate": 0.5,
        "worst_row": {
          "combined_alpha_score": 1.27755,
          "combined_daily_alpha_score_rank": 7,
          "combined_daily_alpha_score_rank_bucket": "top_quartile",
          "daily_rank_improvement": -2,
          "expectation_residual_component_score": 0.5,
          "expectation_watchlist_join_status": "joined",
          "feature_context_date": "2026-05-13",
          "forward_return": -0.06549,
          "future_date": "2026-05-23",
          "gap_reason": null,
          "old_alpha_score": 0.77755,
          "old_daily_alpha_score_rank": 5,
          "old_daily_alpha_score_rank_bucket": "top_decile",
          "pnl_proxy": -654.9,
          "primary_bucket": "C_residual_leader_only",
          "replacement_bucket": "old_top_decile_dropped",
          "residual_state": "strong_residual_leader",
          "signal_effective_trade_date": "2026-05-13",
          "ticker": "MU",
          "watchlist_signal_basis": [
            "none"
          ]
        }
      },
      "20d": {
        "avg_pnl_proxy": null,
        "avg_return": null,
        "closed_outcomes": 0,
        "max_single_ticker_positive_share": null,
        "positive_pnl_by_ticker": {},
        "tail_loss": null,
        "top5_positive_contribution_share": null,
        "total_pnl_proxy": null,
        "win_rate": null,
        "worst_row": null
      },
      "5d": {
        "avg_pnl_proxy": -46.28,
        "avg_return": -0.004628,
        "closed_outcomes": 26,
        "max_single_ticker_positive_share": 0.313912,
        "positive_pnl_by_ticker": {
          "APLD": 2744.92,
          "BE": 945.3,
          "DDOG": 1065.48,
          "GS": 148.76,
          "INTC": 2905.55,
          "LLY": 426.76,
          "MU": 1019.16
        },
        "tail_loss": -0.216014,
        "top5_positive_contribution_share": 0.624441,
        "total_pnl_proxy": -1203.18,
        "win_rate": 0.538462,
        "worst_row": {
          "combined_alpha_score": 1.356675,
          "combined_daily_alpha_score_rank": 8,
          "combined_daily_alpha_score_rank_bucket": "top_quartile",
          "daily_rank_improvement": -6,
          "expectation_residual_component_score": 0.5,
          "expectation_watchlist_join_status": "joined",
          "feature_context_date": "2026-05-14",
          "forward_return": -0.216014,
          "future_date": "2026-05-19",
          "gap_reason": null,
          "old_alpha_score": 0.856675,
          "old_daily_alpha_score_rank": 2,
          "old_daily_alpha_score_rank_bucket": "top_decile",
          "pnl_proxy": -2160.14,
          "primary_bucket": "C_residual_leader_only",
          "replacement_bucket": "old_top_decile_dropped",
          "residual_state": "strong_residual_leader",
          "signal_effective_trade_date": "2026-05-14",
          "ticker": "APLD",
          "watchlist_signal_basis": [
            "none"
          ]
        }
      }
    },
    "join_status_counts": {
      "joined": 36,
      "missing_watchlist_row": 3
    },
    "primary_bucket_counts": {
      "C_residual_leader_only": 31,
      "D_neither": 5,
      "missing_watchlist_row": 3
    },
    "replacement_bucket_counts": {
      "old_top_decile_dropped": 39
    },
    "row_count": 39,
    "ticker_count": 12,
    "tickers": [
      "APLD",
      "BE",
      "CRDO",
      "CVX",
      "DDOG",
      "GS",
      "INTC",
      "LLY",
      "MRVL",
      "MU",
      "RKLB",
      "WDC"
    ]
  },
  "retained_top_decile": {
    "date_count": 14,
    "horizons": {
      "10d": {
        "avg_pnl_proxy": -21.0,
        "avg_return": -0.0021,
        "closed_outcomes": 26,
        "max_single_ticker_positive_share": 0.640886,
        "positive_pnl_by_ticker": {
          "APLD": 1210.84,
          "BE": 776.66,
          "DDOG": 4968.3,
          "MTSI": 796.44
        },
        "tail_loss": -0.134086,
        "top5_positive_contribution_share": 0.551945,
        "total_pnl_proxy": -545.9,
        "win_rate": 0.423077,
        "worst_row": {
          "combined_alpha_score": 1.31932,
          "combined_daily_alpha_score_rank": 1,
          "combined_daily_alpha_score_rank_bucket": "top_decile",
          "daily_rank_improvement": 0,
          "expectation_residual_component_score": 0.5,
          "expectation_watchlist_join_status": "joined",
          "feature_context_date": "2026-05-08",
          "forward_return": -0.134086,
          "future_date": "2026-05-18",
          "gap_reason": null,
          "old_alpha_score": 0.81932,
          "old_daily_alpha_score_rank": 1,
          "old_daily_alpha_score_rank_bucket": "top_decile",
          "pnl_proxy": -1340.86,
          "primary_bucket": "C_residual_leader_only",
          "replacement_bucket": "retained_top_decile",
          "residual_state": "strong_residual_leader",
          "signal_effective_trade_date": "2026-05-08",
          "ticker": "INTC",
          "watchlist_signal_basis": [
            "none"
          ]
        }
      },
      "20d": {
        "avg_pnl_proxy": null,
        "avg_return": null,
        "closed_outcomes": 0,
        "max_single_ticker_positive_share": null,
        "positive_pnl_by_ticker": {},
        "tail_loss": null,
        "top5_positive_contribution_share": null,
        "total_pnl_proxy": null,
        "win_rate": null,
        "worst_row": null
      },
      "5d": {
        "avg_pnl_proxy": -283.18,
        "avg_return": -0.028318,
        "closed_outcomes": 29,
        "max_single_ticker_positive_share": 0.496041,
        "positive_pnl_by_ticker": {
          "DDOG": 2263.65,
          "MTSI": 531.32,
          "MU": 1768.46
        },
        "tail_loss": -0.181001,
        "top5_positive_contribution_share": 0.621708,
        "total_pnl_proxy": -8212.31,
        "win_rate": 0.413793,
        "worst_row": {
          "combined_alpha_score": 1.37061,
          "combined_daily_alpha_score_rank": 1,
          "combined_daily_alpha_score_rank_bucket": "top_decile",
          "daily_rank_improvement": 0,
          "expectation_residual_component_score": 0.5,
          "expectation_watchlist_join_status": "joined",
          "feature_context_date": "2026-05-11",
          "forward_return": -0.181001,
          "future_date": "2026-05-16",
          "gap_reason": null,
          "old_alpha_score": 0.87061,
          "old_daily_alpha_score_rank": 1,
          "old_daily_alpha_score_rank_bucket": "top_decile",
          "pnl_proxy": -1810.01,
          "primary_bucket": "C_residual_leader_only",
          "replacement_bucket": "retained_top_decile",
          "residual_state": "strong_residual_leader",
          "signal_effective_trade_date": "2026-05-11",
          "ticker": "CRDO",
          "watchlist_signal_basis": [
            "none"
          ]
        }
      }
    },
    "join_status_counts": {
      "joined": 36
    },
    "primary_bucket_counts": {
      "A_positive_expectation_and_residual_leader": 8,
      "C_residual_leader_only": 28
    },
    "replacement_bucket_counts": {
      "retained_top_decile": 36
    },
    "row_count": 36,
    "ticker_count": 11,
    "tickers": [
      "AMD",
      "APLD",
      "BE",
      "COHR",
      "CRDO",
      "DDOG",
      "GOOG",
      "INTC",
      "MTSI",
      "MU",
      "UNH"
    ]
  }
}
```

## Next Evidence Needed

If promising, create a separate default-off or strategy Gate 1-4 experiment with shared production-visible ranking logic. If not promising, do not promote this simple additive expectation/residual component; pivot to PEAD eligibility or richer expectation fields.

No JavaScript was used.
