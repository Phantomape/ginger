# SEC / earnings / filing shock no-new-evidence audit

Experiment: `exp-20260504-024`  
Decision: `data_gap`  
Run mode: duplicate guardrail data audit, no production change.

## Hypothesis
SEC filing shock, financial surprise, 8-K event type, and post-earnings drift may improve C-strategy grading or A/B event confirmation. This run only checks whether new PIT-safe SEC/earnings evidence exists after `exp-20260504-023`.

## Historical check
Same-family experiments already cover the current files: `exp-20260504-021` synthesized SEC/earnings availability and prior branches, `exp-20260504-022` found a residual other-filing mild-negative branch that was shadow-positive but not production-promotable, and `exp-20260504-023` decomposed that residual branch into a sample-limited semantic subcategory. Earlier branches rejected raw positive results-8K drift, simple Companyfacts scoring, positive-language text, and agreement/debt event packets.

Mechanism insight guardrail: this is not a single-field C-strategy repair and not a reaction-threshold retry. The only valid next information is LLM/document semantic grading, forward replacement-value evidence, or richer PIT financial surprise fields.

## Coverage table
| Source | Coverage | PIT status | Blocker |
| --- | ---: | --- | --- |
| Current SEC Atom feed in `data/news_20260503.json` | 300 SEC items, 284 ticker-mapped | PIT current observation | No closed 5/10/20/60d returns yet |
| Historical SEC submissions | 1,286 rows, 1,286 accepted-at rows | Public EDGAR accepted-at proxy | Not proof local production observed them |
| SEC companyfacts selected fields | 17,109 rows, 51 mapped CIKs | Filed-date proxy | Sparse same-accession event linkage |
| SEC Item 2.02 filing text | 306 rows, 48 tickers | Public filing text replay context | Needs semantic grading before ranking |
| Earnings snapshots | 138 files, 6,081 ticker rows | Production snapshots from 2025-10-23 | Older fixed windows remain limited |

## Shadow metrics
| Tag / branch | Candidates | Forward return | Overlap / slot value | Interpretation |
| --- | ---: | --- | --- | --- |
| A no recent filing event | not measured | n/a | n/a | Missing complete candidate dump |
| B positive filing shock | 21 | 10d excess -1.828 pp | slot proxy -9.8719 pp | Rejected as C-strategy revival |
| C negative filing shock | 16 text / 25 leadership | 10d excess +4.7408 pp text, +3.8135 pp leadership | active-slot proxy +0.9943 pp text, leadership slot proxy -6.9495 pp | Best remaining shadow family, not production-ready |
| D unclear / missing data | 296 rows in existing table | n/a | one production/pilot overlap row | Mostly missing semantic/XBRL/candidate context |
| Residual other-filing mild-negative | 22 | 10d excess +2.5478 pp, 20d +2.5426 pp | 4 A/B overlaps; 2 replacement samples avg -9.7802 pp | Shadow-positive, not promoted |
| Residual semantic split | sample-limited | see `exp-20260504-023` | not production-promoted | Needs more samples or LLM grading |

## Decision
`data_gap`: no new closed PIT-safe evidence exists after `exp-20260504-023`. Existing SEC/earnings data remains useful for shadow research, but this run adds no production candidate and no default-on ranking/filtering rule.

## Next minimal action
Run LLM semantic grading on frozen residual/negative SEC filing text packets, or wait for forward queue replacement-value outcomes. Do not rerun same-sample reaction, Companyfacts score, keyword, or hard-coded item-code sweeps.
