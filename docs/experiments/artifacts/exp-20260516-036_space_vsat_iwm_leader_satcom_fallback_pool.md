# exp-20260516-036 space_vsat_iwm_leader_satcom_fallback_pool

- hypothesis: VSAT satcom fallback expansion should only be eligible when closed forward evidence beats cash, same-theme replacement, and broad benchmarks, and when IWM 20d momentum leads SPY. This tests whether small-cap risk appetite removes the drawdown and old-window noise from exp-20260516-032 without adding broad ticker noise.
- change_type: alpha_search
- changed_variable: space_forward_benchmark_same_theme_satcom_iwm_leader_fallback_pool_membership
- backtest_protocol: docs/backtesting.md standard 3-window frozen Space replay
- decision: reject
- rejection_reason: extension_trades_present; no_window_regressed; drawdown_delta_within_limit; no_window_ev_regression; max_window_drawdown_delta_lte_0_5pp

## Gate Answers

- alpha_hypothesis: VSAT satcom fallback pool expansion should require both closed forward benchmark/same-theme evidence and IWM-led small-cap risk appetite.
- prior_similar_experiments: exp-20260516-032 rejected VSAT fallback without IWM gating due late drawdown and old_thin EV regression; exp-20260516-015 accepted IWM-leader confirmation inside dual-catalyst Space trend allocation.
- one_independent_variable: space_forward_benchmark_same_theme_satcom_iwm_leader_fallback_pool_membership
- success_criteria: aggregate EV/PnL improve, no window EV regression, drawdown drift <= 0.5pp, survival >= 5%, and fallback signals/trades are present.
- reproducibility: run this script with .venv\Scripts\python.exe; it writes JSON, doc log, ticket, artifact, and experiment_log.jsonl record.

## Three-Window Metrics

| window | before EV | after EV | EV delta | before PnL | after PnL | PnL delta | DD delta | survival delta | trades delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.711600 | 9.122300 | 0.410700 | 247486.83 | 269894.04 | 22407.21 | 0.032200 | -0.028100 | 1 |
| mid_weak | 18.923900 | 18.938300 | 0.014400 | 418668.25 | 418985.58 | 317.33 | 0.000000 | -0.019100 | 0 |
| old_thin | 1.605100 | 1.574600 | -0.030500 | 89672.79 | 88459.44 | -1213.35 | -0.002500 | 0.000000 | 0 |

## Aggregate Delta

- expected_value_score_delta: 0.394600
- total_pnl_delta: 21511.19
- max_drawdown_delta: 0.032200
- trade_count_delta: 1

## Fallback State Audit

```json
{
  "by_action": {
    "filtered": 5,
    "kept": 1
  },
  "by_iwm_state": {
    "smallcap_laggard": 4,
    "smallcap_leader": 2
  },
  "by_peer_state": {
    "leader": 4,
    "nonleader": 2
  },
  "by_reason": {
    "iwm_state_not_smallcap_leader": 3,
    "kept_iwm_leader_trend_fallback": 1,
    "non_trend": 2
  },
  "counts": {
    "filtered_VSAT": 5,
    "filtered_breakout_long": 2,
    "filtered_extension_iwm_state_not_smallcap_leader": 3,
    "filtered_extension_non_trend": 2,
    "filtered_extension_signal": 5,
    "filtered_trend_long": 3,
    "kept_VSAT": 1,
    "kept_extension_signal": 1,
    "kept_smallcap_leader": 1
  },
  "records": [
    {
      "action": "filtered",
      "date": "",
      "reason": "non_trend",
      "space_iwm_relative_state": "smallcap_leader",
      "space_peer_momentum_state": "nonleader",
      "strategy": "breakout_long",
      "ticker": "VSAT"
    },
    {
      "action": "filtered",
      "date": "",
      "reason": "non_trend",
      "space_iwm_relative_state": "smallcap_laggard",
      "space_peer_momentum_state": "leader",
      "strategy": "breakout_long",
      "ticker": "VSAT"
    },
    {
      "action": "filtered",
      "date": "",
      "reason": "iwm_state_not_smallcap_leader",
      "space_iwm_relative_state": "smallcap_laggard",
      "space_peer_momentum_state": "nonleader",
      "strategy": "trend_long",
      "ticker": "VSAT"
    },
    {
      "action": "filtered",
      "date": "",
      "reason": "iwm_state_not_smallcap_leader",
      "space_iwm_relative_state": "smallcap_laggard",
      "space_peer_momentum_state": "leader",
      "strategy": "trend_long",
      "ticker": "VSAT"
    },
    {
      "action": "filtered",
      "date": "",
      "reason": "iwm_state_not_smallcap_leader",
      "space_iwm_relative_state": "smallcap_laggard",
      "space_peer_momentum_state": "leader",
      "strategy": "trend_long",
      "ticker": "VSAT"
    },
    {
      "action": "kept",
      "date": "",
      "reason": "kept_iwm_leader_trend_fallback",
      "space_iwm_relative_state": "smallcap_leader",
      "space_peer_momentum_state": "leader",
      "strategy": "trend_long",
      "ticker": "VSAT"
    }
  ],
  "required_iwm_relative_state": "smallcap_leader",
  "rule": "Added satcom tickers are allowed only for trend_long signals on dates with no base official Space signal and IWM 20d momentum above SPY 20d momentum."
}
```

