# exp-20260529-003 Fundamental Growth + RS Low-Capex Intensity

Decision: `rejected_fundamental_growth_rs_low_capex_intensity_support`.

Single variable: apply a 1.05x paper-notional support scalar to already selected governed Companyfacts+RS paper candidates whose latest PIT matching-duration capex/revenue ratio is <= 8%.

## Gate Questions

- alpha_hypothesis: candidate_pool / capital allocation alpha: PIT capex/revenue <= 8% is a free SEC capital-intensity quality field for the accepted Companyfacts+RS paper pool.
- single_causal_variable: `fundamental_growth_rs_low_capex_intensity_notional_scalar_v1`
- reproducibility: `.venv\Scripts\python.exe -B quant\experiments\exp_20260529_003_fundamental_growth_rs_low_capex_intensity_support.py`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Low-capex supported |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 7.6460 | +2.4832 | $117,072.92 | $142,647.78 | $+25,574.86 | -0.0097 | 99 | 22 |
| mid_weak | 2.1402 | 6.2146 | +4.0744 | $78,110.11 | $135,692.64 | $+57,582.53 | -0.0210 | 116 | 77 |
| old_thin | 0.5911 | 1.8556 | +1.2645 | $39,667.96 | $71,372.65 | $+31,704.69 | +0.0017 | 121 | 115 |

## Aggregate

- EV delta: `7.8221` (`0.990879`)
- PnL delta: `$114862.08` (`0.489085`)
- target trades: `336`
- low-capex supported trades: `214`
- max drawdown drift: `0.0017`
- max single positive share: `0.313671`
- positive PnL HHI: `0.218442`

## Capex-Intensity Audit

```json
{
  "late_strong": {
    "capex_intensity_bucket_counts": {
      "heavy_gt_15pct": 77,
      "low_lte_8pct": 22
    },
    "capex_intensity_status_counts": {
      "capex_intensity_above_threshold": 77,
      "ok": 22
    },
    "daily_top1_filtered": 127,
    "filing_recency_supported": 67,
    "filtered_candidates": 161,
    "final_closed_pnl": 25574.86,
    "input_candidates": 260,
    "low_capex_intensity_supported": 22,
    "low_capex_notional_scalar": 1.05,
    "low_capex_support_pnl_delta_by_ticker": {
      "AMD": 421.89,
      "APP": 11.92,
      "CRDO": -551.48,
      "RTX": 8.1
    },
    "low_capex_supported_ticker_counts": {
      "AMD": 4,
      "APP": 5,
      "CRDO": 4,
      "RTX": 9
    },
    "low_liability_supported": 81,
    "low_volume_supported": 38,
    "max_capex_revenue_ratio": 0.08,
    "max_closed_drawdown_seen_usd": 7196.35,
    "missing_trade_filtered": 31,
    "rule_version": "fundamental_growth_rs_low_capex_intensity_support_v1",
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
    "capex_intensity_bucket_counts": {
      "heavy_gt_15pct": 15,
      "low_lte_8pct": 77,
      "missing_capex": 1,
      "moderate_8_to_15pct": 23
    },
    "capex_intensity_status_counts": {
      "capex_intensity_above_threshold": 38,
      "missing_capex": 1,
      "ok": 77
    },
    "daily_top1_filtered": 268,
    "filing_recency_supported": 84,
    "filtered_candidates": 283,
    "final_closed_pnl": 57582.53,
    "input_candidates": 399,
    "low_capex_intensity_supported": 77,
    "low_capex_notional_scalar": 1.05,
    "low_capex_support_pnl_delta_by_ticker": {
      "AMD": 266.08,
      "APP": 622.31,
      "AVGO": 126.27,
      "COIN": 141.24,
      "CRDO": -13.24,
      "NFLX": 42.54,
      "PLTR": 488.11
    },
    "low_capex_supported_ticker_counts": {
      "AMD": 11,
      "APP": 18,
      "AVGO": 3,
      "COIN": 11,
      "CRDO": 7,
      "NFLX": 2,
      "PLTR": 25
    },
    "low_liability_supported": 61,
    "low_volume_supported": 54,
    "max_capex_revenue_ratio": 0.08,
    "max_closed_drawdown_seen_usd": 4800.0,
    "missing_trade_filtered": 11,
    "rule_version": "fundamental_growth_rs_low_capex_intensity_support_v1",
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
    "capex_intensity_bucket_counts": {
      "heavy_gt_15pct": 4,
      "low_lte_8pct": 115,
      "missing_capex": 2
    },
    "capex_intensity_status_counts": {
      "capex_intensity_above_threshold": 4,
      "missing_capex": 2,
      "ok": 115
    },
    "daily_top1_filtered": 221,
    "filing_recency_supported": 69,
    "filtered_candidates": 238,
    "final_closed_pnl": 31704.69,
    "global_drawdown_scaled": 22,
    "input_candidates": 359,
    "low_capex_intensity_supported": 115,
    "low_capex_notional_scalar": 1.05,
    "low_capex_support_pnl_delta_by_ticker": {
      "APP": 1182.13,
      "AVGO": -254.66,
      "COIN": 156.46,
      "NFLX": -19.05,
      "NOW": 6.74,
      "PLTR": 650.12,
      "RTX": -2.4
    },
    "low_capex_supported_ticker_counts": {
      "APP": 50,
      "AVGO": 13,
      "COIN": 1,
      "NFLX": 7,
      "NOW": 3,
      "PLTR": 27,
      "RTX": 14
    },
    "low_liability_supported": 33,
    "low_volume_supported": 64,
    "max_capex_revenue_ratio": 0.08,
    "max_closed_drawdown_seen_usd": 12089.84,
    "missing_trade_filtered": 12,
    "rule_version": "fundamental_growth_rs_low_capex_intensity_support_v1",
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
    "expected_value_score_delta_sum": -0.7198,
    "max_drawdown_pct_delta_max": 0.0074,
    "total_pnl_delta_sum": -12282.07
  },
  "available": true,
  "by_window_delta_after_vs_accepted_low_liability": {
    "late_strong": {
      "expected_value_score_delta": -0.0345,
      "max_drawdown_pct_delta": 0.0001,
      "total_pnl_delta": -109.59
    },
    "mid_weak": {
      "expected_value_score_delta": 0.1435,
      "max_drawdown_pct_delta": 0.0007,
      "total_pnl_delta": 1673.34
    },
    "old_thin": {
      "expected_value_score_delta": -0.8288,
      "max_drawdown_pct_delta": 0.0074,
      "total_pnl_delta": -13845.82
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
  "low_capex_supported_trade_count": 214,
  "low_capex_supported_trade_count_min": 30,
  "max_drawdown_worse": 0.0017,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.313671,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.218442,
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
