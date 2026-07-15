# exp-20260715-004 FDA Orange Book fresh-NEWA release basket

- Decision: `rejected_fda_orange_book_newa_release_basket`
- Full-stack verdict: `reject`
- Official PDFs / decisions: `19` / `119`
- Eligible issuer-release legs / settled trades: `70` / `53`
- Core+sleeve aggregate EV delta: `0.124`
- Core+sleeve aggregate PnL delta: `$1,648.40`
- Standalone aggregate EV / PnL: `0.0198` / `$1,648.39`
- Gate 2 source hashes + sentinels: `passed`
- Gate 3 survival: `100.00%`
- Single / top-5 positive contribution: `20.93%` / `79.93%`
- Gate 4 failures: `non_positive_aggregate_ev, non_positive_aggregate_pnl, top_5_contribution_pct_cap, old_thin_ev_negative, accepted_candidate_pool_ev_comparator_not_beaten, accepted_candidate_pool_pnl_comparator_not_beaten, top5_positive_contribution_above_60pct`
- DSR: `not_computable` / `None` (Gate 5 only; reasons: `expected_maximum_approximation_negative`)

## Three-window daily-MTM result

| Window | Eligible legs | Tickers | Top1 | Generated | Survived | Trades | Standalone EV | Standalone PnL | Core EV delta | Core PnL delta | DD delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| old_thin | 23 | 11 | 21.74% | 23 | 23 | 19 | 0.0009 | $314.81 | -0.0032 | $314.82 | -0.0002 |
| mid_weak | 24 | 14 | 20.83% | 24 | 24 | 16 | 0.0189 | $1,381.20 | 0.1297 | $1,381.21 | -0.0003 |
| late_strong | 23 | 11 | 21.74% | 23 | 23 | 18 | 0.0000 | $-47.62 | -0.0025 | $-47.63 | -0.0002 |

## Point-in-time and integrity contract

- Official landing page: https://www.fda.gov/drugs/drug-approvals-and-databases/additionsdeletions-prescription-and-otc-drug-product-lists
- Every consumed PDF is frozen byte-for-byte and verified against the source manifest's byte count and SHA-256 before evaluation.
- The official HTTP `Last-Modified` UTC timestamp is the signal clock; approval date is freshness metadata only and must be 0-45 calendar days earlier.
- Only `>A>` rows with terminal reason `NEWA` are eligible. Mapping is exact and event-date-aware; fuzzy holder matching is forbidden.
- Mapping audit repair: Fresenius Kabi USA is not economically represented by FMS (Fresenius Medical Care), so all former FMS legs were removed before evaluation; the corrected PDF parser and preflight agree exactly.
- One ticker x PDF-month decision is retained, every eligible issuer is used, and the fixed $16,000 release budget is divided equally. There is no top-N or threshold sweep.
- Source manifest SHA-256: `5400cefd7f7f0f2c71fad48042442c51f39855940dd0d8047fbd45fc2eec6071`
- Canonical decisions SHA-256: `cdc9b01ef6773e87c3c39c0339eeab5ad5786bc743bde1133f349d2b6a93289d`

Historical replay and the default-off snapshot callable share one policy helper. Gate 4 rejected the policy, so production daily wiring is not retained. The complete date-aligned off/on panel is persisted for Deflated-Sharpe evidence, but DSR affects Gate 5 only and never changes this Gate-4 decision.
