# Frozen plan (written 2026-09-24T16:17Z, before reservation) - news-propagation pair readiness cross-side-overlap contract review

## Identity-only evidence (no outcome/PnL field read)
- readiness_decisions.jsonl sha256 05f005adfd0e68cee873ae73542020a8fdf7fdcd557229a002c7ac25347ff65c: 33 records, 7 measurement_ready / 26 blocked.
- Since 2026-09-14 (exp-20260913-007 effective): 14 records, 2 ready (09-14 nightly, 09-24 nightly = first exp-20260923-004 v2 record) / 12 blocked.
- Under the exp-20260923-004 v2 borrow rule (per-ticker borrow blockers -> exclusion) the hypothetical statuses are 18/33 ready lifetime and 8/14 since 09-14; EVERY remaining post-09-14 block (6/14: 09-15T16, 09-16T03, 09-16T16, 09-17T03, 09-17T16, 09-21T18) carries cross_side_ticker_overlap as its only non-borrow blocker. Lifetime: 10 overlap records; 5 polarity-blocked records (all pre-09-14).
- exp-20260923-004 pre-registered "cross_side_overlap_remains_dominant_batch_blocker" as a main failure mode; it materialised in identity fields. This review is inspired by that observation, not by any result.
- Overlap content is whole sic_peer groups, not noise symbols: semiconductors (AAOI ADI ALAB ALGM ALMU AMAT AMBA AMBQ AMD AMKR ARM ARRY ASML ASTI ASX AVGO KLAC LRCX MU QCOM SMCI TSM, 23-33 tickers), autos (F GM HMC LCID LI RIVN PCAR OSK ..., 17), China internet / AI software (BIDU BZ DJT DOCN DV FDS FLUT PLTR MSFT NOW GOOGL ..., 14-20). Mechanism: one negative and one positive event in the same peer group within one batch -> the peer expansion places the whole group on both sides.
- Residual sides after removing the overlap tickers from BOTH sides (post-09-14 overlap records): long 23/23/35/19/31/26 and short 43/43/39/57/81/25 tickers, residual max ticker row weight <= 0.087 (cap 0.40); both sides non-empty in 6/6. Pre-effective overlap records would have emptied a side (08-25 short, 09-06 long) or breached the cap (08-29 long residual 1 ticker) - they stay frozen and are NOT re-evaluated.

## Rule under review (exp-20260824-002 / exp-20260826-001 readiness gate, consumed by the exp-20260827-001 sleeve)
Any ticker present on both the negative (long) and positive (short) side of a first-seen batch blocks the whole batch (blocker cross_side_ticker_overlap).

## Amendment (forward-only; effective for batches first seen >= 2026-09-24T17:00:00+00:00)
(a) news_propagation_pair_forward_observer.build_readiness_records: for post-effective batches the overlap tickers are EXCLUDED from both sides for readiness evaluation instead of blocking. The record keeps `cross_side_ticker_overlap` (list) unchanged and adds `overlap_exclusion` = {rule_version: news_propagation_pair_cross_side_overlap_exclusion_v2, excluded_tickers, long_side_residual: {ticker_count, row_count, max_ticker_row_weight}, short_side_residual: {...}}. `cross_side_ticker_overlap` no longer enters `blockers`; the 40% concentration blockers are evaluated on the residual sides; new blockers `long_side_emptied_by_overlap` / `short_side_emptied_by_overlap` when a side has rows but no residual ticker; borrow coverage (v2) is evaluated over the residual short tickers (required_tickers = residual count). Pre-effective batches: byte-identical current behaviour (same record_id, same blockers, no new keys).
(b) news_propagation_pair_paper_sleeve.build_pair_basket_decision: when the record carries `overlap_exclusion`, its excluded tickers are removed from BOTH legs' keep sets (after priceability, alongside the v2 uncovered exclusion); each leg records `excluded_cross_side_overlap` (sorted); equal row weights renormalise over the kept tickers exactly as exp-20260913-007 / exp-20260923-004 do; a side that empties is not admitted. Records without the key produce byte-identical decisions. Exclusion labels are independent conditions (a ticker may appear under more than one label).
(c) No persisted readiness record or basket decision is rewritten; no batch first seen before the effective timestamp is admitted retroactively; acceptance counting (restarted 2026-09-14 per exp-20260913-007) continues - overlap-free batches are identical under both rules.

## Locked / unchanged
PIT borrow rule and the v2 uncovered-ticker exclusion; polarity and mixed_first_seen_at blockers; H10; 45bp/leg; USD 1000/leg; 40% row-weight cap (applied to the residual side); acceptance >=20 baskets / >=10 dates / both halves positive / <=40% ticker share; record_id derivations; iBorrowDesk = indicative, not a locate; trade_enabled=false.

## Outcome-blind projection to be saved (before/after artifact)
Per persisted record: first_seen, frozen status, blocker kinds, overlap ticker count, residual long/short ticker count and max row weight, hypothetical status under v2+overlap-exclusion. Expected (already computed from identity fields): 25/33 ready lifetime, 14/14 since 09-14; production keeps all 33 as persisted; the amended observer rebuilds all 33 persisted records byte-identically from live exposure rows + borrow archive.

## Acceptance
New tests pass (post-effective overlap batch -> measurement_ready with overlap_exclusion residuals and no overlap blocker; post-effective batch whose side empties -> blocked *_emptied_by_overlap; residual concentration breach -> blocked; pre-effective overlap batch keeps the blocker byte-identically with no new key; sleeve removes overlap tickers from both legs with renormalised weights and excluded_cross_side_overlap labels, an emptied side is not admitted, a record without the key is byte-identical) together with the existing observer, sleeve, exposure-observer and run.py wiring tests; before/after artifact written; lean-strict audit green. Verification is correct implementation of this frozen rule, not any forward result.

## Budget (declared before reservation)
1 measurement_repair ID; <= 90 wall minutes; 0 HTTP; 0 external spend; 0 outcome/PnL fields read.

## Two outcomes
- Tests pass, 33/33 reproduced, projection matches: close accepted; first post-effective batch = 2026-09-25 nightly (~03:07Z); recount cadence later (expect ~every batch ready unless polarity-missing).
- Pre-effective bytes cannot be kept identical or the residual evaluation cannot be separated from the frozen summaries: close rejected/inconclusive, leave the rule pre-registered, no second ID this unit.
