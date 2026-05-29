# exp-20260529-022 Fundamental Growth + RS Low-Dilution Support

Decision: `rejected_fundamental_growth_rs_low_dilution_support`.

Single variable: apply a 1.05x paper-notional support scalar to already selected governed Companyfacts+RS paper candidates whose PIT diluted-share YoY growth is <= 5%.

## Gate Questions

- alpha_hypothesis: candidate_pool / capital allocation alpha: PIT diluted-share YoY growth <= 5% is a free SEC per-share quality field for the accepted Companyfacts+RS paper pool.
- single_causal_variable: `fundamental_growth_rs_low_dilution_notional_support_v1`
- reproducibility: `.venv\Scripts\python.exe -B quant\experiments\exp_20260529_022_fundamental_growth_rs_low_dilution_support.py`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Low-dilution supported |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 7.8657 | +2.7029 | $117,072.92 | $144,593.03 | $+27,520.11 | -0.0104 | 99 | 95 |
| mid_weak | 2.1402 | 6.1733 | +4.0331 | $78,110.11 | $135,383.15 | $+57,273.04 | -0.0206 | 116 | 57 |
| old_thin | 0.5911 | 1.7920 | +1.2009 | $39,667.96 | $70,002.36 | $+30,334.40 | +0.0027 | 121 | 80 |

## Aggregate

- EV delta: `7.9369` (`1.005422`)
- PnL delta: `$115127.55` (`0.490215`)
- target trades: `336`
- low-dilution supported trades: `232`
- low-dilution supported share: `0.690476`
- max drawdown drift: `0.0027`
- max single positive share: `0.312529`
- positive PnL HHI: `0.219944`

## Dilution Audit

```json
{
  "late_strong": {
    "daily_top1_filtered": 127,
    "dilution_bucket_counts": {
      "buyback_or_flat_lte_0pct": 23,
      "low_0_to_5pct": 72,
      "moderate_5_to_15pct": 4
    },
    "dilution_status_counts": {
      "dilution_above_threshold": 4,
      "ok": 95
    },
    "filing_recency_supported": 67,
    "filtered_candidates": 161,
    "final_closed_pnl": 27520.11,
    "input_candidates": 260,
    "low_dilution_notional_scalar": 1.05,
    "low_dilution_support_pnl_delta_by_ticker": {
      "AMD": 421.89,
      "APP": 11.92,
      "GOOG": 146.81,
      "MU": 1246.98,
      "RTX": 8.1
    },
    "low_dilution_supported": 95,
    "low_dilution_supported_ticker_counts": {
      "AMD": 4,
      "APP": 5,
      "GOOG": 14,
      "MU": 63,
      "RTX": 9
    },
    "low_liability_supported": 81,
    "low_volume_supported": 38,
    "max_closed_drawdown_seen_usd": 7228.88,
    "max_diluted_shares_yoy_growth": 0.05,
    "missing_trade_filtered": 31,
    "rule_version": "fundamental_growth_rs_low_dilution_support_v1",
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
    "dilution_bucket_counts": {
      "buyback_or_flat_lte_0pct": 31,
      "high_gt_15pct": 14,
      "low_0_to_5pct": 26,
      "moderate_5_to_15pct": 45
    },
    "dilution_status_counts": {
      "dilution_above_threshold": 59,
      "ok": 57
    },
    "filing_recency_supported": 84,
    "filtered_candidates": 283,
    "final_closed_pnl": 57273.04,
    "input_candidates": 399,
    "low_dilution_notional_scalar": 1.05,
    "low_dilution_support_pnl_delta_by_ticker": {
      "AMD": 266.08,
      "APP": 622.31,
      "COIN": 141.24,
      "MU": 291.72,
      "NFLX": 42.54
    },
    "low_dilution_supported": 57,
    "low_dilution_supported_ticker_counts": {
      "AMD": 11,
      "APP": 18,
      "COIN": 11,
      "MU": 15,
      "NFLX": 2
    },
    "low_liability_supported": 61,
    "low_volume_supported": 54,
    "max_closed_drawdown_seen_usd": 4800.0,
    "max_diluted_shares_yoy_growth": 0.05,
    "missing_trade_filtered": 11,
    "rule_version": "fundamental_growth_rs_low_dilution_support_v1",
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
    "dilution_bucket_counts": {
      "buyback_or_flat_lte_0pct": 74,
      "high_gt_15pct": 13,
      "low_0_to_5pct": 6,
      "moderate_5_to_15pct": 28
    },
    "dilution_status_counts": {
      "dilution_above_threshold": 41,
      "ok": 80
    },
    "filing_recency_supported": 69,
    "filtered_candidates": 238,
    "final_closed_pnl": 30334.4,
    "global_drawdown_scaled": 20,
    "input_candidates": 359,
    "low_dilution_notional_scalar": 1.05,
    "low_dilution_support_pnl_delta_by_ticker": {
      "APP": 1182.13,
      "ISRG": -53.09,
      "META": -149.17,
      "MU": -17.81,
      "NFLX": -47.54,
      "NOW": 6.74,
      "RTX": -2.4
    },
    "low_dilution_supported": 80,
    "low_dilution_supported_ticker_counts": {
      "APP": 50,
      "ISRG": 2,
      "META": 3,
      "MU": 1,
      "NFLX": 7,
      "NOW": 3,
      "RTX": 14
    },
    "low_liability_supported": 33,
    "low_volume_supported": 64,
    "max_closed_drawdown_seen_usd": 12609.96,
    "max_diluted_shares_yoy_growth": 0.05,
    "missing_trade_filtered": 12,
    "rule_version": "fundamental_growth_rs_low_dilution_support_v1",
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
    "ticker_profit_cap_scaled": 55
  }
}
```

## Current Accepted Baseline Comparison

```json
{
  "aggregate_delta_after_vs_accepted_low_liability": {
    "expected_value_score_delta_sum": -0.605,
    "max_drawdown_pct_delta_max": 0.0084,
    "total_pnl_delta_sum": -12016.6
  },
  "available": true,
  "by_window_delta_after_vs_accepted_low_liability": {
    "late_strong": {
      "expected_value_score_delta": 0.1852,
      "max_drawdown_pct_delta": -0.0006,
      "total_pnl_delta": 1835.66
    },
    "mid_weak": {
      "expected_value_score_delta": 0.1022,
      "max_drawdown_pct_delta": 0.0011,
      "total_pnl_delta": 1363.85
    },
    "old_thin": {
      "expected_value_score_delta": -0.8924,
      "max_drawdown_pct_delta": 0.0084,
      "total_pnl_delta": -15216.11
    }
  },
  "reference_decision": "accepted_candidate_fundamental_growth_rs_low_liability_support",
  "reference_experiment_id": "exp-20260528-017"
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "core_gate4_passed": true,
  "current_accepted_stack_comparison_passed": false,
  "current_accepted_stack_failed_checks": [
    "aggregate_ev_not_above_current_accepted_exp017",
    "aggregate_pnl_not_above_current_accepted_exp017",
    "window_ev_regressed_vs_current_accepted_exp017",
    "window_pnl_regressed_vs_current_accepted_exp017"
  ],
  "low_dilution_supported_trade_count": 232,
  "low_dilution_supported_trade_count_min": 30,
  "low_dilution_supported_trade_share": 0.690476,
  "low_dilution_supported_trade_share_max": 0.85,
  "max_drawdown_worse": 0.0027,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.312529,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.219944,
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

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
