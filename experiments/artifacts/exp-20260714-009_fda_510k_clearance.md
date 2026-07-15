# exp-20260714-009 FDA 510(k) Traditional Clearances

- Decision: `rejected_fda_510k_clearance_candidate_pool`
- Full-stack verdict: `reject`
- Source events / tickers: `415` / `32`
- Target trades / tickers / windows: `242` / `31` / `3`
- Aggregate EV delta: `-0.2697`
- Aggregate PnL delta: `$-1,066.79`
- Gate 3 survival: `67.89%`
- Gate 2 sentinel fields: `passed`
- Single / top-5 positive contribution: `21.30%` / `68.86%`
- Gate 4 failures: `non_positive_aggregate_ev, non_positive_aggregate_pnl, top_5_contribution_pct_cap, old_thin_ev_negative, old_thin_pnl_negative, accepted_distribution_ev_comparator_not_beaten, accepted_distribution_pnl_comparator_not_beaten`
- DSR: `not_computable` / `None` (Gate 5 only; reasons: `expected_maximum_approximation_negative`)

## Three-window daily-MTM result

| Window | Generated | Survived | Trades | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 114 | 78 | 74 | -0.0562 | $223.78 | -0.0059 |
| mid_weak | 133 | 88 | 83 | -0.0848 | $355.25 | -0.0003 |
| old_thin | 133 | 92 | 85 | -0.1287 | $-1,645.81 | -0.0008 |

## Point-in-time source contract

- Official API: https://api.fda.gov/device/510k.json
- Historical availability is `decision_date + 14 calendar days`; entry is the first regular-session open strictly after `public_as_of`.
- Only `Traditional` clearances and normalized exact applicant aliases are eligible; no substring matching or price confirmation is used.
- The FDA searchable database updates weekly, while the openFDA derivative updates monthly; exact gzipped API pages, normalized records, SHA256 hashes, and retrieval UTC are frozen.
- Archive / normalized-event SHA256: `0274517ebb4e79228b15b8046659a579fe266d87617bcd7a50c3db03a95cb850` / `ef92a3ea6a47ff852b44c229951185a2197e0ae725e4f1b5ba00f00896919c97`
- Raw manifest SHA256 / pages verified: `6ee8a7ecf7d5ee04e836f5389345fde4ef3a27ead0de6e5a9b0a9e476fae42b2` / `5`

The shared helper exposes the same replay policy for historical and daily default-off snapshots, but no run.py daily production wiring was retained after Gate 4 rejected the sleeve. DSR is persisted from the complete aligned off-vs-on panel and affects only Gate 5, never the historical Gate-4 decision.
