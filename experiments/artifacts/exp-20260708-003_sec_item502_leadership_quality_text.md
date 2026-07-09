# exp-20260708-003 SEC Item 5.02 Leadership-Quality Text Gate

Decision: `rejected_sec_item502_leadership_quality_text`.

Single variable: a default-off paper candidate source that admits PIT-safe SEC 8-K Item 5.02 filings only when filing-body text shows direct C-suite appointment/succession clarity and rejects abrupt departure or board-only rows.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1313 | -0.0315 | $117,072.92 | $116,623.05 | $-449.87 | +0.0000 | 1 | 1 |
| mid_weak | 2.1331 | 2.1331 | +0.0000 | $77,845.53 | $77,845.53 | $+0.00 | +0.0000 | 0 | 0 |
| old_thin | 0.6440 | 0.6440 | +0.0000 | $42,933.82 | $42,933.82 | $+0.00 | +0.0000 | 0 | 0 |

## Aggregate

- EV delta: `-0.0315` (`-0.003967`)
- PnL delta: `$-449.87` (`-0.001891`)
- target trades: `1` across `1` windows
- max single positive share: `None`
- positive PnL HHI: `None`

## Text Surface

```json
{
  "admitted_text_rows": 17,
  "classification_counts": {
    "board_appointment_not_csuite": 38,
    "clear_exec_appointment": 1,
    "clear_exec_appointment_succession": 16,
    "exec_departure_risk": 1,
    "other_item502_text": 5,
    "planned_transition_mixed_departure": 121
  },
  "event_source_glob": "data/non_ohlcv/sec_filing_events_*.jsonl",
  "load_reject_counts": {
    "amendment": 79,
    "excluded_item_code": 323,
    "not_8k": 50,
    "not_item502": 7616
  },
  "raw_pre_dedupe_classification_counts": {
    "board_appointment_not_csuite": 318,
    "clear_exec_appointment": 7,
    "clear_exec_appointment_succession": 126,
    "exec_departure_risk": 8,
    "other_item502_text": 39,
    "planned_transition_mixed_departure": 975
  },
  "text_source_file_count": 476,
  "text_source_glob": "data/non_ohlcv/sec_filing_text_*.jsonl",
  "unique_item502_text_rows": 182
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": false,
  "aggregate_pnl_delta_positive": false,
  "failed_reasons": [
    "aggregate_ev_not_positive",
    "aggregate_pnl_not_positive",
    "window_ev_regression",
    "window_pnl_regression",
    "target_sample_too_small",
    "target_window_coverage_too_small",
    "target_concentration_failed"
  ],
  "max_drawdown_worse": 0.0,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": null,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": null,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 1,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong"
  ],
  "windows_ev_improved": 0,
  "windows_ev_regressed": 1,
  "windows_pnl_improved": 0,
  "windows_pnl_regressed": 1
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
