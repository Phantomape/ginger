# exp-20260526-031 PEAD Paper Sleeve Readiness Probe

Decision: `observed_only_data_gap`.

Observed-only alpha research. No entries, exits, ranking, sizing, LLM/news, paper sleeves, or orders changed.

## Gate

```json
{
  "data_gap_reasons": [
    "no_t2_t15_last_earnings_date_rows",
    "eligible_closed_5d_outcomes",
    "market_risk_off_context",
    "post_earnings_gap_failure_context"
  ],
  "decision": "observed_only_data_gap",
  "eligible_closed_5d_outcomes": 0,
  "eligible_rows": 0,
  "promotion_gate_passed": false,
  "reason": "pead_required_context_missing"
}
```

## Coverage

```json
{
  "eligible_closed_5d_outcomes": 0,
  "eligible_rows": 0,
  "pead_candidate_bucket_counts": {
    "blocked_missing_last_earnings_date": 41,
    "not_primary_positive_7d": 608
  },
  "source_pead_status_counts": {
    "missing_last_earnings_date": 649
  }
}
```

## Bucket Summary

```json
{
  "blocked_missing_effective_trade_date": {
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
  "blocked_missing_last_earnings_date": {
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
  "blocked_outside_t2_t15_after_earnings": {
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
  "eligible_primary_positive_non_residual_leader": {
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
  "eligible_primary_positive_residual_leader": {
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
  "not_primary_positive_7d": {
    "horizons": {
      "10d": {
        "avg_return": 0.011103,
        "closed_outcomes": 378,
        "max_single_ticker_positive_share": 0.121425,
        "positive_pnl_by_ticker": {
          "AAPL": 2580.19,
          "AMD": 922.79,
          "AMZN": 101.34,
          "APLD": 3612.78,
          "APP": 1597.7,
          "BE": 4709.46,
          "BKNG": 1653.09,
          "COHR": 95.18,
          "CRDO": 7054.34,
          "CVX": 2677.12,
          "DDOG": 5239.17,
          "DIS": 27.26,
          "GE": 1700.37,
          "GS": 3245.78,
          "INTC": 1355.01,
          "ISRG": 2326.68,
          "JPM": 1056.86,
          "LLY": 3978.07,
          "MA": 741.52,
          "MCD": 2033.47,
          "META": 573.13,
          "MRVL": 8305.63,
          "MSFT": 1488.1,
          "MTSI": 2013.95,
          "MU": 363.48,
          "NFLX": 2197.09,
          "NOW": 9266.52,
          "NVDA": 340.43,
          "PLTR": 1155.1,
          "RBLX": 8833.63,
          "RTX": 416.29,
          "SNOW": 8542.99,
          "SOFI": 208.89,
          "SPOT": 13681.17,
          "TRIP": 3034.7,
          "TSLA": 89.29,
          "TSM": 498.06,
          "UNH": 293.44,
          "V": 1743.17,
          "WDC": 46.89,
          "XOM": 2871.49
        },
        "tail_loss": -0.171025,
        "top5_positive_contribution_share": 0.095116,
        "win_rate": 0.574074,
        "worst_row": {
          "as_of_date": "2026-05-08",
          "candidate_hit_10td": null,
          "candidate_hit_3td": null,
          "effective_date_source": "known_ohlcv_calendar",
          "eps_estimate_delta_30d": null,
          "eps_estimate_delta_7d": null,
          "eps_estimate_delta_prev": 0.0,
          "feature_context_date": "2026-05-08",
          "forward_return": -0.171025,
          "future_date": "2026-05-18",
          "pead_status": "missing_last_earnings_date",
          "pnl_proxy": -1710.25,
          "primary_bucket": "C_residual_leader_only",
          "primary_expectation_positive": false,
          "residual_leader": true,
          "residual_state": "strong_residual_leader",
          "residual_strength_score": 0.396341,
          "ret20_excess_qqq": 0.4124,
          "ret20_excess_spy": 0.4907,
          "scout_prev_positive": false,
          "support_30d_positive": false,
          "ticker": "CRDO",
          "watchlist_effective_trade_date": "2026-05-08",
          "watchlist_signal_basis": [
            "none"
          ],
          "wide_watchlist_bucket": "C_residual_leader_only",
          "wide_watchlist_positive": false
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
        "avg_return": 0.00146,
        "closed_outcomes": 514,
        "max_single_ticker_positive_share": 0.085146,
        "positive_pnl_by_ticker": {
          "AAPL": 1172.77,
          "AMD": 2841.44,
          "AMZN": 406.63,
          "APLD": 5852.19,
          "APP": 2582.86,
          "AVGO": 309.2,
          "BE": 5312.76,
          "BKNG": 1259.47,
          "CAT": 54.04,
          "COHR": 443.73,
          "CRDO": 9510.12,
          "CVX": 2680.76,
          "DDOG": 3473.89,
          "DE": 101.07,
          "DIS": 201.81,
          "GE": 1955.77,
          "GEV": 666.75,
          "GOOG": 805.68,
          "GS": 2111.91,
          "HOOD": 52.12,
          "INTC": 2905.55,
          "ISRG": 1231.26,
          "JPM": 850.78,
          "LITE": 3646.46,
          "LLY": 3696.26,
          "MA": 595.73,
          "MCD": 973.64,
          "META": 1283.9,
          "MRVL": 5645.99,
          "MSFT": 1695.27,
          "MTSI": 3010.94,
          "MU": 1881.15,
          "NFLX": 1253.64,
          "NOW": 5883.52,
          "NVDA": 1503.44,
          "NVO": 526.37,
          "PLTR": 990.17,
          "RBLX": 5086.59,
          "RTX": 657.29,
          "SNOW": 5126.26,
          "SOFI": 568.59,
          "SPOT": 7645.08,
          "TRIP": 2074.3,
          "TSLA": 1537.37,
          "TSM": 769.96,
          "UNH": 1426.59,
          "V": 990.32,
          "VRT": 873.22,
          "WDC": 1719.49,
          "XOM": 3847.68
        },
        "tail_loss": -0.216014,
        "top5_positive_contribution_share": 0.119617,
        "win_rate": 0.523346,
        "worst_row": {
          "as_of_date": "2026-05-14",
          "candidate_hit_10td": null,
          "candidate_hit_3td": null,
          "effective_date_source": "known_ohlcv_calendar",
          "eps_estimate_delta_30d": null,
          "eps_estimate_delta_7d": null,
          "eps_estimate_delta_prev": 0.0,
          "feature_context_date": "2026-05-14",
          "forward_return": -0.216014,
          "future_date": "2026-05-19",
          "pead_status": "missing_last_earnings_date",
          "pnl_proxy": -2160.14,
          "primary_bucket": "C_residual_leader_only",
          "primary_expectation_positive": false,
          "residual_leader": true,
          "residual_state": "strong_residual_leader",
          "residual_strength_score": 0.460125,
          "ret20_excess_qqq": 0.4285,
          "ret20_excess_spy": 0.486,
          "scout_prev_positive": false,
          "support_30d_positive": false,
          "ticker": "APLD",
          "watchlist_effective_trade_date": "2026-05-14",
          "watchlist_signal_basis": [
            "none"
          ],
          "wide_watchlist_bucket": "C_residual_leader_only",
          "wide_watchlist_positive": false
        }
      }
    },
    "row_count": 608,
    "ticker_count": 51,
    "ticker_row_counts": {
      "AAPL": 9,
      "AMD": 11,
      "AMZN": 13,
      "APLD": 12,
      "APP": 11,
      "AVGO": 13,
      "BE": 13,
      "BKNG": 13,
      "CAT": 8,
      "COHR": 8,
      "COIN": 12,
      "CRDO": 13,
      "CVX": 11,
      "DDOG": 11,
      "DE": 13,
      "DIS": 10,
      "GE": 13,
      "GEV": 12,
      "GOOG": 13,
      "GS": 13,
      "HOOD": 12,
      "INTC": 13,
      "ISRG": 13,
      "JPM": 13,
      "LITE": 13,
      "LLY": 11,
      "MA": 13,
      "MCD": 12,
      "META": 13,
      "MRVL": 12,
      "MSFT": 13,
      "MTSI": 11,
      "MU": 9,
      "NFLX": 13,
      "NOW": 13,
      "NVDA": 8,
      "NVO": 11,
      "PLTR": 13,
      "RBLX": 10,
      "RTX": 13,
      "SNOW": 13,
      "SOFI": 11,
      "SPOT": 13,
      "TRIP": 12,
      "TSLA": 13,
      "TSM": 13,
      "UNH": 13,
      "V": 12,
      "VRT": 12,
      "WDC": 12,
      "XOM": 13
    },
    "tickers": [
      "AAPL",
      "AMD",
      "AMZN",
      "APLD",
      "APP",
      "AVGO",
      "BE",
      "BKNG",
      "CAT",
      "COHR",
      "COIN",
      "CRDO",
      "CVX",
      "DDOG",
      "DE",
      "DIS",
      "GE",
      "GEV",
      "GOOG",
      "GS",
      "HOOD",
      "INTC",
      "ISRG",
      "JPM",
      "LITE",
      "LLY",
      "MA",
      "MCD",
      "META",
      "MRVL",
      "MSFT",
      "MTSI",
      "MU",
      "NFLX",
      "NOW",
      "NVDA",
      "NVO",
      "PLTR",
      "RBLX",
      "RTX",
      "SNOW",
      "SOFI",
      "SPOT",
      "TRIP",
      "TSLA",
      "TSM",
      "UNH",
      "V",
      "VRT",
      "WDC",
      "XOM"
    ]
  }
}
```

## Next Evidence Needed

Add PIT last_earnings_date/report_date and post-earnings gap-failure fields to daily snapshots.

No JavaScript was used.
