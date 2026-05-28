# exp-20260528-035 Industry-Leadership High-Close Route

Decision: `rejected_industry_leadership_high_close`.

Single variable: route industry-leadership paper candidates only when signal-day close-location value is `>= 0.70`.

## Gate Questions

- alpha_hypothesis: candidate_pool / entry: same-industry leadership breakouts are more likely to add replacement value when the signal day closes near its own high, which is a free OHLCV demand-quality field.
- single_causal_variable: `industry_leadership_signal_day_high_close_routing_v1`
- reproducibility: `.venv\Scripts\python.exe -B quant\experiments\exp_20260528_035_industry_leadership_high_close.py`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw | Routed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.3595 | -0.8033 | $117,072.92 | $109,810.83 | $-7,262.09 | +0.0039 | 12 | 28 | 21 |
| mid_weak | 2.1402 | 2.7014 | +0.5612 | $78,110.11 | $88,281.29 | $+10,171.18 | -0.0038 | 28 | 67 | 41 |
| old_thin | 0.5911 | 0.5266 | -0.0645 | $39,667.96 | $37,349.42 | $-2,318.54 | +0.0011 | 12 | 30 | 20 |

## Aggregate

- EV delta: `-0.3066` (`-0.038839`)
- PnL delta: `$590.55` (`0.002515`)
- target trades: `52` across `3` windows
- max single positive share: `0.570832`
- positive PnL HHI: `0.454214`

## High-Close Audit

```json
{
  "late_strong": {
    "all_close_location_max": 0.991321,
    "all_close_location_min": 0.304992,
    "filtered_candidate_count": 7,
    "min_signal_day_close_location": 0.7,
    "raw_candidate_count": 28,
    "raw_candidate_days": 20,
    "raw_top_industries": {
      "Semiconductors": 25,
      "Software - Application": 3
    },
    "raw_unique_tickers": 7,
    "rule_version": "industry_leadership_signal_day_high_close_routing_v1",
    "selected_candidate_count": 21,
    "selected_candidate_days": 17,
    "selected_close_location_max": 0.991321,
    "selected_close_location_min": 0.716622,
    "selected_top_industries": {
      "Semiconductors": 18,
      "Software - Application": 3
    },
    "selected_unique_tickers": 7
  },
  "mid_weak": {
    "all_close_location_max": 0.993042,
    "all_close_location_min": 0.029536,
    "filtered_candidate_count": 26,
    "min_signal_day_close_location": 0.7,
    "raw_candidate_count": 67,
    "raw_candidate_days": 39,
    "raw_top_industries": {
      "Semiconductors": 53,
      "Software - Application": 14
    },
    "raw_unique_tickers": 7,
    "rule_version": "industry_leadership_signal_day_high_close_routing_v1",
    "selected_candidate_count": 41,
    "selected_candidate_days": 28,
    "selected_close_location_max": 0.993042,
    "selected_close_location_min": 0.739421,
    "selected_top_industries": {
      "Semiconductors": 32,
      "Software - Application": 9
    },
    "selected_unique_tickers": 7
  },
  "old_thin": {
    "all_close_location_max": 0.98305,
    "all_close_location_min": 0.308093,
    "filtered_candidate_count": 10,
    "min_signal_day_close_location": 0.7,
    "raw_candidate_count": 30,
    "raw_candidate_days": 19,
    "raw_top_industries": {
      "Semiconductors": 13,
      "Software - Application": 17
    },
    "raw_unique_tickers": 8,
    "rule_version": "industry_leadership_signal_day_high_close_routing_v1",
    "selected_candidate_count": 20,
    "selected_candidate_days": 13,
    "selected_close_location_max": 0.98305,
    "selected_close_location_min": 0.701413,
    "selected_top_industries": {
      "Semiconductors": 7,
      "Software - Application": 13
    },
    "selected_unique_tickers": 6
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": false,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0039,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.570832,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.454214,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 52,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 1,
  "windows_ev_regressed": 2,
  "windows_pnl_regressed": 2
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
