# exp-20260602-022 Post-Earnings Drift Score Monotonicity

Decision: `rejected_no_monotonic_post_earnings_drift_score_ladder`.

Single causal variable: observed-only monotonicity of `post_earnings_positive_surprise_drift_score` from exp-20260602-006.

## Canonical Three-Window Before/After

- Before aggregate EV/PnL: `7.8941` / `$234,850.99`
- After aggregate EV/PnL: `7.8941` / `$234,850.99`
- Delta: `0.0` EV / `$0.00` PnL because no strategy behavior changed.

## Score Ladder

| Scope | Bucket | Count | Score range | Avg PnL | Total PnL | Avg return | Win rate |
|---|---|---:|---:|---:|---:|---:|---:|
| aggregate | top | 20 | 0.5823-3.4778 | $-270.14 | $-5,402.73 | -2.7014% | 45.00% |
| aggregate | middle | 20 | 0.3525-0.5676 | $383.58 | $7,671.58 | 3.8358% | 60.00% |
| aggregate | bottom | 20 | 0.1666-0.3430 | $153.70 | $3,074.03 | 1.5370% | 50.00% |
| late_strong | top | 6 | 0.5991-3.4778 | $-881.81 | $-5,290.85 | -8.8181% | 16.67% |
| late_strong | middle | 6 | 0.3525-0.5664 | $526.83 | $3,160.96 | 5.2683% | 50.00% |
| late_strong | bottom | 6 | 0.1939-0.3084 | $-115.75 | $-694.51 | -1.1575% | 33.33% |
| mid_weak | top | 7 | 0.5591-0.9772 | $388.09 | $2,716.63 | 3.8809% | 71.43% |
| mid_weak | middle | 7 | 0.3321-0.5586 | $502.96 | $3,520.73 | 5.0296% | 85.71% |
| mid_weak | bottom | 7 | 0.1666-0.3216 | $-6.23 | $-43.63 | -0.0623% | 42.86% |
| old_thin | top | 7 | 0.7271-1.8205 | $-569.76 | $-3,988.32 | -5.6976% | 42.86% |
| old_thin | middle | 7 | 0.3993-0.6660 | $503.78 | $3,526.43 | 5.0378% | 57.14% |
| old_thin | bottom | 7 | 0.2985-0.3785 | $347.92 | $2,435.44 | 3.4792% | 57.14% |

## Gate 4

