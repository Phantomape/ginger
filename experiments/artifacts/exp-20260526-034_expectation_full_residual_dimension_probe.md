# exp-20260526-034 Full Residual Dimension Probe

Decision: `observed_only_data_gap`.

Observed-only alpha research. No entries, exits, ranking, sizing, LLM/news, paper sleeves, or orders changed.

## Gate

```json
{
  "decision": "observed_only_data_gap",
  "promotion_gate_passed": false,
  "reason": "missing_theme_or_sector_residual",
  "sector_residual_rows": 0,
  "theme_residual_rows": 0
}
```

## Coverage

```json
{
  "bucket_counts": {
    "spy_positive_qqq_nonpositive": 9,
    "spy_qqq_residual_nonpositive": 11,
    "spy_qqq_residual_positive": 21
  },
  "field_coverage": {
    "ret20_excess_qqq": {
      "coverage_ratio": 1.0,
      "missing_rows": 0,
      "present_rows": 41
    },
    "ret20_excess_sector": {
      "coverage_ratio": 0.0,
      "missing_rows": 41,
      "present_rows": 0
    },
    "ret20_excess_spy": {
      "coverage_ratio": 1.0,
      "missing_rows": 0,
      "present_rows": 41
    },
    "ret20_excess_theme": {
      "coverage_ratio": 0.0,
      "missing_rows": 41,
      "present_rows": 0
    }
  },
  "primary_positive_7d_rows": 41
}
```

## Bucket Summary

