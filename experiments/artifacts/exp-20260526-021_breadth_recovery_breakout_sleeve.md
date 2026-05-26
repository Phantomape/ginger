# exp-20260526-021 Breadth-Recovery Breakout Paper Sleeve

Decision: `rejected_breadth_recovery_breakout_sleeve`.

Single variable: a default-off paper sleeve admits at most one liquid breakout candidate per day only when market breadth has recovered from a weaker recent state.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates | Recovery days | Tickers |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.2655 | +0.1027 | $117,072.92 | $118,056.53 | $+983.61 | -0.0002 | 4 | 20 | 10 | 14 |
| mid_weak | 2.1402 | 2.2204 | +0.0802 | $78,110.11 | $79,303.72 | $+1,193.61 | -0.0013 | 5 | 13 | 5 | 10 |
| old_thin | 0.5911 | 0.6084 | +0.0173 | $39,667.96 | $40,287.51 | $+619.55 | -0.0004 | 3 | 18 | 3 | 12 |

## Aggregate

- EV delta: `0.2002` (`0.025361`)
- PnL delta: `$2796.77` (`0.011909`)
- target trades: `12` across `3` windows
- max single positive share: `0.202562`
- positive PnL HHI: `0.155115`

## Breadth-Recovery Audit

```json
{
  "late_strong": {
    "breadth_recovery_pass_day_fraction": 0.081301,
    "breadth_recovery_pass_days": 10,
    "candidate_days": 9,
    "candidate_source_tickers": 38,
    "raw_liquid_breadth_recovery_breakout_hits": 20,
    "rule_version": "breadth_recovery_confirmed_breakout_v1",
    "sample_breadth_recovery_context": {
      "2025-10-23": {
        "above_50d_count": 25,
        "above_50d_fraction": 0.657895,
        "above_50d_recovery": 0.184211,
        "alters_orders": false,
        "asof_date": "2025-10-23",
        "breadth_recovery_passed": true,
        "eligible_ticker_count": 38,
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "lookback_trading_days": 5,
        "market_up_fraction": 0.789474,
        "positive_day_count": 30,
        "prior_above_50d_fraction": 0.473684,
        "prior_breadth_date": "2025-10-16",
        "prior_eligible_ticker_count": 38,
        "rule_version": "breadth_recovery_confirmed_breakout_v1",
        "trade_enabled": false,
        "up_volume_fraction": 0.105263,
        "up_volume_spike_count": 4
      },
      "2025-12-03": {
        "above_50d_count": 18,
        "above_50d_fraction": 0.473684,
        "above_50d_recovery": 0.078947,
        "alters_orders": false,
        "asof_date": "2025-12-03",
        "breadth_recovery_passed": true,
        "eligible_ticker_count": 38,
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "lookback_trading_days": 5,
        "market_up_fraction": 0.605263,
        "positive_day_count": 23,
        "prior_above_50d_fraction": 0.394737,
        "prior_breadth_date": "2025-11-25",
        "prior_eligible_ticker_count": 38,
        "rule_version": "breadth_recovery_confirmed_breakout_v1",
        "trade_enabled": false,
        "up_volume_fraction": 0.105263,
        "up_volume_spike_count": 4
      },
      "2025-12-10": {
        "above_50d_count": 21,
        "above_50d_fraction": 0.552632,
        "above_50d_recovery": 0.078948,
        "alters_orders": false,
        "asof_date": "2025-12-10",
        "breadth_recovery_passed": true,
        "eligible_ticker_count": 38,
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "lookback_trading_days": 5,
        "market_up_fraction": 0.605263,
        "positive_day_count": 23,
        "prior_above_50d_fraction": 0.473684,
        "prior_breadth_date": "2025-12-03",
        "prior_eligible_ticker_count": 38,
        "rule_version": "breadth_recovery_confirmed_breakout_v1",
        "trade_enabled": false,
        "up_volume_fraction": 0.236842,
        "up_volume_spike_count": 9
      },
      "2025-12-11": {
        "above_50d_count": 22,
        "above_50d_fraction": 0.578947,
        "above_50d_recovery": 0.105263,
        "alters_orders": false,
        "asof_date": "2025-12-11",
        "breadth_recovery_passed": true,
        "eligible_ticker_count": 38,
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "lookback_trading_days": 5,
        "market_up_fraction": 0.526316,
        "positive_day_count": 20,
        "prior_above_50d_fraction": 0.473684,
        "prior_breadth_date": "2025-12-04",
        "prior_eligible_ticker_count": 38,
        "rule_version": "breadth_recovery_confirmed_breakout_v1",
        "trade_enabled": false,
        "up_volume_fraction": 0.131579,
        "up_volume_spike_count": 5
      },
      "2026-01-09": {
        "above_50d_count": 24,
        "above_50d_fraction": 0.631579,
        "above_50d_recovery": 0.131579,
        "alters_orders": false,
        "asof_date": "2026-01-09",
        "breadth_recovery_passed": true,
        "eligible_ticker_count": 38,
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "lookback_trading_days": 5,
        "market_up_fraction": 0.578947,
        "positive_day_count": 22,
        "prior_above_50d_fraction": 0.5,
        "prior_breadth_date": "2026-01-02",
        "prior_eligible_ticker_count": 38,
        "rule_version": "breadth_recovery_confirmed_breakout_v1",
        "trade_enabled": false,
        "up_volume_fraction": 0.105263,
        "up_volume_spike_count": 4
      },
      "2026-04-13": {
        "above_50d_count": 21,
        "above_50d_fraction": 0.552632,
        "above_50d_recovery": 0.368421,
        "alters_orders": false,
        "asof_date": "2026-04-13",
        "breadth_recovery_passed": true,
        "eligible_ticker_count": 38,
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "lookback_trading_days": 5,
        "market_up_fraction": 0.815789,
        "positive_day_count": 31,
        "prior_above_50d_fraction": 0.184211,
        "prior_breadth_date": "2026-04-06",
        "prior_eligible_ticker_count": 38,
        "rule_version": "breadth_recovery_confirmed_breakout_v1",
        "trade_enabled": false,
        "up_volume_fraction": 0.157895,
        "up_volume_spike_count": 6
      },
      "2026-04-14": {
        "above_50d_count": 24,
        "above_50d_fraction": 0.631579,
        "above_50d_recovery": 0.394737,
        "alters_orders": false,
        "asof_date": "2026-04-14",
        "breadth_recovery_passed": true,
        "eligible_ticker_count": 38,
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "lookback_trading_days": 5,
        "market_up_fraction": 0.789474,
        "positive_day_count": 30,
        "prior_above_50d_fraction": 0.236842,
        "prior_breadth_date": "2026-04-07",
        "prior_eligible_ticker_count": 38,
        "rule_version": "breadth_recovery_confirmed_breakout_v1",
        "trade_enabled": false,
        "up_volume_fraction": 0.184211,
        "up_volume_spike_count": 7
      },
      "2026-04-15": {
        "above_50d_count": 28,
        "above_50d_fraction": 0.736842,
        "above_50d_recovery": 0.289474,
        "alters_orders": false,
        "asof_date": "2026-04-15",
        "breadth_recovery_passed": true,
        "eligible_ticker_count": 38,
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "lookback_trading_days": 5,
        "market_up_fraction": 0.657895,
        "positive_day_count": 25,
        "prior_above_50d_fraction": 0.447368,
        "prior_breadth_date": "2026-04-08",
        "prior_eligible_ticker_count": 38,
        "rule_version": "breadth_recovery_confirmed_breakout_v1",
        "trade_enabled": false,
        "up_volume_fraction": 0.289474,
        "up_volume_spike_count": 11
      },
      "2026-04-16": {
        "above_50d_count": 26,
        "above_50d_fraction": 0.684211,
        "above_50d_recovery": 0.184211,
        "alters_orders": false,
        "asof_date": "2026-04-16",
        "breadth_recovery_passed": true,
        "eligible_ticker_count": 38,
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "lookback_trading_days": 5,
        "market_up_fraction": 0.605263,
        "positive_day_count": 23,
        "prior_above_50d_fraction": 0.5,
        "prior_breadth_date": "2026-04-09",
        "prior_eligible_ticker_count": 38,
        "rule_version": "breadth_recovery_confirmed_breakout_v1",
        "trade_enabled": false,
        "up_volume_fraction": 0.105263,
        "up_volume_spike_count": 4
      },
      "2026-04-17": {
        "above_50d_count": 28,
        "above_50d_fraction": 0.736842,
        "above_50d_recovery": 0.315789,
        "alters_orders": false,
        "asof_date": "2026-04-17",
        "breadth_recovery_passed": true,
        "eligible_ticker_count": 38,
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "lookback_trading_days": 5,
        "market_up_fraction": 0.868421,
        "positive_day_count": 33,
        "prior_above_50d_fraction": 0.421053,
        "prior_breadth_date": "2026-04-10",
        "prior_eligible_ticker_count": 38,
        "rule_version": "breadth_recovery_confirmed_breakout_v1",
        "trade_enabled": false,
        "up_volume_fraction": 0.263158,
        "up_volume_spike_count": 10
      }
    },
    "trading_days": 123,
    "unique_candidate_tickers": 14
  },
  "mid_weak": {
    "breadth_recovery_pass_day_fraction": 0.03937,
    "breadth_recovery_pass_days": 5,
    "candidate_days": 5,
    "candidate_source_tickers": 38,
    "raw_liquid_breadth_recovery_breakout_hits": 13,
    "rule_version": "breadth_recovery_confirmed_breakout_v1",
    "sample_breadth_recovery_context": {
      "2025-05-01": {
        "above_50d_count": 20,
        "above_50d_fraction": 0.526316,
        "above_50d_recovery": 0.263158,
        "alters_orders": false,
        "asof_date": "2025-05-01",
        "breadth_recovery_passed": true,
        "eligible_ticker_count": 38,
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "lookback_trading_days": 5,
        "market_up_fraction": 0.684211,
        "positive_day_count": 26,
        "prior_above_50d_fraction": 0.263158,
        "prior_breadth_date": "2025-04-24",
        "prior_eligible_ticker_count": 38,
        "rule_version": "breadth_recovery_confirmed_breakout_v1",
        "trade_enabled": false,
        "up_volume_fraction": 0.131579,
        "up_volume_spike_count": 5
      },
      "2025-05-07": {
        "above_50d_count": 28,
        "above_50d_fraction": 0.736842,
        "above_50d_recovery": 0.289474,
        "alters_orders": false,
        "asof_date": "2025-05-07",
        "breadth_recovery_passed": true,
        "eligible_ticker_count": 38,
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "lookback_trading_days": 5,
        "market_up_fraction": 0.736842,
        "positive_day_count": 28,
        "prior_above_50d_fraction": 0.447368,
        "prior_breadth_date": "2025-04-30",
        "prior_eligible_ticker_count": 38,
        "rule_version": "breadth_recovery_confirmed_breakout_v1",
        "trade_enabled": false,
        "up_volume_fraction": 0.105263,
        "up_volume_spike_count": 4
      },
      "2025-05-08": {
        "above_50d_count": 31,
        "above_50d_fraction": 0.815789,
        "above_50d_recovery": 0.289473,
        "alters_orders": false,
        "asof_date": "2025-05-08",
        "breadth_recovery_passed": true,
        "eligible_ticker_count": 38,
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "lookback_trading_days": 5,
        "market_up_fraction": 0.789474,
        "positive_day_count": 30,
        "prior_above_50d_fraction": 0.526316,
        "prior_breadth_date": "2025-05-01",
        "prior_eligible_ticker_count": 38,
        "rule_version": "breadth_recovery_confirmed_breakout_v1",
        "trade_enabled": false,
        "up_volume_fraction": 0.210526,
        "up_volume_spike_count": 8
      },
      "2025-08-08": {
        "above_50d_count": 24,
        "above_50d_fraction": 0.631579,
        "above_50d_recovery": 0.105263,
        "alters_orders": false,
        "asof_date": "2025-08-08",
        "breadth_recovery_passed": true,
        "eligible_ticker_count": 38,
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "lookback_trading_days": 5,
        "market_up_fraction": 0.684211,
        "positive_day_count": 26,
        "prior_above_50d_fraction": 0.526316,
        "prior_breadth_date": "2025-08-01",
        "prior_eligible_ticker_count": 38,
        "rule_version": "breadth_recovery_confirmed_breakout_v1",
        "trade_enabled": false,
        "up_volume_fraction": 0.105263,
        "up_volume_spike_count": 4
      },
      "2025-08-12": {
        "above_50d_count": 23,
        "above_50d_fraction": 0.605263,
        "above_50d_recovery": 0.105263,
        "alters_orders": false,
        "asof_date": "2025-08-12",
        "breadth_recovery_passed": true,
        "eligible_ticker_count": 38,
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "lookback_trading_days": 5,
        "market_up_fraction": 0.894737,
        "positive_day_count": 34,
        "prior_above_50d_fraction": 0.5,
        "prior_breadth_date": "2025-08-05",
        "prior_eligible_ticker_count": 38,
        "rule_version": "breadth_recovery_confirmed_breakout_v1",
        "trade_enabled": false,
        "up_volume_fraction": 0.131579,
        "up_volume_spike_count": 5
      }
    },
    "trading_days": 127,
    "unique_candidate_tickers": 10
  },
  "old_thin": {
    "breadth_recovery_pass_day_fraction": 0.021739,
    "breadth_recovery_pass_days": 3,
    "candidate_days": 3,
    "candidate_source_tickers": 38,
    "raw_liquid_breadth_recovery_breakout_hits": 18,
    "rule_version": "breadth_recovery_confirmed_breakout_v1",
    "sample_breadth_recovery_context": {
      "2025-01-17": {
        "above_50d_count": 26,
        "above_50d_fraction": 0.684211,
        "above_50d_recovery": 0.289474,
        "alters_orders": false,
        "asof_date": "2025-01-17",
        "breadth_recovery_passed": true,
        "eligible_ticker_count": 38,
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "lookback_trading_days": 5,
        "market_up_fraction": 0.868421,
        "positive_day_count": 33,
        "prior_above_50d_fraction": 0.394737,
        "prior_breadth_date": "2025-01-10",
        "prior_eligible_ticker_count": 38,
        "rule_version": "breadth_recovery_confirmed_breakout_v1",
        "trade_enabled": false,
        "up_volume_fraction": 0.394737,
        "up_volume_spike_count": 15
      },
      "2025-01-21": {
        "above_50d_count": 26,
        "above_50d_fraction": 0.684211,
        "above_50d_recovery": 0.289474,
        "alters_orders": false,
        "asof_date": "2025-01-21",
        "breadth_recovery_passed": true,
        "eligible_ticker_count": 38,
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "lookback_trading_days": 5,
        "market_up_fraction": 0.736842,
        "positive_day_count": 28,
        "prior_above_50d_fraction": 0.394737,
        "prior_breadth_date": "2025-01-13",
        "prior_eligible_ticker_count": 38,
        "rule_version": "breadth_recovery_confirmed_breakout_v1",
        "trade_enabled": false,
        "up_volume_fraction": 0.421053,
        "up_volume_spike_count": 16
      },
      "2025-01-22": {
        "above_50d_count": 28,
        "above_50d_fraction": 0.736842,
        "above_50d_recovery": 0.289474,
        "alters_orders": false,
        "asof_date": "2025-01-22",
        "breadth_recovery_passed": true,
        "eligible_ticker_count": 38,
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "lookback_trading_days": 5,
        "market_up_fraction": 0.578947,
        "positive_day_count": 22,
        "prior_above_50d_fraction": 0.447368,
        "prior_breadth_date": "2025-01-14",
        "prior_eligible_ticker_count": 38,
        "rule_version": "breadth_recovery_confirmed_breakout_v1",
        "trade_enabled": false,
        "up_volume_fraction": 0.342105,
        "up_volume_spike_count": 13
      }
    },
    "trading_days": 138,
    "unique_candidate_tickers": 12
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": -0.0002,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.202562,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.155115,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 12,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 3,
  "windows_ev_regressed": 0,
  "windows_pnl_regressed": 0
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
