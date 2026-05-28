# exp-20260528-024 RS-Line New-High Closed-Ledger Governor

Decision: `rejected_rs_line_new_high_closed_ledger_governor`.

Single variable: keep the exp-20260527-013 RS-line new-high candidate pool fixed and apply a closed-ledger paper governor using only prior closed sleeve outcomes.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Gov scaled |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.3123 | -0.8505 | $117,072.92 | $109,453.32 | $-7,619.60 | +0.0018 | 61 | 18 |
| mid_weak | 2.1402 | 3.7685 | +1.6283 | $78,110.11 | $104,677.52 | $+26,567.41 | -0.0082 | 74 | 0 |
| old_thin | 0.5911 | 1.0668 | +0.4757 | $39,667.96 | $52,807.63 | $+13,139.67 | +0.0447 | 83 | 18 |

## Aggregate

- EV delta vs core: `1.2535` (`0.158789`)
- PnL delta vs core: `$32087.48` (`0.136629`)
- target trades: `218`
- max drawdown drift: `0.0447`
- max single positive share: `0.279561`
- positive PnL HHI: `0.136172`

## Raw RS-Line Comparison

```json
{
  "aggregate_delta_after_vs_raw_rs_line": {
    "expected_value_score_delta_sum": 0.3807,
    "max_drawdown_pct_delta_max": -0.0718,
    "total_pnl_delta_sum": 11500.52
  },
  "available": true,
  "by_window_delta_after_vs_raw_rs_line": {
    "late_strong": {
      "expected_value_score_delta": 0.0138,
      "max_drawdown_pct_delta": 0.0,
      "total_pnl_delta": 353.42
    },
    "mid_weak": {
      "expected_value_score_delta": 0.0,
      "max_drawdown_pct_delta": 0.0,
      "total_pnl_delta": 0.0
    },
    "old_thin": {
      "expected_value_score_delta": 0.3669,
      "max_drawdown_pct_delta": -0.0718,
      "total_pnl_delta": 11147.1
    }
  },
  "reference_decision": "rejected_rs_line_new_high_paper_sleeve",
  "reference_experiment_id": "exp-20260527-013"
}
```

## Governor Audit

```json
{
  "late_strong": {
    "daily_top1_filtered": 47,
    "ending_closed_pnl": -6253.51,
    "ending_peak_closed_pnl": 1587.14,
    "global_drawdown_scaled": 18,
    "global_scaled_counts": {
      "CAT": 2,
      "CVX": 8,
      "MU": 2,
      "RTX": 1,
      "XOM": 5
    },
    "governor_pnl_delta_by_ticker": {
      "CAT": 113.37,
      "CVX": -1079.85,
      "MU": 2565.42,
      "RTX": 93.18,
      "XOM": -1338.7
    },
    "max_closed_drawdown_seen": 10284.71,
    "missing_trade_filtered": 2,
    "raw_candidate_count": 112,
    "rule_version": "rs_line_new_high_closed_ledger_governor_v1",
    "same_ticker_core_overlap_filtered": 2,
    "selected_ticker_count": 17,
    "selected_trade_count": 61,
    "ticker_scaled_counts": {}
  },
  "mid_weak": {
    "daily_top1_filtered": 67,
    "ending_closed_pnl": 25844.71,
    "ending_peak_closed_pnl": 27951.34,
    "global_scaled_counts": {},
    "governor_pnl_delta_by_ticker": {},
    "max_closed_drawdown_seen": 2106.63,
    "missing_trade_filtered": 6,
    "raw_candidate_count": 150,
    "rule_version": "rs_line_new_high_closed_ledger_governor_v1",
    "same_ticker_core_overlap_filtered": 3,
    "selected_ticker_count": 23,
    "selected_trade_count": 74,
    "ticker_scaled_counts": {}
  },
  "old_thin": {
    "daily_top1_filtered": 75,
    "ending_closed_pnl": 15836.99,
    "ending_peak_closed_pnl": 27050.89,
    "global_drawdown_scaled": 12,
    "global_scaled_counts": {
      "CVX": 1,
      "GE": 1,
      "MCD": 1,
      "MU": 1,
      "RTX": 3,
      "SPOT": 1,
      "UNH": 2,
      "XOM": 2
    },
    "governor_pnl_delta_by_ticker": {
      "APP": 1153.94,
      "CVX": 1504.5,
      "GE": 95.01,
      "MCD": 111.63,
      "MU": 1846.84,
      "RTX": -40.64,
      "SPOT": 1134.1,
      "UNH": 3347.5,
      "XOM": 1994.22
    },
    "max_closed_drawdown_seen": 11213.9,
    "missing_trade_filtered": 6,
    "raw_candidate_count": 167,
    "rule_version": "rs_line_new_high_closed_ledger_governor_v1",
    "same_ticker_core_overlap_filtered": 3,
    "selected_ticker_count": 27,
    "selected_trade_count": 83,
    "ticker_profit_cap_scaled": 6,
    "ticker_scaled_counts": {
      "APP": 6
    }
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0447,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.279561,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.136172,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 218,
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

Replay-only default-off paper. No shared policy, run adapter, backtester adapter, production watchlist, live/default order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
