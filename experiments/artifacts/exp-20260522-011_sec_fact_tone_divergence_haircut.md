# exp-20260522-011 SEC Fact-Tone Divergence Haircut

Decision: `rejected_sec_fact_tone_divergence_haircut`.

## Hypothesis

SEC financial-report T+1 rows whose positive and negative factual language conflict may be lower-replacement-value continuation candidates. A bounded paper-notional haircut can reduce exposure without changing eligibility, exits, live orders, or LLM authority.

## Best Variant

- best_variant: `fact_tone_divergence_scalar_0_00`
- target_scalar: `0.0`
- EV delta: `0.549796`
- PnL delta: `$5375.21`
- gate_passed: `False`

## Three-Window Deltas

| Window | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|
| late_strong | +0.5336 | $+4,371.37 | -0.0015 |
| mid_weak | -0.0592 | $-1,069.94 | +0.0005 |
| old_thin | +0.0754 | $+2,073.78 | -0.0010 |

## Gate

```json
{
  "aggregate_delta": {
    "expected_value_score_sum_delta": 0.549796,
    "expected_value_score_sum_delta_pct": 0.046343,
    "max_drawdown_pct_max_delta": -0.001047,
    "max_drawdown_pct_max_delta_pct": -0.008951,
    "min_survival_rate_delta": 0.0,
    "min_survival_rate_delta_pct": 0.0,
    "sleeve_closed_trade_count_sum_delta": 0.0,
    "sleeve_closed_trade_count_sum_delta_pct": 0.0,
    "sleeve_total_pnl_sum_delta": 5375.21,
    "sleeve_total_pnl_sum_delta_pct": 0.061544,
    "total_pnl_sum_delta": 5375.21,
    "total_pnl_sum_delta_pct": 0.016578,
    "trade_count_sum_delta": 0.0,
    "trade_count_sum_delta_pct": 0.0
  },
  "by_window": {
    "late_strong": {
      "expected_value_score": 0.53365,
      "max_drawdown_pct": -0.001479,
      "sharpe_daily": 0.250937,
      "total_pnl": 4371.37
    },
    "mid_weak": {
      "expected_value_score": -0.059209,
      "max_drawdown_pct": 0.000477,
      "sharpe_daily": -0.017179,
      "total_pnl": -1069.94
    },
    "old_thin": {
      "expected_value_score": 0.075355,
      "max_drawdown_pct": -0.001047,
      "sharpe_daily": 0.035561,
      "total_pnl": 2073.78
    }
  },
  "checks": {
    "adjusted_trade_sample": true,
    "adjusted_window_coverage": true,
    "drawdown_worse_guard": true,
    "ev_improved_window_coverage": true,
    "hhi_concentration_cap": true,
    "no_ev_regressed_windows": false,
    "positive_aggregate_ev": true,
    "positive_aggregate_pnl": true,
    "single_ticker_positive_share_cap": true,
    "top5_contribution_cap": false
  },
  "metrics": {
    "adjusted_trade_count": 10,
    "adjusted_windows": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ],
    "max_drawdown_worse": 0.000477,
    "max_single_positive_pnl_share": 0.4805,
    "pnl_hhi_concentration": 0.3273,
    "pnl_top_5_contribution_pct": 0.9787,
    "windows_ev_improved": 2,
    "windows_ev_regressed": 1
  },
  "passed": false,
  "rules": {
    "metric_gate": "aggregate EV/PnL positive, at least two EV-improved windows, zero EV-regressed windows, and max drawdown worsening <= 0.5pp",
    "sample_guard": {
      "min_adjusted_trades": 6,
      "min_adjusted_windows": 2
    },
    "tail_guard": {
      "max_hhi_concentration": 0.35,
      "max_single_ticker_positive_share": 0.5,
      "max_top5_contribution": 0.6
    }
  }
}
```

## Target Coverage

```json
{
  "bucket_counts": {
    "fact_improvement_positive_tone": 7,
    "fact_negative_or_guidance_cut": 10,
    "fact_tone_divergence": 18,
    "unclassified_insufficient_evidence": 73
  },
  "by_window": {
    "late_strong": {
      "bucket_counts": {
        "fact_improvement_positive_tone": 2,
        "fact_negative_or_guidance_cut": 1,
        "fact_tone_divergence": 7,
        "unclassified_insufficient_evidence": 29
      },
      "candidate_rows": 39,
      "target_accessions": [
        "0000093410-26-000019",
        "0001193125-26-047622",
        "0001561550-25-000310",
        "0001628280-25-048860",
        "0001628280-26-003837",
        "0001628280-26-005005",
        "0001628280-26-013205"
      ],
      "target_rows": 7,
      "target_tickers": [
        "CRDO",
        "CVX",
        "DDOG",
        "LITE",
        "TRIP",
        "TSLA"
      ]
    },
    "mid_weak": {
      "bucket_counts": {
        "fact_improvement_positive_tone": 3,
        "fact_negative_or_guidance_cut": 4,
        "fact_tone_divergence": 5,
        "unclassified_insufficient_evidence": 17
      },
      "candidate_rows": 29,
      "target_accessions": [
        "0000063908-25-000021",
        "0000093410-25-000058",
        "0001561550-25-000118",
        "0001628280-25-035738",
        "0001730168-25-000094"
      ],
      "target_rows": 5,
      "target_tickers": [
        "AVGO",
        "CVX",
        "DDOG",
        "MCD",
        "TSLA"
      ]
    },
    "old_thin": {
      "bucket_counts": {
        "fact_improvement_positive_tone": 2,
        "fact_negative_or_guidance_cut": 5,
        "fact_tone_divergence": 6,
        "unclassified_insufficient_evidence": 27
      },
      "candidate_rows": 40,
      "target_accessions": [
        "0000063908-24-000152",
        "0000093410-25-000004",
        "0000101829-25-000002",
        "0001075531-24-000047",
        "0001628280-25-002993",
        "0001730168-24-000125"
      ],
      "target_rows": 6,
      "target_tickers": [
        "AVGO",
        "BKNG",
        "CVX",
        "MCD",
        "RTX",
        "TSLA"
      ]
    }
  },
  "target_bucket": "fact_tone_divergence",
  "target_candidate_rows": 18,
  "target_share": 0.16666666666666666,
  "target_tickers": {
    "AVGO": 2,
    "BKNG": 1,
    "CRDO": 1,
    "CVX": 3,
    "DDOG": 2,
    "LITE": 2,
    "MCD": 2,
    "RTX": 1,
    "TRIP": 1,
    "TSLA": 3
  },
  "total_candidate_rows": 108
}
```

No JavaScript was used.

## Production impact

No shared policy or live adapter changed. This is an offline default-off paper-sleeve scout; promotion would require shared policy wiring and parity tests.
