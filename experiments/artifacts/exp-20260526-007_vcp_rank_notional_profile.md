# exp-20260526-007 VCP Top-2 Rank-Notional Profile

Decision: `accepted_shared_paper_adapter_vcp_rank_notional_profile`.

Single variable: starting from exp-20260525-037 top-2 equal notional, test rank-1/rank-2 paper-notional profiles while keeping candidate selection and execution fixed.

## Profile Summary

| Variant | Profile | Gate | EV d vs core | PnL d vs core | EV d vs exp037 | PnL d vs exp037 | DD worse vs exp037 | Trades | Max +share | HHI |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| top2_equal_notional_sanity | `[1.0, 1.0]` | fail | +2.0730 | $+34,795.92 | +0.0000 | $+0.00 | +0.0000 | 117 | 0.164729 | 0.097256 |
| rank2_075 | `[1.0, 0.75]` | fail | +1.8659 | $+31,949.34 | -0.2071 | $-2,846.58 | +0.0009 | 117 | 0.167879 | 0.09732 |
| rank2_125 | `[1.0, 1.25]` | PASS | +2.2913 | $+37,642.52 | +0.2183 | $+2,846.60 | -0.0001 | 117 | 0.161821 | 0.09754 |
| rank1_090_rank2_110 | `[0.9, 1.1]` | fail | +2.0140 | $+33,593.61 | -0.0590 | $-1,202.31 | +0.0005 | 117 | 0.162123 | 0.097485 |

## Best Variant: `rank2_125`

| Window | Variant EV d | Exp037 EV d | dEV vs exp037 | Variant PnL d | Exp037 PnL d | dPnL vs exp037 | DD worse vs exp037 |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | +0.1359 | +0.1020 | +0.0339 | $+1,466.65 | $+1,237.73 | $+228.92 | -0.0001 |
| mid_weak | +1.8969 | +1.7203 | +0.1766 | $+27,846.68 | $+25,394.30 | $+2,452.38 | -0.0009 |
| old_thin | +0.2585 | +0.2507 | +0.0078 | $+8,329.19 | $+8,163.89 | $+165.30 | -0.0001 |

## Candidate Rank Audit

```json
{
  "late_strong": {
    "candidate_count": 6,
    "candidate_day_count": 5,
    "dates_with_at_least_2_candidates": 1,
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
    "rank2_125"
  ],
  "best_variant": "rank2_125",
  "best_variant_gate": {
    "aggregate_ev_delta_vs_core": 2.2913,
    "aggregate_pnl_delta_vs_core": 37642.52,
    "beats_exp037_ev_by_min_5pct": true,
    "failed_reasons": [],
    "max_drawdown_worse_vs_exp037": -0.0001,
    "max_drawdown_worse_vs_exp037_guardrail": 0.005,
    "no_ev_or_pnl_window_regression_vs_exp037": true,
    "passed": true,
    "target_concentration": {
      "max_single_positive_pnl_share": 0.161821,
      "max_single_positive_pnl_share_guardrail": 0.4,
      "passed": true,
      "positive_pnl_hhi": 0.09754,
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
  "best_variant_profile": [
    1.0,
    1.25
  ],
  "best_variant_source_exp037_comparison": {
    "beats_exp037_ev_by_min_5pct": true,
    "by_window": {
      "late_strong": {
        "drawdown_worse_vs_exp037": -0.0001,
        "ev_delta_vs_exp037": 0.0339,
        "exp037_drawdown_delta": -0.0003,
        "exp037_ev_delta": 0.102,
        "exp037_pnl_delta": 1237.73,
        "pnl_delta_vs_exp037": 228.92,
        "variant_drawdown_delta": -0.0004,
        "variant_ev_delta": 0.1359,
        "variant_pnl_delta": 1466.65
      },
      "mid_weak": {
        "drawdown_worse_vs_exp037": -0.0009,
        "ev_delta_vs_exp037": 0.1766,
        "exp037_drawdown_delta": -0.0136,
        "exp037_ev_delta": 1.7203,
        "exp037_pnl_delta": 25394.3,
        "pnl_delta_vs_exp037": 2452.38,
        "variant_drawdown_delta": -0.0145,
        "variant_ev_delta": 1.8969,
        "variant_pnl_delta": 27846.68
      },
      "old_thin": {
        "drawdown_worse_vs_exp037": -0.0001,
        "ev_delta_vs_exp037": 0.0078,
        "exp037_drawdown_delta": -0.0051,
        "exp037_ev_delta": 0.2507,
        "exp037_pnl_delta": 8163.89,
        "pnl_delta_vs_exp037": 165.3,
        "variant_drawdown_delta": -0.0052,
        "variant_ev_delta": 0.2585,
        "variant_pnl_delta": 8329.19
      }
    },
    "comparison_artifact": "data/experiments/exp-20260525-037/volatility_contraction_topn_candidate_expansion.json",
    "ev_delta_vs_exp037_sum": 0.2183,
    "ev_lift_pct_vs_exp037": 0.105306,
    "exp037_min_ev_lift": 0.05,
    "max_drawdown_worse_vs_exp037": -0.0001,
    "max_drawdown_worse_vs_exp037_guardrail": 0.005,
    "pnl_delta_vs_exp037_sum": 2846.6,
    "source": "git_HEAD",
    "source_exp037_ev_delta_sum": 2.073,
    "source_exp037_pnl_delta_sum": 34795.92,
    "variant_ev_delta_sum": 2.2913,
    "variant_pnl_delta_sum": 37642.52,
    "windows_ev_regressed_vs_exp037": [],
    "windows_pnl_regressed_vs_exp037": []
  },
  "passed": true
}
```

## Production Impact

At least one rank-notional profile beat exp037 under the replay gate. Promote only the accepted default-off paper adapter profile with parity tests.

No live/default orders, core entry, ranking, sizing, exits, LLM/news, or core universe behavior changed.

No JavaScript was used.
