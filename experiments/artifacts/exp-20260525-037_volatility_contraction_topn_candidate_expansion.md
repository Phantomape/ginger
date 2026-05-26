# exp-20260525-037 VCP Top-N Candidate Expansion

Decision: `promising_replay_only_vcp_topn_candidate_expansion`.

Single variable: starting from exp-20260525-022, expand the QQQ-confirmed VCP same-day paper queue from top-1 to top-2/top-3 eligible candidates while keeping $10k notional, next-open entry, and 10-trading-day hold fixed.

## Variant Summary

| Variant | Gate | EV d vs core | PnL d vs core | EV d vs exp022 | PnL d vs exp022 | Trades | Windows | Max +share | HHI |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| top1_replay_sanity | fail | +1.2493 | $+23,409.56 | +0.0000 | $+0.00 | 71 | 3 | 0.179784 | 0.103924 |
| top2_equal_notional | PASS | +2.0730 | $+34,795.92 | +0.8237 | $+11,386.36 | 117 | 3 | 0.164729 | 0.097256 |
| top3_equal_notional | fail | +1.8444 | $+30,647.40 | +0.5951 | $+7,237.84 | 150 | 3 | 0.183112 | 0.093566 |

## Best Variant: `top2_equal_notional`

| Window | Variant EV d | Exp022 EV d | dEV vs exp022 | Variant PnL d | Exp022 PnL d | dPnL vs exp022 | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | +0.1020 | +0.0024 | +0.0996 | $+1,237.73 | $+322.04 | $+915.69 | 4 |
| mid_weak | +1.7203 | +1.0172 | +0.7031 | $+25,394.30 | $+15,584.73 | $+9,809.57 | 88 |
| old_thin | +0.2507 | +0.2297 | +0.0210 | $+8,163.89 | $+7,502.79 | $+661.10 | 25 |

## Candidate Rank Audit

```json
{
  "late_strong": {
    "candidate_count": 6,
    "candidate_day_count": 5,
    "dates_with_at_least_2_candidates": 1,
    "dates_with_at_least_3_candidates": 0,
    "max_candidates_on_signal_date": 2,
    "rank_count": {
      "1": 5,
      "2": 1
    }
  },
  "mid_weak": {
    "candidate_count": 207,
    "candidate_day_count": 51,
    "dates_with_at_least_2_candidates": 37,
    "dates_with_at_least_3_candidates": 28,
    "max_candidates_on_signal_date": 15,
    "rank_count": {
      "1": 51,
      "10": 2,
      "11": 2,
      "12": 2,
      "13": 2,
      "14": 1,
      "15": 1,
      "2": 37,
      "3": 28,
      "4": 22,
      "5": 19,
      "6": 16,
      "7": 11,
      "8": 8,
      "9": 5
    }
  },
  "old_thin": {
    "candidate_count": 41,
    "candidate_day_count": 17,
    "dates_with_at_least_2_candidates": 8,
    "dates_with_at_least_3_candidates": 5,
    "max_candidates_on_signal_date": 6,
    "rank_count": {
      "1": 17,
      "2": 8,
      "3": 5,
      "4": 5,
      "5": 4,
      "6": 2
    }
  }
}
```

## Gate 4

```json
{
  "accepted_variants": [
    "top2_equal_notional"
  ],
  "best_variant": "top2_equal_notional",
  "best_variant_gate": {
    "beats_exp022_ev_by_min_5pct": true,
    "failed_reasons": [],
    "max_drawdown_worse": -0.0003,
    "max_drawdown_worse_guardrail": 0.005,
    "no_ev_or_pnl_window_regression_vs_exp022": true,
    "passed": true,
    "passed_vs_core": true,
    "promotion_grade_vs_exp022": true,
    "survival_guard_passed": true,
    "target_concentration": {
      "max_single_positive_pnl_share": 0.164729,
      "max_single_positive_pnl_share_guardrail": 0.4,
      "passed": true,
      "positive_pnl_hhi": 0.097256,
      "positive_pnl_hhi_guardrail": 0.3
    },
    "target_trade_count": 117,
    "target_trade_count_min": 20,
    "target_window_count_min": 3,
    "target_windows": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ]
  },
  "best_variant_source_exp022_comparison": {
    "beats_exp022_ev_by_min_5pct": true,
    "by_window": {
      "late_strong": {
        "ev_delta_vs_exp022": 0.0996,
        "exp022_ev_delta": 0.0024,
        "exp022_pnl_delta": 322.04,
        "pnl_delta_vs_exp022": 915.69,
        "variant_ev_delta": 0.102,
        "variant_pnl_delta": 1237.73
      },
      "mid_weak": {
        "ev_delta_vs_exp022": 0.7031,
        "exp022_ev_delta": 1.0172,
        "exp022_pnl_delta": 15584.73,
        "pnl_delta_vs_exp022": 9809.57,
        "variant_ev_delta": 1.7203,
        "variant_pnl_delta": 25394.3
      },
      "old_thin": {
        "ev_delta_vs_exp022": 0.021,
        "exp022_ev_delta": 0.2297,
        "exp022_pnl_delta": 7502.79,
        "pnl_delta_vs_exp022": 661.1,
        "variant_ev_delta": 0.2507,
        "variant_pnl_delta": 8163.89
      }
    },
    "comparison_artifact": "data/experiments/exp-20260525-022/volatility_contraction_qqq_confirmed_sleeve.json",
    "exp022_min_ev_lift": 0.05,
    "overlay_ev_delta_vs_exp022_sum": 0.8237,
    "overlay_ev_lift_pct_vs_exp022": 0.659329,
    "overlay_pnl_delta_vs_exp022_sum": 11386.36,
    "source": "git_HEAD",
    "source_exp022_overlay_ev_delta_sum": 1.2493,
    "source_exp022_overlay_pnl_delta_sum": 23409.56,
    "variant_overlay_ev_delta_sum": 2.073,
    "variant_overlay_pnl_delta_sum": 34795.92,
    "windows_ev_regressed_vs_exp022": [],
    "windows_pnl_regressed_vs_exp022": []
  },
  "passed": true
}
```

## Production Impact

The top-2 expansion variant beat exp-022 under the replay gate and is promoted into the shared default-off paper adapter with parity tests. It remains observe-only and cannot create live/default orders.

No live/default orders, core entry, ranking, sizing, exits, LLM/news, or core universe behavior changed.

No JavaScript was used.
