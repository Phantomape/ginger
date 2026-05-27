# exp-20260526-032 Guidance And Surprise Coverage Probe

Decision: `observed_only_data_gap`.

Observed-only alpha research. No entries, exits, ranking, sizing, LLM/news, paper sleeves, or orders changed.

## Gate

```json
{
  "current_surprise_rows": 0,
  "decision": "observed_only_data_gap",
  "guidance_rows": 0,
  "promotion_gate_passed": false,
  "reason": "current_surprise_and_guidance_absent",
  "snapshot_matched_primary_rows": 41
}
```

## Coverage

```json
{
  "avg_historical_surprise_rows": 39,
  "bucket_counts": {
    "primary_positive_revision_missing_surprise_guidance": 2,
    "primary_positive_revision_positive_surprise_history_proxy": 39
  },
  "current_surprise_rows": 0,
  "guidance_rows": 0,
  "primary_positive_7d_rows": 41,
  "snapshot_date_count": 13,
  "snapshot_dates_with_rows": 13,
  "snapshot_matched_primary_rows": 41
}
```

## Bucket Summary

```json
{
  "primary_positive_revision_current_surprise_nonpositive": {
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
  "primary_positive_revision_current_surprise_positive": {
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
  "primary_positive_revision_guidance_available": {
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
  "primary_positive_revision_missing_surprise_guidance": {
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
        "avg_return": -0.005057,
        "closed_outcomes": 2,
        "max_single_ticker_positive_share": null,
        "positive_pnl_by_ticker": {},
        "tail_loss": -0.005654,
        "top5_positive_contribution_share": null,
        "win_rate": 0.0,
        "worst_row": {
          "as_of_date": "2026-05-20",
          "candidate_hit_10td": null,
          "candidate_hit_3td": null,
          "effective_date_source": "known_ohlcv_calendar",
          "eps_estimate_delta_30d": null,
          "eps_estimate_delta_7d": 11.6309,
          "eps_estimate_delta_prev": 11.6309,
          "feature_context_date": "2026-05-20",
          "forward_return": -0.005654,
          "future_date": "2026-05-25",
          "pead_status": "missing_last_earnings_date",
          "pnl_proxy": -56.54,
          "primary_bucket": "B_positive_expectation_only",
          "primary_expectation_positive": true,
          "residual_leader": false,
          "residual_state": "neutral",
          "residual_strength_score": 0.00162,
          "ret20_excess_qqq": -0.0239,
          "ret20_excess_spy": 0.0225,
          "scout_prev_positive": true,
          "support_30d_positive": false,
          "ticker": "V",
          "watchlist_effective_trade_date": "2026-05-20",
          "watchlist_signal_basis": [
            "primary_7d",
            "scout_prev"
          ],
          "wide_watchlist_bucket": "B_positive_expectation_only",
          "wide_watchlist_positive": true
        }
      }
    },
    "row_count": 2,
    "ticker_count": 2,
    "ticker_row_counts": {
      "SOFI": 1,
      "V": 1
    },
    "tickers": [
      "SOFI",
      "V"
    ]
  },
  "primary_positive_revision_nonpositive_surprise_history_proxy": {
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
  "primary_positive_revision_positive_surprise_history_proxy": {
    "horizons": {
      "10d": {
        "avg_return": 0.008045,
        "closed_outcomes": 16,
        "max_single_ticker_positive_share": 0.364217,
        "positive_pnl_by_ticker": {
          "AAPL": 286.11,
          "AMD": 1419.62,
          "DDOG": 689.49,
          "LLY": 1176.98,
          "MTSI": 276.36,
          "NVO": 49.17
        },
        "tail_loss": -0.086578,
        "top5_positive_contribution_share": 0.843078,
        "win_rate": 0.5,
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
        "avg_return": 0.001139,
        "closed_outcomes": 31,
        "max_single_ticker_positive_share": 0.309203,
        "positive_pnl_by_ticker": {
          "AAPL": 982.76,
          "AMD": 553.64,
          "CAT": 498.0,
          "COHR": 1615.17,
          "DDOG": 204.83,
          "LLY": 284.94,
          "MTSI": 2.93,
          "MU": 1007.62,
          "NVO": 73.76
        },
        "tail_loss": -0.079275,
        "top5_positive_contribution_share": 0.55837,
        "win_rate": 0.580645,
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
    "row_count": 39,
    "ticker_count": 14,
    "ticker_row_counts": {
      "AAPL": 4,
      "AMD": 2,
      "APP": 2,
      "CAT": 5,
      "COHR": 4,
      "CVX": 2,
      "DDOG": 1,
      "DIS": 3,
      "LLY": 2,
      "MTSI": 1,
      "MU": 4,
      "NVDA": 5,
      "NVO": 2,
      "RBLX": 2
    },
    "tickers": [
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
      "RBLX"
    ]
  }
}
```

## Next Evidence Needed

Persist current-quarter surprise/guidance direction in a PIT-safe earnings event ledger.

No JavaScript was used.