## Gate Detail

```json
{
  "aggregate_delta": {
    "expected_value_score_delta": 0.3946000000000005,
    "max_drawdown_delta": 0.032200000000000006,
    "survival_rate_delta": -0.019100000000000006,
    "total_pnl_delta": 21511.19000000006,
    "trade_count_delta": 1
  },
  "aggregate_delta_vs_before": {
    "expected_value_score_sum": 0.3946,
    "max_drawdown_pct_max": 0.0322,
    "min_survival_rate": -0.0191,
    "signals_generated_sum": 5,
    "signals_survived_sum": 0,
    "total_pnl_sum": 21511.19,
    "trade_count_sum": 1
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
      "expected_value_score": 0.0144,
      "max_drawdown_pct": 0.0,
      "sharpe_daily": 0.0,
      "signals_generated": 4.0,
      "signals_survived": 1.0,
      "strategy_total_return_pct": 0.0032,
      "survival_rate": -0.0191,
      "tail_loss_share": 0.0054,
      "total_pnl": 317.33,
      "trade_count": 0.0,
      "win_rate": 0.0,
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
      "total_pnl": 0,
      "trade_count": 0,
      "trades": [],
      "wins": 0
    },
    "old_thin": {
      "losses": 0,
      "total_pnl": 0,
      "trade_count": 0,
      "trades": [],
      "wins": 0
    }
  },
  "extension_trade_count": 0,
  "fallback_filter_summary": {
    "by_action": {
      "filtered": 5,
      "kept": 1
    },
    "by_iwm_state": {
      "smallcap_laggard": 4,
      "smallcap_leader": 2
    },
    "by_peer_state": {
      "leader": 4,
      "nonleader": 2
    },
    "by_reason": {
      "iwm_state_not_smallcap_leader": 3,
      "kept_iwm_leader_trend_fallback": 1,
      "non_trend": 2
    },
    "counts": {
      "filtered_VSAT": 5,
      "filtered_breakout_long": 2,
      "filtered_extension_iwm_state_not_smallcap_leader": 3,
      "filtered_extension_non_trend": 2,
      "filtered_extension_signal": 5,
      "filtered_trend_long": 3,
      "kept_VSAT": 1,
      "kept_extension_signal": 1,
      "kept_smallcap_leader": 1
    },
    "records": [
      {
        "action": "filtered",
        "date": "",
        "reason": "non_trend",
        "space_iwm_relative_state": "smallcap_leader",
        "space_peer_momentum_state": "nonleader",
        "strategy": "breakout_long",
        "ticker": "VSAT"
      },
      {
        "action": "filtered",
        "date": "",
        "reason": "non_trend",
        "space_iwm_relative_state": "smallcap_laggard",
        "space_peer_momentum_state": "leader",
        "strategy": "breakout_long",
        "ticker": "VSAT"
      },
      {
        "action": "filtered",
        "date": "",
        "reason": "iwm_state_not_smallcap_leader",
        "space_iwm_relative_state": "smallcap_laggard",
        "space_peer_momentum_state": "nonleader",
        "strategy": "trend_long",
        "ticker": "VSAT"
      },
      {
        "action": "filtered",
        "date": "",
        "reason": "iwm_state_not_smallcap_leader",
        "space_iwm_relative_state": "smallcap_laggard",
        "space_peer_momentum_state": "leader",
        "strategy": "trend_long",
        "ticker": "VSAT"
      },
      {
        "action": "filtered",
        "date": "",
        "reason": "iwm_state_not_smallcap_leader",
        "space_iwm_relative_state": "smallcap_laggard",
        "space_peer_momentum_state": "leader",
        "strategy": "trend_long",
        "ticker": "VSAT"
      },
      {
        "action": "kept",
        "date": "",
        "reason": "kept_iwm_leader_trend_fallback",
        "space_iwm_relative_state": "smallcap_leader",
        "space_peer_momentum_state": "leader",
        "strategy": "trend_long",
        "ticker": "VSAT"
      }
    ],
    "required_iwm_relative_state": "smallcap_leader",
    "rule": "Added satcom tickers are allowed only for trend_long signals on dates with no base official Space signal and IWM 20d momentum above SPY 20d momentum."
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
    "mid_weak": 0.0144
  },
  "non_trend_filtered_extension_signal_count": 0,
  "passed": false,
  "production_impact": {
    "backtester_adapter_changed": false,
    "live_slots": 0,
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
    "extension_trades_present": false,
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
      "expected_value_score_delta": 0.014400000000001967,
      "max_drawdown_delta": 0.0,
      "survival_rate_delta": -0.019100000000000006,
      "total_pnl_delta": 317.3300000000163,
      "trade_count_delta": 0
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
  live_slots: 0
```
