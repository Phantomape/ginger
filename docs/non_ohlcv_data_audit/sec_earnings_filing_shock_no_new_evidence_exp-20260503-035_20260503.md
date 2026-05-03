# SEC / earnings / filing shock data audit (exp-20260503-035)

## Decision

`data_gap`. This run found no new PIT-safe SEC / XBRL / companyfacts evidence after `exp-20260503-031`, so it did not run a new shadow replay and did not touch production strategy code.

## Hypothesis

SEC filing shock, financial surprise, 8-K event type, and post-earnings drift may improve `earnings_event_long` grading or provide event confirmation for `trend_long` / `breakout_long` candidates. This remains plausible, but the current local evidence is still too sparse to evaluate.

## Historical Check

Exact prior same-family run: `exp-20260503-031`, also `data_gap`.

Same-family records checked: `exp-20260503-002`, `004`, `005`, `006`, `011`, `013`, `016`, `019`, `022`, `024`, `027`, `029`, `031`.

Mechanism insight: the playbook ranks earnings + SEC + financial surprise as the top external alpha source, but explicitly blocks nearby C-strategy single-field/checklist repairs and same-archive filing replay variants until PIT archive density or normalized XBRL/companyfacts fields improve.

## Coverage Table

| Source | Current coverage | PIT status | Blocking gap |
|---|---:|---|---|
| `data/news_20260502.json` SEC rows | 300 rows, 284 ticker-mapped | PIT-safe forward observation only | No new archive after 2026-05-02 |
| SEC source diagnostics | 1 file, 8-K/10-Q/10-K all HTTP 200 | PIT-safe for current feed diagnostics | No multi-day diagnostics history |
| SEC submissions cache | 100 CIK files | Static cache, not PIT replay evidence | No as-of CIK/ticker ledger |
| Earnings snapshots | 137 files, 6033 ticker rows | PIT-like local snapshots from 2025-10-23 to 2026-05-01 | No revenue/gross-margin/FCF/inventory/receivables shock fields |
| XBRL/companyfacts normalized table | 0 rows | unavailable | Adapter/schema still missing |
| Shadow filing table | 300 rows, 279 unique tickers | Forward archive only | Only 1 production/pilot overlap row |

## Tagged Candidate Forward Returns

| Tag cohort | 5d | 10d | 20d | 60d | Status |
|---|---:|---:|---:|---:|---|
| no recent filing event | n/a | n/a | n/a | n/a | Not measured; no replay sample |
| positive filing shock | n/a | n/a | n/a | n/a | No normalized XBRL/companyfacts shock fields |
| negative filing shock | n/a | n/a | n/a | n/a | 4 tags in shadow table, no closed forward sample |
| unclear / missing data | n/a | n/a | n/a | n/a | 296 tags, mostly missing parsed body metrics |

## Slot Conflict Audit

Only one current production/pilot universe overlap exists in the shadow SEC table: `TSLA` `10-K`, event date `2026-04-30`, usable trade date `2026-05-01`, tag `unclear / missing data`. There is no PIT-safe historical overlap with accepted candidates, so scarce-slot opportunity cost and slot conflict value are not measurable.

## Production Impact

None. `shared_policy_changed=false`, `backtester_adapter_changed=false`, `run_adapter_changed=false`, `parity_test_added=false`, `replay_only=true` for audit classification only. The run did not touch `quant/signal_engine.py`, `quant/risk_engine.py`, `quant/portfolio_engine.py`, `quant/run.py`, or `quant/backtester.py`.

## Next Minimum Action

Wait for 5-10 new forward SEC archive days with ticker tags, or add a default-off PIT XBRL/companyfacts field-fill adapter before retrying filing-shock grading, breakout confirmation, or scarce-slot value tests.
