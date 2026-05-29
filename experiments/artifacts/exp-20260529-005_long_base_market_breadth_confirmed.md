# exp-20260529-005 Long-Base Market-Breadth Confirmed

Decision: `rejected_long_base_market_breadth_confirmed`.

Single variable: a default-off paper source admits the existing long-base 63-day breakout candidates only when same-date market volume-breadth participation passes.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw long-base | Confirmed candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.9599 | -0.2029 | $117,072.92 | $115,079.19 | $-1,993.73 | +0.0009 | 4 | 12 | 5 |
| mid_weak | 2.1402 | 2.1883 | +0.0481 | $78,110.11 | $78,998.40 | $+888.29 | +0.0000 | 2 | 10 | 2 |
| old_thin | 0.5911 | 0.5797 | -0.0114 | $39,667.96 | $39,166.59 | $-501.37 | +0.0013 | 7 | 18 | 8 |

## Aggregate

- EV delta: `-0.1662` (`-0.021054`)
- PnL delta: `$-1606.81` (`-0.006842`)
- target trades: `13` across `3` windows
- max single positive share: `0.591037`
- positive PnL HHI: `0.483932`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": false,
  "aggregate_pnl_delta_positive": false,
  "failed_reasons": [
    "aggregate_ev_not_positive",
    "aggregate_pnl_not_positive",
    "window_ev_regression",
    "window_pnl_regression",
    "target_sample_too_small",
    "target_concentration_failed"
  ],
  "max_drawdown_worse": 0.0013,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.591037,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.483932,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 13,
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

## Candidate Audit

