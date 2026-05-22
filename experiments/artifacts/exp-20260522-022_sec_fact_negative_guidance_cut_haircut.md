# exp-20260522-022 SEC Fact-Negative / Guidance-Cut Haircut

Decision: `rejected_sec_fact_negative_guidance_cut_haircut`.

## Hypothesis

SEC financial-report T+1 rows with factual negatives or guidance-cut evidence may be lower-quality continuation candidates. A bounded paper-notional haircut tests whether the existing fact-tone bucket improves replacement value without changing eligibility, exits, live orders, or LLM authority.

## Trial Accounting

- trial_family: `sec_fact_tone_gap_semantic_allocation`
- changed_variable: `sec_fact_negative_guidance_cut_notional_scalar`
- prior_trial_count: `2`
- multiple_testing_risk_bucket: `moderate`
- new_evidence_type: `production_visible_fact_tone_gap_bucket_now_backtestable`

## Best Variant

- best_variant: `fact_negative_guidance_cut_scalar_0_75`
- target_scalar: `0.75`
- EV delta: `-0.071872`
- PnL delta: `$-1022.21`
- gate_passed: `False`

## Three-Window Deltas

| Window | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|
| late_strong | -0.0119 | $-105.54 | +0.0000 |
| mid_weak | -0.0623 | $-986.87 | +0.0003 |
| old_thin | +0.0024 | $+70.20 | -0.0011 |

## Gate

```json
{
  "aggregate_delta": {
    "expected_value_score_sum_delta": -0.071872,
    "expected_value_score_sum_delta_pct": -0.006058,
    "max_drawdown_pct_max_delta": -0.001115,
    "max_drawdown_pct_max_delta_pct": -0.009532,
    "min_survival_rate_delta": 0.0,
    "min_survival_rate_delta_pct": 0.0,
    "sleeve_closed_trade_count_sum_delta": 0.0,
    "sleeve_closed_trade_count_sum_delta_pct": 0.0,
    "sleeve_total_pnl_sum_delta": -999.34,
    "sleeve_total_pnl_sum_delta_pct": -0.011442,
    "total_pnl_sum_delta": -1022.21,
    "total_pnl_sum_delta_pct": -0.003153,
    "trade_count_sum_delta": 0.0,
    "trade_count_sum_delta_pct": 0.0
  },
  "by_window": {
    "late_strong": {
      "expected_value_score": -0.011893,
      "max_drawdown_pct": 4.8e-05,
      "sharpe_daily": -0.005501,
      "total_pnl": -105.54
    },
    "mid_weak": {
      "expected_value_score": -0.06234,
      "max_drawdown_pct": 0.000349,
      "sharpe_daily": -0.022831,
      "total_pnl": -986.87
    },
    "old_thin": {
      "expected_value_score": 0.002361,
      "max_drawdown_pct": -0.001115,
      "sharpe_daily": 0.001004,
      "total_pnl": 70.2
    }
  },
  "checks": {
    "adjusted_trade_sample": true,
    "adjusted_window_coverage": true,
    "drawdown_worse_guard": true,
    "ev_improved_window_coverage": false,
    "hhi_concentration_cap": false,
    "no_ev_regressed_windows": false,
    "positive_aggregate_ev": false,
    "positive_aggregate_pnl": false,
    "single_ticker_positive_share_cap": false,
    "top5_contribution_cap": false
  },
  "metrics": {
    "adjusted_trade_count": 8,
    "adjusted_windows": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ],
    "max_drawdown_worse": 0.000349,
    "max_single_positive_pnl_share": 1.0,
    "pnl_hhi_concentration": 1.0,
    "pnl_top_5_contribution_pct": 1.0,
    "windows_ev_improved": 1,
    "windows_ev_regressed": 2
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
        "0001104659-25-116130"
      ],
      "target_rows": 1,
      "target_tickers": [
        "DE"
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
        "0000018230-25-000013",
        "0001035267-25-000206",
        "0001628280-25-028827",
        "0001807794-25-000018"
      ],
      "target_rows": 4,
      "target_tickers": [
        "CAT",
        "CRDO",
        "ISRG"
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
        "0000019617-24-000555",
        "0000731766-25-000022",
        "0001193125-25-006554",
        "0001558370-24-015876",
        "0001558370-25-000892"
      ],
      "target_rows": 5,
      "target_tickers": [
        "DE",
        "GS",
        "JPM",
        "UNH"
      ]
    }
  },
  "target_bucket": "fact_negative_or_guidance_cut",
  "target_candidate_rows": 10,
  "target_share": 0.09259259259259259,
  "target_tickers": {
    "CAT": 1,
    "CRDO": 2,
    "DE": 3,
    "GS": 1,
    "ISRG": 1,
    "JPM": 1,
    "UNH": 1
  },
  "total_candidate_rows": 108
}
```

## Production Impact

No shared policy, production adapter, live/default order path, or LLM boundary changed. This is an offline default-off paper-sleeve scout.

No JavaScript was used.
