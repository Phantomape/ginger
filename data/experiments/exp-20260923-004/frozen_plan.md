# Frozen plan (written 2026-09-23T16:23:16+00:00, before reservation) - news-propagation pair readiness borrow-coverage contract review

## Identity-only evidence (no outcome/PnL field read)
- readiness_decisions.jsonl sha256 fef641e10f0ce49c21555912732ca6ac90756ce5c6833b30444e42d115869ab1: 32 records, 6 measurement_ready / 26 blocked.
- Since 2026-09-14 (first batch after exp-20260913-007 took effect): 13 records, 1 ready (09-14) / 12 blocked; 0 ready since 09-15.
- Blocked-only-by-per-ticker-borrow: 11 lifetime (7 since 09-14). Batch-level blockers (overlap/polarity) on the other 15.
- Per-ticker blocker kinds x fetch_state: missing_pit_borrow+not_found 83, missing_pit_borrow+ok 18, stale_pit_borrow+ok 41.
- Recurring not_found short tickers: BAO DBIM EVON HWEP LILW SBEV BAGZ BLTG GRAY MOT (prefetch attempted on batch day; iBorrowDesk has no page). BAO/DBIM/EVON/HWEP are the symbols exp-20260913-007 already names as absent from instrument_master (unpriceable).
- Coverage of the blocked-only-by-borrow batches: 17/20 .. 101/109 (85-98%).

## Rule under review (exp-20260826-001 readiness gate, consumed by exp-20260827-001 sleeve)
Every short-side ticker needs PIT iBorrowDesk evidence archived_at <= first_seen_at and <= 3 calendar days old; any single uncovered ticker blocks the whole batch.

## Amendment (forward-only; effective for batches first seen >= 2026-09-23T17:00:00+00:00)
(a) news_propagation_pair_forward_observer.build_readiness_records: for post-effective batches, per-ticker borrow blockers (missing/stale/invalid/unavailable) no longer enter `blockers`; they are recorded as borrow_coverage.uncovered_tickers = [{ticker, blocker}] with borrow_coverage.coverage_rule_version = news_propagation_pair_borrow_coverage_v2; batch-level blockers unchanged; new blocker `short_side_no_borrow_coverage` when the short side has rows but zero covered tickers. Pre-effective batches: byte-identical v1 behaviour (same record_id, same blockers, no new keys).
(b) news_propagation_pair_paper_sleeve.build_pair_basket_decision: short-side keep set = (priceable keep or all short tickers) minus uncovered tickers; short_leg records excluded_no_pit_borrow (sorted); equal row weights renormalised over kept tickers exactly as exp-20260913-007 does for priceability; empty short side -> not admitted. Records without uncovered_tickers produce byte-identical decisions.
(c) No persisted readiness record or basket decision is rewritten; no batch first seen before the effective timestamp is admitted retroactively; acceptance counting continues (fully-covered batches are identical under both rules).

## Locked / unchanged
PIT rule (archived_at <= first_seen, 3-day max age); batch-level blockers; H10; 45bp/leg; USD 1000/leg; 40% row-weight cap; acceptance >=20 baskets / >=10 dates / both halves positive / <=40% ticker share; record_id derivations; iBorrowDesk = indicative, not a locate; trade_enabled=false.

## Outcome-blind projection to be saved (before/after artifact)
Per persisted record: first_seen date, frozen status, batch-level blockers, per-ticker blocker kind counts, covered/required, hypothetical v2 status. Expected (already computed from identity fields): 17 ready / 15 blocked lifetime; 7 of 13 since 09-14. Production keeps all 32 as persisted.

## Acceptance
New tests pass with existing observer/sleeve/exposure/wiring tests; before/after artifact written; lean-strict audit green. Verification is correct implementation of this frozen rule, not any forward result.

## Budget (declared before reservation)
1 measurement_repair ID; <= 90 wall minutes; 0 HTTP; 0 external spend; 0 outcome/PnL fields read.

## Two outcomes
- Tests pass and projection matches: close accepted; first post-effective batch = 2026-09-24 nightly; recount ready cadence in later units.
- Implementation cannot keep pre-effective bytes identical or the sleeve cannot separate the two exclusion labels: close rejected/inconclusive, leave the rule pre-registered, no second ID this unit.