```json
{
  "late_strong": {
    "breadth_pass_day_fraction": 0.130081,
    "breadth_pass_days": 16,
    "breadth_rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
    "candidate_count": 5,
    "candidate_days": 4,
    "dates_checked": 123,
    "long_base_raw_candidate_count": 12,
    "long_base_source_audit": {
      "candidate_days": 11,
      "long_base_breakout_candidates": 12,
      "raw_ticker_days_considered": 5102,
      "rule_version": "long_base_63d_breakout_v1",
      "source_tickers_considered": 42,
      "unique_candidate_tickers": 11
    },
    "reject_counts": {
      "market_breadth_context_not_passed": 7
    },
    "rule_version": "long_base_63d_market_breadth_confirmed_v1",
    "sample_breadth_context": {
      "2025-10-29": {
        "above_50d_count": 30,
        "above_50d_fraction": 0.731707,
        "eligible_ticker_count": 41,
        "market_up_fraction": 0.560976,
        "positive_day_count": 23,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 7,
        "volume_breadth_fraction": 0.170732,
        "volume_breadth_thrust_passed": true
      },
      "2025-11-05": {
        "above_50d_count": 27,
        "above_50d_fraction": 0.658537,
        "eligible_ticker_count": 41,
        "market_up_fraction": 0.634146,
        "positive_day_count": 26,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 8,
        "volume_breadth_fraction": 0.195122,
        "volume_breadth_thrust_passed": true
      },
      "2025-11-12": {
        "above_50d_count": 27,
        "above_50d_fraction": 0.658537,
        "eligible_ticker_count": 41,
        "market_up_fraction": 0.609756,
        "positive_day_count": 25,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 7,
        "volume_breadth_fraction": 0.170732,
        "volume_breadth_thrust_passed": true
      },
      "2025-12-10": {
        "above_50d_count": 23,
        "above_50d_fraction": 0.560976,
        "eligible_ticker_count": 41,
        "market_up_fraction": 0.609756,
        "positive_day_count": 25,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 7,
        "volume_breadth_fraction": 0.170732,
        "volume_breadth_thrust_passed": true
      },
      "2025-12-19": {
        "above_50d_count": 20,
        "above_50d_fraction": 0.487805,
        "eligible_ticker_count": 41,
        "market_up_fraction": 0.829268,
        "positive_day_count": 34,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 27,
        "volume_breadth_fraction": 0.658537,
        "volume_breadth_thrust_passed": true
      },
      "2026-01-02": {
        "above_50d_count": 21,
        "above_50d_fraction": 0.512195,
        "eligible_ticker_count": 41,
        "market_up_fraction": 0.536585,
        "positive_day_count": 22,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 5,
        "volume_breadth_fraction": 0.121951,
        "volume_breadth_thrust_passed": true
      },
      "2026-01-05": {
        "above_50d_count": 24,
        "above_50d_fraction": 0.585366,
        "eligible_ticker_count": 41,
        "market_up_fraction": 0.682927,
        "positive_day_count": 28,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 11,
        "volume_breadth_fraction": 0.268293,
        "volume_breadth_thrust_passed": true
      },
      "2026-01-06": {
        "above_50d_count": 24,
        "above_50d_fraction": 0.585366,
        "eligible_ticker_count": 41,
        "market_up_fraction": 0.634146,
        "positive_day_count": 26,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 8,
        "volume_breadth_fraction": 0.195122,
        "volume_breadth_thrust_passed": true
      },
      "2026-01-09": {
        "above_50d_count": 27,
        "above_50d_fraction": 0.658537,
        "eligible_ticker_count": 41,
        "market_up_fraction": 0.609756,
        "positive_day_count": 25,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 6,
        "volume_breadth_fraction": 0.146341,
        "volume_breadth_thrust_passed": true
      },
      "2026-01-13": {
        "above_50d_count": 23,
        "above_50d_fraction": 0.560976,
        "eligible_ticker_count": 41,
        "market_up_fraction": 0.536585,
        "positive_day_count": 22,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 6,
        "volume_breadth_fraction": 0.146341,
        "volume_breadth_thrust_passed": true
      }
    },
    "unique_candidate_tickers": 5
  },
  "mid_weak": {
    "breadth_pass_day_fraction": 0.165354,
    "breadth_pass_days": 21,
    "breadth_rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
    "candidate_count": 2,
    "candidate_days": 2,
    "dates_checked": 127,
    "long_base_raw_candidate_count": 10,
    "long_base_source_audit": {
      "candidate_days": 10,
      "long_base_breakout_candidates": 10,
      "raw_ticker_days_considered": 4826,
      "rule_version": "long_base_63d_breakout_v1",
      "source_tickers_considered": 38,
      "unique_candidate_tickers": 10
    },
    "reject_counts": {
      "market_breadth_context_not_passed": 8
    },
    "rule_version": "long_base_63d_market_breadth_confirmed_v1",
    "sample_breadth_context": {
      "2025-05-08": {
        "above_50d_count": 31,
        "above_50d_fraction": 0.815789,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.789474,
        "positive_day_count": 30,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 7,
        "volume_breadth_fraction": 0.184211,
        "volume_breadth_thrust_passed": true
      },
      "2025-05-12": {
        "above_50d_count": 32,
        "above_50d_fraction": 0.842105,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.894737,
        "positive_day_count": 34,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 17,
        "volume_breadth_fraction": 0.447368,
        "volume_breadth_thrust_passed": true
      },
      "2025-05-13": {
        "above_50d_count": 32,
        "above_50d_fraction": 0.842105,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.815789,
        "positive_day_count": 31,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 13,
        "volume_breadth_fraction": 0.342105,
        "volume_breadth_thrust_passed": true
      },
      "2025-05-14": {
        "above_50d_count": 32,
        "above_50d_fraction": 0.842105,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.605263,
        "positive_day_count": 23,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 5,
        "volume_breadth_fraction": 0.131579,
        "volume_breadth_thrust_passed": true
      },
      "2025-05-30": {
        "above_50d_count": 33,
        "above_50d_fraction": 0.868421,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.552632,
        "positive_day_count": 21,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 13,
        "volume_breadth_fraction": 0.342105,
        "volume_breadth_thrust_passed": true
      },
      "2025-06-16": {
        "above_50d_count": 33,
        "above_50d_fraction": 0.868421,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.868421,
        "positive_day_count": 33,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 6,
        "volume_breadth_fraction": 0.157895,
        "volume_breadth_thrust_passed": true
      },
      "2025-06-23": {
        "above_50d_count": 30,
        "above_50d_fraction": 0.789474,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.710526,
        "positive_day_count": 27,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 6,
        "volume_breadth_fraction": 0.157895,
        "volume_breadth_thrust_passed": true
      },
      "2025-06-24": {
        "above_50d_count": 32,
        "above_50d_fraction": 0.842105,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.868421,
        "positive_day_count": 33,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 12,
        "volume_breadth_fraction": 0.315789,
        "volume_breadth_thrust_passed": true
      },
      "2025-06-26": {
        "above_50d_count": 31,
        "above_50d_fraction": 0.815789,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.894737,
        "positive_day_count": 34,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 6,
        "volume_breadth_fraction": 0.157895,
        "volume_breadth_thrust_passed": true
      },
      "2025-06-27": {
        "above_50d_count": 29,
        "above_50d_fraction": 0.763158,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.631579,
        "positive_day_count": 24,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 16,
        "volume_breadth_fraction": 0.421053,
        "volume_breadth_thrust_passed": true
      }
    },
    "unique_candidate_tickers": 2
  },
  "old_thin": {
    "breadth_pass_day_fraction": 0.166667,
    "breadth_pass_days": 23,
    "breadth_rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
    "candidate_count": 8,
    "candidate_days": 7,
    "dates_checked": 138,
    "long_base_raw_candidate_count": 18,
    "long_base_source_audit": {
      "candidate_days": 16,
      "long_base_breakout_candidates": 18,
      "raw_ticker_days_considered": 5244,
      "rule_version": "long_base_63d_breakout_v1",
      "source_tickers_considered": 38,
      "unique_candidate_tickers": 16
    },
    "reject_counts": {
      "market_breadth_context_not_passed": 10
    },
    "rule_version": "long_base_63d_market_breadth_confirmed_v1",
    "sample_breadth_context": {
      "2024-10-16": {
        "above_50d_count": 33,
        "above_50d_fraction": 0.868421,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.631579,
        "positive_day_count": 24,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 5,
        "volume_breadth_fraction": 0.131579,
        "volume_breadth_thrust_passed": true
      },
      "2024-10-29": {
        "above_50d_count": 32,
        "above_50d_fraction": 0.842105,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.605263,
        "positive_day_count": 23,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 8,
        "volume_breadth_fraction": 0.210526,
        "volume_breadth_thrust_passed": true
      },
      "2024-11-01": {
        "above_50d_count": 28,
        "above_50d_fraction": 0.736842,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.578947,
        "positive_day_count": 22,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 7,
        "volume_breadth_fraction": 0.184211,
        "volume_breadth_thrust_passed": true
      },
      "2024-11-05": {
        "above_50d_count": 28,
        "above_50d_fraction": 0.736842,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.868421,
        "positive_day_count": 33,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 5,
        "volume_breadth_fraction": 0.131579,
        "volume_breadth_thrust_passed": true
      },
      "2024-11-06": {
        "above_50d_count": 31,
        "above_50d_fraction": 0.815789,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.842105,
        "positive_day_count": 32,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 25,
        "volume_breadth_fraction": 0.657895,
        "volume_breadth_thrust_passed": true
      },
      "2024-11-07": {
        "above_50d_count": 32,
        "above_50d_fraction": 0.842105,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.736842,
        "positive_day_count": 28,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 10,
        "volume_breadth_fraction": 0.263158,
        "volume_breadth_thrust_passed": true
      },
      "2024-11-08": {
        "above_50d_count": 34,
        "above_50d_fraction": 0.894737,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.552632,
        "positive_day_count": 21,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 8,
        "volume_breadth_fraction": 0.210526,
        "volume_breadth_thrust_passed": true
      },
      "2024-11-21": {
        "above_50d_count": 28,
        "above_50d_fraction": 0.736842,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.631579,
        "positive_day_count": 24,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 8,
        "volume_breadth_fraction": 0.210526,
        "volume_breadth_thrust_passed": true
      },
      "2024-11-25": {
        "above_50d_count": 27,
        "above_50d_fraction": 0.710526,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.657895,
        "positive_day_count": 25,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 12,
        "volume_breadth_fraction": 0.315789,
        "volume_breadth_thrust_passed": true
      },
      "2024-12-16": {
        "above_50d_count": 27,
        "above_50d_fraction": 0.710526,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.631579,
        "positive_day_count": 24,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 6,
        "volume_breadth_fraction": 0.157895,
        "volume_breadth_thrust_passed": true
      }
    },
    "unique_candidate_tickers": 7
  }
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
