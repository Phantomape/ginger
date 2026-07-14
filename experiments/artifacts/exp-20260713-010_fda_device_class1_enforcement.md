# exp-20260713-010 FDA Device Class-I Enforcement Reports

- Decision: `rejected_fda_device_class1_enforcement_candidate_pool`
- Full-stack verdict: `reject`
- Source events / tickers: `86` / `19`
- Target trades / tickers / windows: `22` / `10` / `3`
- Aggregate EV delta: `0.1359`
- Aggregate PnL delta: `$476.80`
- Gate 3 survival: `25.58%`
- Gate 4 failures: `insufficient_ev_improved_windows, ev_regressed_windows, single_ticker_positive_share_cap, top_5_contribution_pct_cap, window_pnl_regression, accepted_distribution_ev_comparator_not_beaten, accepted_distribution_pnl_comparator_not_beaten`
- DSR: `not_computable` / `None` (Gate 5 only; reasons: `expected_maximum_approximation_negative`)

## Point-in-time source contract

- Official API: https://open.fda.gov/apis/device/enforcement/
- Searchable fields: https://open.fda.gov/apis/device/enforcement/searchable-fields/
- `report_date` is the FDA enforcement-report issue date and is the only historical availability date used.
- `recall_initiation_date` and `classification_date` are excluded from policy timing.
- openFDA updates weekly and historical rows may change, so exact canonical API pages, normalized records, SHA256 hashes, and retrieval UTC are frozen.

The historical helper is retained only for replay evidence; the rejected daily production wiring was rolled back and daily candidate parity remains incomplete. DSR is persisted from the complete aligned off-vs-on panel and affects only Gate 5, never the historical Gate-4 decision.
