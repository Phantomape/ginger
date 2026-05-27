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
    "10d": 394,
    "20d": 0,
    "5d": 547
  },
  "effective_date_source_counts": {
    "known_ohlcv_calendar": 700
  },
  "expectation_status_counts": {
    "non_positive_eps_estimate_delta_7d": 341,
    "pit_usable_missing_7d_delta": 312,
    "positive_eps_estimate_delta_7d": 47
  },
  "ledger_rows_total": 2133,
  "pead_status_counts": {
    "missing_last_earnings_date": 700
  },
  "pit_unusable_revision_rows": 1433,
  "pit_usable_revision_rows": 700,
  "primary_positive_7d_rows": 47,
  "primary_positive_7d_ticker_count": 17,
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
    "V",
    "XOM"
  ],
  "residual_context_status_counts": {
    "ok": 700
  },
  "residual_leader_rows": 226,
  "residual_state_counts": {
    "beta_lagging": 343,
    "neutral": 131,
    "residual_leader": 55,
    "strong_residual_leader": 171
  },
  "scout_prev_positive_rows": 25,
  "support_30d_positive_rows": 0,
  "watchlist_signal_basis_counts": {
    "none": 639,
    "primary_7d": 36,
    "primary_7d+scout_prev": 11,
    "scout_prev": 14
  },
  "wide_watchlist_positive_rows": 61,
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
  "latest_as_of_date": "2026-05-26",
  "primary_positive_7d": [
    {
      "as_of_date": "2026-05-26",
      "candidate_hit_10td": false,
      "candidate_hit_3td": false,
      "effective_date_source": "known_ohlcv_calendar",
      "eps_estimate_delta_30d": null,
      "eps_estimate_delta_7d": 0.19,
      "eps_estimate_delta_prev": 0.06,
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
      "pead_status": "missing_last_earnings_date",
      "primary_bucket": "A_positive_expectation_and_residual_leader",
      "primary_expectation_positive": true,
      "residual_leader": true,
      "residual_state": "strong_residual_leader",
      "residual_strength_score": 0.600061,
      "ret20_excess_qqq": 0.6085,
      "ret20_excess_sector": 0.450512,
      "ret20_excess_spy": 0.6584,
      "ret20_excess_theme": 0.454029,
      "same_event_history_count": 19,
      "scout_prev_positive": true,
      "sector": "Technology",
      "support_30d_positive": false,
      "theme_residuals": {
        "ai": 0.454029
      },
      "themes": [
        "ai"
      ],
      "ticker": "MU",
      "watchlist_effective_trade_date": "2026-05-26",
      "watchlist_signal_basis": [
        "primary_7d",
        "scout_prev"
      ],
      "wide_watchlist_bucket": "A_positive_expectation_and_residual_leader",
      "wide_watchlist_positive": true
    },
    {
      "as_of_date": "2026-05-26",
      "candidate_hit_10td": false,
      "candidate_hit_3td": false,
      "effective_date_source": "known_ohlcv_calendar",
      "eps_estimate_delta_30d": null,
      "eps_estimate_delta_7d": 0.01,
      "eps_estimate_delta_prev": 0.0,
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
      "pead_status": "missing_last_earnings_date",
      "primary_bucket": "A_positive_expectation_and_residual_leader",
      "primary_expectation_positive": true,
      "residual_leader": true,
      "residual_state": "strong_residual_leader",
      "residual_strength_score": 0.397961,
      "ret20_excess_qqq": 0.4064,
      "ret20_excess_sector": 0.248412,
      "ret20_excess_spy": 0.4563,
      "ret20_excess_theme": 0.251929,
      "same_event_history_count": 19,
      "scout_prev_positive": false,
      "sector": "Technology",
      "support_30d_positive": false,
      "theme_residuals": {
        "ai": 0.251929
      },
      "themes": [
        "ai"
      ],
      "ticker": "AMD",
      "watchlist_effective_trade_date": "2026-05-26",
      "watchlist_signal_basis": [
        "primary_7d"
      ],
      "wide_watchlist_bucket": "A_positive_expectation_and_residual_leader",
      "wide_watchlist_positive": true
    },
    {
      "as_of_date": "2026-05-26",
      "candidate_hit_10td": false,
      "candidate_hit_3td": false,
      "effective_date_source": "known_ohlcv_calendar",
      "eps_estimate_delta_30d": null,
      "eps_estimate_delta_7d": 0.03,
      "eps_estimate_delta_prev": 0.03,
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
      "pead_status": "missing_last_earnings_date",
      "primary_bucket": "B_positive_expectation_only",
      "primary_expectation_positive": true,
      "residual_leader": false,
      "residual_state": "beta_lagging",
      "residual_strength_score": -0.054155,
      "ret20_excess_qqq": -0.0816,
      "ret20_excess_sector": null,
      "ret20_excess_spy": -0.0317,
      "ret20_excess_theme": null,
      "same_event_history_count": 19,
      "scout_prev_positive": true,
      "sector": "Unknown",
      "support_30d_positive": false,
      "theme_residuals": {},
      "themes": [],
      "ticker": "XOM",
      "watchlist_effective_trade_date": "2026-05-26",
      "watchlist_signal_basis": [
        "primary_7d",
        "scout_prev"
      ],
      "wide_watchlist_bucket": "B_positive_expectation_only",
      "wide_watchlist_positive": true
    },
    {
      "as_of_date": "2026-05-26",
      "candidate_hit_10td": false,
      "candidate_hit_3td": false,
      "effective_date_source": "known_ohlcv_calendar",
      "eps_estimate_delta_30d": null,
      "eps_estimate_delta_7d": 0.01,
      "eps_estimate_delta_prev": 0.0,
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
      "pead_status": "missing_last_earnings_date",
      "primary_bucket": "B_positive_expectation_only",
      "primary_expectation_positive": true,
      "residual_leader": false,
      "residual_state": "beta_lagging",
      "residual_strength_score": -0.062855,
      "ret20_excess_qqq": -0.0903,
      "ret20_excess_sector": 0.027083,
      "ret20_excess_spy": -0.0404,
      "ret20_excess_theme": null,
      "same_event_history_count": 19,
      "scout_prev_positive": false,
      "sector": "Communication Services",
      "support_30d_positive": false,
      "theme_residuals": {},
      "themes": [],
      "ticker": "DIS",
      "watchlist_effective_trade_date": "2026-05-26",
      "watchlist_signal_basis": [
        "primary_7d"
      ],
      "wide_watchlist_bucket": "B_positive_expectation_only",
      "wide_watchlist_positive": true
    },
    {
      "as_of_date": "2026-05-26",
      "candidate_hit_10td": false,
      "candidate_hit_3td": false,
      "effective_date_source": "known_ohlcv_calendar",
      "eps_estimate_delta_30d": null,
      "eps_estimate_delta_7d": 0.14,
      "eps_estimate_delta_prev": 0.09,
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
      "pead_status": "missing_last_earnings_date",
      "primary_bucket": "B_positive_expectation_only",
      "primary_expectation_positive": true,
      "residual_leader": false,
      "residual_state": "beta_lagging",
      "residual_strength_score": -0.063155,
      "ret20_excess_qqq": -0.0906,
      "ret20_excess_sector": 0.0,
      "ret20_excess_spy": -0.0407,
      "ret20_excess_theme": null,
      "same_event_history_count": 19,
      "scout_prev_positive": true,
      "sector": "Energy",
      "support_30d_positive": false,
      "theme_residuals": {},
      "themes": [],
      "ticker": "CVX",
      "watchlist_effective_trade_date": "2026-05-26",
      "watchlist_signal_basis": [
        "primary_7d",
        "scout_prev"
      ],
      "wide_watchlist_bucket": "B_positive_expectation_only",
      "wide_watchlist_positive": true
    },
    {
      "as_of_date": "2026-05-26",
      "candidate_hit_10td": false,
      "candidate_hit_3td": false,
      "effective_date_source": "known_ohlcv_calendar",
      "eps_estimate_delta_30d": null,
      "eps_estimate_delta_7d": 0.01,
      "eps_estimate_delta_prev": 0.0,
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
      "pead_status": "missing_last_earnings_date",
      "primary_bucket": "B_positive_expectation_only",
      "primary_expectation_positive": true,
      "residual_leader": false,
      "residual_state": "beta_lagging",
      "residual_strength_score": -0.272255,
      "ret20_excess_qqq": -0.2997,
      "ret20_excess_sector": -0.182317,
      "ret20_excess_spy": -0.2498,
      "ret20_excess_theme": null,
      "same_event_history_count": 18,
      "scout_prev_positive": false,
      "sector": "Communication Services",
      "support_30d_positive": false,
      "theme_residuals": {},
      "themes": [],
      "ticker": "RBLX",
      "watchlist_effective_trade_date": "2026-05-26",
      "watchlist_signal_basis": [
        "primary_7d"
      ],
      "wide_watchlist_bucket": "B_positive_expectation_only",
      "wide_watchlist_positive": true
    }
  ],
  "primary_positive_7d_count": 6,
  "wide_positive": [
    {
      "as_of_date": "2026-05-26",
      "candidate_hit_10td": false,
      "candidate_hit_3td": false,
      "effective_date_source": "known_ohlcv_calendar",
      "eps_estimate_delta_30d": null,
      "eps_estimate_delta_7d": 0.19,
      "eps_estimate_delta_prev": 0.06,
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
      "pead_status": "missing_last_earnings_date",
      "primary_bucket": "A_positive_expectation_and_residual_leader",
      "primary_expectation_positive": true,
      "residual_leader": true,
      "residual_state": "strong_residual_leader",
      "residual_strength_score": 0.600061,
      "ret20_excess_qqq": 0.6085,
      "ret20_excess_sector": 0.450512,
      "ret20_excess_spy": 0.6584,
      "ret20_excess_theme": 0.454029,
      "same_event_history_count": 19,
      "scout_prev_positive": true,
      "sector": "Technology",
      "support_30d_positive": false,
      "theme_residuals": {
        "ai": 0.454029
      },
      "themes": [
        "ai"
      ],
      "ticker": "MU",
      "watchlist_effective_trade_date": "2026-05-26",
      "watchlist_signal_basis": [
        "primary_7d",
        "scout_prev"
      ],
      "wide_watchlist_bucket": "A_positive_expectation_and_residual_leader",
      "wide_watchlist_positive": true
    },
    {
      "as_of_date": "2026-05-26",
      "candidate_hit_10td": false,
      "candidate_hit_3td": false,
      "effective_date_source": "known_ohlcv_calendar",
      "eps_estimate_delta_30d": null,
      "eps_estimate_delta_7d": 0.01,
      "eps_estimate_delta_prev": 0.0,
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
      "pead_status": "missing_last_earnings_date",
      "primary_bucket": "A_positive_expectation_and_residual_leader",
      "primary_expectation_positive": true,
      "residual_leader": true,
      "residual_state": "strong_residual_leader",
      "residual_strength_score": 0.397961,
      "ret20_excess_qqq": 0.4064,
      "ret20_excess_sector": 0.248412,
      "ret20_excess_spy": 0.4563,
      "ret20_excess_theme": 0.251929,
      "same_event_history_count": 19,
      "scout_prev_positive": false,
      "sector": "Technology",
      "support_30d_positive": false,
      "theme_residuals": {
        "ai": 0.251929
      },
      "themes": [
        "ai"
      ],
      "ticker": "AMD",
      "watchlist_effective_trade_date": "2026-05-26",
      "watchlist_signal_basis": [
        "primary_7d"
      ],
      "wide_watchlist_bucket": "A_positive_expectation_and_residual_leader",
      "wide_watchlist_positive": true
    },
    {
      "as_of_date": "2026-05-26",
      "candidate_hit_10td": false,
      "candidate_hit_3td": false,
      "effective_date_source": "known_ohlcv_calendar",
      "eps_estimate_delta_30d": null,
      "eps_estimate_delta_7d": 0.03,
      "eps_estimate_delta_prev": 0.03,
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
      "pead_status": "missing_last_earnings_date",
      "primary_bucket": "B_positive_expectation_only",
      "primary_expectation_positive": true,
      "residual_leader": false,
      "residual_state": "beta_lagging",
      "residual_strength_score": -0.054155,
      "ret20_excess_qqq": -0.0816,
      "ret20_excess_sector": null,
      "ret20_excess_spy": -0.0317,
      "ret20_excess_theme": null,
      "same_event_history_count": 19,
      "scout_prev_positive": true,
      "sector": "Unknown",
      "support_30d_positive": false,
      "theme_residuals": {},
      "themes": [],
      "ticker": "XOM",
      "watchlist_effective_trade_date": "2026-05-26",
      "watchlist_signal_basis": [
        "primary_7d",
        "scout_prev"
      ],
      "wide_watchlist_bucket": "B_positive_expectation_only",
      "wide_watchlist_positive": true
    },
    {
      "as_of_date": "2026-05-26",
      "candidate_hit_10td": false,
      "candidate_hit_3td": false,
      "effective_date_source": "known_ohlcv_calendar",
      "eps_estimate_delta_30d": null,
      "eps_estimate_delta_7d": 0.01,
      "eps_estimate_delta_prev": 0.0,
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
      "pead_status": "missing_last_earnings_date",
      "primary_bucket": "B_positive_expectation_only",
      "primary_expectation_positive": true,
      "residual_leader": false,
      "residual_state": "beta_lagging",
      "residual_strength_score": -0.062855,
      "ret20_excess_qqq": -0.0903,
      "ret20_excess_sector": 0.027083,
      "ret20_excess_spy": -0.0404,
      "ret20_excess_theme": null,
      "same_event_history_count": 19,
      "scout_prev_positive": false,
      "sector": "Communication Services",
      "support_30d_positive": false,
      "theme_residuals": {},
      "themes": [],
      "ticker": "DIS",
      "watchlist_effective_trade_date": "2026-05-26",
      "watchlist_signal_basis": [
        "primary_7d"
      ],
      "wide_watchlist_bucket": "B_positive_expectation_only",
      "wide_watchlist_positive": true
    },
    {
      "as_of_date": "2026-05-26",
      "candidate_hit_10td": false,
      "candidate_hit_3td": false,
      "effective_date_source": "known_ohlcv_calendar",
      "eps_estimate_delta_30d": null,
      "eps_estimate_delta_7d": 0.14,
      "eps_estimate_delta_prev": 0.09,
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
      "pead_status": "missing_last_earnings_date",
      "primary_bucket": "B_positive_expectation_only",
      "primary_expectation_positive": true,
      "residual_leader": false,
      "residual_state": "beta_lagging",
      "residual_strength_score": -0.063155,
      "ret20_excess_qqq": -0.0906,
      "ret20_excess_sector": 0.0,
      "ret20_excess_spy": -0.0407,
      "ret20_excess_theme": null,
      "same_event_history_count": 19,
      "scout_prev_positive": true,
      "sector": "Energy",
      "support_30d_positive": false,
      "theme_residuals": {},
      "themes": [],
      "ticker": "CVX",
      "watchlist_effective_trade_date": "2026-05-26",
      "watchlist_signal_basis": [
        "primary_7d",
        "scout_prev"
      ],
      "wide_watchlist_bucket": "B_positive_expectation_only",
      "wide_watchlist_positive": true
    },
    {
      "as_of_date": "2026-05-26",
      "candidate_hit_10td": false,
      "candidate_hit_3td": false,
      "effective_date_source": "known_ohlcv_calendar",
      "eps_estimate_delta_30d": null,
      "eps_estimate_delta_7d": 0.01,
      "eps_estimate_delta_prev": 0.0,
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
      "pead_status": "missing_last_earnings_date",
      "primary_bucket": "B_positive_expectation_only",
      "primary_expectation_positive": true,
      "residual_leader": false,
      "residual_state": "beta_lagging",
      "residual_strength_score": -0.272255,
      "ret20_excess_qqq": -0.2997,
      "ret20_excess_sector": -0.182317,
      "ret20_excess_spy": -0.2498,
      "ret20_excess_theme": null,
      "same_event_history_count": 18,
      "scout_prev_positive": false,
      "sector": "Communication Services",
      "support_30d_positive": false,
      "theme_residuals": {},
      "themes": [],
      "ticker": "RBLX",
      "watchlist_effective_trade_date": "2026-05-26",
      "watchlist_signal_basis": [
        "primary_7d"
      ],
      "wide_watchlist_bucket": "B_positive_expectation_only",
      "wide_watchlist_positive": true
    }
  ],
  "wide_positive_count": 6
}
```

## Primary Bucket Summary

| Bucket | Rows | 5d Closed | 5d Avg Return | 10d Closed | 10d Avg Return | 20d Closed | 20d Avg Return |
|---|---:|---:|---:|---:|---:|---:|---:|
| A_positive_expectation_and_residual_leader | 20 | 16 | -0.7459% | 10 | 0.7018% | 0 |  |
| B_positive_expectation_only | 27 | 17 | 0.8502% | 6 | 0.9756% | 0 |  |
| C_residual_leader_only | 206 | 161 | -1.2734% | 126 | -0.4806% | 0 |  |
| D_neither | 447 | 353 | 0.7934% | 252 | 1.9058% | 0 |  |

## Wide Watchlist Bucket Summary

| Bucket | Rows | 5d Closed | 5d Avg Return | 10d Closed | 10d Avg Return | 20d Closed | 20d Avg Return |
|---|---:|---:|---:|---:|---:|---:|---:|
| A_positive_expectation_and_residual_leader | 28 | 24 | -0.5938% | 17 | 0.4036% | 0 |  |
| B_positive_expectation_only | 33 | 23 | 1.5371% | 11 | 0.5722% | 0 |  |
| C_residual_leader_only | 198 | 153 | -1.3249% | 119 | -0.5075% | 0 |  |
| D_neither | 441 | 347 | 0.7469% | 247 | 1.9426% | 0 |  |

## Current Position Overlap

```json
{
  "current_position_count": 13,
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
    "bucket_a_closed_5d_outcomes": 16,
    "comparisons": [
      {
        "bucket_a_avg_return": -0.007459,
        "comparison_bucket": "B_positive_expectation_only",
        "horizon": "5d",
        "other_avg_return": 0.008502,
        "passed": false
      },
      {
        "bucket_a_avg_return": -0.007459,
        "comparison_bucket": "C_residual_leader_only",
        "horizon": "5d",
        "other_avg_return": -0.012734,
        "passed": true
      },
      {
        "bucket_a_avg_return": -0.007459,
        "comparison_bucket": "D_neither",
        "horizon": "5d",
        "other_avg_return": 0.007934,
        "passed": false
      },
      {
        "bucket_a_avg_return": 0.007018,
        "comparison_bucket": "B_positive_expectation_only",
        "horizon": "10d",
        "other_avg_return": 0.009756,
        "passed": false
      },
      {
        "bucket_a_avg_return": 0.007018,
        "comparison_bucket": "C_residual_leader_only",
        "horizon": "10d",
        "other_avg_return": -0.004806,
        "passed": true
      },
      {
        "bucket_a_avg_return": 0.007018,
        "comparison_bucket": "D_neither",
        "horizon": "10d",
        "other_avg_return": 0.019058,
        "passed": false
      }
    ],
    "concentration": {
      "max_single_ticker_positive_guardrail": 0.5,
      "max_single_ticker_positive_share": 0.422814,
      "passed": false,
      "top5_positive_contribution_guardrail": 0.6,
      "top5_positive_contribution_share": 0.884589
    },
    "decision": "rejected_or_scout_only_revision_watchlist",
    "decision_scope": "primary_7d_promotable_readout",
    "passed": false,
    "positive_expectation_rows": 47,
    "promotable": true,
    "reason": "bucket_a_failed_outperformance_concentration_or_scope",
    "total_closed_5d_outcomes": 547
  },
  "wide_watchlist_scout_gate": {
    "bucket_a_closed_5d_outcomes": 24,
    "comparisons": [
      {
        "bucket_a_avg_return": -0.005938,
        "comparison_bucket": "B_positive_expectation_only",
        "horizon": "5d",
        "other_avg_return": 0.015371,
        "passed": false
      },
      {
        "bucket_a_avg_return": -0.005938,
        "comparison_bucket": "C_residual_leader_only",
        "horizon": "5d",
        "other_avg_return": -0.013249,
        "passed": true
      },
      {
        "bucket_a_avg_return": -0.005938,
        "comparison_bucket": "D_neither",
        "horizon": "5d",
        "other_avg_return": 0.007469,
        "passed": false
      },
      {
        "bucket_a_avg_return": 0.004036,
        "comparison_bucket": "B_positive_expectation_only",
        "horizon": "10d",
        "other_avg_return": 0.005722,
        "passed": false
      },
      {
        "bucket_a_avg_return": 0.004036,
        "comparison_bucket": "C_residual_leader_only",
        "horizon": "10d",
        "other_avg_return": -0.005075,
        "passed": true
      },
      {
        "bucket_a_avg_return": 0.004036,
        "comparison_bucket": "D_neither",
        "horizon": "10d",
        "other_avg_return": 0.019426,
        "passed": false
      }
    ],
    "concentration": {
      "max_single_ticker_positive_guardrail": 0.5,
      "max_single_ticker_positive_share": 0.262006,
      "passed": false,
      "top5_positive_contribution_guardrail": 0.6,
      "top5_positive_contribution_share": 0.662613
    },
    "decision": "rejected_or_scout_only_revision_watchlist",
    "decision_scope": "wide_watchlist_scout_not_promotable",
    "passed": false,
    "positive_expectation_rows": 61,
    "promotable": false,
    "reason": "bucket_a_failed_outperformance_concentration_or_scope",
    "total_closed_5d_outcomes": 547
  }
}
```

No JavaScript was used.