```json
{
  "canonical_before_after_aggregate": {
    "after": {
      "expected_value_score": 7.8941,
      "max_drawdown_pct": 0.1119,
      "min_survival_rate": 0.7925,
      "total_pnl": 234850.99,
      "trade_count": 61
    },
    "before": {
      "expected_value_score": 7.8941,
      "max_drawdown_pct": 0.1119,
      "min_survival_rate": 0.7925,
      "total_pnl": 234850.99,
      "trade_count": 61
    },
    "delta": {
      "expected_value_score": 0.0,
      "max_drawdown_pct": 0.0,
      "min_survival_rate": 0.0,
      "total_pnl": 0.0,
      "trade_count": 0
    }
  },
  "canonical_before_after_windows": {
    "late_strong": {
      "after": {
        "expected_value_score": 5.1628,
        "max_drawdown_pct": 0.0665,
        "sharpe_daily": 4.41,
        "signals_generated": 51,
        "signals_survived": 41,
        "strategy_total_return_pct": 1.1707,
        "survival_rate": 0.8039,
        "total_pnl": 117072.92,
        "trade_count": 18,
        "win_rate": 0.8333
      },
      "artifact": "data/experiments/exp-20260602-003/late_strong_after.json",
      "before": {
        "expected_value_score": 5.1628,
        "max_drawdown_pct": 0.0665,
        "sharpe_daily": 4.41,
        "signals_generated": 51,
        "signals_survived": 41,
        "strategy_total_return_pct": 1.1707,
        "survival_rate": 0.8039,
        "total_pnl": 117072.92,
        "trade_count": 18,
        "win_rate": 0.8333
      },
      "delta": {
        "expected_value_score": 0.0,
        "max_drawdown_pct": 0.0,
        "sharpe_daily": 0.0,
        "signals_generated": 0,
        "signals_survived": 0,
        "strategy_total_return_pct": 0.0,
        "survival_rate": 0.0,
        "total_pnl": 0.0,
        "trade_count": 0,
        "win_rate": 0.0
      },
      "end": "2026-04-21",
      "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
      "start": "2025-10-23"
    },
    "mid_weak": {
      "after": {
        "expected_value_score": 2.1402,
        "max_drawdown_pct": 0.1119,
        "sharpe_daily": 2.74,
        "signals_generated": 53,
        "signals_survived": 42,
        "strategy_total_return_pct": 0.7811,
        "survival_rate": 0.7925,
        "total_pnl": 78110.11,
        "trade_count": 21,
        "win_rate": 0.5238
      },
      "artifact": "data/experiments/exp-20260602-003/mid_weak_after.json",
      "before": {
        "expected_value_score": 2.1402,
        "max_drawdown_pct": 0.1119,
        "sharpe_daily": 2.74,
        "signals_generated": 53,
        "signals_survived": 42,
        "strategy_total_return_pct": 0.7811,
        "survival_rate": 0.7925,
        "total_pnl": 78110.11,
        "trade_count": 21,
        "win_rate": 0.5238
      },
      "delta": {
        "expected_value_score": 0.0,
        "max_drawdown_pct": 0.0,
        "sharpe_daily": 0.0,
        "signals_generated": 0,
        "signals_survived": 0,
        "strategy_total_return_pct": 0.0,
        "survival_rate": 0.0,
        "total_pnl": 0.0,
        "trade_count": 0,
        "win_rate": 0.0
      },
      "end": "2025-10-22",
      "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
      "start": "2025-04-23"
    },
    "old_thin": {
      "after": {
        "expected_value_score": 0.5911,
        "max_drawdown_pct": 0.1001,
        "sharpe_daily": 1.49,
        "signals_generated": 60,
        "signals_survived": 52,
        "strategy_total_return_pct": 0.3967,
        "survival_rate": 0.8667,
        "total_pnl": 39667.96,
        "trade_count": 22,
        "win_rate": 0.4091
      },
      "artifact": "data/experiments/exp-20260602-003/old_thin_after.json",
      "before": {
        "expected_value_score": 0.5911,
        "max_drawdown_pct": 0.1001,
        "sharpe_daily": 1.49,
        "signals_generated": 60,
        "signals_survived": 52,
        "strategy_total_return_pct": 0.3967,
        "survival_rate": 0.8667,
        "total_pnl": 39667.96,
        "trade_count": 22,
        "win_rate": 0.4091
      },
      "delta": {
        "expected_value_score": 0.0,
        "max_drawdown_pct": 0.0,
        "sharpe_daily": 0.0,
        "signals_generated": 0,
        "signals_survived": 0,
        "strategy_total_return_pct": 0.0,
        "survival_rate": 0.0,
        "total_pnl": 0.0,
        "trade_count": 0,
        "win_rate": 0.0
      },
      "end": "2025-04-22",
      "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
      "start": "2024-10-02"
    }
  },
  "decision": "rejected_no_monotonic_post_earnings_drift_score_ladder",
  "failed_reasons": [
    "aggregate_score_terciles_not_monotonic",
    "fewer_than_two_windows_monotonic"
  ],
  "observed_monotonicity": {
    "aggregate_fully_monotonic": false,
    "monotonic_window_count": 0,
    "monotonic_windows": [],
    "top_bucket_concentration_passed": true,
    "window_requirement_passed": false
  },
  "passed": false
}
```

## Interpretation

The existing post-earnings positive-surprise drift score is not a durable ranking field on the frozen canonical windows: the top score bucket does not outperform lower buckets.

No JavaScript was used.
