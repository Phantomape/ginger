# SEC / Earnings Filing-Shock Duplicate Guardrail Audit (exp-20260504-045)

## Scope

This is a shadow/data audit only. It does not alter production orders, signal generation, candidate ranking, sizing, exits, LLM prompts, SEC packet thresholds, or the default-off governance/procedural queue policy.

## Hypothesis

SEC filing shock, earnings surprise, and 8-K filing context may improve C-strategy grading or work as event confirmation, but the broad same-sample path appears exhausted after `exp-20260504-040`; `exp-20260504-044` already implemented the allowed follow-up as a default-off governance/procedural queue plus paper ledger.

## Historical Check

- `exp-20260504-021`: broad data availability and prior-shadow synthesis, decision `shadow_only`.
- `exp-20260504-040`: exact broad SEC/earnings filing-shock consolidation, decision `default_off_candidate` only for governance/procedural follow-up.
- `exp-20260504-044`: implemented shared default-off SEC governance/procedural queue and paper outcome ledger, decision `accepted_default_off_forward_ledger` with no order/ranking/sizing change.

Anti-repeat conclusion: do not rerun positive results-8K reaction gates, stale Companyfacts buckets, keyword text scoring, nearby reaction thresholds, or production promotion before forward ledger outcomes close.

## Coverage Table

| Source | Rows / files | PIT status | Main gap |
|---|---:|---|---|
| SEC submissions | 1286 rows | Accepted datetime is a public EDGAR PIT proxy | Backfill does not prove daily local observation |
| SEC Companyfacts | 17109 rows | Filed date can be PIT background context | Same-accession 8-K grading remains missing/stale |
| SEC filing text | 306 rows | Replay context after accepted_at | Keyword scoring exhausted; needs structured LLM grades |
| Earnings snapshots | 138 files / 6081 rows | Production snapshots from first to latest file only | Older/mid windows and revenue/guidance fields remain incomplete |
| Current shadow SEC event table | 300 rows | Shadow-only | Not connected to signal path; broad tags mostly unclear/missing |

## Tagged Candidate Evidence

- `A_no_recent_filing_event`: not measured; complete historical pre-entry candidate dumps are still unavailable.
- `B_positive_filing_shock`: prior proxy had 21 candidates; average 5d excess `-1.1756%`, 10d `-1.8280%`, 20d `+1.3323%`; slot replacement proxy `-9.8719 pp`.
- `C_negative_filing_shock`: negative text and leadership-change branches remain shadow-promising, but replacement value is incomplete or weak.
- `D_unclear_or_missing_data`: still the dominant broad bucket because same-accession XBRL, revenue surprise, audited guidance fields, and full candidate dumps are missing.

## Slot Value

Current evidence does not prove broad SEC/earnings filing shock is a core slot competitor. The only narrow branch with material prior evidence is the governance/procedural sleeve from `exp-20260504-039`, now observable through the default-off ledger from `exp-20260504-044`.

## Decision

Decision: `shadow_only`.

Expected value delta: `0.0` in `late_strong`, `mid_weak`, `old_thin`, and production because this run changed no trading path.

Next minimum action: let the default-off SEC governance/procedural paper ledger accumulate closed forward outcomes and frozen same-day alternatives. Revisit C-strategy financial-shock grading only with PIT same-accession/same-day XBRL, analyst revisions, or persisted structured LLM filing-text grades.