```json
{
  "missing_spy_or_qqq_residual": {
    "horizons": {
      "10d": {
        "avg_return": null,
        "closed_outcomes": 0,
        "max_single_ticker_positive_share": null,
        "positive_pnl_by_ticker": {},
        "tail_loss": null,
        "top5_positive_contribution_share": null,
        "win_rate": null,
        "worst_row": null
      },
      "20d": {
        "avg_return": null,
        "closed_outcomes": 0,
        "max_single_ticker_positive_share": null,
        "positive_pnl_by_ticker": {},
        "tail_loss": null,
        "top5_positive_contribution_share": null,
        "win_rate": null,
        "worst_row": null
      },
      "5d": {
        "avg_return": null,
        "closed_outcomes": 0,
        "max_single_ticker_positive_share": null,
        "positive_pnl_by_ticker": {},
        "tail_loss": null,
        "top5_positive_contribution_share": null,
        "win_rate": null,
        "worst_row": null
      }
    },
    "row_count": 0,
    "ticker_count": 0,
    "ticker_row_counts": {},
    "tickers": []
  },
  "qqq_positive_spy_nonpositive": {
    "horizons": {
      "10d": {
        "avg_return": null,
        "closed_outcomes": 0,
        "max_single_ticker_positive_share": null,
        "positive_pnl_by_ticker": {},
        "tail_loss": null,
        "top5_positive_contribution_share": null,
        "win_rate": null,
        "worst_row": null
      },
      "20d": {
        "avg_return": null,
        "closed_outcomes": 0,
        "max_single_ticker_positive_share": null,
        "positive_pnl_by_ticker": {},
        "tail_loss": null,
        "top5_positive_contribution_share": null,
        "win_rate": null,
        "worst_row": null
      },
      "5d": {
        "avg_return": null,
        "closed_outcomes": 0,
        "max_single_ticker_positive_share": null,
        "positive_pnl_by_ticker": {},
        "tail_loss": null,
        "top5_positive_contribution_share": null,
        "win_rate": null,
        "worst_row": null
      }
    },
    "row_count": 0,
    "ticker_count": 0,
    "ticker_row_counts": {},
    "tickers": []
  },
  "spy_positive_qqq_nonpositive": {
    "horizons": {
      "10d": {
        "avg_return": 0.015199,
        "closed_outcomes": 4,
        "max_single_ticker_positive_share": 1.0,
        "positive_pnl_by_ticker": {
          "LLY": 1176.98
        },
        "tail_loss": -0.038563,
        "top5_positive_contribution_share": 1.0,
        "win_rate": 0.5,
        "worst_row": {
          "as_of_date": "2026-05-15",
          "candidate_hit_10td": null,
          "candidate_hit_3td": null,
          "effective_date_source": "known_ohlcv_calendar",
          "eps_estimate_delta_30d": null,
          "eps_estimate_delta_7d": 0.06,
          "eps_estimate_delta_prev": 0.0,
          "feature_context_date": "2026-05-15",
          "forward_return": -0.038563,
          "future_date": "2026-05-25",
          "pead_status": "missing_last_earnings_date",
          "pnl_proxy": -385.63,
          "primary_bucket": "B_positive_expectation_only",
          "primary_expectation_positive": true,
          "residual_leader": false,
          "residual_state": "neutral",
          "residual_strength_score": -0.014265,
          "ret20_excess_qqq": -0.0427,
          "ret20_excess_spy": 0.009,
          "scout_prev_positive": false,
          "support_30d_positive": false,
          "ticker": "APP",
          "watchlist_effective_trade_date": "2026-05-15",
          "watchlist_signal_basis": [
            "primary_7d"
          ],
          "wide_watchlist_bucket": "B_positive_expectation_only",
          "wide_watchlist_positive": true
        }
      },
      "20d": {
        "avg_return": null,
        "closed_outcomes": 0,
        "max_single_ticker_positive_share": null,
        "positive_pnl_by_ticker": {},
        "tail_loss": null,
        "top5_positive_contribution_share": null,
        "win_rate": null,
        "worst_row": null
      },
      "5d": {
        "avg_return": 0.004746,
        "closed_outcomes": 9,
        "max_single_ticker_positive_share": 0.418772,
        "positive_pnl_by_ticker": {
          "CAT": 498.0,
          "COHR": 406.25,
          "LLY": 284.94
        },
        "tail_loss": -0.037365,
        "top5_positive_contribution_share": 0.929355,
        "win_rate": 0.666667,
        "worst_row": {
          "as_of_date": "2026-05-15",
          "candidate_hit_10td": null,
          "candidate_hit_3td": null,
          "effective_date_source": "known_ohlcv_calendar",
          "eps_estimate_delta_30d": null,
          "eps_estimate_delta_7d": 0.06,
          "eps_estimate_delta_prev": 0.0,
          "feature_context_date": "2026-05-15",
          "forward_return": -0.037365,
          "future_date": "2026-05-20",
          "pead_status": "missing_last_earnings_date",
          "pnl_proxy": -373.65,
          "primary_bucket": "B_positive_expectation_only",
          "primary_expectation_positive": true,
          "residual_leader": false,
          "residual_state": "neutral",
          "residual_strength_score": -0.014265,
          "ret20_excess_qqq": -0.0427,
          "ret20_excess_spy": 0.009,
          "scout_prev_positive": false,
          "support_30d_positive": false,
          "ticker": "APP",
          "watchlist_effective_trade_date": "2026-05-15",
          "watchlist_signal_basis": [
            "primary_7d"
          ],
          "wide_watchlist_bucket": "B_positive_expectation_only",
          "wide_watchlist_positive": true
        }
      }
    },
    "row_count": 9,
    "ticker_count": 6,
    "ticker_row_counts": {
      "APP": 1,
      "CAT": 3,
      "COHR": 1,
      "LLY": 2,
      "NVO": 1,
      "V": 1
    },
    "tickers": [
      "APP",
      "CAT",
      "COHR",
      "LLY",
      "NVO",
      "V"
    ]
  },
  "spy_qqq_residual_nonpositive": {
    "horizons": {
      "10d": {
        "avg_return": -0.007173,
        "closed_outcomes": 1,
        "max_single_ticker_positive_share": null,
        "positive_pnl_by_ticker": {},
        "tail_loss": -0.007173,
        "top5_positive_contribution_share": null,
        "win_rate": 0.0,
        "worst_row": {
          "as_of_date": "2026-05-14",
          "candidate_hit_10td": null,
          "candidate_hit_3td": null,
          "effective_date_source": "known_ohlcv_calendar",
          "eps_estimate_delta_30d": null,
          "eps_estimate_delta_7d": 0.06,
          "eps_estimate_delta_prev": 0.0,
          "feature_context_date": "2026-05-14",
          "forward_return": -0.007173,
          "future_date": "2026-05-24",
          "pead_status": "missing_last_earnings_date",
          "pnl_proxy": -71.73,
          "primary_bucket": "B_positive_expectation_only",
          "primary_expectation_positive": true,
          "residual_leader": false,
          "residual_state": "beta_lagging",
          "residual_strength_score": -0.051275,
          "ret20_excess_qqq": -0.0829,
          "ret20_excess_spy": -0.0254,
          "scout_prev_positive": false,
          "support_30d_positive": false,
          "ticker": "APP",
          "watchlist_effective_trade_date": "2026-05-14",
          "watchlist_signal_basis": [
            "primary_7d"
          ],
          "wide_watchlist_bucket": "B_positive_expectation_only",
          "wide_watchlist_positive": true
        }
      },
      "20d": {
        "avg_return": null,
        "closed_outcomes": 0,
        "max_single_ticker_positive_share": null,
        "positive_pnl_by_ticker": {},
        "tail_loss": null,
        "top5_positive_contribution_share": null,
        "win_rate": null,
        "worst_row": null
      },
      "5d": {
        "avg_return": 0.017806,
        "closed_outcomes": 5,
        "max_single_ticker_positive_share": 1.0,
        "positive_pnl_by_ticker": {
          "COHR": 1208.92
        },
        "tail_loss": -0.017025,
        "top5_positive_contribution_share": 1.0,
        "win_rate": 0.4,
        "worst_row": {
          "as_of_date": "2026-05-14",
          "candidate_hit_10td": null,
          "candidate_hit_3td": null,
          "effective_date_source": "known_ohlcv_calendar",
          "eps_estimate_delta_30d": null,
          "eps_estimate_delta_7d": 0.06,
          "eps_estimate_delta_prev": 0.0,
          "feature_context_date": "2026-05-14",
          "forward_return": -0.017025,
          "future_date": "2026-05-19",
          "pead_status": "missing_last_earnings_date",
          "pnl_proxy": -170.25,
          "primary_bucket": "B_positive_expectation_only",
          "primary_expectation_positive": true,
          "residual_leader": false,
          "residual_state": "beta_lagging",
          "residual_strength_score": -0.051275,
          "ret20_excess_qqq": -0.0829,
          "ret20_excess_spy": -0.0254,
          "scout_prev_positive": false,
          "support_30d_positive": false,
          "ticker": "APP",
          "watchlist_effective_trade_date": "2026-05-14",
          "watchlist_signal_basis": [
            "primary_7d"
          ],
          "wide_watchlist_bucket": "B_positive_expectation_only",
          "wide_watchlist_positive": true
        }
      }
    },
    "row_count": 11,
    "ticker_count": 6,
    "ticker_row_counts": {
      "APP": 1,
      "COHR": 2,
      "CVX": 2,
      "DIS": 3,
      "RBLX": 2,
      "SOFI": 1
    },
    "tickers": [
      "APP",
      "COHR",
      "CVX",
      "DIS",
      "RBLX",
      "SOFI"
    ]
  },
  "spy_qqq_residual_positive": {
    "horizons": {
      "10d": {
        "avg_return": 0.006827,
        "closed_outcomes": 11,
        "max_single_ticker_positive_share": 0.521775,
        "positive_pnl_by_ticker": {
          "AAPL": 286.11,
          "AMD": 1419.62,
          "DDOG": 689.49,
          "MTSI": 276.36,
          "NVO": 49.17
        },
        "tail_loss": -0.086578,
        "top5_positive_contribution_share": 0.981928,
        "win_rate": 0.545455,
        "worst_row": {
          "as_of_date": "2026-05-14",
          "candidate_hit_10td": null,
          "candidate_hit_3td": null,
          "effective_date_source": "known_ohlcv_calendar",
          "eps_estimate_delta_30d": null,
          "eps_estimate_delta_7d": 0.01,
          "eps_estimate_delta_prev": 0.0,
          "feature_context_date": "2026-05-14",
          "forward_return": -0.086578,
          "future_date": "2026-05-24",
          "pead_status": "missing_last_earnings_date",
          "pnl_proxy": -865.78,
          "primary_bucket": "A_positive_expectation_and_residual_leader",
          "primary_expectation_positive": true,
          "residual_leader": true,
          "residual_state": "residual_leader",
          "residual_strength_score": 0.099558,
          "ret20_excess_qqq": 0.0647,
          "ret20_excess_spy": 0.1222,
          "scout_prev_positive": false,
          "support_30d_positive": false,
          "ticker": "NVDA",
          "watchlist_effective_trade_date": "2026-05-14",
          "watchlist_signal_basis": [
            "primary_7d"
          ],
          "wide_watchlist_bucket": "A_positive_expectation_and_residual_leader",
          "wide_watchlist_positive": true
        }
      },
      "20d": {
        "avg_return": null,
        "closed_outcomes": 0,
        "max_single_ticker_positive_share": null,
        "positive_pnl_by_ticker": {},
        "tail_loss": null,
        "top5_positive_contribution_share": null,
        "win_rate": null,
        "worst_row": null
      },
      "5d": {
        "avg_return": -0.005608,
        "closed_outcomes": 19,
        "max_single_ticker_positive_share": 0.356611,
        "positive_pnl_by_ticker": {
          "AAPL": 982.76,
          "AMD": 553.64,
          "DDOG": 204.83,
          "MTSI": 2.93,
          "MU": 1007.62,
          "NVO": 73.76
        },
        "tail_loss": -0.079275,
        "top5_positive_contribution_share": 0.799624,
        "win_rate": 0.526316,
        "worst_row": {
          "as_of_date": "2026-05-14",
          "candidate_hit_10td": null,
          "candidate_hit_3td": null,
          "effective_date_source": "known_ohlcv_calendar",
          "eps_estimate_delta_30d": null,
          "eps_estimate_delta_7d": 0.01,
          "eps_estimate_delta_prev": 0.0,
          "feature_context_date": "2026-05-14",
          "forward_return": -0.079275,
          "future_date": "2026-05-19",
          "pead_status": "missing_last_earnings_date",
          "pnl_proxy": -792.75,
          "primary_bucket": "A_positive_expectation_and_residual_leader",
          "primary_expectation_positive": true,
          "residual_leader": true,
          "residual_state": "strong_residual_leader",
          "residual_strength_score": 0.477644,
          "ret20_excess_qqq": 0.4923,
          "ret20_excess_spy": 0.5498,
          "scout_prev_positive": false,
          "support_30d_positive": false,
          "ticker": "AMD",
          "watchlist_effective_trade_date": "2026-05-14",
          "watchlist_signal_basis": [
            "primary_7d"
          ],
          "wide_watchlist_bucket": "A_positive_expectation_and_residual_leader",
          "wide_watchlist_positive": true
        }
      }
    },
    "row_count": 21,
    "ticker_count": 9,
    "ticker_row_counts": {
      "AAPL": 4,
      "AMD": 2,
      "CAT": 2,
      "COHR": 1,
      "DDOG": 1,
      "MTSI": 1,
      "MU": 4,
      "NVDA": 5,
      "NVO": 1
    },
    "tickers": [
      "AAPL",
      "AMD",
      "CAT",
      "COHR",
      "DDOG",
      "MTSI",
      "MU",
      "NVDA",
      "NVO"
    ]
  }
}
```

## Next Evidence Needed

Persist sector/theme benchmark residual returns in the daily feature context.

No JavaScript was used.
