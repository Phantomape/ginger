# SEC / Earnings / Filing Shock Post-Exp051 Audit

Experiment: `exp-20260504-052`  
Run type: data audit + shadow-tagging guardrail  
Production impact: none

## Hypothesis

SEC filing shock and earnings surprise may improve `earnings_event_long` grading or act as an event confirmation overlay for `trend_long` / `breakout_long`, but only if fresh PIT-safe evidence exists after `exp-20260504-051`.

## Historical Check

This exact mechanism family has already been audited repeatedly. The latest relevant records are:

| Experiment | Result | Implication |
|---|---|---|
| `exp-20260504-040` | `default_off_candidate` | Broad SEC/earnings filing-shock tuning was exhausted; governance/procedural cells were the only positive branch. |
| `exp-20260504-049` | `promising_replay_only` | Default-off external event bundle improved aggregate EV by 23.29%, but needs forward replacement-value evidence. |
| `exp-20260504-050` | `data_gap` | Normalized filing-shock shadow table exists, but financial shock fields are null. |
| `exp-20260504-051` | `accepted_observe_only` | SEC negative-reaction paper ledger schema/path is now production-visible, but has no closed outcomes yet. |

Mechanism guardrail: do not rerun raw 8-K reaction thresholds, stale Companyfacts buckets, or filing-text keyword variants on the same sample. A valid retry needs forward paper outcomes, PIT same-accession financial fields, analyst revisions, or persisted LLM filing grades.

## Coverage Table

| Source | Coverage | PIT status | Current blocker |
|---|---:|---|---|
| SEC filing events | 1,286 rows | `accepted_at` is a PIT proxy, but backfill is not proof production observed it daily | No fresh post-`exp051` archive and no same-day replacement outcomes |
| SEC Companyfacts | 17,109 rows | PIT as stale background by filed date | Same-accession shock coverage still missing |
| SEC filing text | 306 rows | Usable after accepted timestamp | Keyword scoring already tested; needs structured LLM grades |
| Earnings snapshots | 138 files, last `20260503` | PIT production snapshots for covered dates | No `earnings_snapshot_20260504.json`; no revenue/margin/FCF/inventory/receivables surprise fields |
| Normalized filing-shock table | 300 rows | Timestamp-safe shadow table | 296/300 unclear, 0 positive shock rows, all financial shock fields null |
| SEC negative paper ledger | schema/code present | Default-off observe-only | No `data/sec_negative_event_sleeve_paper_state.json` or snapshots yet |

## Shadow Tags

| Tag | Count | Forward 5/10/20/60d return |
|---|---:|---|
| A. no recent filing event | 0 | Not measured |
| B. positive filing shock | 0 | Not measured |
| C. negative filing shock | 4 | Not computable: no new closed paper/outcome sample |
| D. unclear / missing data | 296 | Not useful for grading; financial shock fields are null |

Current production snapshot `data/quant_signals_20260503.json` has 0 new trade candidates, 0 pilot candidates, and SEC negative queue `candidate_count=0`. It was generated before `exp-20260504-051`, so it has no `sec_negative_event_sleeve` field.

## Slot Conflict Audit

Slot value is not computable this run:

- current trade candidates: 0
- current SEC negative queue candidates: 0
- normalized shadow table overlap with production/pilot universe: 1 row
- closed SEC negative paper outcomes after `exp051`: 0

The positive evidence remains `exp-20260504-049` at the event-bundle level, not a fresh C-strategy filing-shock grading result.

## Decision

Decision: `data_gap`.

Do not enter a default-off C strategy grading harness yet. The next minimum action is to let the post-`exp051` SEC negative paper ledger accumulate real forward state and closed outcomes, or add PIT same-accession XBRL / analyst revision / structured LLM filing-grade data.
