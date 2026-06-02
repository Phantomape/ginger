# exp-20260602-005: VBB Rank-2 Strong-RS Candidate Extension

- Decision: `rejected_vbb_rank2_strong_rs_candidate_extension`
- Changed variable: `vbb_rank2_strong_rs_high_close_candidate_extension_v1`
- Before: `exp-20260526-014` accepted VBB after metrics
- JavaScript: not used

## Gate 4 Summary

| Metric | Before | After | Delta |
|---|---:|---:|---:|
| Aggregate EV | 8.6065 | 8.5483 | -0.0582 |
| Aggregate PnL | $248,076.49 | $246,526.85 | $-1,549.64 |
| Max drawdown delta | | | +0.0016 |

## Three Windows

| Window | EV before | EV after | EV delta | PnL delta | Rank2 trades | Rank2 candidate days |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 5.5780 | 5.5413 | -0.0367 | $-263.71 | 2 | 2 |
| mid_weak | 2.2780 | 2.3072 | +0.0292 | $461.38 | 3 | 3 |
| old_thin | 0.7505 | 0.6998 | -0.0507 | $-1,747.31 | 3 | 3 |

## Rank2 Diagnostics

```json
{
  "late_strong": {
    "filtered_rank2_candidate_count": 0,
    "filtered_rank2_reasons": {},
    "full_vbb_candidate_count": 30,
    "full_vbb_candidate_days": 11,
    "rank2_trade_pnl": -263.71,
    "reference_top1_trade_count": 8,
    "reject_counts": {
      "breadth_fraction_below_min": 3,
      "no_rank2_candidate": 3,
      "rank2_close_location_below_min": 1,
      "rank2_rs_below_min": 2
    },
    "selected_rank2_candidate_count": 2,
    "selected_rank2_candidate_days": 2,
    "selected_rank2_trade_count": 2,
    "selected_rank2_unique_tickers": 2,
    "source_rank2_candidate_days": 8,
    "thresholds": {
      "min_rank2_breadth_fraction": 0.25,
      "min_rank2_close_location": 0.7,
      "min_rank2_rs_vs_spy": 0.02,
      "min_rank2_volume_ratio_20": 1.5
    }
  },
  "mid_weak": {
    "filtered_rank2_candidate_count": 0,
    "filtered_rank2_reasons": {},
    "full_vbb_candidate_count": 78,
    "full_vbb_candidate_days": 18,
    "rank2_trade_pnl": 461.38,
    "reference_top1_trade_count": 17,
    "reject_counts": {
      "breadth_fraction_below_min": 7,
      "no_rank2_candidate": 3,
      "rank2_close_location_below_min": 1,
      "rank2_rs_below_min": 4
    },
    "selected_rank2_candidate_count": 3,
    "selected_rank2_candidate_days": 3,
    "selected_rank2_trade_count": 3,
    "selected_rank2_unique_tickers": 3,
    "source_rank2_candidate_days": 15,
    "thresholds": {
      "min_rank2_breadth_fraction": 0.25,
      "min_rank2_close_location": 0.7,
      "min_rank2_rs_vs_spy": 0.02,
      "min_rank2_volume_ratio_20": 1.5
    }
  },
  "old_thin": {
    "filtered_rank2_candidate_count": 0,
    "filtered_rank2_reasons": {},
    "full_vbb_candidate_count": 86,
    "full_vbb_candidate_days": 22,
    "rank2_trade_pnl": -1747.31,
    "reference_top1_trade_count": 22,
    "reject_counts": {
      "breadth_fraction_below_min": 5,
      "no_rank2_candidate": 2,
      "rank2_close_location_below_min": 6,
      "rank2_rs_below_min": 6
    },
    "selected_rank2_candidate_count": 3,
    "selected_rank2_candidate_days": 3,
    "selected_rank2_trade_count": 3,
    "selected_rank2_unique_tickers": 3,
    "source_rank2_candidate_days": 20,
    "thresholds": {
      "min_rank2_breadth_fraction": 0.25,
      "min_rank2_close_location": 0.7,
      "min_rank2_rs_vs_spy": 0.02,
      "min_rank2_volume_ratio_20": 1.5
    }
  }
}
```

## Gate 4

```json
{
  "acceptance": {
    "max_drawdown_worse": 0.005,
    "max_positive_hhi": 0.3,
    "max_single_positive_share": 0.4,
    "min_target_trades": 20,
    "min_target_windows": 3
  },
  "checks": {
    "aggregate_ev_delta_positive": false,
    "aggregate_pnl_delta_positive": false,
    "all_windows_ev_improved": false,
    "concentration_passed": false,
    "drawdown_guard_passed": true,
    "no_window_pnl_regression": false,
    "survival_guard_passed": true,
    "target_trade_count_passed": false,
    "target_window_count_passed": true
  },
  "failed_gates": [
    "aggregate_ev_delta_positive",
    "aggregate_pnl_delta_positive",
    "all_windows_ev_improved",
    "no_window_pnl_regression",
    "target_trade_count_passed",
    "concentration_passed"
  ],
  "min_survival_rate": 0.7925,
  "passed": false,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ]
}
```

## Production Parity

No shared VBB adapter or production order path changed. This is incremental replay versus the accepted default-off VBB top-1 adapter; any positive result would still require shared-adapter implementation and parity tests before promotion.

## Interpretation

The rank-2 strong-RS VBB extension did not clear Gate 4. Do not promote it or retry nearby rank-2 RS/high-close/breadth thresholds on these frozen windows without forward evidence or a materially different source-quality field.
