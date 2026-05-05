# SEC / Earnings / Filing Shock No-New-Evidence Audit (exp-20260504-048)

## Decision

`data_gap`. No production signal, ranking, sizing, order, backtester, run adapter, risk, or portfolio path changed.

## Hypothesis

SEC filing shock, earnings surprise, and filing-context events may improve C-strategy grading or A/B event confirmation only if fresh point-in-time evidence exists beyond `exp-20260504-046`.

## Historical Check

This family has already been exercised heavily:

- `exp-20260504-040`: broad SEC/earnings filing-shock consolidation; only governance/procedural events remained as a default-off candidate.
- `exp-20260504-044`: allowed follow-up added an observe-only default-off SEC governance/procedural queue plus paper ledger.
- `exp-20260504-046`: fresh-evidence guardrail found no new PIT-safe SEC/earnings evidence beyond the queue path.
- `exp-20260504-047`: unrelated A/B sleeve isolation; it did not add SEC/earnings evidence.

This run is not a same-sample replay. It only checks whether fresh evidence arrived after `exp-20260504-046`.

## Coverage Table

| Source | Coverage | PIT Status | Blocking Gap |
|---|---:|---|---|
| SEC submissions | 1,286 rows | `accepted_at` / `accepted_datetime` is a public EDGAR timestamp proxy | backfill does not prove live observation |
| SEC filing text | 306 Item 2.02 8-K rows | replayable after accepted timestamp | keyword scoring already exhausted; needs structured grades |
| SEC Companyfacts | 17,109 rows | filed date is PIT-safe for background facts | stale for immediate 8-K grading; prior same-accession packet had `0/16` rows |
| Earnings snapshots | 138 files; 6,081 ticker rows | production snapshots through `20260503` | no `earnings_snapshot_20260504.json` |
| Current SEC shadow table | 300 rows; 284 ticker-mapped | timestamp-safe shadow rows | financial-shock fields remain null |

Fresh file check after the prior guardrail:

| File | Present |
|---|---:|
| `data/news_20260504.json` | no |
| `data/news_source_stats_20260504.json` | no |
| `data/earnings_snapshot_20260504.json` | no |
| `data/sec_event_sleeve_paper_state.json` | no |
| `data/sec_event_sleeve_paper_snapshots.jsonl` | no |

## Shadow Event Table

The existing shadow table at `data/non_ohlcv/sec_filing_shadow_events_20260503.json` was reused. It already contains the required schema fields, but not the financial-shock values needed for C-strategy grading.

| Tag | Rows |
|---|---:|
| positive filing shock | 0 |
| negative filing shock | 4 |
| unclear / missing data | 296 |
| no recent filing event | 0 |

Non-null field audit:

| Field | Non-null rows |
|---|---:|
| accepted datetime | 300 |
| usable trade date | 300 |
| PIT flag | 300 |
| 8-K item type | 100 |
| EPS surprise | 0 |
| Revenue surprise | 0 |
| Gross margin delta | 0 |
| FCF-to-net-income gap | 0 |
| Inventory growth | 0 |
| Receivables growth | 0 |
| Guidance raise/cut | 0 |

## Tagged Candidates And Slot Value

Current candidate count is `0` for this recheck. There are no fresh Ginger candidates to tag, no overlap with existing signals, and no computable scarce-slot opportunity cost.

Existing historical context remains unchanged:

| Packet | Evidence | Decision |
|---|---:|---|
| All inferred earnings events (`exp-20260504-002`) | 68 valid 10d, avg 10d excess `-0.7036%` | not promoted |
| Filing text all events (`exp-20260504-007`) | 218 valid 10d, avg 10d excess `+0.6779%` | observed-only |
| Leadership-change negative reaction (`exp-20260504-015/018`) | avg 10d excess `+3.8135%`, but replacement proxy `-6.9495%` | shadow-promising, not promoted |
| Other-filing mild negative (`exp-20260504-022`) | avg 10d excess `+2.5478%`, replacement proxy `-9.7802%` | shadow-promising, not promoted |
| Governance/procedural overlay (`exp-20260504-039`) | 13 event trades, PnL `+$7,333.02` | default-off forward ledger only |

No new 5/10/20/60d forward-return evidence was generated.

## Baseline Metrics

| Window | EV | Return | PnL | Sharpe daily | Max DD | Win rate | Trades | Generated / Survived | Survival | vs SPY | vs QQQ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 78.60% | $78,600.33 | 4.35 | 5.41% | 78.95% | 19 | 51 / 41 | 80.39% | +73.19pp | +72.80pp |
| mid_weak | 1.4415 | 55.02% | $55,015.08 | 2.62 | 8.79% | 52.38% | 21 | 53 / 42 | 79.25% | +29.58pp | +21.51pp |
| old_thin | 0.3179 | 24.64% | $24,642.07 | 1.29 | 8.05% | 40.91% | 22 | 60 / 55 | 91.67% | +31.37pp | +32.13pp |

Expected-value delta for this audit: `0.0` in all windows.

## Next Minimum Action

Do not rerun this SEC/earnings filing-shock family until at least one of these exists: closed forward SEC governance/procedural paper outcomes, same-accession PIT XBRL fields, PIT analyst revisions, or persisted structured LLM filing-text grades joined to forward outcomes.
