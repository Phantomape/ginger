# exp-20260713-008 ClinicalTrials.gov Phase 3 results

- Decision: `rejected_clinicaltrials_phase3_results_candidate_pool`
- Full-stack verdict: `reject`
- Source events / tickers: `156` / `9`
- Target trades / tickers / windows: `47` / `9` / `3`
- Aggregate EV delta: `0.0457`
- Aggregate PnL delta: `$1,387.60`
- Gate 3 survival: `18.80%`
- Gate 4 failures: `ev_regressed_windows, top_5_contribution_pct_cap, accepted_distribution_pnl_comparator_not_beaten, daily_candidate_lifecycle_parity_incomplete`

Historical replay uses only exact ACTUAL first-post Record History versions. No daily production wiring was retained after the Gate 4 rejection.

Residual unknowns: the exact selected versions are frozen but their history change-lists are not, and the current exact-sponsor retrieval prefilter can miss studies whose sponsor later changed away from a preregistered name.
