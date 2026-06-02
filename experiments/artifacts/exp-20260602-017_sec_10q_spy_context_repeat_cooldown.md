# exp-20260602-017 SEC 10-Q SPY Context Repeat Cooldown

Decision: `rejected_sec_10q_spy_context_repeat_cooldown`.

## Hypothesis

SEC 10-Q paper entries with non-adverse SPY T+1 context may retain the prior all-window lift while reducing concentration if repeated same-ticker 10-Q admissions are cooled down for 90 calendar days.

## Results vs Scalar 1.0 Baseline

- EV delta: `0.596267`
- PnL delta: `$12303.14`
- gate_passed: `False`
- failed_checks: `['top5_contribution_cap']`

## Cooldown Delta vs 1.5x No-Cooldown

- EV delta: `0.0`
- PnL delta: `$0.0`

## Three-Window Deltas vs Scalar 1.0 Baseline

| Window | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|
| late_strong | +0.1161 | $+2,779.63 | -0.0012 |
| mid_weak | +0.3802 | $+6,380.01 | -0.0012 |
| old_thin | +0.1000 | $+3,143.50 | +0.0039 |

## Cooldown Diagnostics

```json
{
  "admitted_target_candidate_count": 24,
  "admitted_target_candidates": [
    {
      "accession_number": "0001075531-24-000048",
      "date_text": "2024-11-04",
      "form_base": "10-Q",
      "index": 5,
      "spy_t1_return": 0.00422,
      "ticker": "BKNG",
      "window": "old_thin"
    },
    {
      "accession_number": "0001679788-24-000187",
      "date_text": "2024-11-04",
      "form_base": "10-Q",
      "index": 7,
      "spy_t1_return": 0.00422,
      "ticker": "COIN",
      "window": "old_thin"
    },
    {
      "accession_number": "0000886982-24-000025",
      "date_text": "2024-11-06",
      "form_base": "10-Q",
      "index": 8,
      "spy_t1_return": 0.012092,
      "ticker": "GS",
      "window": "old_thin"
    },
    {
      "accession_number": "0001321655-24-000209",
      "date_text": "2024-11-07",
      "form_base": "10-Q",
      "index": 10,
      "spy_t1_return": 0.024866,
      "ticker": "PLTR",
      "window": "old_thin"
    },
    {
      "accession_number": "0000731766-24-000323",
      "date_text": "2024-11-07",
      "form_base": "10-Q",
      "index": 11,
      "spy_t1_return": 0.024866,
      "ticker": "UNH",
      "window": "old_thin"
    },
    {
      "accession_number": "0001561550-24-000175",
      "date_text": "2024-11-13",
      "form_base": "10-Q",
      "index": 12,
      "spy_t1_return": -0.003106,
      "ticker": "DDOG",
      "window": "old_thin"
    },
    {
      "accession_number": "0001628280-24-049786",
      "date_text": "2024-12-06",
      "form_base": "10-Q",
      "index": 15,
      "spy_t1_return": -0.001645,
      "ticker": "CRDO",
      "window": "old_thin"
    },
    {
      "accession_number": "0000723125-24-000047",
      "date_text": "2024-12-23",
      "form_base": "10-Q",
      "index": 18,
      "spy_t1_return": 0.012011,
      "ticker": "MU",
      "window": "old_thin"
    },
    {
      "accession_number": "0000320193-25-000008",
      "date_text": "2025-02-05",
      "form_base": "10-Q",
      "index": 29,
      "spy_t1_return": 0.006708,
      "ticker": "AAPL",
      "window": "old_thin"
    },
    {
      "accession_number": "0001628280-25-011738",
      "date_text": "2025-03-13",
      "form_base": "10-Q",
      "index": 39,
      "spy_t1_return": 0.005307,
      "ticker": "CRDO",
      "window": "old_thin"
    },
    {
      "accession_number": "0001628280-25-018911",
      "date_text": "2025-04-28",
      "form_base": "10-Q",
      "index": 2,
      "spy_t1_return": 0.007225,
      "ticker": "TSLA",
      "window": "mid_weak"
    },
    {
      "accession_number": "0001321655-25-000066",
      "date_text": "2025-05-08",
      "form_base": "10-Q",
      "index": 7,
      "spy_t1_return": 0.004205,
      "ticker": "PLTR",
      "window": "mid_weak"
    },
    {
      "accession_number": "0001035267-25-000192",
      "date_text": "2025-07-28",
      "form_base": "10-Q",
      "index": 11,
      "spy_t1_return": 0.004224,
      "ticker": "ISRG",
      "window": "mid_weak"
    },
    {
      "accession_number": "0001628280-25-035806",
      "date_text": "2025-07-29",
      "form_base": "10-Q",
      "index": 13,
      "spy_t1_return": -0.000251,
      "ticker": "TSLA",
      "window": "mid_weak"
    },
    {
      "accession_number": "0001321655-25-000106",
      "date_text": "2025-08-07",
      "form_base": "10-Q",
      "index": 16,
      "spy_t1_return": 0.00766,
      "ticker": "PLTR",
      "window": "mid_weak"
    },
    {
      "accession_number": "0000002488-25-000108",
      "date_text": "2025-08-08",
      "form_base": "10-Q",
      "index": 18,
      "spy_t1_return": -0.000838,
      "ticker": "AMD",
      "window": "mid_weak"
    },
    {
      "accession_number": "0000059478-25-000204",
      "date_text": "2025-08-12",
      "form_base": "10-Q",
      "index": 20,
      "spy_t1_return": -0.001978,
      "ticker": "LLY",
      "window": "mid_weak"
    },
    {
      "accession_number": "0000731766-25-000236",
      "date_text": "2025-08-14",
      "form_base": "10-Q",
      "index": 21,
      "spy_t1_return": 0.003423,
      "ticker": "UNH",
      "window": "mid_weak"
    },
    {
      "accession_number": "0001807794-25-000021",
      "date_text": "2025-09-09",
      "form_base": "10-Q",
      "index": 24,
      "spy_t1_return": 0.002457,
      "ticker": "CRDO",
      "window": "mid_weak"
    },
    {
      "accession_number": "0000040545-25-000132",
      "date_text": "2025-10-24",
      "form_base": "10-Q",
      "index": 27,
      "spy_t1_return": 0.00593,
      "ticker": "GE",
      "window": "mid_weak"
    },
    {
      "accession_number": "0001628280-25-045968",
      "date_text": "2025-10-28",
      "form_base": "10-Q",
      "index": 1,
      "spy_t1_return": 0.011798,
      "ticker": "TSLA",
      "window": "late_strong"
    },
    {
      "accession_number": "0000018230-25-000048",
      "date_text": "2025-11-06",
      "form_base": "10-Q",
      "index": 10,
      "spy_t1_return": 0.003465,
      "ticker": "CAT",
      "window": "late_strong"
    },
    {
      "accession_number": "0000723125-25-000046",
      "date_text": "2025-12-22",
      "form_base": "10-Q",
      "index": 17,
      "spy_t1_return": 0.009063,
      "ticker": "MU",
      "window": "late_strong"
    },
    {
      "accession_number": "0001403161-26-000045",
      "date_text": "2026-02-03",
      "form_base": "10-Q",
      "index": 23,
      "spy_t1_return": 0.004971,
      "ticker": "V",
      "window": "late_strong"
    }
  ],
  "cooldown_days": 90,
  "excluded_by_ticker": {
    "LLY": 1
  },
  "excluded_by_window": {
    "late_strong": 1
  },
  "excluded_target_candidate_count": 1,
  "excluded_target_candidates": [
    {
      "accession_number": "0000059478-25-000254",
      "cooldown_days": 90,
      "date_text": "2025-11-04",
      "days_since_prior_admission": 84,
      "form_base": "10-Q",
      "index": 6,
      "prior_admitted_date": "2025-08-12",
      "spy_t1_return": 0.001877,
      "ticker": "LLY",
      "window": "late_strong"
    }
  ],
  "target_by_ticker": {
    "AAPL": 1,
    "AMD": 1,
    "BKNG": 1,
    "CAT": 1,
    "COIN": 1,
    "CRDO": 3,
    "DDOG": 1,
    "GE": 1,
    "GS": 1,
    "ISRG": 1,
    "LLY": 2,
    "MU": 2,
    "PLTR": 3,
    "TSLA": 3,
    "UNH": 2,
    "V": 1
  },
  "target_by_window": {
    "late_strong": 5,
    "mid_weak": 10,
    "old_thin": 10
  },
  "target_candidate_count": 25
}
```

