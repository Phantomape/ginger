# exp-20260527-022 Industry-Leadership Breadth Breakout Paper Sleeve

Decision: `rejected_industry_leadership_breadth_breakout_sleeve`.

Single variable: a default-off paper sleeve admits at most one liquid breakout candidate per day only when its industry has same-date peer leadership breadth.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates | Industry days | Industries |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.4449 | -0.7179 | $117,072.92 | $110,570.78 | $-6,502.14 | +0.0032 | 14 | 28 | 46 | 2 |
| mid_weak | 2.1402 | 3.0917 | +0.9515 | $78,110.11 | $94,260.03 | $+16,149.92 | -0.0066 | 38 | 67 | 93 | 2 |
| old_thin | 0.5911 | 0.6625 | +0.0714 | $39,667.96 | $42,197.21 | $+2,529.25 | -0.0020 | 18 | 30 | 50 | 2 |

## Aggregate

- EV delta: `0.305` (`0.038636`)
- PnL delta: `$12177.03` (`0.05185`)
- target trades: `70` across `3` windows
- max single positive share: `0.430604`
- positive PnL HHI: `0.353713`

## Industry Audit

```json
{
  "late_strong": {
    "candidate_days": 20,
    "candidate_source_tickers": 39,
    "industry_cache_coverage": {
      "cache_generated_at": "2026-05-27T05:25:19Z",
      "ok_share": 0.702128,
      "rule_version": "yfinance_gics_proxy_sector_v1",
      "sector_counts": {
        "Communication Services": 5,
        "Consumer Cyclical": 3,
        "Energy": 1,
        "Financial Services": 4,
        "Healthcare": 3,
        "Industrials": 5,
        "Technology": 12
      },
      "sector_unique_count": 7,
      "source": "yfinance.Ticker.info.sector",
      "status_counts": {
        "fetch_error": 12,
        "missing_info": 0,
        "missing_ticker": 2,
        "ok": 33
      },
      "status_shares": {
        "fetch_error": 0.255319,
        "missing_info": 0.0,
        "missing_ticker": 0.042553,
        "ok": 0.702128
      },
      "tickers_requested": 47,
      "tickers_unique": 47,
      "unresolved_sample": [
        "GLD",
        "IAU",
        "IWM",
        "QQQ",
        "SLV",
        "SNXX",
        "SPOT",
        "SPY",
        "TRIP",
        "TSLA",
        "TSM",
        "UNH",
        "V",
        "XOM"
      ]
    },
    "industry_pass_day_fraction": 0.373984,
    "industry_pass_days": 46,
    "raw_breakouts_after_industry_day_precheck": 51,
    "raw_industry_confirmed_breakouts": 28,
    "rule_version": "industry_leadership_breadth_breakout_v1",
    "sample_industry_context": {
      "2025-10-23": {
        "industry_count": 19,
        "passed_industries": {
          "Semiconductors": {
            "avg_day_rs_vs_spy": 0.031012,
            "avg_ret20_excess_spy": 0.152591,
            "eligible_count": 5,
            "leader_count": 5,
            "leaders": [
              "AMD",
              "AVGO",
              "CRDO",
              "MU",
              "NVDA"
            ],
            "leadership_fraction": 1.0,
            "sector": "Technology"
          },
          "Software - Application": {
            "avg_day_rs_vs_spy": 0.016082,
            "avg_ret20_excess_spy": 0.082623,
            "eligible_count": 3,
            "leader_count": 2,
            "leaders": [
              "DDOG",
              "SNOW"
            ],
            "leadership_fraction": 0.666667,
            "sector": "Technology"
          }
        },
        "passed_industry_count": 2,
        "rule_version": "industry_leadership_breadth_breakout_v1"
      },
      "2025-10-24": {
        "industry_count": 19,
        "passed_industries": {
          "Semiconductors": {
            "avg_day_rs_vs_spy": 0.035283,
            "avg_ret20_excess_spy": 0.211043,
            "eligible_count": 5,
            "leader_count": 5,
            "leaders": [
              "AMD",
              "AVGO",
              "CRDO",
              "MU",
              "NVDA"
            ],
            "leadership_fraction": 1.0,
            "sector": "Technology"
          }
        },
        "passed_industry_count": 1,
        "rule_version": "industry_leadership_breadth_breakout_v1"
      },
      "2025-10-27": {
        "industry_count": 19,
        "passed_industries": {
          "Semiconductors": {
            "avg_day_rs_vs_spy": 0.003856,
            "avg_ret20_excess_spy": 0.201804,
            "eligible_count": 5,
            "leader_count": 3,
            "leaders": [
              "AMD",
              "AVGO",
              "NVDA"
            ],
            "leadership_fraction": 0.6,
            "sector": "Technology"
          }
        },
        "passed_industry_count": 1,
        "rule_version": "industry_leadership_breadth_breakout_v1"
      },
      "2025-10-28": {
        "industry_count": 19,
        "passed_industries": {
          "Semiconductors": {
            "avg_day_rs_vs_spy": 0.023025,
            "avg_ret20_excess_spy": 0.217373,
            "eligible_count": 5,
            "leader_count": 4,
            "leaders": [
              "AVGO",
              "CRDO",
              "MU",
              "NVDA"
            ],
            "leadership_fraction": 0.8,
            "sector": "Technology"
          }
        },
        "passed_industry_count": 1,
        "rule_version": "industry_leadership_breadth_breakout_v1"
      },
      "2025-10-29": {
        "industry_count": 19,
        "passed_industries": {
          "Semiconductors": {
            "avg_day_rs_vs_spy": 0.033146,
            "avg_ret20_excess_spy": 0.232419,
            "eligible_count": 5,
            "leader_count": 5,
            "leaders": [
              "AMD",
              "AVGO",
              "CRDO",
              "MU",
              "NVDA"
            ],
            "leadership_fraction": 1.0,
            "sector": "Technology"
          }
        },
        "passed_industry_count": 1,
        "rule_version": "industry_leadership_breadth_breakout_v1"
      }
    },
    "top_candidate_industries": {
      "Semiconductors": 25,
      "Software - Application": 3
    },
    "trading_days": 123,
    "unique_candidate_industries": 2,
    "unique_candidate_tickers": 7
  },
  "mid_weak": {
    "candidate_days": 39,
    "candidate_source_tickers": 38,
    "industry_cache_coverage": {
      "cache_generated_at": "2026-05-27T05:25:19Z",
      "ok_share": 0.702128,
      "rule_version": "yfinance_gics_proxy_sector_v1",
      "sector_counts": {
        "Communication Services": 5,
        "Consumer Cyclical": 3,
        "Energy": 1,
        "Financial Services": 4,
        "Healthcare": 3,
        "Industrials": 5,
        "Technology": 12
      },
      "sector_unique_count": 7,
      "source": "yfinance.Ticker.info.sector",
      "status_counts": {
        "fetch_error": 12,
        "missing_info": 0,
        "missing_ticker": 2,
        "ok": 33
      },
      "status_shares": {
        "fetch_error": 0.255319,
        "missing_info": 0.0,
        "missing_ticker": 0.042553,
        "ok": 0.702128
      },
      "tickers_requested": 47,
      "tickers_unique": 47,
      "unresolved_sample": [
        "GLD",
        "IAU",
        "IWM",
        "QQQ",
        "SLV",
        "SNXX",
        "SPOT",
        "SPY",
        "TRIP",
        "TSLA",
        "TSM",
        "UNH",
        "V",
        "XOM"
      ]
    },
    "industry_pass_day_fraction": 0.732283,
    "industry_pass_days": 93,
    "raw_breakouts_after_industry_day_precheck": 125,
    "raw_industry_confirmed_breakouts": 67,
    "rule_version": "industry_leadership_breadth_breakout_v1",
    "sample_industry_context": {
      "2025-05-01": {
        "industry_count": 19,
        "passed_industries": {
          "Software - Application": {
            "avg_day_rs_vs_spy": 0.019781,
            "avg_ret20_excess_spy": 0.104796,
            "eligible_count": 3,
            "leader_count": 2,
            "leaders": [
              "DDOG",
              "SNOW"
            ],
            "leadership_fraction": 0.666667,
            "sector": "Technology"
          }
        },
        "passed_industry_count": 1,
        "rule_version": "industry_leadership_breadth_breakout_v1"
      },
      "2025-05-02": {
        "industry_count": 19,
        "passed_industries": {
          "Semiconductors": {
            "avg_day_rs_vs_spy": 0.020711,
            "avg_ret20_excess_spy": 0.121099,
            "eligible_count": 5,
            "leader_count": 3,
            "leaders": [
              "AVGO",
              "CRDO",
              "NVDA"
            ],
            "leadership_fraction": 0.6,
            "sector": "Technology"
          }
        },
        "passed_industry_count": 1,
        "rule_version": "industry_leadership_breadth_breakout_v1"
      },
      "2025-05-05": {
        "industry_count": 19,
        "passed_industries": {
          "Semiconductors": {
            "avg_day_rs_vs_spy": 0.006341,
            "avg_ret20_excess_spy": 0.176079,
            "eligible_count": 5,
            "leader_count": 2,
            "leaders": [
              "AMD",
              "CRDO"
            ],
            "leadership_fraction": 0.4,
            "sector": "Technology"
          },
          "Software - Application": {
            "avg_day_rs_vs_spy": 0.008609,
            "avg_ret20_excess_spy": 0.165908,
            "eligible_count": 3,
            "leader_count": 3,
            "leaders": [
              "DDOG",
              "NOW",
              "SNOW"
            ],
            "leadership_fraction": 1.0,
            "sector": "Technology"
          }
        },
        "passed_industry_count": 2,
        "rule_version": "industry_leadership_breadth_breakout_v1"
      },
      "2025-05-06": {
        "industry_count": 19,
        "passed_industries": {
          "Semiconductors": {
            "avg_day_rs_vs_spy": -0.000644,
            "avg_ret20_excess_spy": 0.121125,
            "eligible_count": 5,
            "leader_count": 2,
            "leaders": [
              "AVGO",
              "NVDA"
            ],
            "leadership_fraction": 0.4,
            "sector": "Technology"
          },
          "Software - Application": {
            "avg_day_rs_vs_spy": 0.006286,
            "avg_ret20_excess_spy": 0.158894,
            "eligible_count": 3,
            "leader_count": 2,
            "leaders": [
              "DDOG",
              "SNOW"
            ],
            "leadership_fraction": 0.666667,
            "sector": "Technology"
          }
        },
        "passed_industry_count": 2,
        "rule_version": "industry_leadership_breadth_breakout_v1"
      },
      "2025-05-07": {
        "industry_count": 19,
        "passed_industries": {
          "Semiconductors": {
            "avg_day_rs_vs_spy": 0.018672,
            "avg_ret20_excess_spy": 0.158539,
            "eligible_count": 5,
            "leader_count": 4,
            "leaders": [
              "AMD",
              "AVGO",
              "CRDO",
              "NVDA"
            ],
            "leadership_fraction": 0.8,
            "sector": "Technology"
          },
          "Software - Application": {
            "avg_day_rs_vs_spy": 0.006071,
            "avg_ret20_excess_spy": 0.152258,
            "eligible_count": 3,
            "leader_count": 2,
            "leaders": [
              "NOW",
              "SNOW"
            ],
            "leadership_fraction": 0.666667,
            "sector": "Technology"
          }
        },
        "passed_industry_count": 2,
        "rule_version": "industry_leadership_breadth_breakout_v1"
      }
    },
    "top_candidate_industries": {
      "Semiconductors": 53,
      "Software - Application": 14
    },
    "trading_days": 127,
    "unique_candidate_industries": 2,
    "unique_candidate_tickers": 7
  },
  "old_thin": {
    "candidate_days": 19,
    "candidate_source_tickers": 38,
    "industry_cache_coverage": {
      "cache_generated_at": "2026-05-27T05:25:19Z",
      "ok_share": 0.702128,
      "rule_version": "yfinance_gics_proxy_sector_v1",
      "sector_counts": {
        "Communication Services": 5,
        "Consumer Cyclical": 3,
        "Energy": 1,
        "Financial Services": 4,
        "Healthcare": 3,
        "Industrials": 5,
        "Technology": 12
      },
      "sector_unique_count": 7,
      "source": "yfinance.Ticker.info.sector",
      "status_counts": {
        "fetch_error": 12,
        "missing_info": 0,
        "missing_ticker": 2,
        "ok": 33
      },
      "status_shares": {
        "fetch_error": 0.255319,
        "missing_info": 0.0,
        "missing_ticker": 0.042553,
        "ok": 0.702128
      },
      "tickers_requested": 47,
      "tickers_unique": 47,
      "unresolved_sample": [
        "GLD",
        "IAU",
        "IWM",
        "QQQ",
        "SLV",
        "SNXX",
        "SPOT",
        "SPY",
        "TRIP",
        "TSLA",
        "TSM",
        "UNH",
        "V",
        "XOM"
      ]
    },
    "industry_pass_day_fraction": 0.362319,
    "industry_pass_days": 50,
    "raw_breakouts_after_industry_day_precheck": 47,
    "raw_industry_confirmed_breakouts": 30,
    "rule_version": "industry_leadership_breadth_breakout_v1",
    "sample_industry_context": {
      "2024-10-02": {
        "industry_count": 19,
        "passed_industries": {
          "Semiconductors": {
            "avg_day_rs_vs_spy": 0.008808,
            "avg_ret20_excess_spy": 0.05528,
            "eligible_count": 5,
            "leader_count": 2,
            "leaders": [
              "AVGO",
              "NVDA"
            ],
            "leadership_fraction": 0.4,
            "sector": "Technology"
          },
          "Software - Application": {
            "avg_day_rs_vs_spy": 0.00946,
            "avg_ret20_excess_spy": 0.002289,
            "eligible_count": 3,
            "leader_count": 2,
            "leaders": [
              "DDOG",
              "NOW"
            ],
            "leadership_fraction": 0.666667,
            "sector": "Technology"
          }
        },
        "passed_industry_count": 2,
        "rule_version": "industry_leadership_breadth_breakout_v1"
      },
      "2024-10-03": {
        "industry_count": 19,
        "passed_industries": {
          "Semiconductors": {
            "avg_day_rs_vs_spy": 0.020813,
            "avg_ret20_excess_spy": 0.1118,
            "eligible_count": 5,
            "leader_count": 5,
            "leaders": [
              "AMD",
              "AVGO",
              "CRDO",
              "MU",
              "NVDA"
            ],
            "leadership_fraction": 1.0,
            "sector": "Technology"
          },
          "Software - Application": {
            "avg_day_rs_vs_spy": 0.011952,
            "avg_ret20_excess_spy": 0.004449,
            "eligible_count": 3,
            "leader_count": 2,
            "leaders": [
              "DDOG",
              "NOW"
            ],
            "leadership_fraction": 0.666667,
            "sector": "Technology"
          }
        },
        "passed_industry_count": 2,
        "rule_version": "industry_leadership_breadth_breakout_v1"
      },
      "2024-10-04": {
        "industry_count": 19,
        "passed_industries": {
          "Semiconductors": {
            "avg_day_rs_vs_spy": 0.021418,
            "avg_ret20_excess_spy": 0.196423,
            "eligible_count": 5,
            "leader_count": 4,
            "leaders": [
              "AMD",
              "AVGO",
              "CRDO",
              "NVDA"
            ],
            "leadership_fraction": 0.8,
            "sector": "Technology"
          },
          "Software - Application": {
            "avg_day_rs_vs_spy": 0.028491,
            "avg_ret20_excess_spy": 0.040889,
            "eligible_count": 3,
            "leader_count": 2,
            "leaders": [
              "DDOG",
              "NOW"
            ],
            "leadership_fraction": 0.666667,
            "sector": "Technology"
          }
        },
        "passed_industry_count": 2,
        "rule_version": "industry_leadership_breadth_breakout_v1"
      },
      "2024-10-07": {
        "industry_count": 19,
        "passed_industries": {
          "Semiconductors": {
            "avg_day_rs_vs_spy": 0.013172,
            "avg_ret20_excess_spy": 0.201699,
            "eligible_count": 5,
            "leader_count": 5,
            "leaders": [
              "AMD",
              "AVGO",
              "CRDO",
              "MU",
              "NVDA"
            ],
            "leadership_fraction": 1.0,
            "sector": "Technology"
          }
        },
        "passed_industry_count": 1,
        "rule_version": "industry_leadership_breadth_breakout_v1"
      },
      "2024-10-08": {
        "industry_count": 19,
        "passed_industries": {
          "Semiconductors": {
            "avg_day_rs_vs_spy": 0.013705,
            "avg_ret20_excess_spy": 0.192053,
            "eligible_count": 5,
            "leader_count": 4,
            "leaders": [
              "AMD",
              "AVGO",
              "CRDO",
              "NVDA"
            ],
            "leadership_fraction": 0.8,
            "sector": "Technology"
          },
          "Software - Application": {
            "avg_day_rs_vs_spy": -0.000777,
            "avg_ret20_excess_spy": 0.034259,
            "eligible_count": 3,
            "leader_count": 2,
            "leaders": [
              "DDOG",
              "NOW"
            ],
            "leadership_fraction": 0.666667,
            "sector": "Technology"
          }
        },
        "passed_industry_count": 2,
        "rule_version": "industry_leadership_breadth_breakout_v1"
      }
    },
    "top_candidate_industries": {
      "Semiconductors": 13,
      "Software - Application": 17
    },
    "trading_days": 138,
    "unique_candidate_industries": 2,
    "unique_candidate_tickers": 8
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0032,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.430604,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.353713,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 70,
  "target_trade_count_min": 30,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 2,
  "windows_ev_regressed": 1,
  "windows_pnl_regressed": 1
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
