# exp-20260525-032 VCP Volume Dry-Up Confirmation

Decision: `observed_only_vcp_volume_dryup_attribution`.

Single variable: require `pre_signal_volume_dryup_ratio_10v50 <= 0.80` inside the already accepted exp-022 QQQ-confirmed VCP paper sleeve.

## Three-Window Result

| Window | Before EV | Dry-up EV | dEV | Exp-022 dEV | EV vs 022 | Dry-up PnL d | Exp-022 PnL d | PnL vs 022 | Trades | Dry-up candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1652 | +0.0024 | +0.0024 | +0.0000 | $+322.04 | $+322.04 | $+0.00 | 3 | 5 |
| mid_weak | 2.1402 | 2.6799 | +0.5397 | +1.0172 | -0.4775 | $+8,904.43 | $+15,584.73 | $-6,680.30 | 39 | 115 |
| old_thin | 0.5911 | 0.6403 | +0.0492 | +0.2297 | -0.1805 | $+1,638.41 | $+7,502.79 | $-5,864.38 | 9 | 15 |

## Aggregate

- dry-up EV delta vs core: `0.5913` (`0.074904`)
- exp-022 EV delta vs core: `1.2493`
- EV delta vs exp-022: `-0.658` (`-0.526695`)
- dry-up PnL delta vs core: `$10864.88` (`0.046263`)
- PnL delta vs exp-022: `$-12544.68`
- target trades: `51` across `3` windows
- max single positive share: `0.207734`
- positive PnL HHI: `0.127689`

## Exp-022 Selected-Trade Volume Attribution

```json
{
  "dryup_not_supported_available": {
    "avg_pnl": 398.37,
    "negative_pnl": -2020.36,
    "positive_pnl": 13573.09,
    "tickers": [
      "AAPL",
      "AMZN",
      "APP",
      "CRDO",
      "CVX",
      "DIS",
      "GE",
      "GOOG",
      "MSFT",
      "NFLX",
      "NVDA",
      "PLTR",
      "RTX",
      "SNOW",
      "TSLA"
    ],
    "total_pnl": 11552.73,
    "trade_count": 29,
    "win_rate": 0.793103
  },
  "dryup_supported": {
    "avg_pnl": 282.31,
    "negative_pnl": -4831.06,
    "positive_pnl": 16687.89,
    "tickers": [
      "AMD",
      "APP",
      "AVGO",
      "BKNG",
      "CAT",
      "COIN",
      "CRDO",
      "DIS",
      "GE",
      "GOOG",
      "GS",
      "JPM",
      "MA",
      "META",
      "MSFT",
      "MU",
      "NFLX",
      "NOW",
      "NVDA",
      "NVO",
      "PLTR",
      "TSLA",
      "UNH",
      "V"
    ],
    "total_pnl": 11856.83,
    "trade_count": 42,
    "win_rate": 0.547619
  }
}
```

## Volume Dry-Up Gate Audit

