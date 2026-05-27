# exp-20260526-030 Expectation Revision Velocity Attribution

Decision: `observed_only_data_gap`.

Observed-only alpha research. No entries, exits, ranking, sizing, LLM/news, paper sleeves, or orders changed.

## Gate

```json
{
  "data_gap_reasons": [
    "eps_acceleration_proxy_rows",
    "revenue_revision_velocity_30d",
    "analyst_count_delta_30d"
  ],
  "decision": "observed_only_data_gap",
  "minimum_group_5d_outcomes": 8,
  "promotion_gate_passed": false,
  "reason": "missing_velocity_components"
}
```

## Coverage

```json
{
  "bucket_counts": {
    "primary_7d_missing_30d_velocity": 41
  },
  "field_coverage": {
    "analyst_count_delta_30d": {
      "coverage_ratio": 0.0,
      "missing_rows": 41,
      "present_rows": 0
    },
    "eps_estimate_delta_30d": {
      "coverage_ratio": 0.0,
      "missing_rows": 41,
      "present_rows": 0
    },
    "eps_estimate_delta_7d": {
      "coverage_ratio": 1.0,
      "missing_rows": 0,
      "present_rows": 41
    },
    "eps_revision_acceleration_proxy": {
      "coverage_ratio": 0.0,
      "missing_rows": 41,
      "present_rows": 0
    },
    "revenue_revision_velocity_30d": {
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
  "primary_7d_30d_positive_accelerating": {
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
  "primary_7d_30d_positive_decelerating": {
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
  "primary_7d_missing_30d_velocity": {
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
        "avg_return": 0.000764,
        "closed_outcomes": 33,
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
    "row_count": 41,
    "ticker_count": 16,
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
      "RBLX": 2,
      "SOFI": 1,
      "V": 1
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
      "RBLX",
      "SOFI",
      "V"
    ]
  },
  "primary_7d_positive_30d_nonpositive": {
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
  }
}
```

## Next Evidence Needed

Persist revenue estimate deltas and analyst count deltas in the PIT ledger before promoting revision velocity.

No JavaScript was used.
