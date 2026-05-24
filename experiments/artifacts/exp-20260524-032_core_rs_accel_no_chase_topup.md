# exp-20260524-032 core_rs_accel_no_chase_topup

## Hypothesis
Already-qualified core stock signals with improving 20-day SPY-relative strength versus the prior 20-day window, while not opening with a 3% signal-day gap chase, may be cleaner continuation setups. A small cap-aware post-sizing top-up could improve EV without changing entries, exits, ranking, universe, news, or LLM.

## Decision
- decision: rejected_failed_gate4
- selected_variant: rs_accel_no_chase_topup_10125
- gate4_passed: False
- aggregate_ev_delta: -0.0082
- aggregate_pnl_delta: 73.64
- improved_windows: none
- regressed_windows: late_strong

## Production Impact
{
  "backtester_adapter_changed": false,
  "parity_test_added": false,
  "promotion_required_if_accepted": "Move rs_accel_no_chase feature/state/sizing into shared feature_layer/risk_engine/portfolio_engine with parity tests, then rerun the same three-window protocol before live/default use.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}

## Gate Questions
{
  "1_alpha_hypothesis": "Core allocation: RS acceleration versus SPY plus no 3% signal-day gap chase may identify cleaner continuation among already-qualified trend_long/breakout_long stock signals. This matches the playbook's new production-visible field preference.",
  "2_history_check": {
    "exp-20260508-029": "Proposed shadow tag only; not yet completed.",
    "exp-20260524-003": "Relative-strength component band top-up was too sparse.",
    "exp-20260524-011": "Raw trend component top-up regressed and concentrated.",
    "exp-20260524-018": "Alpha/breadth midpoint top-up had too little changed sample.",
    "exp-20260524-019": "Signal-day close-location top-up regressed aggregate EV."
  },
  "3_single_causal_variable": "Only the post-sizing multiplier for the fixed rs_accel_no_chase state changes; all entries, exits, ranking, slots, universe, LLM, and news logic stay fixed.",
  "4_acceptance_standard": "docs/backtesting.md canonical three-window before/after, requiring positive aggregate EV/PnL, at least two EV-improved windows, no EV-regressed windows, drawdown/survival/trade-count/sample guards, and concentration guard pass.",
  "5_reproducibility": ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260524_032_core_rs_accel_no_chase_topup.py"
}

## Gate 4
{
  "adjusted_signal_count": 4,
  "affected_window_count": 3,
  "aggregate_delta": {
    "expected_value_score_sum": -0.0082,
    "max_consecutive_losses_max": 0,
    "max_drawdown_pct_max": 0.0,
    "survival_rate_min": 0.0,
    "tail_loss_share_max": 0.0,
    "total_pnl_sum": 73.64,
    "trade_count_sum": 0,
    "worst_trade_pct_min": 0.0
  },
  "changed_trade_count": 1,
  "changed_trades": {
    "late_strong": [
      {
        "entry_date": "2026-01-07",
        "incremental_pnl": 73.64,
        "key": "MU|2026-01-07|breakout_long|340.74",
        "pnl_after": 9499.12,
        "pnl_before": 9425.48,
        "sector": "Technology",
        "shares_after": 129,
        "shares_before": 128,
        "strategy": "breakout_long",
        "ticker": "MU"
      }
    ]
  },
  "concentration": {
    "max_single_positive_ticker_share": 1.0,
    "passed": false,
    "positive_incremental_pnl": 73.64,
    "positive_incremental_pnl_by_ticker": {
      "MU": 73.64
    }
  },
  "guardrails": {
    "max_drawdown_worse_guardrail": 0.005,
    "max_single_positive_ticker_share": 0.5,
    "min_adjusted_signal_count": 4,
    "min_affected_window_count": 2,
    "min_changed_trade_count": 4,
    "min_survival_rate": 0.05,
    "min_trade_count_sum": 58,
    "requires_no_ev_regression_windows": true
  },
  "improved_windows": [],
  "passed": false,
  "regressed_windows": [
    "late_strong"
  ],
  "window_deltas": {
    "late_strong": {
      "expected_value_score": -0.0082,
      "max_consecutive_losses": 0,
      "max_drawdown_pct": 0.0003,
      "sharpe_daily": -0.01,
      "signals_generated": 0,
      "signals_survived": 0,
      "survival_rate": 0.0,
      "tail_loss_share": 0.0,
      "total_pnl": 73.64,
      "total_return_pct": 0.0008,
      "trade_count": 0,
      "win_rate": 0.0,
      "worst_trade_pct": 0.0
    },
    "mid_weak": {
      "expected_value_score": 0.0,
      "max_consecutive_losses": 0,
      "max_drawdown_pct": 0.0,
      "sharpe_daily": 0.0,
      "signals_generated": 0,
      "signals_survived": 0,
      "survival_rate": 0.0,
      "tail_loss_share": 0.0,
      "total_pnl": 0.0,
      "total_return_pct": 0.0,
      "trade_count": 0,
      "win_rate": 0.0,
      "worst_trade_pct": 0.0
    },
    "old_thin": {
      "expected_value_score": 0.0,
      "max_consecutive_losses": 0,
      "max_drawdown_pct": 0.0,
      "sharpe_daily": 0.0,
      "signals_generated": 0,
      "signals_survived": 0,
      "survival_rate": 0.0,
      "tail_loss_share": 0.0,
      "total_pnl": 0.0,
      "total_return_pct": 0.0,
      "trade_count": 0,
      "win_rate": 0.0,
      "worst_trade_pct": 0.0
    }
  }
}

## Sweep Summary
[
  {
    "adjustment_summary": {
      "count": 4,
      "sample": {
        "late_strong": [
          {
            "baseline_shares": 128,
            "confidence_score": 1.0,
            "current_rel_spy_20d": 0.4364,
            "days_to_earnings": 51,
            "gap_vulnerability_pct": 0.0706,
            "multiplier": 1.0125,
            "new_shares": 129,
            "previous_rel_spy_20d": -0.027602,
            "price_vs_200ma_extension_state": true,
            "regime_exit_bucket": "risk_on",
            "rs20_entry_state_leader": true,
            "rs_accel_delta_20d": 0.464002,
            "sector": "Technology",
            "signal_day_open_gap_pct": 0.019638,
            "signal_day_ticker_green_candle": true,
            "signal_day_ticker_outperformed_spy": true,
            "spy_relative_leader": true,
            "strategy": "breakout_long",
            "ticker": "MU",
            "trade_quality_score": 0.919
          },
          {
            "baseline_shares": 184,
            "confidence_score": 0.93,
            "current_rel_spy_20d": 0.1633,
            "days_to_earnings": 9,
            "gap_vulnerability_pct": 0.0627,
            "multiplier": 1.0125,
            "new_shares": 186,
            "previous_rel_spy_20d": -0.010117,
            "price_vs_200ma_extension_state": true,
            "regime_exit_bucket": "risk_on",
            "rs20_entry_state_leader": true,
            "rs_accel_delta_20d": 0.173417,
            "sector": "Technology",
            "signal_day_open_gap_pct": 0.017549,
            "signal_day_ticker_green_candle": true,
            "signal_day_ticker_outperformed_spy": true,
            "spy_relative_leader": true,
            "strategy": "breakout_long",
            "ticker": "AMD",
            "trade_quality_score": 0.917
          }
        ],
        "mid_weak": [
          {
            "baseline_shares": 122,
            "confidence_score": 0.93,
            "current_rel_spy_20d": 0.2525,
            "days_to_earnings": 64,
            "gap_vulnerability_pct": 0.0765,
            "multiplier": 1.0125,
            "new_shares": 123,
            "previous_rel_spy_20d": -0.137982,
            "price_vs_200ma_extension_state": true,
            "regime_exit_bucket": "risk_on",
            "rs20_entry_state_leader": true,
            "rs_accel_delta_20d": 0.390482,
            "sector": "Technology",
            "signal_day_open_gap_pct": 0.017103,
            "signal_day_ticker_green_candle": true,
            "signal_day_ticker_outperformed_spy": true,
            "spy_relative_leader": true,
            "strategy": "breakout_long",
            "ticker": "APP",
            "trade_quality_score": 0.972
          }
        ],
        "old_thin": [
          {
            "baseline_shares": 423,
            "confidence_score": 1.0,
            "current_rel_spy_20d": 0.5598,
            "days_to_earnings": 62,
            "gap_vulnerability_pct": 0.0794,
            "multiplier": 1.0125,
            "new_shares": 428,
            "previous_rel_spy_20d": -0.054884,
            "price_vs_200ma_extension_state": true,
            "regime_exit_bucket": "risk_on",
            "rs20_entry_state_leader": true,
            "rs_accel_delta_20d": 0.614684,
            "sector": "Technology",
            "signal_day_open_gap_pct": -0.002664,
            "signal_day_ticker_green_candle": true,
            "signal_day_ticker_outperformed_spy": true,
            "spy_relative_leader": true,
            "strategy": "breakout_long",
            "ticker": "PLTR",
            "trade_quality_score": 0.912
          }
        ]
      },
      "sector_counts": {
        "Technology": 4
      },
      "unique_tickers": [
        "AMD",
        "APP",
        "MU",
        "PLTR"
      ],
      "window_counts": {
        "late_strong": 2,
        "mid_weak": 1,
        "old_thin": 1
      }
    },
    "gate4": {
      "adjusted_signal_count": 4,
      "affected_window_count": 3,
      "aggregate_delta": {
        "expected_value_score_sum": -0.0082,
        "max_consecutive_losses_max": 0,
        "max_drawdown_pct_max": 0.0,
        "survival_rate_min": 0.0,
        "tail_loss_share_max": 0.0,
        "total_pnl_sum": 73.64,
        "trade_count_sum": 0,
        "worst_trade_pct_min": 0.0
      },
      "changed_trade_count": 1,
      "changed_trades": {
        "late_strong": [
          {
            "entry_date": "2026-01-07",
            "incremental_pnl": 73.64,
            "key": "MU|2026-01-07|breakout_long|340.74",
            "pnl_after": 9499.12,
            "pnl_before": 9425.48,
            "sector": "Technology",
            "shares_after": 129,
            "shares_before": 128,
            "strategy": "breakout_long",
            "ticker": "MU"
          }
        ]
      },
      "concentration": {
        "max_single_positive_ticker_share": 1.0,
        "passed": false,
        "positive_incremental_pnl": 73.64,
        "positive_incremental_pnl_by_ticker": {
          "MU": 73.64
        }
      },
      "guardrails": {
        "max_drawdown_worse_guardrail": 0.005,
        "max_single_positive_ticker_share": 0.5,
        "min_adjusted_signal_count": 4,
        "min_affected_window_count": 2,
        "min_changed_trade_count": 4,
        "min_survival_rate": 0.05,
        "min_trade_count_sum": 58,
        "requires_no_ev_regression_windows": true
      },
      "improved_windows": [],
      "passed": false,
      "regressed_windows": [
        "late_strong"
      ],
      "window_deltas": {
        "late_strong": {
          "expected_value_score": -0.0082,
          "max_consecutive_losses": 0,
          "max_drawdown_pct": 0.0003,
          "sharpe_daily": -0.01,
          "signals_generated": 0,
          "signals_survived": 0,
          "survival_rate": 0.0,
          "tail_loss_share": 0.0,
          "total_pnl": 73.64,
          "total_return_pct": 0.0008,
          "trade_count": 0,
          "win_rate": 0.0,
          "worst_trade_pct": 0.0
        },
        "mid_weak": {
          "expected_value_score": 0.0,
          "max_consecutive_losses": 0,
          "max_drawdown_pct": 0.0,
          "sharpe_daily": 0.0,
          "signals_generated": 0,
          "signals_survived": 0,
          "survival_rate": 0.0,
          "tail_loss_share": 0.0,
          "total_pnl": 0.0,
          "total_return_pct": 0.0,
          "trade_count": 0,
          "win_rate": 0.0,
          "worst_trade_pct": 0.0
        },
        "old_thin": {
          "expected_value_score": 0.0,
          "max_consecutive_losses": 0,
          "max_drawdown_pct": 0.0,
          "sharpe_daily": 0.0,
          "signals_generated": 0,
          "signals_survived": 0,
          "survival_rate": 0.0,
          "tail_loss_share": 0.0,
          "total_pnl": 0.0,
          "total_return_pct": 0.0,
          "trade_count": 0,
          "win_rate": 0.0,
          "worst_trade_pct": 0.0
        }
      }
    },
    "multiplier": 1.0125,
    "variant": "rs_accel_no_chase_topup_10125"
  },
  {
    "adjustment_summary": {
      "count": 5,
      "sample": {
        "late_strong": [
          {
            "baseline_shares": 128,
            "confidence_score": 1.0,
            "current_rel_spy_20d": 0.4364,
            "days_to_earnings": 51,
            "gap_vulnerability_pct": 0.0706,
            "multiplier": 1.025,
            "new_shares": 131,
            "previous_rel_spy_20d": -0.027602,
            "price_vs_200ma_extension_state": true,
            "regime_exit_bucket": "risk_on",
            "rs20_entry_state_leader": true,
            "rs_accel_delta_20d": 0.464002,
            "sector": "Technology",
            "signal_day_open_gap_pct": 0.019638,
            "signal_day_ticker_green_candle": true,
            "signal_day_ticker_outperformed_spy": true,
            "spy_relative_leader": true,
            "strategy": "breakout_long",
            "ticker": "MU",
            "trade_quality_score": 0.919
          },
          {
            "baseline_shares": 184,
            "confidence_score": 0.93,
            "current_rel_spy_20d": 0.1633,
            "days_to_earnings": 9,
            "gap_vulnerability_pct": 0.0627,
            "multiplier": 1.025,
            "new_shares": 188,
            "previous_rel_spy_20d": -0.010117,
            "price_vs_200ma_extension_state": true,
            "regime_exit_bucket": "risk_on",
            "rs20_entry_state_leader": true,
            "rs_accel_delta_20d": 0.173417,
            "sector": "Technology",
            "signal_day_open_gap_pct": 0.017549,
            "signal_day_ticker_green_candle": true,
            "signal_day_ticker_outperformed_spy": true,
            "spy_relative_leader": true,
            "strategy": "breakout_long",
            "ticker": "AMD",
            "trade_quality_score": 0.917
          }
        ],
        "mid_weak": [
          {
            "baseline_shares": 122,
            "confidence_score": 0.93,
            "current_rel_spy_20d": 0.2525,
            "days_to_earnings": 64,
            "gap_vulnerability_pct": 0.0765,
            "multiplier": 1.025,
            "new_shares": 125,
            "previous_rel_spy_20d": -0.137982,
            "price_vs_200ma_extension_state": true,
            "regime_exit_bucket": "risk_on",
            "rs20_entry_state_leader": true,
            "rs_accel_delta_20d": 0.390482,
            "sector": "Technology",
            "signal_day_open_gap_pct": 0.017103,
            "signal_day_ticker_green_candle": true,
            "signal_day_ticker_outperformed_spy": true,
            "spy_relative_leader": true,
            "strategy": "breakout_long",
            "ticker": "APP",
            "trade_quality_score": 0.972
          },
          {
            "baseline_shares": 41,
            "confidence_score": 1.0,
            "current_rel_spy_20d": 0.4416,
            "days_to_earnings": 19,
            "gap_vulnerability_pct": 0.0714,
            "multiplier": 1.025,
            "new_shares": 42,
            "previous_rel_spy_20d": -0.102895,
            "price_vs_200ma_extension_state": true,
            "regime_exit_bucket": "risk_on",
            "rs20_entry_state_leader": true,
            "rs_accel_delta_20d": 0.544495,
            "sector": "Technology",
            "signal_day_open_gap_pct": 0.006808,
            "signal_day_ticker_green_candle": true,
            "signal_day_ticker_outperformed_spy": true,
            "spy_relative_leader": true,
            "strategy": "trend_long",
            "ticker": "AMD",
            "trade_quality_score": 1.0
          }
        ],
        "old_thin": [
          {
            "baseline_shares": 423,
            "confidence_score": 1.0,
            "current_rel_spy_20d": 0.5598,
            "days_to_earnings": 62,
            "gap_vulnerability_pct": 0.0794,
            "multiplier": 1.025,
            "new_shares": 433,
            "previous_rel_spy_20d": -0.054884,
            "price_vs_200ma_extension_state": true,
            "regime_exit_bucket": "risk_on",
            "rs20_entry_state_leader": true,
            "rs_accel_delta_20d": 0.614684,
            "sector": "Technology",
            "signal_day_open_gap_pct": -0.002664,
            "signal_day_ticker_green_candle": true,
            "signal_day_ticker_outperformed_spy": true,
            "spy_relative_leader": true,
            "strategy": "breakout_long",
            "ticker": "PLTR",
            "trade_quality_score": 0.912
          }
        ]
      },
      "sector_counts": {
        "Technology": 5
      },
      "unique_tickers": [
        "AMD",
        "APP",
        "MU",
        "PLTR"
      ],
      "window_counts": {
        "late_strong": 2,
        "mid_weak": 2,
        "old_thin": 1
      }
    },
    "gate4": {
      "adjusted_signal_count": 5,
      "affected_window_count": 3,
      "aggregate_delta": {
        "expected_value_score_sum": -0.0116,
        "max_consecutive_losses_max": 0,
        "max_drawdown_pct_max": 0.0,
        "survival_rate_min": 0.0,
        "tail_loss_share_max": 0.0,
        "total_pnl_sum": 260.59,
        "trade_count_sum": 0,
        "worst_trade_pct_min": 0.0
      },
      "changed_trade_count": 6,
      "changed_trades": {
        "late_strong": [
          {
            "entry_date": "2026-04-10",
            "incremental_pnl": 6269.72,
            "key": "AMZN|2026-04-10|breakout_long|236.52",
            "pnl_after": 6269.72,
            "pnl_before": 0.0,
            "sector": "Consumer Discretionary",
            "shares_after": 506,
            "shares_before": 0,
            "strategy": "breakout_long",
            "ticker": "AMZN"
          },
          {
            "entry_date": "2026-04-10",
            "incremental_pnl": -6242.18,
            "key": "AMZN|2026-04-10|breakout_long|236.55",
            "pnl_after": 0.0,
            "pnl_before": 6242.18,
            "sector": "Consumer Discretionary",
            "shares_after": 0,
            "shares_before": 505,
            "strategy": "breakout_long",
            "ticker": "AMZN"
          },
          {
            "entry_date": "2026-03-13",
            "incremental_pnl": 15.34,
            "key": "CVX|2026-03-13|trend_long|196.1",
            "pnl_after": 6351.28,
            "pnl_before": 6335.94,
            "sector": "Energy",
            "shares_after": 414,
            "shares_before": 413,
            "strategy": "trend_long",
            "ticker": "CVX"
          },
          {
            "entry_date": "2026-01-07",
            "incremental_pnl": 220.91,
            "key": "MU|2026-01-07|breakout_long|340.74",
            "pnl_after": 9646.39,
            "pnl_before": 9425.48,
            "sector": "Technology",
            "shares_after": 131,
            "shares_before": 128,
            "strategy": "breakout_long",
            "ticker": "MU"
          },
          {
            "entry_date": "2026-02-04",
            "incremental_pnl": 15.48,
            "key": "XOM|2026-02-04|breakout_long|143.24",
            "pnl_after": 12563.96,
            "pnl_before": 12548.48,
            "sector": "Energy",
            "shares_after": 812,
            "shares_before": 811,
            "strategy": "breakout_long",
            "ticker": "XOM"
          }
        ],
        "mid_weak": [
          {
            "entry_date": "2025-10-09",
            "incremental_pnl": -18.68,
            "key": "AMD|2025-10-09|trend_long|236.42",
            "pnl_after": -784.29,
            "pnl_before": -765.61,
            "sector": "Technology",
            "shares_after": 42,
            "shares_before": 41,
            "strategy": "trend_long",
            "ticker": "AMD"
          }
        ]
      },
      "concentration": {
        "max_single_positive_ticker_share": 0.9614,
        "passed": false,
        "positive_incremental_pnl": 6521.45,
        "positive_incremental_pnl_by_ticker": {
          "AMZN": 6269.72,
          "CVX": 15.34,
          "MU": 220.91,
          "XOM": 15.48
        }
      },
      "guardrails": {
        "max_drawdown_worse_guardrail": 0.005,
        "max_single_positive_ticker_share": 0.5,
        "min_adjusted_signal_count": 4,
        "min_affected_window_count": 2,
        "min_changed_trade_count": 4,
        "min_survival_rate": 0.05,
        "min_trade_count_sum": 58,
        "requires_no_ev_regression_windows": true
      },
      "improved_windows": [],
      "passed": false,
      "regressed_windows": [
        "late_strong",
        "mid_weak"
      ],
      "window_deltas": {
        "late_strong": {
          "expected_value_score": -0.0111,
          "max_consecutive_losses": 0,
          "max_drawdown_pct": 0.0009,
          "sharpe_daily": -0.02,
          "signals_generated": 0,
          "signals_survived": 0,
          "survival_rate": 0.0,
          "tail_loss_share": 0.0,
          "total_pnl": 279.27,
          "total_return_pct": 0.0028,
          "trade_count": 0,
          "win_rate": 0.0,
          "worst_trade_pct": 0.0
        },
        "mid_weak": {
          "expected_value_score": -0.0005,
          "max_consecutive_losses": 0,
          "max_drawdown_pct": 0.0,
          "sharpe_daily": 0.0,
          "signals_generated": 0,
          "signals_survived": 0,
          "survival_rate": 0.0,
          "tail_loss_share": 0.002069,
          "total_pnl": -18.68,
          "total_return_pct": -0.0002,
          "trade_count": 0,
          "win_rate": 0.0,
          "worst_trade_pct": 0.0
        },
        "old_thin": {
          "expected_value_score": 0.0,
          "max_consecutive_losses": 0,
          "max_drawdown_pct": 0.0,
          "sharpe_daily": 0.0,
          "signals_generated": 0,
          "signals_survived": 0,
          "survival_rate": 0.0,
          "tail_loss_share": 0.0,
          "total_pnl": 0.0,
          "total_return_pct": 0.0,
          "trade_count": 0,
          "win_rate": 0.0,
          "worst_trade_pct": 0.0
        }
      }
    },
    "multiplier": 1.025,
    "variant": "rs_accel_no_chase_topup_1025"
  },
  {
    "adjustment_summary": {
      "count": 6,
      "sample": {
        "late_strong": [
          {
            "baseline_shares": 128,
            "confidence_score": 1.0,
            "current_rel_spy_20d": 0.4364,
            "days_to_earnings": 51,
            "gap_vulnerability_pct": 0.0706,
            "multiplier": 1.05,
            "new_shares": 134,
            "previous_rel_spy_20d": -0.027602,
            "price_vs_200ma_extension_state": true,
            "regime_exit_bucket": "risk_on",
            "rs20_entry_state_leader": true,
            "rs_accel_delta_20d": 0.464002,
            "sector": "Technology",
            "signal_day_open_gap_pct": 0.019638,
            "signal_day_ticker_green_candle": true,
            "signal_day_ticker_outperformed_spy": true,
            "spy_relative_leader": true,
            "strategy": "breakout_long",
            "ticker": "MU",
            "trade_quality_score": 0.919
          },
          {
            "baseline_shares": 184,
            "confidence_score": 0.93,
            "current_rel_spy_20d": 0.1633,
            "days_to_earnings": 9,
            "gap_vulnerability_pct": 0.0627,
            "multiplier": 1.05,
            "new_shares": 193,
            "previous_rel_spy_20d": -0.010117,
            "price_vs_200ma_extension_state": true,
            "regime_exit_bucket": "risk_on",
            "rs20_entry_state_leader": true,
            "rs_accel_delta_20d": 0.173417,
            "sector": "Technology",
            "signal_day_open_gap_pct": 0.017549,
            "signal_day_ticker_green_candle": true,
            "signal_day_ticker_outperformed_spy": true,
            "spy_relative_leader": true,
            "strategy": "breakout_long",
            "ticker": "AMD",
            "trade_quality_score": 0.917
          }
        ],
        "mid_weak": [
          {
            "baseline_shares": 122,
            "confidence_score": 0.93,
            "current_rel_spy_20d": 0.2525,
            "days_to_earnings": 64,
            "gap_vulnerability_pct": 0.0765,
            "multiplier": 1.05,
            "new_shares": 128,
            "previous_rel_spy_20d": -0.137982,
            "price_vs_200ma_extension_state": true,
            "regime_exit_bucket": "risk_on",
            "rs20_entry_state_leader": true,
            "rs_accel_delta_20d": 0.390482,
            "sector": "Technology",
            "signal_day_open_gap_pct": 0.017103,
            "signal_day_ticker_green_candle": true,
            "signal_day_ticker_outperformed_spy": true,
            "spy_relative_leader": true,
            "strategy": "breakout_long",
            "ticker": "APP",
            "trade_quality_score": 0.972
          },
          {
            "baseline_shares": 41,
            "confidence_score": 1.0,
            "current_rel_spy_20d": 0.4416,
            "days_to_earnings": 19,
            "gap_vulnerability_pct": 0.0714,
            "multiplier": 1.05,
            "new_shares": 43,
            "previous_rel_spy_20d": -0.102895,
            "price_vs_200ma_extension_state": true,
            "regime_exit_bucket": "risk_on",
            "rs20_entry_state_leader": true,
            "rs_accel_delta_20d": 0.544495,
            "sector": "Technology",
            "signal_day_open_gap_pct": 0.006808,
            "signal_day_ticker_green_candle": true,
            "signal_day_ticker_outperformed_spy": true,
            "spy_relative_leader": true,
            "strategy": "trend_long",
            "ticker": "AMD",
            "trade_quality_score": 1.0
          }
        ],
        "old_thin": [
          {
            "baseline_shares": 24,
            "confidence_score": 1.0,
            "current_rel_spy_20d": 0.1645,
            "days_to_earnings": 43,
            "gap_vulnerability_pct": 0.0333,
            "multiplier": 1.05,
            "new_shares": 25,
            "previous_rel_spy_20d": 0.048484,
            "price_vs_200ma_extension_state": true,
            "regime_exit_bucket": "risk_on",
            "rs20_entry_state_leader": true,
            "rs_accel_delta_20d": 0.116016,
            "sector": "Communication Services",
            "signal_day_open_gap_pct": 9e-05,
            "signal_day_ticker_green_candle": true,
            "signal_day_ticker_outperformed_spy": true,
            "spy_relative_leader": true,
            "strategy": "breakout_long",
            "ticker": "NFLX",
            "trade_quality_score": 0.902
          },
          {
            "baseline_shares": 423,
            "confidence_score": 1.0,
            "current_rel_spy_20d": 0.5598,
            "days_to_earnings": 62,
            "gap_vulnerability_pct": 0.0794,
            "multiplier": 1.05,
            "new_shares": 444,
            "previous_rel_spy_20d": -0.054884,
            "price_vs_200ma_extension_state": true,
            "regime_exit_bucket": "risk_on",
            "rs20_entry_state_leader": true,
            "rs_accel_delta_20d": 0.614684,
            "sector": "Technology",
            "signal_day_open_gap_pct": -0.002664,
            "signal_day_ticker_green_candle": true,
            "signal_day_ticker_outperformed_spy": true,
            "spy_relative_leader": true,
            "strategy": "breakout_long",
            "ticker": "PLTR",
            "trade_quality_score": 0.912
          }
        ]
      },
      "sector_counts": {
        "Communication Services": 1,
        "Technology": 5
      },
      "unique_tickers": [
        "AMD",
        "APP",
        "MU",
        "NFLX",
        "PLTR"
      ],
      "window_counts": {
        "late_strong": 2,
        "mid_weak": 2,
        "old_thin": 2
      }
    },
    "gate4": {
      "adjusted_signal_count": 6,
      "affected_window_count": 3,
      "aggregate_delta": {
        "expected_value_score_sum": -0.021,
        "max_consecutive_losses_max": 0,
        "max_drawdown_pct_max": 0.0,
        "survival_rate_min": 0.0,
        "tail_loss_share_max": 0.0,
        "total_pnl_sum": 577.77,
        "trade_count_sum": 0,
        "worst_trade_pct_min": 0.0
      },
      "changed_trade_count": 8,
      "changed_trades": {
        "late_strong": [
          {
            "entry_date": "2026-04-10",
            "incremental_pnl": 24.72,
            "key": "AMZN|2026-04-10|breakout_long|236.55",
            "pnl_after": 6266.9,
            "pnl_before": 6242.18,
            "sector": "Consumer Discretionary",
            "shares_after": 507,
            "shares_before": 505,
            "strategy": "breakout_long",
            "ticker": "AMZN"
          },
          {
            "entry_date": "2026-01-30",
            "incremental_pnl": 87.84,
            "key": "CAT|2026-01-30|breakout_long|654.73",
            "pnl_after": 14581.29,
            "pnl_before": 14493.45,
            "sector": "Industrials",
            "shares_after": 166,
            "shares_before": 165,
            "strategy": "breakout_long",
            "ticker": "CAT"
          },
          {
            "entry_date": "2026-02-02",
            "incremental_pnl": 17.72,
            "key": "CVX|2026-02-02|breakout_long|171.85",
            "pnl_after": 11145.24,
            "pnl_before": 11127.52,
            "sector": "Energy",
            "shares_after": 629,
            "shares_before": 628,
            "strategy": "breakout_long",
            "ticker": "CVX"
          },
          {
            "entry_date": "2026-03-13",
            "incremental_pnl": 15.34,
            "key": "CVX|2026-03-13|trend_long|196.1",
            "pnl_after": 6351.28,
            "pnl_before": 6335.94,
            "sector": "Energy",
            "shares_after": 414,
            "shares_before": 413,
            "strategy": "trend_long",
            "ticker": "CVX"
          },
          {
            "entry_date": "2026-01-07",
            "incremental_pnl": 441.82,
            "key": "MU|2026-01-07|breakout_long|340.74",
            "pnl_after": 9867.3,
            "pnl_before": 9425.48,
            "sector": "Technology",
            "shares_after": 134,
            "shares_before": 128,
            "strategy": "breakout_long",
            "ticker": "MU"
          },
          {
            "entry_date": "2026-02-04",
            "incremental_pnl": 30.95,
            "key": "XOM|2026-02-04|breakout_long|143.24",
            "pnl_after": 12579.43,
            "pnl_before": 12548.48,
            "sector": "Energy",
            "shares_after": 813,
            "shares_before": 811,
            "strategy": "breakout_long",
            "ticker": "XOM"
          }
        ],
        "mid_weak": [
          {
            "entry_date": "2025-10-09",
            "incremental_pnl": -37.35,
            "key": "AMD|2025-10-09|trend_long|236.42",
            "pnl_after": -802.96,
            "pnl_before": -765.61,
            "sector": "Technology",
            "shares_after": 43,
            "shares_before": 41,
            "strategy": "trend_long",
            "ticker": "AMD"
          }
        ],
        "old_thin": [
          {
            "entry_date": "2024-11-22",
            "incremental_pnl": -3.27,
            "key": "NFLX|2024-11-22|breakout_long|89.64",
            "pnl_after": -81.75,
            "pnl_before": -78.48,
            "sector": "Communication Services",
            "shares_after": 25,
            "shares_before": 24,
            "strategy": "breakout_long",
            "ticker": "NFLX"
          }
        ]
      },
      "concentration": {
        "max_single_positive_ticker_share": 0.714468,
        "passed": false,
        "positive_incremental_pnl": 618.39,
        "positive_incremental_pnl_by_ticker": {
          "AMZN": 24.72,
          "CAT": 87.84,
          "CVX": 33.06,
          "MU": 441.82,
          "XOM": 30.95
        }
      },
      "guardrails": {
        "max_drawdown_worse_guardrail": 0.005,
        "max_single_positive_ticker_share": 0.5,
        "min_adjusted_signal_count": 4,
        "min_affected_window_count": 2,
        "min_changed_trade_count": 4,
        "min_survival_rate": 0.05,
        "min_trade_count_sum": 58,
        "requires_no_ev_regression_windows": true
      },
      "improved_windows": [],
      "passed": false,
      "regressed_windows": [
        "late_strong",
        "mid_weak",
        "old_thin"
      ],
      "window_deltas": {
        "late_strong": {
          "expected_value_score": -0.0197,
          "max_consecutive_losses": 0,
          "max_drawdown_pct": 0.0019,
          "sharpe_daily": -0.04,
          "signals_generated": 0,
          "signals_survived": 0,
          "survival_rate": 0.0,
          "tail_loss_share": 0.0,
          "total_pnl": 618.39,
          "total_return_pct": 0.0062,
          "trade_count": 0,
          "win_rate": 0.0,
          "worst_trade_pct": 0.0
        },
        "mid_weak": {
          "expected_value_score": -0.0011,
          "max_consecutive_losses": 0,
          "max_drawdown_pct": 0.0,
          "sharpe_daily": 0.0,
          "signals_generated": 0,
          "signals_survived": 0,
          "survival_rate": 0.0,
          "tail_loss_share": 0.004105,
          "total_pnl": -37.35,
          "total_return_pct": -0.0004,
          "trade_count": 0,
          "win_rate": 0.0,
          "worst_trade_pct": 0.0
        },
        "old_thin": {
          "expected_value_score": -0.0002,
          "max_consecutive_losses": 0,
          "max_drawdown_pct": 0.0,
          "sharpe_daily": 0.0,
          "signals_generated": 0,
          "signals_survived": 0,
          "survival_rate": 0.0,
          "tail_loss_share": -0.000101,
          "total_pnl": -3.27,
          "total_return_pct": -0.0001,
          "trade_count": 0,
          "win_rate": 0.0,
          "worst_trade_pct": 0.0
        }
      }
    },
    "multiplier": 1.05,
    "variant": "rs_accel_no_chase_topup_1050"
  },
  {
    "adjustment_summary": {
      "count": 6,
      "sample": {
        "late_strong": [
          {
            "baseline_shares": 128,
            "confidence_score": 1.0,
            "current_rel_spy_20d": 0.4364,
            "days_to_earnings": 51,
            "gap_vulnerability_pct": 0.0706,
            "multiplier": 1.075,
            "new_shares": 137,
            "previous_rel_spy_20d": -0.027602,
            "price_vs_200ma_extension_state": true,
            "regime_exit_bucket": "risk_on",
            "rs20_entry_state_leader": true,
            "rs_accel_delta_20d": 0.464002,
            "sector": "Technology",
            "signal_day_open_gap_pct": 0.019638,
            "signal_day_ticker_green_candle": true,
            "signal_day_ticker_outperformed_spy": true,
            "spy_relative_leader": true,
            "strategy": "breakout_long",
            "ticker": "MU",
            "trade_quality_score": 0.919
          },
          {
            "baseline_shares": 184,
            "confidence_score": 0.93,
            "current_rel_spy_20d": 0.1633,
            "days_to_earnings": 9,
            "gap_vulnerability_pct": 0.0627,
            "multiplier": 1.075,
            "new_shares": 197,
            "previous_rel_spy_20d": -0.010117,
            "price_vs_200ma_extension_state": true,
            "regime_exit_bucket": "risk_on",
            "rs20_entry_state_leader": true,
            "rs_accel_delta_20d": 0.173417,
            "sector": "Technology",
            "signal_day_open_gap_pct": 0.017549,
            "signal_day_ticker_green_candle": true,
            "signal_day_ticker_outperformed_spy": true,
            "spy_relative_leader": true,
            "strategy": "breakout_long",
            "ticker": "AMD",
            "trade_quality_score": 0.917
          }
        ],
        "mid_weak": [
          {
            "baseline_shares": 122,
            "confidence_score": 0.93,
            "current_rel_spy_20d": 0.2525,
            "days_to_earnings": 64,
            "gap_vulnerability_pct": 0.0765,
            "multiplier": 1.075,
            "new_shares": 129,
            "previous_rel_spy_20d": -0.137982,
            "price_vs_200ma_extension_state": true,
            "regime_exit_bucket": "risk_on",
            "rs20_entry_state_leader": true,
            "rs_accel_delta_20d": 0.390482,
            "sector": "Technology",
            "signal_day_open_gap_pct": 0.017103,
            "signal_day_ticker_green_candle": true,
            "signal_day_ticker_outperformed_spy": true,
            "spy_relative_leader": true,
            "strategy": "breakout_long",
            "ticker": "APP",
            "trade_quality_score": 0.972
          },
          {
            "baseline_shares": 41,
            "confidence_score": 1.0,
            "current_rel_spy_20d": 0.4416,
            "days_to_earnings": 19,
            "gap_vulnerability_pct": 0.0714,
            "multiplier": 1.075,
            "new_shares": 44,
            "previous_rel_spy_20d": -0.102895,
            "price_vs_200ma_extension_state": true,
            "regime_exit_bucket": "risk_on",
            "rs20_entry_state_leader": true,
            "rs_accel_delta_20d": 0.544495,
            "sector": "Technology",
            "signal_day_open_gap_pct": 0.006808,
            "signal_day_ticker_green_candle": true,
            "signal_day_ticker_outperformed_spy": true,
            "spy_relative_leader": true,
            "strategy": "trend_long",
            "ticker": "AMD",
            "trade_quality_score": 1.0
          }
        ],
        "old_thin": [
          {
            "baseline_shares": 24,
            "confidence_score": 1.0,
            "current_rel_spy_20d": 0.1645,
            "days_to_earnings": 43,
            "gap_vulnerability_pct": 0.0333,
            "multiplier": 1.075,
            "new_shares": 25,
            "previous_rel_spy_20d": 0.048484,
            "price_vs_200ma_extension_state": true,
            "regime_exit_bucket": "risk_on",
            "rs20_entry_state_leader": true,
            "rs_accel_delta_20d": 0.116016,
            "sector": "Communication Services",
            "signal_day_open_gap_pct": 9e-05,
            "signal_day_ticker_green_candle": true,
            "signal_day_ticker_outperformed_spy": true,
            "spy_relative_leader": true,
            "strategy": "breakout_long",
            "ticker": "NFLX",
            "trade_quality_score": 0.902
          },
          {
            "baseline_shares": 423,
            "confidence_score": 1.0,
            "current_rel_spy_20d": 0.5598,
            "days_to_earnings": 62,
            "gap_vulnerability_pct": 0.0794,
            "multiplier": 1.075,
            "new_shares": 454,
            "previous_rel_spy_20d": -0.054884,
            "price_vs_200ma_extension_state": true,
            "regime_exit_bucket": "risk_on",
            "rs20_entry_state_leader": true,
            "rs_accel_delta_20d": 0.614684,
            "sector": "Technology",
            "signal_day_open_gap_pct": -0.002664,
            "signal_day_ticker_green_candle": true,
            "signal_day_ticker_outperformed_spy": true,
            "spy_relative_leader": true,
            "strategy": "breakout_long",
            "ticker": "PLTR",
            "trade_quality_score": 0.912
          }
        ]
      },
      "sector_counts": {
        "Communication Services": 1,
        "Technology": 5
      },
      "unique_tickers": [
        "AMD",
        "APP",
        "MU",
        "NFLX",
        "PLTR"
      ],
      "window_counts": {
        "late_strong": 2,
        "mid_weak": 2,
        "old_thin": 2
      }
    },
    "gate4": {
      "adjusted_signal_count": 6,
      "affected_window_count": 3,
      "aggregate_delta": {
        "expected_value_score_sum": -0.0207,
        "max_consecutive_losses_max": 0,
        "max_drawdown_pct_max": 0.0,
        "survival_rate_min": 0.0,
        "tail_loss_share_max": 0.0,
        "total_pnl_sum": 843.75,
        "trade_count_sum": 0,
        "worst_trade_pct_min": 0.0
      },
      "changed_trade_count": 9,
      "changed_trades": {
        "late_strong": [
          {
            "entry_date": "2026-04-10",
            "incremental_pnl": 6282.11,
            "key": "AMZN|2026-04-10|breakout_long|236.52",
            "pnl_after": 6282.11,
            "pnl_before": 0.0,
            "sector": "Consumer Discretionary",
            "shares_after": 507,
            "shares_before": 0,
            "strategy": "breakout_long",
            "ticker": "AMZN"
          },
          {
            "entry_date": "2026-04-10",
            "incremental_pnl": -6242.18,
            "key": "AMZN|2026-04-10|breakout_long|236.55",
            "pnl_after": 0.0,
            "pnl_before": 6242.18,
            "sector": "Consumer Discretionary",
            "shares_after": 0,
            "shares_before": 505,
            "strategy": "breakout_long",
            "ticker": "AMZN"
          },
          {
            "entry_date": "2026-01-30",
            "incremental_pnl": 87.84,
            "key": "CAT|2026-01-30|breakout_long|654.73",
            "pnl_after": 14581.29,
            "pnl_before": 14493.45,
            "sector": "Industrials",
            "shares_after": 166,
            "shares_before": 165,
            "strategy": "breakout_long",
            "ticker": "CAT"
          },
          {
            "entry_date": "2026-02-02",
            "incremental_pnl": 35.44,
            "key": "CVX|2026-02-02|breakout_long|171.85",
            "pnl_after": 11162.96,
            "pnl_before": 11127.52,
            "sector": "Energy",
            "shares_after": 630,
            "shares_before": 628,
            "strategy": "breakout_long",
            "ticker": "CVX"
          },
          {
            "entry_date": "2026-03-13",
            "incremental_pnl": 30.68,
            "key": "CVX|2026-03-13|trend_long|196.1",
            "pnl_after": 6366.62,
            "pnl_before": 6335.94,
            "sector": "Energy",
            "shares_after": 415,
            "shares_before": 413,
            "strategy": "trend_long",
            "ticker": "CVX"
          },
          {
            "entry_date": "2026-01-07",
            "incremental_pnl": 662.73,
            "key": "MU|2026-01-07|breakout_long|340.74",
            "pnl_after": 10088.21,
            "pnl_before": 9425.48,
            "sector": "Technology",
            "shares_after": 137,
            "shares_before": 128,
            "strategy": "breakout_long",
            "ticker": "MU"
          },
          {
            "entry_date": "2026-02-04",
            "incremental_pnl": 46.42,
            "key": "XOM|2026-02-04|breakout_long|143.24",
            "pnl_after": 12594.9,
            "pnl_before": 12548.48,
            "sector": "Energy",
            "shares_after": 814,
            "shares_before": 811,
            "strategy": "breakout_long",
            "ticker": "XOM"
          }
        ],
        "mid_weak": [
          {
            "entry_date": "2025-10-09",
            "incremental_pnl": -56.02,
            "key": "AMD|2025-10-09|trend_long|236.42",
            "pnl_after": -821.63,
            "pnl_before": -765.61,
            "sector": "Technology",
            "shares_after": 44,
            "shares_before": 41,
            "strategy": "trend_long",
            "ticker": "AMD"
          }
        ],
        "old_thin": [
          {
            "entry_date": "2024-11-22",
            "incremental_pnl": -3.27,
            "key": "NFLX|2024-11-22|breakout_long|89.64",
            "pnl_after": -81.75,
            "pnl_before": -78.48,
            "sector": "Communication Services",
            "shares_after": 25,
            "shares_before": 24,
            "strategy": "breakout_long",
            "ticker": "NFLX"
          }
        ]
      },
      "concentration": {
        "max_single_positive_ticker_share": 0.879205,
        "passed": false,
        "positive_incremental_pnl": 7145.22,
        "positive_incremental_pnl_by_ticker": {
          "AMZN": 6282.11,
          "CAT": 87.84,
          "CVX": 66.12,
          "MU": 662.73,
          "XOM": 46.42
        }
      },
      "guardrails": {
        "max_drawdown_worse_guardrail": 0.005,
        "max_single_positive_ticker_share": 0.5,
        "min_adjusted_signal_count": 4,
        "min_affected_window_count": 2,
        "min_changed_trade_count": 4,
        "min_survival_rate": 0.05,
        "min_trade_count_sum": 58,
        "requires_no_ev_regression_windows": true
      },
      "improved_windows": [],
      "passed": false,
      "regressed_windows": [
        "late_strong",
        "mid_weak",
        "old_thin"
      ],
      "window_deltas": {
        "late_strong": {
          "expected_value_score": -0.0189,
          "max_consecutive_losses": 0,
          "max_drawdown_pct": 0.0029,
          "sharpe_daily": -0.05,
          "signals_generated": 0,
          "signals_survived": 0,
          "survival_rate": 0.0,
          "tail_loss_share": 0.0,
          "total_pnl": 903.04,
          "total_return_pct": 0.0091,
          "trade_count": 0,
          "win_rate": 0.0,
          "worst_trade_pct": 0.0
        },
        "mid_weak": {
          "expected_value_score": -0.0016,
          "max_consecutive_losses": 0,
          "max_drawdown_pct": 0.0,
          "sharpe_daily": 0.0,
          "signals_generated": 0,
          "signals_survived": 0,
          "survival_rate": 0.0,
          "tail_loss_share": 0.006108,
          "total_pnl": -56.02,
          "total_return_pct": -0.0006,
          "trade_count": 0,
          "win_rate": 0.0,
          "worst_trade_pct": 0.0
        },
        "old_thin": {
          "expected_value_score": -0.0002,
          "max_consecutive_losses": 0,
          "max_drawdown_pct": 0.0,
          "sharpe_daily": 0.0,
          "signals_generated": 0,
          "signals_survived": 0,
          "survival_rate": 0.0,
          "tail_loss_share": -0.000101,
          "total_pnl": -3.27,
          "total_return_pct": -0.0001,
          "trade_count": 0,
          "win_rate": 0.0,
          "worst_trade_pct": 0.0
        }
      }
    },
    "multiplier": 1.075,
    "variant": "rs_accel_no_chase_topup_1075"
  }
]
