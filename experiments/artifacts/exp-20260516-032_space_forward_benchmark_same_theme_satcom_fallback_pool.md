# exp-20260516-032 space_forward_benchmark_same_theme_satcom_fallback_pool

- hypothesis: A Space candidate-pool expansion should require closed forward evidence that a satcom fallback ticker beats cash, same-theme replacement, and broad benchmarks; VSAT passes this stronger gate while IRDM does not.
- change_type: alpha_search
- changed_variable: space_forward_benchmark_same_theme_satcom_fallback_pool_membership
- backtest_protocol: docs/backtesting.md standard 3-window frozen Space replay
- decision: reject
- rejection_reason: no_window_regressed; drawdown_delta_within_limit; no_window_ev_regression; max_window_drawdown_delta_lte_0_5pp

## Gate Answers

- alpha_hypothesis: VSAT-only satcom fallback candidate-pool expansion gated by closed cash, same-theme, and benchmark outperformance evidence.
- prior_similar_experiments: exp-20260516-010 broad satcom fallback rejected; exp-20260515-035 older VSAT-only fallback rejected; exp-20260516-031 target-width no-op.
- one_independent_variable: space_forward_benchmark_same_theme_satcom_fallback_pool_membership
- success_criteria: aggregate EV/PnL improve, no window EV regression, drawdown drift <= 0.5pp, survival >= 5%, fallback signals present.
- reproducibility: script, JSON artifact, doc artifact, ticket, and experiment_log.jsonl record are written by this run.

## Three-Window Metrics

| window | before EV | after EV | EV delta | before PnL | after PnL | PnL delta | DD delta | survival delta | trades delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.711600 | 9.122300 | 0.410700 | 247486.83 | 269894.04 | 22407.21 | 0.032200 | -0.028100 | 1 |
| mid_weak | 18.923900 | 23.705800 | 4.781900 | 418668.25 | 499073.70 | 80405.45 | -0.004300 | 0.018900 | 1 |
| old_thin | 1.605100 | 1.574600 | -0.030500 | 89672.79 | 88459.44 | -1213.35 | -0.002500 | 0.000000 | 0 |

## Aggregate Delta

- expected_value_score_delta: 5.162100
- total_pnl_delta: 101599.31
- max_drawdown_delta: 0.032200
- trade_count_delta: 2

## Gate Detail

