# exp-20260523-002 SEC Unclassified Evidence Haircut

Decision: `rejected_sec_unclassified_evidence_haircut`.

## Hypothesis

SEC financial-report T+1 rows whose fact/tone evidence remains unclassified may be lower-quality continuation candidates than rows with explicit improving facts. A bounded paper-notional haircut tests disclosure-quality risk without changing queue eligibility, exits, live orders, or LLM authority.

## Trial Accounting

- trial_family: `sec_fact_tone_gap_semantic_allocation`
- changed_variable: `sec_unclassified_evidence_notional_scalar`
- prior_trial_count: `4`
- multiple_testing_risk_bucket: `moderate`
- new_evidence_type: `previously_untested_high_coverage_fact_tone_bucket`

## Best Variant

- best_variant: `unclassified_evidence_scalar_0_75`
- target_scalar: `0.75`
- EV delta: `-0.858596`
- PnL delta: `$-20907.63`
- gate_passed: `False`

## Three-Window Deltas

| Window | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|
| late_strong | -0.1381 | $-2,899.79 | +0.0005 |
| mid_weak | -0.4351 | $-6,883.69 | +0.0020 |
| old_thin | -0.2853 | $-11,124.15 | -0.0056 |

## Gate

```json
{
  "aggregate_delta": {
    "expected_value_score_sum_delta": -0.858596,
    "expected_value_score_sum_delta_pct": -0.072373,
    "max_drawdown_pct_max_delta": -0.005612,
    "max_drawdown_pct_max_delta_pct": -0.047978,
    "min_survival_rate_delta": 0.0,
    "min_survival_rate_delta_pct": 0.0,
    "sleeve_closed_trade_count_sum_delta": 0.0,
    "sleeve_closed_trade_count_sum_delta_pct": 0.0,
    "sleeve_total_pnl_sum_delta": -20666.92,
    "sleeve_total_pnl_sum_delta_pct": -0.23663,
    "total_pnl_sum_delta": -20907.63,
    "total_pnl_sum_delta_pct": -0.064483,
    "trade_count_sum_delta": 0.0,
    "trade_count_sum_delta_pct": 0.0
  },
  "by_window": {
    "late_strong": {
      "expected_value_score": -0.138142,
      "max_drawdown_pct": 0.000482,
      "sharpe_daily": -0.00527,
      "total_pnl": -2899.79
    },
    "mid_weak": {
      "expected_value_score": -0.435121,
      "max_drawdown_pct": 0.001982,
      "sharpe_daily": -0.168507,
      "total_pnl": -6883.69
    },
    "old_thin": {
      "expected_value_score": -0.285333,
      "max_drawdown_pct": -0.005612,
      "sharpe_daily": -0.06129,
      "total_pnl": -11124.15
    }
  },
  "checks": {
    "adjusted_trade_sample": true,
    "adjusted_window_coverage": true,
    "drawdown_worse_guard": true,
    "ev_improved_window_coverage": false,
    "hhi_concentration_cap": true,
    "no_ev_regressed_windows": false,
    "positive_aggregate_ev": false,
    "positive_aggregate_pnl": false,
    "single_ticker_positive_share_cap": true,
    "top5_contribution_cap": false
  },
  "metrics": {
    "adjusted_trade_count": 31,
    "adjusted_windows": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ],
    "max_drawdown_worse": 0.001982,
    "max_single_positive_pnl_share": 0.3823,
    "pnl_hhi_concentration": 0.2312,
    "pnl_top_5_contribution_pct": 0.9063,
    "windows_ev_improved": 0,
    "windows_ev_regressed": 3
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
        "0000002488-26-000021",
        "0000018230-25-000048",
        "0000018230-26-000003",
        "0000034088-25-000059",
        "0000034088-26-000033",
        "0000050863-25-000169",
        "0000059478-25-000251",
        "0000059478-25-000254",
        "0000059478-26-000008",
        "0000063908-26-000035",
        "0000320193-25-000079",
        "0000320193-26-000005",
        "0000723125-25-000046",
        "0000886982-25-001411",
        "0001075531-25-000050",
        "0001075531-25-000051",
        "0001075531-26-000008",
        "0001075531-26-000009",
        "0001141391-26-000003",
        "0001403161-25-000077",
        "0001403161-26-000044",
        "0001403161-26-000045",
        "0001628280-25-045968",
        "0001628280-25-048859",
        "0001628280-25-049073",
        "0001628280-26-005129",
        "0001628280-26-006516",
        "0001628280-26-014017",
        "0001628280-26-024990"
      ],
      "target_rows": 29,
      "target_tickers": [
        "AAPL",
        "AMD",
        "BE",
        "BKNG",
        "CAT",
        "CRDO",
        "GS",
        "INTC",
        "JPM",
        "LITE",
        "LLY",
        "MA",
        "MCD",
        "MU",
        "TSLA",
        "V",
        "XOM"
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
        "0000002488-25-000106",
        "0000002488-25-000108",
        "0000034088-25-000022",
        "0000040545-25-000131",
        "0000040545-25-000132",
        "0000059478-25-000202",
        "0000059478-25-000204",
        "0000731766-25-000236",
        "0001035267-25-000192",
        "0001321655-25-000066",
        "0001321655-25-000106",
        "0001628280-25-018851",
        "0001628280-25-018911",
        "0001628280-25-033813",
        "0001628280-25-035806",
        "0001628280-25-043530",
        "0001807794-25-000021"
      ],
      "target_rows": 17,
      "target_tickers": [
        "AMD",
        "CRDO",
        "GE",
        "ISRG",
        "LLY",
        "PLTR",
        "TSLA",
        "UNH",
        "XOM"
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
        "0000034088-25-000006",
        "0000059478-25-000005",
        "0000059478-25-000067",
        "0000063908-25-000012",
        "0000320193-25-000008",
        "0000723125-24-000047",
        "0000731766-24-000323",
        "0000886982-24-000025",
        "0001045810-25-000021",
        "0001045810-25-000023",
        "0001075531-24-000048",
        "0001075531-25-000009",
        "0001075531-25-000010",
        "0001141391-25-000003",
        "0001321655-24-000209",
        "0001373715-25-000007",
        "0001403161-24-000058",
        "0001403161-25-000016",
        "0001403161-25-000017",
        "0001561550-24-000175",
        "0001628280-24-041816",
        "0001628280-24-043432",
        "0001628280-24-049786",
        "0001628280-25-011738",
        "0001679788-24-000186",
        "0001679788-24-000187",
        "0001730168-24-000139"
      ],
      "target_rows": 27,
      "target_tickers": [
        "AAPL",
        "AVGO",
        "BKNG",
        "COIN",
        "CRDO",
        "DDOG",
        "GS",
        "LLY",
        "MA",
        "MCD",
        "MU",
        "NOW",
        "NVDA",
        "PLTR",
        "TSLA",
        "UNH",
        "V",
        "XOM"
      ]
    }
  },
  "target_bucket": "unclassified_insufficient_evidence",
  "target_candidate_rows": 73,
  "target_share": 0.6759259259259259,
  "target_tickers": {
    "AAPL": 3,
    "AMD": 3,
    "AVGO": 1,
    "BE": 1,
    "BKNG": 7,
    "CAT": 2,
    "COIN": 2,
    "CRDO": 5,
    "DDOG": 1,
    "GE": 2,
    "GS": 2,
    "INTC": 1,
    "ISRG": 1,
    "JPM": 2,
    "LITE": 2,
    "LLY": 7,
    "MA": 2,
    "MCD": 2,
    "MU": 2,
    "NOW": 1,
    "NVDA": 2,
    "PLTR": 3,
    "TSLA": 7,
    "UNH": 2,
    "V": 6,
    "XOM": 4
  },
  "total_candidate_rows": 108
}
```

## Production Impact

No shared policy, production adapter, live/default order path, or LLM boundary changed. This is an offline default-off paper-sleeve scout.

No JavaScript was used.
