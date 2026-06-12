# exp-20260612-008 Post-Earnings Event+1 Exclusion

Decision: `rejected_post_earnings_event_plus_one_exclusion`.

Single variable: exclude `recent_signal_trading_day_offset == 1` from the accepted `POST_EARNINGS_UNDERPRICED_DRIFT_PAPER` candidate pool.

Baseline: `exp-20260603-022` accepted after metrics.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Before trades | After trades | Baseline event+1 PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.5416 | 5.5416 | +0.0000 | $120,469.55 | $120,469.55 | $+0.00 | +0.0000 | 5 | 5 | $+0.00 |
| mid_weak | 2.2038 | 2.2310 | +0.0272 | $78,989.68 | $79,677.79 | $+688.11 | +0.0002 | 9 | 4 | $-688.11 |
| old_thin | 0.5985 | 0.6070 | +0.0085 | $39,897.97 | $40,201.87 | $+303.90 | -0.0002 | 6 | 5 | $-303.90 |

## Aggregate

- EV delta: `0.0357` (`0.004279`)
- PnL delta: `$992.01` (`0.004144`)
- after target trades: `14`
- failed reasons: `target_sample_too_small`

## Offset Summary

```json
{
  "baseline_event_plus_one_pnl_by_ticker": {
    "DE": -409.58,
    "ISRG": -303.9,
    "NOW": 336.74,
    "RTX": -84.85,
    "SNOW": -861.48,
    "V": 331.06
  },
  "by_window": {
    "late_strong": {
      "after_event_plus_one_trade_count": 0,
      "after_offsets": {
        "0": 4,
        "2": 1
      },
      "after_trade_count": 5,
      "baseline_event_plus_one_pnl": 0,
      "baseline_event_plus_one_trade_count": 0,
      "baseline_trade_count": 5,
      "filtered_event_plus_one_candidate_count": 0
    },
    "mid_weak": {
      "after_event_plus_one_trade_count": 0,
      "after_offsets": {
        "0": 1,
        "2": 1,
        "3": 1,
        "5": 1
      },
      "after_trade_count": 4,
      "baseline_event_plus_one_pnl": -688.11,
      "baseline_event_plus_one_trade_count": 5,
      "baseline_trade_count": 9,
      "filtered_event_plus_one_candidate_count": 0
    },
    "old_thin": {
      "after_event_plus_one_trade_count": 0,
      "after_offsets": {
        "0": 2,
        "2": 1,
        "3": 1,
        "4": 1
      },
      "after_trade_count": 5,
      "baseline_event_plus_one_pnl": -303.9,
      "baseline_event_plus_one_trade_count": 1,
      "baseline_trade_count": 6,
      "filtered_event_plus_one_candidate_count": 0
    }
  },
  "excluded_recent_signal_offsets": [
    1
  ]
}
```

## Gate 4

```json
{
  "acceptance_rule": "Metric Gate 4 uses docs/backtesting.md three canonical windows versus exp-20260603-022 accepted after-state. Retention also requires shared default-off adapter promotion, which this scout does not do.",
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "target_sample_too_small"
  ],
  "max_drawdown_worse": 0.0002,
  "max_drawdown_worse_guardrail": 0.005,
  "metric_gate4_passed": false,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.329617,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": true,
    "positive_pnl_hhi": 0.206594,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 14,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 2,
  "windows_ev_regressed": 0,
  "windows_pnl_regressed": 0
}
```

## Production Impact

Replay scout only. No shared helper, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, exit, LLM, or news behavior changed. A positive metric result must be promoted through the shared default-off helper before retention.

No JavaScript was used.
