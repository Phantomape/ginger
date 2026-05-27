# exp-20260527-015 Kova Fundamental + RS Proxy Shadow Ranking

Decision: `observed_only_no_actionable_kova_fundamental_rs_proxy_split`.

The Kova fundamental+RS proxy score did not clear the observed-only promotion bar. Keep the VCP top-2 rank-notional sleeve unchanged and do not convert the split into a filter or rank rule.

## Source

- Source population: `exp-20260526-007` `rank2_125` selected paper trades.
- Core, VCP definition, QQQ/SPY gate, top-2 selection, rank-notional profile, exits, LLM/news, universe, and live/default orders unchanged.
- Tested field: `kova_fundamental_rs_proxy_score_v1`.

## Coverage

- Closed paper trades: `117`.
- Score available: `117`.
- EPS+revenue pair available: `91`.
- Fundamental pass: `21`.
- RS proxy available: `117`.
- RS leader proxy count: `16`.
- Strong Kova bucket count: `11`.

## Aggregate Buckets

| bucket | trades | total pnl | avg pnl | win rate | avg score | avg RS |
|---|---:|---:|---:|---:|---:|---:|
| fundamental_growth_and_rs_leader_proxy | 11 | 6307.66 | 573.42 | 0.727273 | 0.991384 | 0.982767 |
| fundamental_growth_without_rs_leader_proxy | 10 | 6596.47 | 659.65 | 0.8 | 0.872342 | 0.744684 |
| rs_leader_without_fundamental_growth | 5 | 180.91 | 36.18 | 0.4 | 0.662667 | 0.925333 |
| below_kova_growth_rs_proxy | 91 | 24557.48 | 269.86 | 0.604396 | 0.44477 | 0.647781 |
| unavailable | 0 | 0.0 | None | None | None | None |

## Window Buckets

| window | bucket | trades | total pnl | avg pnl | win rate |
|---|---|---:|---:|---:|---:|
| late_strong | fundamental_growth_and_rs_leader_proxy | 1 | 1144.61 | 1144.61 | 1.0 |
| late_strong | fundamental_growth_without_rs_leader_proxy | 1 | 810.19 | 810.19 | 1.0 |
| late_strong | below_kova_growth_rs_proxy | 2 | -488.15 | -244.07 | 0.0 |
| mid_weak | fundamental_growth_and_rs_leader_proxy | 2 | 375.38 | 187.69 | 0.5 |
| mid_weak | fundamental_growth_without_rs_leader_proxy | 8 | 6296.54 | 787.07 | 0.875 |
| mid_weak | rs_leader_without_fundamental_growth | 5 | 180.91 | 36.18 | 0.4 |
| mid_weak | below_kova_growth_rs_proxy | 73 | 20993.85 | 287.59 | 0.616438 |
| old_thin | fundamental_growth_and_rs_leader_proxy | 8 | 4787.67 | 598.46 | 0.75 |
| old_thin | fundamental_growth_without_rs_leader_proxy | 1 | -510.26 | -510.26 | 0.0 |
| old_thin | below_kova_growth_rs_proxy | 16 | 4051.78 | 253.24 | 0.625 |

## Score-Bonus Shadow

This read-only audit gives the largest existing scalar to the higher Kova score inside same-day top-2 pairs. It is not promoted.

| window | trades | reassigned | source pnl | shadow pnl | delta |
|---|---:|---:|---:|---:|---:|
| late_strong | 4 | 0 | 1466.65 | 1466.65 | 0.0 |
| mid_weak | 88 | 36 | 27846.68 | 28112.79 | 266.11 |
| old_thin | 25 | 10 | 8329.19 | 9165.38 | 836.19 |
| aggregate | 117 | 46 | 37642.52 | 38744.82 | 1102.3 |

- Aggregate shadow PnL delta vs source: `1102.3`.
- Reassigned trades: `46`.

## Gate 4

No strategy promotion was possible in this experiment because this is read-only attribution and shadow ranking only.

```json
{
  "decision_evidence": {
    "coverage": {
      "eps_growth_available_count": 102,
      "fundamental_pair_available_count": 91,
      "fundamental_pass_count": 21,
      "revenue_growth_available_count": 103,
      "rs_available_count": 117,
      "rs_leader_count": 16,
      "score_available_count": 117,
      "strong_bucket_count": 11,
      "trade_count": 117
    },
    "non_strong_avg_pnl": 295.61,
    "shadow_no_window_pnl_regression": true,
    "shadow_pnl_delta_vs_source": 1102.3,
    "shadow_windows_pnl_improved": 2,
    "shadow_windows_pnl_regressed": 0,
    "strong_avg_pnl": 573.42,
    "strong_beats_non_strong_avg_pnl": true,
    "strong_concentration_passed": false,
    "strong_max_single_positive_pnl_share": 0.674743,
    "strong_positive_aggregate": true,
    "strong_positive_pnl_hhi": 0.512841,
    "strong_positive_windows": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ],
    "strong_trade_count_min_20": false
  },
  "passed": false,
  "promotion_grade": false,
  "reason": "Observed-only metadata and frozen-sample shadow ranking. A later closed replacement replay is required before any rule can be kept.",
  "strategy_replacement_tested": false
}
```

## Repro

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260527_015_kova_fundamental_rs_proxy_shadow_ranking.py
```
