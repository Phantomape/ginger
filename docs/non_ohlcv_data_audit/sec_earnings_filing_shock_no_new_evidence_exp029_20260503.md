# SEC / Earnings Filing Shock No-New-Evidence Recheck (exp-20260503-029)

Generated: 2026-05-03T12:07:39+00:00

## Decision

`data_gap`. No production path, signal path, ranking, sizing, entry, exit, LLM/news replay, or OHLCV threshold was changed.

## Hypothesis

SEC filing shock, financial surprise, 8-K event type, and post-earnings drift may improve `earnings_event_long` grading or provide event confirmation for `trend_long` / `breakout_long` candidates. This run did not test a new alpha rule; it only checked whether new point-in-time evidence exists after `exp-20260503-027`.

## Historical Check

Same-family runs already exist: `exp-20260503-002`, `004`, `005`, `006`, `011`, `013`, `016`, `019`, `022`, `024`, and `027`. The latest exact prior run, `exp-20260503-027`, was also `data_gap` because the repo had one forward SEC archive, no PIT XBRL/companyfacts table, and no closed forward-return sample.

This run found no new local evidence after `exp-20260503-027`, so replaying filing severity, 8-K item type, C-strategy grading, breakout confirmation, or scarce-slot tie-breaker variants would be a duplicate same-archive rerun.

## Coverage Table

| Source | Current coverage | PIT status | Use now |
|---|---:|---|---|
| News archives | 31 files; latest `data/news_20260502.json` | Forward archive only | Observation only |
| SEC source stats | 1 file; latest `data/news_source_stats_20260502.json` | Forward diagnostics only | Coverage audit |
| SEC shadow events | 300 rows, 284 ticker mapped, 279 unique tickers | Source timestamp exists for one archive; historical replay not PIT-safe | Shadow table only |
| Production/pilot overlap | 1 rows | Too sparse | No slot conclusion |
| Earnings snapshots | 137 files, 86.16% EPS-estimate coverage | Snapshot archive exists | Can support EPS fields only |
| XBRL/companyfacts financial fields | 0 normalized rows | Missing | Blocked |

SEC source diagnostics from `data/news_source_stats_20260502.json`:

| Form | Parsed | With CIK | With ticker | Without ticker | Status |
|---|---:|---:|---:|---:|---:|
| 10-K | 100 | 100 | 98 | 2 | 200 |
| 10-Q | 100 | 100 | 91 | 9 | 200 |
| 8-K | 100 | 100 | 95 | 5 | 200 |

## Shadow Candidate Metrics

| Metric | Value |
|---|---:|
| Candidate count | 300 existing rows |
| New rows since `exp-20260503-027` | 0 |
| Current production/pilot universe overlap | 1 row |
| Historical A/B signal overlap | blocked |
| Forward 5/10/20/60d returns | blocked; no closed forward sample |
| Scarce-slot opportunity cost | not measurable |

Form counts: `{"10-K": 100, "10-Q": 100, "8-K": 100}`

Shock tags: `{"negative filing shock": 4, "unclear / missing data": 296}`

Overlap sample: `[{"event_date": "2026-04-30", "filing_shock_reason": "statement_without_xbrl_metric_parse", "filing_shock_tag": "unclear / missing data", "form_type": "10-K", "ticker": "TSLA", "usable_trade_date": "2026-05-01"}]`

## Baseline Metrics

No replay was run because this is a data audit only. Baseline accepted fixed-window metrics remain:

| Window | EV | Return | PnL | Sharpe daily | Max DD | Win rate | Trades | Generated | Survived | Survival | vs SPY | vs QQQ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 78.60% | $78,600.33 | 4.35 | 5.41% | 78.95% | 19 | 51 | 41 | 80.39% | 73.19% | 72.80% |
| mid_weak | 1.4415 | 55.02% | $55,015.08 | 2.62 | 8.79% | 52.38% | 21 | 53 | 42 | 79.25% | 29.58% | 21.51% |
| old_thin | 0.3179 | 24.64% | $24,642.07 | 1.29 | 8.05% | 40.91% | 22 | 60 | 55 | 91.67% | 31.37% | 32.13% |

## PIT Risk

The current SEC rows are useful for forward observation because accepted timestamps and source URLs exist in the archived rows. They are not enough for historical replay because the canonical windows do not have daily append-only SEC archives with as-of CIK/ticker mapping and parsed XBRL fields.

Do not use fiscal period end as a tradable date. Do not treat the static SEC submissions cache or latest company ticker map as proof of historical eligibility.

## Next Minimum Action

Accumulate 5-10 new forward SEC archive days with ticker tags, or add a default-off PIT XBRL/companyfacts field-fill adapter. Only then rerun filing-shock grading, breakout confirmation, or scarce-slot value tests.
