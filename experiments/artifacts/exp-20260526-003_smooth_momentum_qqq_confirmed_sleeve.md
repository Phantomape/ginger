# exp-20260526-003 Smooth Momentum QQQ-Confirmed Sleeve

Decision: `rejected_smooth_momentum_qqq_confirmed_sleeve`.

Single variable: keep exp-20260526-002 smooth-path candidate definition fixed, but admit paper candidates only when QQQ's 20-day return is above SPY's 20-day return.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | QQQ-confirmed | Raw smooth |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.7964 | -0.3664 | $117,072.92 | $114,201.48 | $-2,871.44 | +0.0018 | 40 | 110 | 242 |
| mid_weak | 2.1402 | 2.5459 | +0.4057 | $78,110.11 | $86,010.36 | $+7,900.25 | -0.0033 | 76 | 440 | 513 |
| old_thin | 0.5911 | 0.8429 | +0.2518 | $39,667.96 | $46,830.33 | $+7,162.37 | +0.0289 | 64 | 232 | 364 |

## Aggregate

- EV delta: `0.2911` (`0.036876`)
- PnL delta: `$12191.18` (`0.05191`)
- target trades: `180` across `3` windows
- max single positive share: `0.248183`
- positive PnL HHI: `0.129039`

## Market Gate Audit

```json
{
  "late_strong": {
    "candidate_days_after_confirmation": 44,
    "market_rule": "QQQ 20d close-to-close return > SPY 20d close-to-close return",
    "missing_market_context": 0,
    "qqq_confirmed_candidates": 110,
    "qqq_not_stronger_than_spy_rejected": 132,
    "raw_smooth_momentum_candidates": 242
  },
  "mid_weak": {
    "candidate_days_after_confirmation": 83,
    "market_rule": "QQQ 20d close-to-close return > SPY 20d close-to-close return",
    "missing_market_context": 0,
    "qqq_confirmed_candidates": 440,
    "qqq_not_stronger_than_spy_rejected": 73,
    "raw_smooth_momentum_candidates": 513
  },
  "old_thin": {
    "candidate_days_after_confirmation": 64,
    "market_rule": "QQQ 20d close-to-close return > SPY 20d close-to-close return",
    "missing_market_context": 0,
    "qqq_confirmed_candidates": 232,
    "qqq_not_stronger_than_spy_rejected": 132,
    "raw_smooth_momentum_candidates": 364
  }
}
```

## Comparison To exp-20260526-002

```json
{
  "by_window": {
    "late_strong": {
      "ev_delta_vs_exp002": 0.6149,
      "exp002_ev_delta": -0.9813,
      "exp002_pnl_delta": -10944.08,
      "pnl_delta_vs_exp002": 8072.64,
      "variant_ev_delta": -0.3664,
      "variant_pnl_delta": -2871.44
    },
    "mid_weak": {
      "ev_delta_vs_exp002": -0.5714,
      "exp002_ev_delta": 0.9771,
      "exp002_pnl_delta": 18398.73,
      "pnl_delta_vs_exp002": -10498.48,
      "variant_ev_delta": 0.4057,
      "variant_pnl_delta": 7900.25
    },
    "old_thin": {
      "ev_delta_vs_exp002": -0.0331,
      "exp002_ev_delta": 0.2849,
      "exp002_pnl_delta": 8200.09,
      "pnl_delta_vs_exp002": -1037.72,
      "variant_ev_delta": 0.2518,
      "variant_pnl_delta": 7162.37
    }
  },
  "comparison_artifact": "data/experiments/exp-20260526-002/smooth_momentum_path_sleeve.json",
  "overlay_ev_delta_vs_exp002_sum": 0.0104,
  "overlay_pnl_delta_vs_exp002_sum": -3463.56,
  "source": "git_HEAD",
  "source_exp002_overlay_ev_delta_sum": 0.2807,
  "source_exp002_overlay_pnl_delta_sum": 15654.74,
  "variant_overlay_ev_delta_sum": 0.2911,
  "variant_overlay_pnl_delta_sum": 12191.18,
  "windows_ev_regressed_vs_exp002": [
    "mid_weak",
    "old_thin"
  ],
  "windows_pnl_regressed_vs_exp002": [
    "mid_weak",
    "old_thin"
  ]
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0289,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.248183,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.129039,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 180,
  "target_trade_count_min": 20,
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

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
