# exp-20260526-013 Volume-Breadth Confirmed Breakout Paper Sleeve

Decision: `promising_replay_only_volume_breadth_breakout_sleeve`.

Single variable: a default-off paper sleeve admits at most one liquid breakout candidate per day only when same-date market up-volume breadth confirms broad participation.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates | Breadth days | Tickers |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.5780 | +0.4152 | $117,072.92 | $121,255.25 | $+4,182.33 | -0.0022 | 8 | 30 | 12 | 23 |
| mid_weak | 2.1402 | 2.2780 | +0.1378 | $78,110.11 | $80,780.62 | $+2,670.51 | -0.0011 | 17 | 78 | 21 | 29 |
| old_thin | 0.5911 | 0.7505 | +0.1594 | $39,667.96 | $46,040.62 | $+6,372.66 | -0.0033 | 22 | 86 | 23 | 32 |

## Aggregate

- EV delta: `0.7124` (`0.090245`)
- PnL delta: `$13225.5` (`0.056314`)
- target trades: `47` across `3` windows
- max single positive share: `0.230268`
- positive PnL HHI: `0.151383`

## Breadth Audit

```json
{
  "late_strong": {
    "breadth_pass_day_fraction": 0.097561,
    "breadth_pass_days": 12,
    "candidate_days": 11,
    "candidate_source_tickers": 38,
    "raw_liquid_breadth_breakout_hits": 30,
    "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
    "sample_breadth_context": {
      "2025-10-29": {
        "above_50d_count": 27,
        "above_50d_fraction": 0.710526,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.552632,
        "positive_day_count": 21,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 5,
        "volume_breadth_fraction": 0.131579,
        "volume_breadth_thrust_passed": true
      },
      "2025-11-05": {
        "above_50d_count": 24,
        "above_50d_fraction": 0.631579,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.605263,
        "positive_day_count": 23,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 7,
        "volume_breadth_fraction": 0.184211,
        "volume_breadth_thrust_passed": true
      },
      "2025-11-12": {
        "above_50d_count": 24,
        "above_50d_fraction": 0.631579,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.605263,
        "positive_day_count": 23,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 7,
        "volume_breadth_fraction": 0.184211,
        "volume_breadth_thrust_passed": true
      },
      "2025-12-10": {
        "above_50d_count": 21,
        "above_50d_fraction": 0.552632,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.605263,
        "positive_day_count": 23,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 7,
        "volume_breadth_fraction": 0.184211,
        "volume_breadth_thrust_passed": true
      },
      "2025-12-19": {
        "above_50d_count": 19,
        "above_50d_fraction": 0.5,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.815789,
        "positive_day_count": 31,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 26,
        "volume_breadth_fraction": 0.684211,
        "volume_breadth_thrust_passed": true
      },
      "2026-01-05": {
        "above_50d_count": 22,
        "above_50d_fraction": 0.578947,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.710526,
        "positive_day_count": 27,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 11,
        "volume_breadth_fraction": 0.289474,
        "volume_breadth_thrust_passed": true
      },
      "2026-01-06": {
        "above_50d_count": 22,
        "above_50d_fraction": 0.578947,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.631579,
        "positive_day_count": 24,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 7,
        "volume_breadth_fraction": 0.184211,
        "volume_breadth_thrust_passed": true
      },
      "2026-01-22": {
        "above_50d_count": 18,
        "above_50d_fraction": 0.473684,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.710526,
        "positive_day_count": 27,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 7,
        "volume_breadth_fraction": 0.184211,
        "volume_breadth_thrust_passed": true
      },
      "2026-01-26": {
        "above_50d_count": 18,
        "above_50d_fraction": 0.473684,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.578947,
        "positive_day_count": 22,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 7,
        "volume_breadth_fraction": 0.184211,
        "volume_breadth_thrust_passed": true
      },
      "2026-04-13": {
        "above_50d_count": 21,
        "above_50d_fraction": 0.552632,
        "eligible_ticker_count": 38,
        "market_up_fraction": 0.815789,
        "positive_day_count": 31,
        "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
        "up_volume_spike_count": 5,
        "volume_breadth_fraction": 0.131579,
        "volume_breadth_thrust_passed": true
      }
    },
    "trading_days": 123,
    "unique_candidate_tickers": 23
  },
  "mid_weak": {
    "breadth_pass_day_fraction": 0.165354,
    "breadth_pass_days": 21,
    "candidate_days": 18,
    "candidate_source_tickers": 38,
    "raw_liquid_breadth_breakout_hits": 78,
    "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
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
    "trading_days": 127,
    "unique_candidate_tickers": 29
  },
  "old_thin": {
    "breadth_pass_day_fraction": 0.166667,
    "breadth_pass_days": 23,
    "candidate_days": 22,
    "candidate_source_tickers": 38,
    "raw_liquid_breadth_breakout_hits": 86,
    "rule_version": "volume_breadth_thrust_confirmed_breakout_v1",
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
    "trading_days": 138,
    "unique_candidate_tickers": 32
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": -0.0011,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": true,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.230268,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.151383,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 47,
  "target_trade_count_min": 30,
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
