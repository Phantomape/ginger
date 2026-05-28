# exp-20260528-015 Fundamental Growth + RS Low-Volume Participation

Decision: `accepted_candidate_fundamental_growth_rs_low_volume_participation_support`.

Single variable: apply a 1.10x paper-notional support scalar to already selected governed Companyfacts+RS paper candidates with signal-day `volume_ratio_20 <= 0.90`.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Low-volume supported |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 7.5427 | +2.3799 | $117,072.92 | $141,251.80 | $+24,178.88 | -0.0091 | 99 | 38 |
| mid_weak | 2.1402 | 5.7975 | +3.6573 | $78,110.11 | $130,865.52 | $+52,755.41 | -0.0205 | 116 | 54 |
| old_thin | 0.5911 | 2.5095 | +1.9184 | $39,667.96 | $82,008.33 | $+42,340.37 | -0.0050 | 121 | 64 |

## Aggregate

- EV delta: `7.9556` (`1.007791`)
- PnL delta: `$119274.66` (`0.507874`)
- target trades: `336`
- max drawdown drift: `-0.005`
- max single positive share: `0.396114`
- positive PnL HHI: `0.25012`

## Low-Volume Audit

```json
{
  "late_strong": {
    "daily_top1_filtered": 127,
    "filtered_candidates": 161,
    "final_closed_pnl": 24178.88,
    "input_candidates": 260,
    "low_volume_notional_scalar": 1.1,
    "low_volume_ratio_20_max": 0.9,
    "low_volume_support_pnl_delta_by_ticker": {
      "AMD": 220.89,
      "APP": -24.78,
      "CRDO": -191.4,
      "GOOG": 249.56,
      "MU": 1219.68,
      "RTX": 19.17
    },
    "low_volume_supported": 38,
    "low_volume_supported_ticker_counts": {
      "AMD": 1,
      "APP": 2,
      "CRDO": 1,
      "GOOG": 5,
      "MU": 25,
      "RTX": 4
    },
    "max_closed_drawdown_seen_usd": 6605.61,
    "missing_trade_filtered": 31,
    "rule_version": "fundamental_growth_rs_low_volume_participation_support_v1",
    "same_ticker_core_overlap_filtered": 3,
    "selected_ticker_counts": {
      "AMD": 4,
      "APP": 5,
      "CRDO": 4,
      "GOOG": 14,
      "MU": 63,
      "RTX": 9
    },
    "selected_trades": 99,
    "selected_unique_tickers": 6,
    "ticker_profit_cap_scaled": 34
  },
  "mid_weak": {
    "daily_top1_filtered": 268,
    "filtered_candidates": 283,
    "final_closed_pnl": 52755.41,
    "input_candidates": 399,
    "low_volume_notional_scalar": 1.1,
    "low_volume_ratio_20_max": 0.9,
    "low_volume_support_pnl_delta_by_ticker": {
      "AMD": 147.74,
      "APP": 838.64,
      "AVGO": 166.84,
      "COIN": 575.3,
      "CRDO": 737.9,
      "MU": 220.24,
      "NFLX": 73.66,
      "PLTR": 419.6
    },
    "low_volume_supported": 54,
    "low_volume_supported_ticker_counts": {
      "AMD": 2,
      "APP": 10,
      "AVGO": 2,
      "COIN": 7,
      "CRDO": 16,
      "MU": 5,
      "NFLX": 2,
      "PLTR": 10
    },
    "max_closed_drawdown_seen_usd": 4353.74,
    "missing_trade_filtered": 11,
    "rule_version": "fundamental_growth_rs_low_volume_participation_support_v1",
    "same_ticker_core_overlap_filtered": 4,
    "selected_ticker_counts": {
      "AMD": 11,
      "APP": 18,
      "AVGO": 3,
      "COIN": 11,
      "CRDO": 30,
      "MU": 15,
      "NFLX": 2,
      "NVDA": 1,
      "PLTR": 25
    },
    "selected_trades": 116,
    "selected_unique_tickers": 9,
    "ticker_profit_cap_scaled": 32
  },
  "old_thin": {
    "both_governor_scalars_applied": 3,
    "daily_top1_filtered": 221,
    "filtered_candidates": 238,
    "final_closed_pnl": 42340.37,
    "global_drawdown_scaled": 19,
    "input_candidates": 359,
    "low_volume_notional_scalar": 1.1,
    "low_volume_ratio_20_max": 0.9,
    "low_volume_support_pnl_delta_by_ticker": {
      "APP": 3082.21,
      "AVGO": -396.27,
      "META": -258.3,
      "NFLX": -2.16,
      "NOW": 65.21,
      "PLTR": 552.34,
      "RTX": 6.61
    },
    "low_volume_supported": 64,
    "low_volume_supported_ticker_counts": {
      "APP": 29,
      "AVGO": 10,
      "META": 3,
      "NFLX": 2,
      "NOW": 1,
      "PLTR": 10,
      "RTX": 9
    },
    "max_closed_drawdown_seen_usd": 12123.41,
    "missing_trade_filtered": 12,
    "rule_version": "fundamental_growth_rs_low_volume_participation_support_v1",
    "same_ticker_core_overlap_filtered": 5,
    "selected_ticker_counts": {
      "APP": 50,
      "AVGO": 13,
      "COIN": 1,
      "ISRG": 2,
      "META": 3,
      "MU": 1,
      "NFLX": 7,
      "NOW": 3,
      "PLTR": 27,
      "RTX": 14
    },
    "selected_trades": 121,
    "selected_unique_tickers": 10,
    "ticker_profit_cap_scaled": 53
  }
}
```

## Current Accepted Baseline Comparison

```json
{
  "aggregate_delta_after_vs_accepted_governed_operating_profit_quality": {
    "expected_value_score_delta_sum": 0.6247,
    "max_drawdown_pct_delta_max": -0.0002,
    "total_pnl_delta_sum": 8005.73
  },
  "available": true,
  "by_window_delta_after_vs_accepted_governed_operating_profit_quality": {
    "late_strong": {
      "expected_value_score_delta": 0.1634,
      "max_drawdown_pct_delta": -0.0005,
      "total_pnl_delta": 1493.1
    },
    "mid_weak": {
      "expected_value_score_delta": 0.2811,
      "max_drawdown_pct_delta": -0.0001,
      "total_pnl_delta": 3463.01
    },
    "old_thin": {
      "expected_value_score_delta": 0.1802,
      "max_drawdown_pct_delta": -0.0002,
      "total_pnl_delta": 3049.62
    }
  },
  "reference_decision": "accepted_candidate_operating_profit_quality_closed_ledger_governor",
  "reference_experiment_id": "exp-20260528-008"
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "core_gate4_passed": true,
  "current_accepted_stack_comparison_passed": true,
  "current_accepted_stack_failed_checks": [],
  "max_drawdown_worse": -0.005,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": true,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.396114,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.25012,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 336,
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

Accepted into the shared default-off paper adapter only. The daily production path surfaces the same low-volume participation metadata/scalar through `fundamental_growth_rs_paper_sleeve.py`; live/default orders, core universe, core ranking, sizing, exits, LLM/news, and trade-enabled behavior remain unchanged.

No JavaScript was used.
