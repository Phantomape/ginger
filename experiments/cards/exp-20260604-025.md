# Theme-Density No Core-Overlap Candidate Scout

- experiment_id: `exp-20260604-025`
- decision: `rejected_theme_density_no_core_overlap`
- EV delta: `0.1893`
- PnL delta: `$5,469.59`
- target trades: `43`

## Three-Window Result

| Window | Before EV | After EV | dEV | dPnL | Trades | Post-filter candidates | Filtered overlap |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.9321 | -0.2307 | $-2,369.39 | 6 | 18 | 3 |
| mid_weak | 2.1402 | 2.5670 | +0.4268 | $+8,029.45 | 24 | 52 | 8 |
| old_thin | 0.5911 | 0.5843 | -0.0068 | $-190.47 | 13 | 24 | 1 |

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0001,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.518334,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.370531,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 43,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 1,
  "windows_ev_regressed": 2,
  "windows_pnl_regressed": 2
}
```

## Theme-Density Audit

```json
{
  "late_strong": {
    "candidate_days": 13,
    "candidate_source_tickers": 39,
    "core_overlap_discriminator_rule_version": "theme_density_no_same_day_core_overlap_candidate_source_v1",
    "post_core_overlap_filter_candidate_count": 18,
    "post_core_overlap_filter_candidate_days": 11,
    "post_core_overlap_filter_unique_tickers": 9,
    "pre_core_overlap_filter_candidate_count": 21,
    "raw_liquid_theme_density_breakout_hits": 21,
    "rule_version": "theme_density_confirmed_breakout_v1",
    "same_day_ab_overlap_filtered_count": 3,
    "same_day_ab_overlap_filtered_days": 2,
    "sample_filtered_candidates": [
      {
        "alters_orders": false,
        "breakout_above_prior_20d_high_pct": 0.008574,
        "candidate_day_return": 0.021768,
        "candidate_day_rs_vs_spy": 0.016544,
        "candidate_day_spy_return": 0.005223,
        "close": 397.413,
        "date": "2026-01-22",
        "dollar_volume": 15740576125.12,
        "filter_reason": "same_day_ab_overlap",
        "pct_above_50d_ma": 0.463967,
        "same_day_ab_entry_count": 2,
        "same_day_ab_overlap": true,
        "same_ticker_ab_overlap": false,
        "sector": "Technology",
        "selected_theme": "ai",
        "source_universe": "current_production_universe_ohlcv",
        "strategy": "theme_density_breakout",
        "theme_density_context": {
          "above_50d_count": 4,
          "alters_orders": false,
          "asof_date": "2026-01-22",
          "breakout_count": 2,
          "eligible_ticker_count": 6,
          "known_at": "after_signal_date_close_before_next_open_paper_entry",
          "members": [
            "AMD",
            "AVGO",
            "CRDO",
            "MU",
            "NVDA",
            "TSM"
          ],
          "passed": true,
          "positive_ret20_count": 4,
          "rule_version": "theme_density_confirmed_breakout_v1",
          "spy_ret20": 0.00606,
          "status": "passed",
          "theme": "ai",
          "theme_above_50d_fraction": 0.666667,
          "theme_avg_ret20": 0.099202,
          "theme_avg_ret20_excess_spy": 0.093142,
          "theme_breakout_fraction": 0.333333,
          "theme_positive_ret20_fraction": 0.666667,
          "trade_enabled": false
        },
        "theme_density_rule_version": "theme_density_confirmed_breakout_v1",
        "theme_density_score": 1.254816,
        "themes": [
          "ai"
        ],
        "ticker": "MU",
        "trade_enabled": false,
        "volume_ratio_20": 1.260333
      },
      {
        "alters_orders": false,
        "breakout_above_prior_20d_high_pct": 0.011491,
        "candidate_day_return": 0.02593,
        "candidate_day_rs_vs_spy": 0.013845,
        "candidate_day_spy_return": 0.012086,
        "close": 270.23,
        "date": "2026-04-17",
        "dollar_volume": 16601905000.96,
        "filter_reason": "same_day_ab_overlap",
        "pct_above_50d_ma": 0.036659,
        "same_day_ab_entry_count": 1,
        "same_day_ab_overlap": true,
        "same_ticker_ab_overlap": false,
        "sector": "Technology",
        "selected_theme": "mega_cap",
        "source_universe": "current_production_universe_ohlcv",
        "strategy": "theme_density_breakout",
        "theme_density_context": {
          "above_50d_count": 7,
          "alters_orders": false,
          "asof_date": "2026-04-17",
          "breakout_count": 6,
          "eligible_ticker_count": 7,
          "known_at": "after_signal_date_close_before_next_open_paper_entry",
          "members": [
            "AAPL",
            "AMZN",
            "GOOG",
            "META",
            "MSFT",
            "NVDA",
            "TSLA"
          ],
          "passed": true,
          "positive_ret20_count": 7,
          "rule_version": "theme_density_confirmed_breakout_v1",
          "spy_ret20": 0.079235,
          "status": "passed",
          "theme": "mega_cap",
          "theme_above_50d_fraction": 1.0,
          "theme_avg_ret20": 0.114346,
          "theme_avg_ret20_excess_spy": 0.035111,
          "theme_breakout_fraction": 0.857143,
          "theme_positive_ret20_fraction": 1.0,
          "trade_enabled": false
        },
        "theme_density_rule_version": "theme_density_confirmed_breakout_v1",
        "theme_density_score": 1.992123,
        "themes": [
          "mega_cap"
        ],
        "ticker": "AAPL",
        "trade_enabled": false,
        "volume_ratio_20": 1.433372
      },
      {
        "alters_orders": false,
        "breakout_above_prior_20d_high_pct": 0.011079,
        "candidate_day_return": 0.030136,
        "candidate_day_rs_vs_spy": 0.018051,
        "candidate_day_spy_return": 0.012086,
        "close": 400.62,
        "date": "2026-04-17",
        "dollar_volume": 36312196357.42,
        "filter_reason": "same_day_ab_overlap",
        "pct_above_50d_ma": 0.026072,
        "same_day_ab_entry_count": 1,
        "same_day_ab_overlap": true,
        "same_ticker_ab_overlap": false,
        "sector": "Consumer Discretionary",
        "selected_theme": "mega_cap",
        "source_universe": "current_production_universe_ohlcv",
        "strategy": "theme_density_breakout",
        "theme_density_context": {
          "above_50d_count": 7,
          "alters_orders": false,
          "asof_date": "2026-04-17",
          "breakout_count": 6,
          "eligible_ticker_count": 7,
          "known_at": "after_signal_date_close_before_next_open_paper_entry",
          "members": [
            "AAPL",
            "AMZN",
            "GOOG",
            "META",
            "MSFT",
            "NVDA",
            "TSLA"
          ],
          "passed": true,
          "positive_ret20_count": 7,
          "rule_version": "theme_density_confirmed_breakout_v1",
          "spy_ret20": 0.079235,
          "status": "passed",
          "theme": "mega_cap",
          "theme_above_50d_fraction": 1.0,
          "theme_avg_ret20": 0.114346,
          "theme_avg_ret20_excess_spy": 0.035111,
          "theme_breakout_fraction": 0.857143,
          "theme_positive_ret20_fraction": 1.0,
          "trade_enabled": false
        },
        "theme_density_rule_version": "theme_density_confirmed_breakout_v1",
        "theme_density_score": 1.906564,
        "themes": [
          "mega_cap"
        ],
        "ticker": "TSLA",
        "trade_enabled": false,
        "volume_ratio_20": 1.319607
      }
    ],
    "selected_theme_counts": {
      "ai": 13,
      "mega_cap": 8
    },
    "theme_groups": {
      "ai": [
        "AMD",
        "AVGO",
        "CRDO",
        "MU",
        "NVDA",
        "TSM"
      ],
      "crypto": [
        "COIN"
      ],
      "mega_cap": [
        "AAPL",
        "AMZN",
        "GOOG",
        "META",
        "MSFT",
        "NVDA",
        "TSLA"
      ]
    },
    "theme_pass_counts": {
      "ai": 16,
      "mega_cap": 8
    },
    "theme_pass_days": 17,
    "theme_pass_instances": 145,
    "trading_days": 123,
    "unique_candidate_tickers": 11
  },
  "mid_weak": {
    "candidate_days": 28,
    "candidate_source_tickers": 38,
    "core_overlap_discriminator_rule_version": "theme_density_no_same_day_core_overlap_candidate_source_v1",
    "post_core_overlap_filter_candidate_count": 52,
    "post_core_overlap_filter_candidate_days": 24,
    "post_core_overlap_filter_unique_tickers": 12,
    "pre_core_overlap_filter_candidate_count": 60,
    "raw_liquid_theme_density_breakout_hits": 60,
    "rule_version": "theme_density_confirmed_breakout_v1",
    "same_day_ab_overlap_filtered_count": 8,
    "same_day_ab_overlap_filtered_days": 4,
    "sample_filtered_candidates": [
      {
        "alters_orders": false,
        "breakout_above_prior_20d_high_pct": 0.040573,
        "candidate_day_return": 0.046772,
        "candidate_day_rs_vs_spy": 0.045494,
        "candidate_day_spy_return": 0.001278,
        "close": 117.72,
        "date": "2025-05-14",
        "dollar_volume": 10211468469.89,
        "filter_reason": "same_day_ab_overlap",
        "pct_above_50d_ma": 0.194121,
        "same_day_ab_entry_count": 1,
        "same_day_ab_overlap": true,
        "same_ticker_ab_overlap": false,
        "sector": "Technology",
        "selected_theme": "ai",
        "source_universe": "current_production_universe_ohlcv",
        "strategy": "theme_density_breakout",
        "theme_density_context": {
          "above_50d_count": 6,
          "alters_orders": false,
          "asof_date": "2025-05-14",
          "breakout_count": 3,
          "eligible_ticker_count": 6,
          "known_at": "after_signal_date_close_before_next_open_paper_entry",
          "members": [
            "AMD",
            "AVGO",
            "CRDO",
            "MU",
            "NVDA",
            "TSM"
          ],
          "passed": true,
          "positive_ret20_count": 6,
          "rule_version": "theme_density_confirmed_breakout_v1",
          "spy_ret20": 0.092967,
          "status": "passed",
          "theme": "ai",
          "theme_above_50d_fraction": 1.0,
          "theme_avg_ret20": 0.307411,
          "theme_avg_ret20_excess_spy": 0.214444,
          "theme_breakout_fraction": 0.5,
          "theme_positive_ret20_fraction": 1.0,
          "trade_enabled": false
        },
        "theme_density_rule_version": "theme_density_confirmed_breakout_v1",
        "theme_density_score": 3.005446,
        "themes": [
          "ai"
        ],
        "ticker": "AMD",
        "trade_enabled": false,
        "volume_ratio_20": 2.13638
      },
      {
        "alters_orders": false,
        "breakout_above_prior_20d_high_pct": 0.031398,
        "candidate_day_return": 0.041638,
        "candidate_day_rs_vs_spy": 0.04036,
        "candidate_day_spy_return": 0.001278,
        "close": 135.3081,
        "date": "2025-05-14",
        "dollar_volume": 38046041342.19,
        "filter_reason": "same_day_ab_overlap",
        "pct_above_50d_ma": 0.214529,
        "same_day_ab_entry_count": 1,
        "same_day_ab_overlap": true,
        "same_ticker_ab_overlap": false,
        "sector": "Technology",
        "selected_theme": "ai",
        "source_universe": "current_production_universe_ohlcv",
        "strategy": "theme_density_breakout",
        "theme_density_context": {
          "above_50d_count": 6,
          "alters_orders": false,
          "asof_date": "2025-05-14",
          "breakout_count": 3,
          "eligible_ticker_count": 6,
          "known_at": "after_signal_date_close_before_next_open_paper_entry",
          "members": [
            "AMD",
            "AVGO",
            "CRDO",
            "MU",
            "NVDA",
            "TSM"
          ],
          "passed": true,
          "positive_ret20_count": 6,
          "rule_version": "theme_density_confirmed_breakout_v1",
          "spy_ret20": 0.092967,
          "status": "passed",
          "theme": "ai",
          "theme_above_50d_fraction": 1.0,
          "theme_avg_ret20": 0.307411,
          "theme_avg_ret20_excess_spy": 0.214444,
          "theme_breakout_fraction": 0.5,
          "theme_positive_ret20_fraction": 1.0,
          "trade_enabled": false
        },
        "theme_density_rule_version": "theme_density_confirmed_breakout_v1",
        "theme_density_score": 2.030193,
        "themes": [
          "ai",
          "mega_cap"
        ],
        "ticker": "NVDA",
        "trade_enabled": false,
        "volume_ratio_20": 1.224594
      },
      {
        "alters_orders": false,
        "breakout_above_prior_20d_high_pct": 0.029888,
        "candidate_day_return": 0.04074,
        "candidate_day_rs_vs_spy": 0.039462,
        "candidate_day_spy_return": 0.001278,
        "close": 347.68,
        "date": "2025-05-14",
        "dollar_volume": 47631220260.6,
        "filter_reason": "same_day_ab_overlap",
        "pct_above_50d_ma": 0.324746,
        "same_day_ab_entry_count": 1,
        "same_day_ab_overlap": true,
        "same_ticker_ab_overlap": false,
        "sector": "Consumer Discretionary",
        "selected_theme": "mega_cap",
        "source_universe": "current_production_universe_ohlcv",
        "strategy": "theme_density_breakout",
        "theme_density_context": {
          "above_50d_count": 7,
          "alters_orders": false,
          "asof_date": "2025-05-14",
          "breakout_count": 3,
          "eligible_ticker_count": 7,
          "known_at": "after_signal_date_close_before_next_open_paper_entry",
          "members": [
            "AAPL",
            "AMZN",
            "GOOG",
            "META",
            "MSFT",
            "NVDA",
            "TSLA"
          ],
          "passed": true,
          "positive_ret20_count": 7,
          "rule_version": "theme_density_confirmed_breakout_v1",
          "spy_ret20": 0.092967,
          "status": "passed",
          "theme": "mega_cap",
          "theme_above_50d_fraction": 1.0,
          "theme_avg_ret20": 0.183822,
          "theme_avg_ret20_excess_spy": 0.090855,
          "theme_breakout_fraction": 0.428571,
          "theme_positive_ret20_fraction": 1.0,
          "trade_enabled": false
        },
        "theme_density_rule_version": "theme_density_confirmed_breakout_v1",
        "theme_density_score": 1.703315,
        "themes": [
          "mega_cap"
        ],
        "ticker": "TSLA",
        "trade_enabled": false,
        "volume_ratio_20": 1.227136
      },
      {
        "alters_orders": false,
        "breakout_above_prior_20d_high_pct": 0.083459,
        "candidate_day_return": 0.147965,
        "candidate_day_rs_vs_spy": 0.142262,
        "candidate_day_spy_return": 0.005703,
        "close": 71.92,
        "date": "2025-06-03",
        "dollar_volume": 1628685894.53,
        "filter_reason": "same_day_ab_overlap",
        "pct_above_50d_ma": 0.500478,
        "same_day_ab_entry_count": 1,
        "same_day_ab_overlap": true,
        "same_ticker_ab_overlap": false,
        "sector": "Technology",
        "selected_theme": "ai",
        "source_universe": "current_production_universe_ohlcv",
        "strategy": "theme_density_breakout",
        "theme_density_context": {
          "above_50d_count": 6,
          "alters_orders": false,
          "asof_date": "2025-06-03",
          "breakout_count": 3,
          "eligible_ticker_count": 6,
          "known_at": "after_signal_date_close_before_next_open_paper_entry",
          "members": [
            "AMD",
            "AVGO",
            "CRDO",
            "MU",
            "NVDA",
            "TSM"
          ],
          "passed": true,
          "positive_ret20_count": 6,
          "rule_version": "theme_density_confirmed_breakout_v1",
          "spy_ret20": 0.057816,
          "status": "passed",
          "theme": "ai",
          "theme_above_50d_fraction": 1.0,
          "theme_avg_ret20": 0.25923,
          "theme_avg_ret20_excess_spy": 0.201414,
          "theme_breakout_fraction": 0.5,
          "theme_positive_ret20_fraction": 1.0,
          "trade_enabled": false
        },
        "theme_density_rule_version": "theme_density_confirmed_breakout_v1",
        "theme_density_score": 5.64904,
        "themes": [
          "ai"
        ],
        "ticker": "CRDO",
        "trade_enabled": false,
        "volume_ratio_20": 5.820001
      },
      {
        "alters_orders": false,
        "breakout_above_prior_20d_high_pct": 0.0274,
        "candidate_day_return": 0.032729,
        "candidate_day_rs_vs_spy": 0.027026,
        "candidate_day_spy_return": 0.005703,
        "close": 254.7856,
        "date": "2025-06-03",
        "dollar_volume": 7740437447.29,
        "filter_reason": "same_day_ab_overlap",
        "pct_above_50d_ma": 0.303717,
        "same_day_ab_entry_count": 1,
        "same_day_ab_overlap": true,
        "same_ticker_ab_overlap": false,
        "sector": "Technology",
        "selected_theme": "ai",
        "source_universe": "current_production_universe_ohlcv",
        "strategy": "theme_density_breakout",
        "theme_density_context": {
          "above_50d_count": 6,
          "alters_orders": false,
          "asof_date": "2025-06-03",
          "breakout_count": 3,
          "eligible_ticker_count": 6,
          "known_at": "after_signal_date_close_before_next_open_paper_entry",
          "members": [
            "AMD",
            "AVGO",
            "CRDO",
            "MU",
            "NVDA",
            "TSM"
          ],
          "passed": true,
          "positive_ret20_count": 6,
          "rule_version": "theme_density_confirmed_breakout_v1",
          "spy_ret20": 0.057816,
          "status": "passed",
          "theme": "ai",
          "theme_above_50d_fraction": 1.0,
          "theme_avg_ret20": 0.25923,
          "theme_avg_ret20_excess_spy": 0.201414,
          "theme_breakout_fraction": 0.5,
          "theme_positive_ret20_fraction": 1.0,
          "trade_enabled": false
        },
        "theme_density_rule_version": "theme_density_confirmed_breakout_v1",
        "theme_density_score": 2.280859,
        "themes": [
          "ai"
        ],
        "ticker": "AVGO",
        "trade_enabled": false,
        "volume_ratio_20": 1.606647
      },
      {
        "alters_orders": false,
        "breakout_above_prior_20d_high_pct": 0.026297,
        "candidate_day_return": 0.041454,
        "candidate_day_rs_vs_spy": 0.035752,
        "candidate_day_spy_return": 0.005703,
        "close": 102.0058,
        "date": "2025-06-03",
        "dollar_volume": 2321408024.43,
        "filter_reason": "same_day_ab_overlap",
        "pct_above_50d_ma": 0.215822,
        "same_day_ab_entry_count": 1,
        "same_day_ab_overlap": true,
        "same_ticker_ab_overlap": false,
        "sector": "Technology",
        "selected_theme": "ai",
        "source_universe": "current_production_universe_ohlcv",
        "strategy": "theme_density_breakout",
        "theme_density_context": {
          "above_50d_count": 6,
          "alters_orders": false,
          "asof_date": "2025-06-03",
          "breakout_count": 3,
          "eligible_ticker_count": 6,
          "known_at": "after_signal_date_close_before_next_open_paper_entry",
          "members": [
            "AMD",
            "AVGO",
            "CRDO",
            "MU",
            "NVDA",
            "TSM"
          ],
          "passed": true,
          "positive_ret20_count": 6,
          "rule_version": "theme_density_confirmed_breakout_v1",
          "spy_ret20": 0.057816,
          "status": "passed",
          "theme": "ai",
          "theme_above_50d_fraction": 1.0,
          "theme_avg_ret20": 0.25923,
          "theme_avg_ret20_excess_spy": 0.201414,
          "theme_breakout_fraction": 0.5,
          "theme_positive_ret20_fraction": 1.0,
          "trade_enabled": false
        },
        "theme_density_rule_version": "theme_density_confirmed_breakout_v1",
        "theme_density_score": 2.005436,
        "themes": [
          "ai"
        ],
        "ticker": "MU",
        "trade_enabled": false,
        "volume_ratio_20": 1.273454
      },
      {
        "alters_orders": false,
        "breakout_above_prior_20d_high_pct": 0.012264,
        "candidate_day_return": 0.01509,
        "candidate_day_rs_vs_spy": 0.012778,
        "candidate_day_spy_return": 0.002312,
        "close": 248.7565,
        "date": "2025-09-09",
        "dollar_volume": 3344133135.38,
        "filter_reason": "same_day_ab_overlap",
        "pct_above_50d_ma": 0.061646,
        "same_day_ab_entry_count": 1,
        "same_day_ab_overlap": true,
        "same_ticker_ab_overlap": false,
        "sector": "Technology",
        "selected_theme": "ai",
        "source_universe": "current_production_universe_ohlcv",
        "strategy": "theme_density_breakout",
        "theme_density_context": {
          "above_50d_count": 4,
          "alters_orders": false,
          "asof_date": "2025-09-09",
          "breakout_count": 2,
          "eligible_ticker_count": 6,
          "known_at": "after_signal_date_close_before_next_open_paper_entry",
          "members": [
            "AMD",
            "AVGO",
            "CRDO",
            "MU",
            "NVDA",
            "TSM"
          ],
          "passed": true,
          "positive_ret20_count": 4,
          "rule_version": "theme_density_confirmed_breakout_v1",
          "spy_ret20": 0.02266,
          "status": "passed",
          "theme": "ai",
          "theme_above_50d_fraction": 0.666667,
          "theme_avg_ret20": 0.056117,
          "theme_avg_ret20_excess_spy": 0.033457,
          "theme_breakout_fraction": 0.333333,
          "theme_positive_ret20_fraction": 0.666667,
          "trade_enabled": false
        },
        "theme_density_rule_version": "theme_density_confirmed_breakout_v1",
        "theme_density_score": 1.174059,
        "themes": [
          "ai"
        ],
        "ticker": "TSM",
        "trade_enabled": false,
        "volume_ratio_20": 1.314243
      },
      {
        "alters_orders": false,
        "breakout_above_prior_20d_high_pct": 0.028044,
        "candidate_day_return": 0.034876,
        "candidate_day_rs_vs_spy": 0.033724,
        "candidate_day_spy_return": 0.001152,
        "close": 169.73,
        "date": "2025-10-02",
        "dollar_volume": 9415805458.98,
        "filter_reason": "same_day_ab_overlap",
        "pct_above_50d_ma": 0.024079,
        "same_day_ab_entry_count": 1,
        "same_day_ab_overlap": true,
        "same_ticker_ab_overlap": false,
        "sector": "Technology",
        "selected_theme": "ai",
        "source_universe": "current_production_universe_ohlcv",
        "strategy": "theme_density_breakout",
        "theme_density_context": {
          "above_50d_count": 6,
          "alters_orders": false,
          "asof_date": "2025-10-02",
          "breakout_count": 3,
          "eligible_ticker_count": 6,
          "known_at": "after_signal_date_close_before_next_open_paper_entry",
          "members": [
            "AMD",
            "AVGO",
            "CRDO",
            "MU",
            "NVDA",
            "TSM"
          ],
          "passed": true,
          "positive_ret20_count": 6,
          "rule_version": "theme_density_confirmed_breakout_v1",
          "spy_ret20": 0.033823,
          "status": "passed",
          "theme": "ai",
          "theme_above_50d_fraction": 1.0,
          "theme_avg_ret20": 0.180161,
          "theme_avg_ret20_excess_spy": 0.146338,
          "theme_breakout_fraction": 0.5,
          "theme_positive_ret20_fraction": 1.0,
          "trade_enabled": false
        },
        "theme_density_rule_version": "theme_density_confirmed_breakout_v1",
        "theme_density_score": 1.865079,
        "themes": [
          "ai"
        ],
        "ticker": "AMD",
        "trade_enabled": false,
        "volume_ratio_20": 1.252203
      }
    ],
    "selected_theme_counts": {
      "ai": 47,
      "mega_cap": 13
    },
    "theme_groups": {
      "ai": [
        "AMD",
        "AVGO",
        "CRDO",
        "MU",
        "NVDA",
        "TSM"
      ],
      "crypto": [
        "COIN"
      ],
      "mega_cap": [
        "AAPL",
        "AMZN",
        "GOOG",
        "META",
        "MSFT",
        "NVDA",
        "TSLA"
      ]
    },
    "theme_pass_counts": {
      "ai": 33,
      "mega_cap": 19
    },
    "theme_pass_days": 41,
    "theme_pass_instances": 320,
    "trading_days": 127,
    "unique_candidate_tickers": 12
  },
  "old_thin": {
    "candidate_days": 14,
    "candidate_source_tickers": 38,
    "core_overlap_discriminator_rule_version": "theme_density_no_same_day_core_overlap_candidate_source_v1",
    "post_core_overlap_filter_candidate_count": 24,
    "post_core_overlap_filter_candidate_days": 13,
    "post_core_overlap_filter_unique_tickers": 11,
    "pre_core_overlap_filter_candidate_count": 25,
    "raw_liquid_theme_density_breakout_hits": 25,
    "rule_version": "theme_density_confirmed_breakout_v1",
    "same_day_ab_overlap_filtered_count": 1,
    "same_day_ab_overlap_filtered_days": 1,
    "sample_filtered_candidates": [
      {
        "alters_orders": false,
        "breakout_above_prior_20d_high_pct": 0.026012,
        "candidate_day_return": 0.02739,
        "candidate_day_rs_vs_spy": 0.021402,
        "candidate_day_spy_return": 0.005988,
        "close": 38.26,
        "date": "2024-10-11",
        "dollar_volume": 117534714.84,
        "filter_reason": "same_day_ab_overlap",
        "pct_above_50d_ma": 0.271417,
        "same_day_ab_entry_count": 1,
        "same_day_ab_overlap": true,
        "same_ticker_ab_overlap": false,
        "sector": "Technology",
        "selected_theme": "ai",
        "source_universe": "current_production_universe_ohlcv",
        "strategy": "theme_density_breakout",
        "theme_density_context": {
          "above_50d_count": 6,
          "alters_orders": false,
          "asof_date": "2024-10-11",
          "breakout_count": 2,
          "eligible_ticker_count": 6,
          "known_at": "after_signal_date_close_before_next_open_paper_entry",
          "members": [
            "AMD",
            "AVGO",
            "CRDO",
            "MU",
            "NVDA",
            "TSM"
          ],
          "passed": true,
          "positive_ret20_count": 6,
          "rule_version": "theme_density_confirmed_breakout_v1",
          "spy_ret20": 0.034426,
          "status": "passed",
          "theme": "ai",
          "theme_above_50d_fraction": 1.0,
          "theme_avg_ret20": 0.156912,
          "theme_avg_ret20_excess_spy": 0.122486,
          "theme_breakout_fraction": 0.333333,
          "theme_positive_ret20_fraction": 1.0,
          "trade_enabled": false
        },
        "theme_density_rule_version": "theme_density_confirmed_breakout_v1",
        "theme_density_score": 1.75112,
        "themes": [
          "ai"
        ],
        "ticker": "CRDO",
        "trade_enabled": false,
        "volume_ratio_20": 1.444967
      }
    ],
    "selected_theme_counts": {
      "ai": 10,
      "mega_cap": 15
    },
    "theme_groups": {
      "ai": [
        "AMD",
        "AVGO",
        "CRDO",
        "MU",
        "NVDA",
        "TSM"
      ],
      "crypto": [
        "COIN"
      ],
      "mega_cap": [
        "AAPL",
        "AMZN",
        "GOOG",
        "META",
        "MSFT",
        "NVDA",
        "TSLA"
      ]
    },
    "theme_pass_counts": {
      "ai": 11,
      "mega_cap": 13
    },
    "theme_pass_days": 21,
    "theme_pass_instances": 154,
    "trading_days": 138,
    "unique_candidate_tickers": 11
  }
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
