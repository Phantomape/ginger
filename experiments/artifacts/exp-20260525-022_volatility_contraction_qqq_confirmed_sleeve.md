# exp-20260525-022 QQQ-Confirmed Volatility-Contraction Sleeve

Decision: `promising_replay_only_volatility_contraction_qqq_confirmed_sleeve`.

Single variable: keep the exp-020 volatility-contraction top-1 paper sleeve, but require QQQ 20d return > SPY 20d return on the signal date.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | QQQ-gated candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1652 | +0.0024 | $117,072.92 | $117,394.96 | $+322.04 | +0.0002 | 3 | 6 |
| mid_weak | 2.1402 | 3.1574 | +1.0172 | $78,110.11 | $93,694.84 | $+15,584.73 | -0.0097 | 51 | 207 |
| old_thin | 0.5911 | 0.8208 | +0.2297 | $39,667.96 | $47,170.75 | $+7,502.79 | -0.0047 | 17 | 41 |

## Aggregate

- EV delta: `1.2493` (`0.158257`)
- PnL delta: `$23409.56` (`0.099678`)
- target trades: `71` across `3` windows
- max single positive share: `0.179784`
- positive PnL HHI: `0.103924`

## Exp-020 Discriminator Precheck

```json
{
  "available": true,
  "interpretation": "In the rejected source sleeve, QQQ-leading-SPY isolated the late_strong failure without changing volatility-compression or breakout thresholds.",
  "qqq_gt_spy20_bucket_summary": {
    "False": {
      "pnl_by_window": {
        "late_strong": -4930.47,
        "mid_weak": 1294.2,
        "old_thin": -112.96
      },
      "total_pnl": -3749.23,
      "trade_count": 22,
      "win_rate": 0.227273
    },
    "True": {
      "pnl_by_window": {
        "late_strong": 322.04,
        "mid_weak": 15584.73,
        "old_thin": 7502.79
      },
      "total_pnl": 23409.56,
      "trade_count": 71,
      "win_rate": 0.647887
    }
  },
  "source_decision": "rejected_volatility_contraction_top1_fixed_notional_sleeve",
  "source_experiment_id": "exp-20260525-020",
  "source_rejection_reason": "window_ev_regression; window_pnl_regression; drawdown_drift_too_high"
}
```

## Market Gate Audit

```json
{
  "late_strong": {
    "candidate_dates_after_gate": 5,
    "candidate_dates_before_gate": 15,
    "qqq_confirmed_candidates": 6,
    "raw_volatility_candidates": 22,
    "rejected_missing_market_context": 0,
    "rejected_qqq_not_leading_spy": 16
  },
  "mid_weak": {
    "candidate_dates_after_gate": 51,
    "candidate_dates_before_gate": 58,
    "qqq_confirmed_candidates": 207,
    "raw_volatility_candidates": 215,
    "rejected_missing_market_context": 0,
    "rejected_qqq_not_leading_spy": 8
  },
  "old_thin": {
    "candidate_dates_after_gate": 17,
    "candidate_dates_before_gate": 22,
    "qqq_confirmed_candidates": 41,
    "raw_volatility_candidates": 46,
    "rejected_missing_market_context": 0,
    "rejected_qqq_not_leading_spy": 5
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0002,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": true,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.179784,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.103924,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 71,
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
