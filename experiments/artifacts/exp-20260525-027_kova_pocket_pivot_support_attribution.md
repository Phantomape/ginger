# exp-20260525-027 Kova Pocket-Pivot Support Attribution

Decision: `rejected_kova_pocket_pivot_support_gate`.

Single variable: require `pre_signal_pocket_pivot_seen_10d` inside the already accepted exp-022 QQQ-confirmed volatility-contraction paper sleeve.

## Three-Window Result

| Window | Before EV | Pocket EV | dEV | Exp-022 dEV | EV vs 022 | Pocket PnL d | Exp-022 PnL d | PnL vs 022 | Trades | Pocket candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1628 | +0.0000 | +0.0024 | -0.0024 | $-6.37 | $+322.04 | $-328.41 | 1 | 2 |
| mid_weak | 2.1402 | 2.8016 | +0.6614 | +1.0172 | -0.3558 | $+10,266.17 | $+15,584.73 | $-5,318.56 | 44 | 154 |
| old_thin | 0.5911 | 0.6986 | +0.1075 | +0.2297 | -0.1222 | $+3,725.77 | $+7,502.79 | $-3,777.02 | 10 | 17 |

## Aggregate

- pocket EV delta vs core: `0.7689` (`0.097402`)
- exp-022 EV delta vs core: `1.2493`
- EV delta vs exp-022: `-0.4804` (`-0.384535`)
- pocket PnL delta vs core: `$13985.57` (`0.059551`)
- PnL delta vs exp-022: `$-9423.99`
- target trades: `55` across `3` windows
- max single positive share: `0.258056`
- positive PnL HHI: `0.126356`

## Exp-022 Selected-Trade Bucket Attribution

```json
{
  "supported": {
    "avg_pnl": 246.04,
    "negative_pnl": -3442.92,
    "positive_pnl": 14022.62,
    "tickers": [
      "AAPL",
      "APP",
      "AVGO",
      "BKNG",
      "CRDO",
      "CVX",
      "DIS",
      "GE",
      "GOOG",
      "GS",
      "JPM",
      "MA",
      "META",
      "MSFT",
      "NFLX",
      "NVDA",
      "NVO",
      "RTX",
      "SNOW",
      "TSLA",
      "UNH",
      "V"
    ],
    "total_pnl": 10579.7,
    "trade_count": 43,
    "win_rate": 0.651163
  },
  "unsupported_available": {
    "avg_pnl": 458.21,
    "negative_pnl": -3408.5,
    "positive_pnl": 16238.36,
    "tickers": [
      "AMD",
      "AMZN",
      "APP",
      "AVGO",
      "CAT",
      "COIN",
      "CRDO",
      "DIS",
      "GOOG",
      "GS",
      "JPM",
      "MSFT",
      "MU",
      "NFLX",
      "NOW",
      "NVDA",
      "PLTR",
      "RTX",
      "UNH"
    ],
    "total_pnl": 12829.86,
    "trade_count": 28,
    "win_rate": 0.642857
  }
}
```

## Pocket Gate Audit

```json
{
  "late_strong": {
    "candidate_dates_after_pocket_gate": 2,
    "candidate_dates_after_qqq_gate": 5,
    "candidate_dates_before_gate": 15,
    "pocket_supported_after_qqq_candidates": 2,
    "qqq_candidate_bucket_attribution": {
      "supported": {
        "avg_fwd_10d": -0.000446,
        "candidate_count": 2,
        "candidate_date_count": 2,
        "fwd_10d_sample": 1,
        "fwd_10d_win_rate": 0.0,
        "ticker_count": 2
      },
      "unsupported_available": {
        "avg_fwd_10d": 0.036695,
        "candidate_count": 4,
        "candidate_date_count": 3,
        "fwd_10d_sample": 3,
        "fwd_10d_win_rate": 0.666667,
        "ticker_count": 4
      },
      "unsupported_unavailable": {
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
    "rejected_no_pocket_support_after_qqq": 4,
    "rejected_pocket_context_unavailable_after_qqq": 0,
    "rejected_qqq_not_leading_spy": 16
  },
  "mid_weak": {
    "candidate_dates_after_pocket_gate": 44,
    "candidate_dates_after_qqq_gate": 51,
    "candidate_dates_before_gate": 58,
    "pocket_supported_after_qqq_candidates": 154,
    "qqq_candidate_bucket_attribution": {
      "supported": {
        "avg_fwd_10d": 0.026234,
        "candidate_count": 154,
        "candidate_date_count": 44,
        "fwd_10d_sample": 154,
        "fwd_10d_win_rate": 0.688312,
        "ticker_count": 33
      },
      "unsupported_available": {
        "avg_fwd_10d": 0.051445,
        "candidate_count": 53,
        "candidate_date_count": 34,
        "fwd_10d_sample": 53,
        "fwd_10d_win_rate": 0.754717,
        "ticker_count": 26
      },
      "unsupported_unavailable": {
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
    "rejected_no_pocket_support_after_qqq": 53,
    "rejected_pocket_context_unavailable_after_qqq": 0,
    "rejected_qqq_not_leading_spy": 8
  },
  "old_thin": {
    "candidate_dates_after_pocket_gate": 10,
    "candidate_dates_after_qqq_gate": 17,
    "candidate_dates_before_gate": 22,
    "pocket_supported_after_qqq_candidates": 17,
    "qqq_candidate_bucket_attribution": {
      "supported": {
        "avg_fwd_10d": 0.033156,
        "candidate_count": 17,
        "candidate_date_count": 10,
        "fwd_10d_sample": 17,
        "fwd_10d_win_rate": 0.823529,
        "ticker_count": 11
      },
      "unsupported_available": {
        "avg_fwd_10d": 0.029795,
        "candidate_count": 24,
        "candidate_date_count": 11,
        "fwd_10d_sample": 24,
        "fwd_10d_win_rate": 0.625,
        "ticker_count": 15
      },
      "unsupported_unavailable": {
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
    "rejected_no_pocket_support_after_qqq": 24,
    "rejected_pocket_context_unavailable_after_qqq": 0,
    "rejected_qqq_not_leading_spy": 5
  }
}
```

## Gate 4

```json
{
  "accepted_for_attribution_only": false,
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "beats_exp022_ev_by_min_5pct": false,
  "comparison_artifact": "data/experiments/exp-20260525-022/volatility_contraction_qqq_confirmed_sleeve.json",
  "exp022_min_ev_lift": 0.05,
  "failed_reasons": [
    "did_not_pass_vs_core",
    "did_not_beat_exp022_aggregate_ev_by_5pct",
    "window_ev_regression_vs_exp022",
    "window_pnl_regression_vs_exp022"
  ],
  "max_drawdown_worse": 0.0,
  "max_drawdown_worse_guardrail": 0.005,
  "no_ev_or_pnl_window_regression_vs_exp022": false,
  "passed": false,
  "passed_vs_core": false,
  "pocket_variant_trade_count_min": 20,
  "pocket_variant_window_count_min": 3,
  "promotion_grade_vs_exp022": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.258056,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.126356,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 55,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 2,
  "windows_ev_regressed": 0,
  "windows_ev_regressed_vs_exp022": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_pnl_regressed": 1,
  "windows_pnl_regressed_vs_exp022": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ]
}
```

## Production Impact

Default-off paper metadata and attribution only. No live orders, watchlists, core entries, ranking, sizing, exits, LLM/news, or backtester adapter behavior changed.

No JavaScript was used.