## Gate

```json
{
  "aggregate_delta": {
    "expected_value_score_sum_delta": 0.596267,
    "expected_value_score_sum_delta_pct": 0.050261,
    "max_drawdown_pct_max_delta": 0.003898,
    "max_drawdown_pct_max_delta_pct": 0.033324,
    "min_survival_rate_delta": 0.0,
    "min_survival_rate_delta_pct": 0.0,
    "sleeve_closed_trade_count_sum_delta": 0.0,
    "sleeve_closed_trade_count_sum_delta_pct": 0.0,
    "sleeve_total_pnl_sum_delta": 11992.55,
    "sleeve_total_pnl_sum_delta_pct": 0.137311,
    "total_pnl_sum_delta": 12303.14,
    "total_pnl_sum_delta_pct": 0.037945,
    "trade_count_sum_delta": 0.0,
    "trade_count_sum_delta_pct": 0.0
  },
  "by_window": {
    "late_strong": {
      "expected_value_score": 0.116075,
      "max_drawdown_pct": -0.001232,
      "sharpe_daily": -0.007539,
      "total_pnl": 2779.63
    },
    "mid_weak": {
      "expected_value_score": 0.380211,
      "max_drawdown_pct": -0.001168,
      "sharpe_daily": 0.11901,
      "total_pnl": 6380.01
    },
    "old_thin": {
      "expected_value_score": 0.099981,
      "max_drawdown_pct": 0.003898,
      "sharpe_daily": 0.0368,
      "total_pnl": 3143.5
    }
  },
  "failed_checks": [
    "top5_contribution_cap"
  ],
  "metric_checks": {
    "adjusted_trade_sample": true,
    "adjusted_window_coverage": true,
    "drawdown_worse_guard": true,
    "ev_improved_window_coverage": true,
    "hhi_concentration_cap": true,
    "no_ev_regressed_windows": true,
    "positive_aggregate_ev": true,
    "positive_aggregate_pnl": true,
    "single_ticker_positive_share_cap": true,
    "top5_contribution_cap": false
  },
  "metric_gate_passed": false,
  "metrics": {
    "adjusted_trade_count": 12,
    "adjusted_windows": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ],
    "max_drawdown_worse": 0.003898,
    "max_single_positive_pnl_share": 0.313,
    "pnl_hhi_concentration": 0.2043,
    "pnl_top_5_contribution_pct": 0.9207,
    "windows_ev_improved": 3,
    "windows_ev_regressed": 0
  },
  "passed": false,
  "rules": {
    "metric_gate": "aggregate EV/PnL positive versus scalar=1.0 baseline, at least two EV-improved windows, zero EV-regressed windows, and max drawdown worsening <= 0.5pp",
    "production_parity_guard": "Uses production-visible SEC form_base, ticker, dates, and spy_t1_return fields only; no archive coverage or LLM field.",
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

## Production Impact

```json
{
  "alters_candidate_ranking": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_sizing": false,
  "backtester_adapter_changed": false,
  "default_off_paper_only": true,
  "live_default_orders_changed": false,
  "parity_test_added": false,
  "promotion_blocker_if_positive": "A shared SEC financial-report paper adapter path must apply the same cooldown before any daily report or production-facing paper state changes are retained.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

No JavaScript was used.
