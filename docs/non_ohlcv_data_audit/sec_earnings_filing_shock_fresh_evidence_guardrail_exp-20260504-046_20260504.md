# SEC / Earnings / Filing Shock Fresh-Evidence Guardrail (exp-20260504-046)

## Decision

`data_gap`. No production signal, ranking, sizing, order, backtester, run adapter, risk, or portfolio path changed.

## Hypothesis

SEC filing shock, earnings surprise, and 8-K filing context may improve C-strategy grading or A/B event confirmation, but only if fresh PIT-safe evidence exists beyond the existing SEC governance queue and duplicate-guardrail audits.

## Historical Check

This direction has already been heavily tested today:

- `exp-20260504-002`: earnings + nearby SEC results filing + price reaction packet was observed-only and not promoted.
- `exp-20260504-004`: Companyfacts financial-quality scoring was rejected as non-monotonic/stale.
- `exp-20260504-007`: SEC filing-text keyword/language proxy was observed-only; useful as LLM input, not standalone alpha.
- `exp-20260504-014`: Companyfacts context had `0/16` same-accession rows for the negative-reaction packet.
- `exp-20260504-019`: agreement/debt packet was rejected.
- `exp-20260504-039`: governance/procedural overlay was positive, but only as a follow-up/default-off candidate.
- `exp-20260504-044`: the allowed follow-up already added an observe-only default-off governance/procedural paper ledger.
- `exp-20260504-045`: an ID collision exists between an Energy ETF ticket/log and a SEC duplicate-guardrail artifact, so this run uses a fresh ID.

## Coverage Table

| Source | Coverage | PIT Status | Blocking Gap |
|---|---:|---|---|
| SEC submissions | 1,286 rows; 969 8-K | `accepted_at` is public-PIT proxy | Backfill does not prove live pipeline observation |
| SEC filing text | 306 Item 2.02 8-K rows; 1,224 docs; 12,024,232 chars | replayable after accepted timestamp | keyword scoring exhausted; needs structured LLM grades |
| SEC Companyfacts | 17,109 rows | filed date is PIT proxy | stale for immediate 8-K grading; prior same-accession coverage `0/16` |
| Earnings snapshots | 138 files; 6,081 ticker rows; 5,239 EPS/surprise rows | production snapshots, mostly late-window | older/mid windows lack snapshot-backed fields |
| Current shadow table | 300 rows; 300 PIT-safe timestamps | timestamp-safe shadow table | financial-shock fields are all null |

Current shadow table non-null field audit:

| Field family | Non-null rows |
|---|---:|
| accepted datetime / usable trade date / PIT flag | 300 / 300 |
| 8-K item type | 100 / 300 |
| EPS surprise | 0 / 300 |
| Revenue surprise | 0 / 300 |
| Gross margin delta | 0 / 300 |
| FCF-to-net-income gap | 0 / 300 |
| Inventory growth | 0 / 300 |
| Receivables growth | 0 / 300 |
| Guidance raise/cut | 0 / 300 |

## Tagged Candidates And Forward Returns

Current production candidate tagging is blocked: the latest current-candidate audit had `candidate_count=0`, so overlap and forward returns are not computable for live Ginger candidates.

Existing historical packets remain the relevant evidence:

| Packet | Count | 10d excess return | Slot/overlap evidence | Decision |
|---|---:|---:|---|---|
| All inferred earnings events (`exp-20260504-002`) | 68 valid 10d | -0.7036% avg | not promoted | rejected/observed-only |
| Filing text all Item 2.02 events (`exp-20260504-007`) | 218 valid 10d | +0.6779% avg | keyword layer not promotion-quality | observed-only |
| Positive filing text language (`exp-20260504-007`) | 62 valid 10d | -1.2674% avg | not useful as C-grade | observed-only |
| Leadership-change negative reaction (`exp-20260504-015/018`) | 23 valid 10d | +3.8135% avg | 12% A/B overlap; replacement proxy -6.9495% | shadow-promising, not promoted |
| Agreement/debt packet (`exp-20260504-019`) | 38 valid 10d | -0.8619% avg | unstable by window | rejected |
| Other-filing mild negative (`exp-20260504-022`) | 20 valid 10d | +2.5478% avg | 18.18% A/B overlap; replacement proxy -9.7802% | shadow-promising, not promoted |
| Governance/procedural overlay (`exp-20260504-039`) | 24 candidates / 13 trades | event PnL +$7,333.02 | satellite overlay, not core slot tie-breaker | default-off follow-up only |

No new 60d forward-return evidence was generated in this run. A default-off replay would need a frozen runner that records 5/10/20/60d outcomes.

## Slot Conflict Audit

- Current Ginger candidate overlap: `0`, because no current new-trade candidates were available in the prior current-candidate tag audit.
- Leadership-change branch: `3` same-day A/B overlaps (`12%`), replacement proxy average `-6.9495%`.
- Other-filing mild-negative branch: `4` same-day A/B overlaps (`18.18%`), replacement proxy average `-9.7802%`.
- Governance/procedural branch: best current candidate, but it is a satellite/default-off paper-ledger path, not a core scarce-slot tie-breaker yet.

## Baseline Metrics

| Window | EV | Return | PnL | Sharpe daily | Max DD | Win rate | Trades | Generated / Survived | Survival | vs SPY | vs QQQ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 78.60% | $78,600.33 | 4.35 | 5.41% | 78.95% | 19 | 51 / 41 | 80.39% | +73.19pp | +72.80pp |
| mid_weak | 1.4415 | 55.02% | $55,015.08 | 2.62 | 8.79% | 52.38% | 21 | 53 / 42 | 79.25% | +29.58pp | +21.51pp |
| old_thin | 0.3179 | 24.64% | $24,642.07 | 1.29 | 8.05% | 40.91% | 22 | 60 / 55 | 91.67% | +31.37pp | +32.13pp |

Expected-value delta for this audit: `0.0` in all windows.

## Next Minimum Action

Let the default-off SEC governance/procedural paper ledger accumulate closed forward outcomes and frozen same-day alternatives. Only revisit C-strategy grading with PIT same-accession XBRL, analyst revisions, or persisted structured LLM filing-text grades.