```json
{
  "late_strong": {
    "candidate_dates_after_dryup_gate": 4,
    "candidate_dates_after_qqq_gate": 5,
    "candidate_dates_before_gate": 15,
    "dryup_supported_after_qqq_candidates": 5,
    "qqq_candidate_volume_dryup_bucket_attribution": {
      "dryup_not_supported_available": {
        "avg_fwd_10d": null,
        "candidate_count": 1,
        "candidate_date_count": 1,
        "fwd_10d_sample": 0,
        "fwd_10d_win_rate": null,
        "ticker_count": 1
      },
      "dryup_supported": {
        "avg_fwd_10d": 0.027409,
        "candidate_count": 5,
        "candidate_date_count": 4,
        "fwd_10d_sample": 4,
        "fwd_10d_win_rate": 0.5,
        "ticker_count": 5
      },
      "dryup_unavailable": {
        "avg_fwd_10d": null,
        "candidate_count": 0,
        "candidate_date_count": 0,
        "fwd_10d_sample": 0,
        "fwd_10d_win_rate": null,
        "ticker_count": 0
      }
    },
    "qqq_confirmed_candidates": 6,
    "raw_volatility_candidates": 22,
    "rejected_missing_market_context": 0,
    "rejected_no_volume_dryup_after_qqq": 1,
    "rejected_qqq_not_leading_spy": 16,
    "rejected_volume_dryup_unavailable_after_qqq": 0
  },
  "mid_weak": {
    "candidate_dates_after_dryup_gate": 39,
    "candidate_dates_after_qqq_gate": 51,
    "candidate_dates_before_gate": 58,
    "dryup_supported_after_qqq_candidates": 115,
    "qqq_candidate_volume_dryup_bucket_attribution": {
      "dryup_not_supported_available": {
        "avg_fwd_10d": 0.024324,
        "candidate_count": 92,
        "candidate_date_count": 41,
        "fwd_10d_sample": 92,
        "fwd_10d_win_rate": 0.663043,
        "ticker_count": 30
      },
      "dryup_supported": {
        "avg_fwd_10d": 0.039381,
        "candidate_count": 115,
        "candidate_date_count": 39,
        "fwd_10d_sample": 115,
        "fwd_10d_win_rate": 0.73913,
        "ticker_count": 31
      },
      "dryup_unavailable": {
        "avg_fwd_10d": null,
        "candidate_count": 0,
        "candidate_date_count": 0,
        "fwd_10d_sample": 0,
        "fwd_10d_win_rate": null,
        "ticker_count": 0
      }
    },
    "qqq_confirmed_candidates": 207,
    "raw_volatility_candidates": 215,
    "rejected_missing_market_context": 0,
    "rejected_no_volume_dryup_after_qqq": 92,
    "rejected_qqq_not_leading_spy": 8,
    "rejected_volume_dryup_unavailable_after_qqq": 0
  },
  "old_thin": {
    "candidate_dates_after_dryup_gate": 9,
    "candidate_dates_after_qqq_gate": 17,
    "candidate_dates_before_gate": 22,
    "dryup_supported_after_qqq_candidates": 15,
    "qqq_candidate_volume_dryup_bucket_attribution": {
      "dryup_not_supported_available": {
        "avg_fwd_10d": 0.045345,
        "candidate_count": 26,
        "candidate_date_count": 15,
        "fwd_10d_sample": 26,
        "fwd_10d_win_rate": 0.846154,
        "ticker_count": 15
      },
      "dryup_supported": {
        "avg_fwd_10d": 0.006651,
        "candidate_count": 15,
        "candidate_date_count": 9,
        "fwd_10d_sample": 15,
        "fwd_10d_win_rate": 0.466667,
        "ticker_count": 9
      },
      "dryup_unavailable": {
        "avg_fwd_10d": null,
        "candidate_count": 0,
        "candidate_date_count": 0,
        "fwd_10d_sample": 0,
        "fwd_10d_win_rate": null,
        "ticker_count": 0
      }
    },
    "qqq_confirmed_candidates": 41,
    "raw_volatility_candidates": 46,
    "rejected_missing_market_context": 0,
    "rejected_no_volume_dryup_after_qqq": 26,
    "rejected_qqq_not_leading_spy": 5,
    "rejected_volume_dryup_unavailable_after_qqq": 0
  }
}
```

## Gate 4

```json
{
  "accepted_for_attribution_only": true,
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "beats_exp022_ev_by_min_5pct": false,
  "comparison_artifact": "data/experiments/exp-20260525-022/volatility_contraction_qqq_confirmed_sleeve.json",
  "exp022_min_ev_lift": 0.05,
  "failed_reasons": [
    "did_not_beat_exp022_aggregate_ev_by_5pct",
    "window_ev_regression_vs_exp022",
    "window_pnl_regression_vs_exp022"
  ],
  "max_drawdown_worse": 0.0002,
  "max_drawdown_worse_guardrail": 0.005,
  "no_ev_or_pnl_window_regression_vs_exp022": false,
  "passed": false,
  "passed_vs_core": true,
  "positive_vs_core": true,
  "promotion_grade_vs_exp022": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.207734,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.127689,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 51,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "volume_dryup_variant_trade_count_min": 20,
  "volume_dryup_variant_window_count_min": 3,
  "windows_ev_improved": 3,
  "windows_ev_regressed": 0,
  "windows_ev_regressed_vs_exp022": [
    "mid_weak",
    "old_thin"
  ],
  "windows_pnl_regressed": 0,
  "windows_pnl_regressed_vs_exp022": [
    "mid_weak",
    "old_thin"
  ]
}
```

## Production Impact

Replay-only/default-off paper attribution only. No live orders, watchlists, shared adapter, core entries, ranking, sizing, exits, LLM/news, or backtester behavior changed.

No JavaScript was used.
