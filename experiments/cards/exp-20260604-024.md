# Form 4 plus SEC FTD Overlap Candidate Pool

- experiment_id: `exp-20260604-024`
- timestamp: `2026-06-04T20:16:02+00:00`
- decision: `rejected_form4_ftd_overlap_candidate_pool`
- aggregate EV vs core: `7.8941` -> `7.9571` (+0.0630)
- aggregate PnL vs core: `$+1,183.45`
- aggregate EV vs raw Form 4: `8.1547` -> `7.9571` (-0.1976)
- selected overlap trades: `1`
- failed gates: `does_not_improve_raw_form4_queue, not_material_vs_core, target_sample_too_small, target_window_coverage_too_small, single_ticker_concentration, positive_pnl_hhi_concentration`

## Three-Window Result

| window | Core EV | Raw Form4 EV | Overlap EV | Delta vs raw | Delta vs core | Core PnL | Overlap PnL | Event PnL | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.2947 | 5.2238 | -0.0709 | 0.061 | $117,072.92 | $118,184.73 | $194.27 | 1 |
| mid_weak | 2.1402 | 2.2689 | 2.1422 | -0.1267 | 0.002 | $78,110.11 | $78,181.75 | $0.00 | 0 |
| old_thin | 0.5911 | 0.5911 | 0.5911 | 0.0 | 0.0 | $39,667.96 | $39,667.96 | $0.00 | 0 |

## Gate Read

{
  "drawdown_guard_passed": true,
  "failed_reasons": [
    "does_not_improve_raw_form4_queue",
    "not_material_vs_core",
    "target_sample_too_small",
    "target_window_coverage_too_small",
    "single_ticker_concentration",
    "positive_pnl_hhi_concentration"
  ],
  "improves_core_cleanly": true,
  "improves_vs_raw_form4": false,
  "material_vs_core": false,
  "max_drawdown_drift_guard": "<= 0.005",
  "min_survival_rate": 0.7925,
  "passed": false,
  "positive_pnl_hhi": 1.0,
  "positive_pnl_hhi_guard": "<= 0.35",
  "sample_guard_passed": false,
  "selected_event_trades": 1,
  "single_ticker_positive_share": 1.0,
  "single_ticker_positive_share_guard": "<= 0.5",
  "target_trade_count_min": 8,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong"
  ]
}

## Source Diagnostics

{
  "form4": {
    "events_with_ownership_delta": 17,
    "ownership_delta_floor": 0.1,
    "ownership_delta_floor_event_count": 11,
    "raw_forward_event_count": 17,
    "source_status": "loaded",
    "transaction_rows": 27879
  },
  "ftd": {
    "file_count": 44,
    "publication_lag_note": "First-half files are used no earlier than the next month end plus one calendar day; second-half files are used no earlier than the 16th of the next month.",
    "row_count": 2724,
    "row_summary_artifact": "data/experiments/exp-20260604-024/sec_ftd_rows_summary.json",
    "source_files_artifact": "data/experiments/exp-20260604-024/sec_ftd_source_files.json",
    "source_page": "https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data"
  },
  "overlap": {
    "overlap_event_count": 2,
    "parameters": {
      "max_ftd_publication_age_days": 45,
      "min_ftd_notional": 250000.0,
      "min_ftd_notional_to_form4_purchase_value": 0.25,
      "min_ftd_shares": 25000
    },
    "raw_pass_counts": {
      "form4_event_scanned": 17,
      "ftd_absolute_pressure_passed": 2,
      "ftd_to_purchase_pressure_passed": 2,
      "has_published_ftd_row": 16,
      "publication_lag_passed": 16
    }
  }
}

## Conclusion

Gate 4 failed; no production or shared strategy behavior is retained.

Core production orders, ranking, sizing, exits, LLM/news inputs, and watchlists were unchanged. The overlap is replay-only/default-off and would require a shared production-visible adapter before promotion.
