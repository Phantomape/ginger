# exp-20260525-030 VCP Event-Context Attribution

Decision: `observed_only_vcp_event_context_attribution`.

Single variable: require `pre_signal_event_snapshot_seen_20d` inside the already accepted exp-022 QQQ-confirmed VCP paper sleeve.

## Three-Window Result

| Window | Before EV | Event EV | dEV | Exp-022 dEV | EV vs 022 | Event PnL d | Exp-022 PnL d | PnL vs 022 | Trades | Event candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.2221 | +0.0593 | +0.0024 | +0.0569 | $+810.19 | $+322.04 | $+488.15 | 1 | 1 |
| mid_weak | 2.1402 | 2.8643 | +0.7241 | +1.0172 | -0.2931 | $+11,674.94 | $+15,584.73 | $-3,909.79 | 41 | 116 |
| old_thin | 0.5911 | 0.6610 | +0.0699 | +0.2297 | -0.1598 | $+2,702.05 | $+7,502.79 | $-4,800.74 | 7 | 7 |

## Aggregate

- event EV delta vs core: `0.8533` (`0.108093`)
- exp-022 EV delta vs core: `1.2493`
- EV delta vs exp-022: `-0.396` (`-0.316978`)
- event PnL delta vs core: `$15187.18` (`0.064667`)
- PnL delta vs exp-022: `$-8222.38`
- target trades: `49` across `3` windows

## Exp-022 Selected-Trade Event Attribution

```json
{
  "event_quiet_20d": {
    "avg_pnl": 387.4,
    "negative_pnl": -3373.94,
    "positive_pnl": 17320.47,
    "tickers": [
      "AAPL",
      "AMZN",
      "APP",
      "CAT",
      "COIN",
      "CRDO",
      "DIS",
      "GOOG",
      "GS",
      "MSFT",
      "MU",
      "NFLX",
      "NVDA",
      "NVO",
      "PLTR",
      "RTX"
    ],
    "total_pnl": 13946.53,
    "trade_count": 36,
    "win_rate": 0.666667
  },
  "event_seen_20d": {
    "avg_pnl": 270.37,
    "negative_pnl": -3477.48,
    "positive_pnl": 12940.51,
    "tickers": [
      "AMD",
      "APP",
      "AVGO",
      "BKNG",
      "CVX",
      "DIS",
      "GE",
      "JPM",
      "MA",
      "META",
      "MSFT",
      "NFLX",
      "NOW",
      "NVDA",
      "SNOW",
      "TSLA",
      "UNH",
      "V"
    ],
    "total_pnl": 9463.03,
    "trade_count": 35,
    "win_rate": 0.628571
  }
}
```

## Event Gate Audit

```json
{
  "late_strong": {
    "candidate_dates_after_event_gate": 1,
    "candidate_dates_after_qqq_gate": 5,
    "candidate_dates_before_gate": 15,
    "event_supported_after_qqq_candidates": 1,
    "qqq_candidate_event_bucket_attribution": {
      "event_quiet_20d": {
        "avg_fwd_10d": 0.011773,
        "candidate_count": 5,
        "candidate_date_count": 4,
        "fwd_10d_sample": 3,
        "fwd_10d_win_rate": 0.333333,
        "ticker_count": 5
      },
      "event_seen_20d": {
        "avg_fwd_10d": 0.074318,
        "candidate_count": 1,
        "candidate_date_count": 1,
        "fwd_10d_sample": 1,
        "fwd_10d_win_rate": 1.0,
        "ticker_count": 1
      }
    },
    "qqq_confirmed_candidates": 6,
    "raw_volatility_candidates": 22,
    "rejected_missing_market_context": 0,
    "rejected_no_event_context_after_qqq": 5,
    "rejected_qqq_not_leading_spy": 16
  },
  "mid_weak": {
    "candidate_dates_after_event_gate": 41,
    "candidate_dates_after_qqq_gate": 51,
    "candidate_dates_before_gate": 58,
    "event_supported_after_qqq_candidates": 116,
    "qqq_candidate_event_bucket_attribution": {
      "event_quiet_20d": {
        "avg_fwd_10d": 0.037226,
        "candidate_count": 91,
        "candidate_date_count": 39,
        "fwd_10d_sample": 91,
        "fwd_10d_win_rate": 0.714286,
        "ticker_count": 23
      },
      "event_seen_20d": {
        "avg_fwd_10d": 0.029129,
        "candidate_count": 116,
        "candidate_date_count": 41,
        "fwd_10d_sample": 116,
        "fwd_10d_win_rate": 0.698276,
        "ticker_count": 27
      }
    },
    "qqq_confirmed_candidates": 207,
    "raw_volatility_candidates": 215,
    "rejected_missing_market_context": 0,
    "rejected_no_event_context_after_qqq": 91,
    "rejected_qqq_not_leading_spy": 8
  },
  "old_thin": {
    "candidate_dates_after_event_gate": 7,
    "candidate_dates_after_qqq_gate": 17,
    "candidate_dates_before_gate": 22,
    "event_supported_after_qqq_candidates": 7,
    "qqq_candidate_event_bucket_attribution": {
      "event_quiet_20d": {
        "avg_fwd_10d": 0.028704,
        "candidate_count": 34,
        "candidate_date_count": 13,
        "fwd_10d_sample": 34,
        "fwd_10d_win_rate": 0.705882,
        "ticker_count": 16
      },
      "event_seen_20d": {
        "avg_fwd_10d": 0.04326,
        "candidate_count": 7,
        "candidate_date_count": 7,
        "fwd_10d_sample": 7,
        "fwd_10d_win_rate": 0.714286,
        "ticker_count": 3
      }
    },
    "qqq_confirmed_candidates": 41,
    "raw_volatility_candidates": 46,
    "rejected_missing_market_context": 0,
    "rejected_no_event_context_after_qqq": 34,
    "rejected_qqq_not_leading_spy": 5
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
  "event_variant_trade_count_min": 20,
  "event_variant_window_count_min": 3,
  "exp022_min_ev_lift": 0.05,
  "failed_reasons": [
    "did_not_beat_exp022_aggregate_ev_by_5pct",
    "window_ev_regression_vs_exp022",
    "window_pnl_regression_vs_exp022"
  ],
  "max_drawdown_worse": 0.0,
  "max_drawdown_worse_guardrail": 0.005,
  "no_ev_or_pnl_window_regression_vs_exp022": false,
  "passed": false,
  "passed_vs_core": true,
  "promotion_grade_vs_exp022": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.208545,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.125428,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 49,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
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

No JavaScript was used.
