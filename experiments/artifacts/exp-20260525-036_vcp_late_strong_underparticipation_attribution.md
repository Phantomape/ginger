# exp-20260525-036 VCP Late-Strong Underparticipation Attribution

Decision: `observed_only_vcp_late_strong_underparticipation_attribution`.

## Diagnosis

late_strong weakness is mainly underparticipation/rank-depth scarcity, not an obvious failed QQQ gate. Only one late_strong signal date had a rank-2 QQQ-confirmed alternative; adding it explains the small top-2 late_strong uplift.

## Top-N Diagnostic

| Variant | late_strong EV d | late_strong PnL d | Aggregate EV d | Aggregate PnL d | Trades |
|---|---:|---:|---:|---:|---:|
| top1_exp022_replay | +0.0024 | $+322.04 | +1.2493 | $+23,409.56 | 71 |
| top2_candidate_depth | +0.1020 | $+1,237.73 | +2.0730 | $+34,795.92 | 117 |
| top3_candidate_depth | +0.1020 | $+1,237.73 | +1.8444 | $+30,647.40 | 150 |

## Late-Strong Funnel

```json
{
  "qqq_confirmed_candidate_days": 5,
  "qqq_confirmed_candidates": 6,
  "qqq_rejected_candidate_days": 10,
  "qqq_rejected_candidates": 16,
  "raw_vcp_candidate_days": 15,
  "raw_vcp_candidates": 22
}
```

## Late-Strong Rank-2 Replacement

```json
[
  {
    "rank1_fwd_10d": -0.051337,
    "rank1_pnl": -481.78,
    "rank1_ticker": "CAT",
    "rank2_fwd_10d": 0.087103,
    "rank2_minus_rank1_pnl": 1397.47,
    "rank2_pnl": 915.69,
    "rank2_ticker": "MU",
    "signal_date": "2025-12-10"
  }
]
```

## Late-Strong QQQ-Rejected Counterfactual

```json
{
  "qqq_rejected_daily_top1_counterfactual": {
    "avg_pnl": -493.05,
    "negative_pnl": -4930.47,
    "positive_pnl": 0.0,
    "signal_dates": [
      "2025-12-11",
      "2025-12-12",
      "2025-12-15",
      "2025-12-16",
      "2025-12-23",
      "2026-01-02",
      "2026-01-05",
      "2026-01-06",
      "2026-01-07",
      "2026-01-12"
    ],
    "ticker_count": 8,
    "tickers": [
      "CAT",
      "GE",
      "GOOG",
      "ISRG",
      "JPM",
      "LLY",
      "NVDA",
      "TSLA"
    ],
    "total_pnl": -4930.47,
    "trade_count": 10,
    "win_rate": 0.0
  },
  "raw_vcp_daily_top1_no_qqq_gate_counterfactual": {
    "avg_pnl": -354.49,
    "negative_pnl": -5418.62,
    "positive_pnl": 810.19,
    "signal_dates": [
      "2025-12-10",
      "2025-12-11",
      "2025-12-12",
      "2025-12-15",
      "2025-12-16",
      "2025-12-23",
      "2026-01-02",
      "2026-01-05",
      "2026-01-06",
      "2026-01-07",
      "2026-01-12",
      "2026-01-13",
      "2026-03-25"
    ],
    "ticker_count": 9,
    "tickers": [
      "AMD",
      "CAT",
      "GE",
      "GOOG",
      "ISRG",
      "JPM",
      "LLY",
      "NVDA",
      "TSLA"
    ],
    "total_pnl": -4608.43,
    "trade_count": 13,
    "win_rate": 0.076923
  }
}
```

## Gate

```json
{
  "note": "This run explains late_strong underparticipation only. Any top-N or rank-depth promotion requires a separate shared adapter/parity experiment and forward evidence.",
  "observed_only": true,
  "passed": false,
  "promotion_grade": false,
  "strategy_behavior_changed": false
}
```

No JavaScript was used.
