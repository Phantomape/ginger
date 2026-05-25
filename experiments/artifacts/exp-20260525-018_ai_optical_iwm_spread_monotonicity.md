# exp-20260525-018 AI Optical IWM/SPY Spread Monotonicity

Decision: `observed_only_binary_gate_confirmed_strength_not_monotonic`.

Observed-only alpha search. No entries, exits, ranking, sizing, adapter behavior, LLM/news, or orders changed.

## Source Three-Window Before/After

- source experiment: `exp-20260525-003`
- EV delta: `0.4482`
- PnL delta: `$7372.78`
- windows EV improved/regressed: `3` / `0`

## Binary Gate

| Binary Gate | Trades | Windows | Win rate | Total PnL | Avg PnL |
|---|---:|---|---:|---:|---:|
| filtered_out | 5 | late_strong, old_thin | 20.00% | $-493.78 | $-98.76 |
| selected | 10 | late_strong, mid_weak, old_thin | 60.00% | $7,372.78 | $737.28 |

## Spread Buckets

| Bucket | Trades | Windows | Win rate | Total PnL | Avg PnL | Max positive share | HHI |
|---|---:|---|---:|---:|---:|---:|---:|
| failed_iwm_lead | 5 | late_strong, old_thin | 20.00% | $-493.78 | $-98.76 | 1.0 | 1.0 |
| edge_iwm_lead | 4 | late_strong, mid_weak, old_thin | 100.00% | $6,817.29 | $1,704.32 | 0.371743 | 0.338312 |
| broad_iwm_lead | 6 | late_strong, mid_weak, old_thin | 33.33% | $555.49 | $92.58 | 0.70796 | 0.586495 |

## Monotonic Gate

```json
{
  "adjacent_bucket_checks": [
    {
      "higher_avg_pnl": 1704.32,
      "higher_bucket": "edge_iwm_lead",
      "lower_avg_pnl": -98.76,
      "lower_bucket": "failed_iwm_lead",
      "passed": true
    },
    {
      "higher_avg_pnl": 92.58,
      "higher_bucket": "broad_iwm_lead",
      "lower_avg_pnl": 1704.32,
      "lower_bucket": "edge_iwm_lead",
      "passed": false
    }
  ],
  "binary_participation_gate_passed": true,
  "decision": "observed_only_binary_gate_confirmed_strength_not_monotonic",
  "failed_summary": {
    "avg_pnl": -98.76,
    "avg_pnl_pct_net": -0.009876,
    "best_pnl": 2173.15,
    "max_single_positive_share": 1.0,
    "positive_hhi": 1.0,
    "positive_pnl_by_ticker": {
      "MRVL": 2173.15
    },
    "ticker_count": 4,
    "total_pnl": -493.78,
    "trades": 5,
    "win_rate": 0.2,
    "windows": [
      "late_strong",
      "old_thin"
    ],
    "worst_pnl": -1022.91
  },
  "field_coverage": 1.0,
  "field_coverage_passed": true,
  "interpretation": "The existing binary IWM/SPY participation gate is supported, but larger spread strength is not monotonic; do not retune toward a higher IWM-spread threshold on the frozen sample.",
  "passed": false,
  "selected_summary": {
    "avg_pnl": 737.28,
    "avg_pnl_pct_net": 0.073728,
    "best_pnl": 2467.95,
    "max_single_positive_share": 0.282052,
    "positive_hhi": 0.251461,
    "positive_pnl_by_ticker": {
      "CIEN": 2467.95,
      "GLW": 2534.28,
      "LITE": 2395.0,
      "MTSI": 2906.06
    },
    "ticker_count": 5,
    "total_pnl": 7372.78,
    "trades": 10,
    "win_rate": 0.6,
    "windows": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ],
    "worst_pnl": -950.1
  },
  "strength_monotonicity_passed": false
}
```

Conclusion: keep the existing binary IWM/SPY participation gate as a forward-watch paper lead, but reject higher-threshold / larger-notional follow-ups until forward replacement-value rows arrive.

No JavaScript was used.