```json
{
  "aggregate_delta": {
    "expected_value_score_delta": 5.162100000000002,
    "max_drawdown_delta": 0.032200000000000006,
    "survival_rate_delta": 0.00039999999999995595,
    "total_pnl_delta": 101599.31000000006,
    "trade_count_delta": 2
  },
  "aggregate_delta_vs_before": {
    "expected_value_score_sum": 5.1621,
    "max_drawdown_pct_max": 0.0322,
    "min_survival_rate": 0.0004,
    "signals_generated_sum": 5,
    "signals_survived_sum": 3,
    "total_pnl_sum": 101599.31,
    "trade_count_sum": 2
  },
  "by_window_delta_vs_before": {
    "late_strong": {
      "expected_value_score": 0.4107,
      "max_drawdown_pct": 0.0322,
      "sharpe_daily": -0.14,
      "signals_generated": 1.0,
      "signals_survived": -1.0,
      "strategy_total_return_pct": 0.224,
      "survival_rate": -0.0281,
      "tail_loss_share": -0.0349,
      "total_pnl": 22407.21,
      "trade_count": 1.0,
      "win_rate": -0.041,
      "worst_trade_pct": -0.0354
    },
    "mid_weak": {
      "expected_value_score": 4.7819,
      "max_drawdown_pct": -0.0043,
      "sharpe_daily": 0.23,
      "signals_generated": 4.0,
      "signals_survived": 4.0,
      "strategy_total_return_pct": 0.804,
      "survival_rate": 0.0189,
      "tail_loss_share": -0.0037,
      "total_pnl": 80405.45,
      "trade_count": 1.0,
      "win_rate": 0.02,
      "worst_trade_pct": 0.0
    },
    "old_thin": {
      "expected_value_score": -0.0305,
      "max_drawdown_pct": -0.0025,
      "sharpe_daily": -0.01,
      "signals_generated": 0.0,
      "signals_survived": 0.0,
      "strategy_total_return_pct": -0.0121,
      "survival_rate": 0.0,
      "tail_loss_share": 0.015,
      "total_pnl": -1213.35,
      "trade_count": 0.0,
      "win_rate": 0.0,
      "worst_trade_pct": 0.0
    }
  },
  "decision": "reject",
  "extension_trade_attribution": {
    "late_strong": {
      "losses": 0,
      "total_pnl": 0,
      "trade_count": 0,
      "trades": [],
      "wins": 0
    },
    "mid_weak": {
      "losses": 0,
      "total_pnl": 37425.59,
      "trade_count": 1,
      "trades": [
        {
          "entry_date": "2025-08-06",
          "exit_date": "2025-08-06",
          "exit_reason": "target",
          "pnl": 37425.59,
          "pnl_pct_net": 0.280044,
          "shares": 6238,
          "strategy": "trend_long",
          "ticker": "VSAT"
        }
      ],
      "wins": 1
    },
    "old_thin": {
      "losses": 0,
      "total_pnl": 0,
      "trade_count": 0,
      "trades": [],
      "wins": 0
    }
  },
  "extension_trade_count": 1,
  "fallback_filter_summary": {
    "by_window": {
      "unknown": {
        "actions": {
          "filtered": 2
        },
        "count": 2,
        "reasons": {
          "non_trend": 2
        },
        "tickers": {
          "VSAT": 2
        }
      }
    },
    "counts": {
      "filtered_VSAT": 2,
      "filtered_breakout_long": 2,
      "filtered_extension_non_trend_signal": 2,
      "filtered_extension_signal": 2,
      "kept_VSAT": 4,
      "kept_extension_signal": 4
    },
    "records": [
      {
        "action": "filtered",
        "date": "",
        "reason": "non_trend",
        "space_iwm_relative_state": "smallcap_leader",
        "space_peer_momentum_state": "nonleader",
        "strategy": "breakout_long",
        "ticker": "VSAT",
        "window": null
      },
      {
        "action": "filtered",
        "date": "",
        "reason": "non_trend",
        "space_iwm_relative_state": "smallcap_laggard",
        "space_peer_momentum_state": "leader",
        "strategy": "breakout_long",
        "ticker": "VSAT",
        "window": null
      }
    ],
    "rule": "Added satcom tickers are allowed only for trend_long signals on dates with no base official Space signal in the same sizing batch."
  },
  "forward_gate": {
    "description": "Add only satcom fallback tickers with closed positive 5d cash, 10d cash, same-theme replacement, and broad benchmark evidence.",
    "passed": true,
    "passed_tickers": [
      "VSAT"
    ],
    "per_ticker": {
      "VSAT": {
        "asof_date": "2026-05-15",
        "event_date": "2026-04-24",
        "metrics": {
          "10d_arkx": 1957.13,
          "10d_cash": 2456.53,
          "10d_qqq": 1717.93,
          "10d_same_theme": 528.77,
          "10d_spy": 2119.13,
          "10d_ufo": 1338.84,
          "5d_cash": 879.65
        },
        "passed": true,
        "semantic_bucket": "defense_budget_theme",
        "source_type": "official_government_release",
        "theme_segment": "satellite_connectivity"
      }
    },
    "target_added_tickers": [
      "VSAT"
    ]
  },
  "improved_windows": {
    "late_strong": 0.4107,
    "mid_weak": 4.7819
  },
  "non_trend_filtered_extension_signal_count": 0,
  "passed": false,
  "production_impact": {
    "backtester_adapter_changed": false,
    "parity_test_added": false,
    "replay_only": true,
    "run_adapter_changed": false,
    "shared_policy_changed": false
  },
  "reasons": {
    "aggregate_ev_delta_positive": true,
    "aggregate_ev_positive": true,
    "aggregate_pnl_delta_positive": true,
    "at_least_two_windows_improved": true,
    "drawdown_delta_within_limit": false,
    "extension_trades_present": true,
    "fallback_signals_present": true,
    "forward_gate_passed": true,
    "max_window_drawdown_delta_lte_0_5pp": false,
    "no_window_ev_regression": false,
    "no_window_regressed": false,
    "survival_rate_ok": true,
    "trade_count_ok": true
  },
  "regressed_windows": {
    "old_thin": -0.0305
  },
  "window_deltas": {
    "late_strong": {
      "expected_value_score_delta": 0.4106999999999985,
      "max_drawdown_delta": 0.032200000000000006,
      "survival_rate_delta": -0.028100000000000014,
      "total_pnl_delta": 22407.209999999992,
      "trade_count_delta": 1
    },
    "mid_weak": {
      "expected_value_score_delta": 4.7819,
      "max_drawdown_delta": -0.004299999999999998,
      "survival_rate_delta": 0.018899999999999917,
      "total_pnl_delta": 80405.45000000001,
      "trade_count_delta": 1
    },
    "old_thin": {
      "expected_value_score_delta": -0.03049999999999997,
      "max_drawdown_delta": -0.0025000000000000022,
      "survival_rate_delta": 0.0,
      "total_pnl_delta": -1213.3499999999913,
      "trade_count_delta": 0
    }
  },
  "window_ev_regressions": [
    "old_thin"
  ]
}
```

## Production Impact

```text
production_impact:
  shared_policy_changed: False
  backtester_adapter_changed: False
  run_adapter_changed: False
  replay_only: True
  parity_test_added: False
```
