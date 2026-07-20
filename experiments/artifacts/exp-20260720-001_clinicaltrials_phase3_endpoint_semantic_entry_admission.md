# exp-20260720-001 ClinicalTrials Phase-3 endpoint semantics

- Decision: `rejected_clinicaltrials_phase3_endpoint_semantic_entry_admission`
- Rule: `clinicaltrials_phase3_primary_endpoint_semantic_top1_10d_v1`
- Exact events / positive grades / tickers: `156` / `26` / `6`
- Closed target trades / tickers / windows: `22` / `6` / `3`
- Aggregate EV delta: `0.1724`
- Aggregate PnL delta: `$2,053.51`
- Top-5 positive contribution: `1.0`
- Gate-3 survival: `14.74%`
- Gate-4 failures: `ev_regressed_windows, drawdown_worse_guardrail, top_5_contribution_pct_cap, immaterial_effect, window_pnl_regression, accepted_distribution_pnl_comparator_not_beaten, source_positive_ticker_universe_cannot_meet_top5_contribution_cap`

The exact source payload SHA, treatment/control measurement direction, and next-session timing are audited. The helper and daily snapshot remain default-off; central scheduling and lifecycle parity are incomplete.
