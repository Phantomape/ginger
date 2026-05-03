# SEC / Earnings / Filing Shock Data Audit

Experiment: `exp-20260503-041`
Date: 2026-05-03
Mode: data audit only; no production change

## Hypothesis

SEC filing shock, financial surprise, 8-K event type, and post-earnings drift may improve C-strategy grading or A/B event confirmation, but only if point-in-time SEC/XBRL and earnings surprise fields are dense enough to tag candidates without lookahead.

This run did not test a new filing score, filter, slot tie-breaker, C-strategy rule, or production path. The single causal variable was whether new PIT-safe SEC / earnings filing-shock evidence existed after `exp-20260503-036`.

## Historical Check

Same-family work already exists:

| Experiment | Result |
|---|---|
| `exp-20260503-002` | Schema-ready but coverage-blocked. |
| `exp-20260503-004` | SEC source observability added after zero persisted SEC rows. |
| `exp-20260503-005` | SEC CIK-to-ticker mapping works on live feed. |
| `exp-20260503-006` | Broad filing scout was not alpha; 10-K/ADV branch identified. |
| `exp-20260503-011` | Liquidity-gated 10-K scout was positive but static/shadow and PIT-blocked. |
| `exp-20260503-013` | Duplicate static universe scout correctly blocked. |
| `exp-20260503-016/019/022/024/027/029/031/035/036` | Repeated data-gap guardrails; no new SEC archive depth or XBRL/companyfacts fields. |

Mechanism insight check: the playbook still ranks earnings + SEC + financial surprise first among external alpha sources, but it explicitly requires denser PIT archives or normalized XBRL/companyfacts fields before another replay. This run does not violate that guardrail because it records a no-new-evidence data gap rather than rerunning a shadow alpha variant.

## Coverage Table

| Source / artifact | Current coverage | PIT status | Notes |
|---|---:|---|---|
| `data/news_20260502.json` | 1,680 rows | Forward-observation only | Latest normalized news archive; no newer SEC archive found. |
| SEC rows in latest news archive | 300 rows | Forward-observation only | 100 each for `8-K`, `10-Q`, `10-K`. |
| SEC rows with ticker mapping | 284 / 300 | Forward-observation only | CIK mapping works for the current feed, but historical as-of mapping is not frozen. |
| `data/news_source_stats_20260502.json` | 1 file | Forward diagnostic only | No newer source stats file found. |
| `data/non_ohlcv/sec_filing_shadow_events_20260503.json` | 300 rows | Shadow only | Same table as prior audit; 0 new rows since `exp-20260503-036`. |
| Existing earnings snapshots | 137 files | PIT snapshots by snapshot date | 6,033 ticker rows; EPS estimate and surprise-history coverage both 86.16%. |
| XBRL/companyfacts normalized table | 0 files / 0 rows | Unavailable | Required for revenue, margin, FCF/NI, inventory, and receivables shock fields. |
| SEC submissions cache | 100 files | Biased static cache | Useful for adapter diagnostics, not historical replay evidence without an as-of archive ledger. |

## Field Availability

Available:

- SEC feed metadata: ticker for mapped rows, accepted/published datetime, form type, source URL, CIK-derived issuer mapping.
- Earnings snapshot fields: `days_to_earnings`, `next_earnings_date`, `eps_estimate`, `historical_surprise_pct`, `avg_historical_surprise_pct`, `positive_surprise_history`, `earnings_event_window`.

Missing for a filing-shock grading harness:

- `revenue_surprise`
- `gross_margin_delta`
- `fcf_to_net_income_gap`
- `inventory_growth`
- `receivables_growth`
- reliable `guidance_raise_cut`
- normalized `eight_k_item_type`
- stable historical as-of CIK-to-ticker ledger
- closed 5/10/20/60d forward outcomes for SEC-tagged rows

## Shadow Tagging Status

| Tag bucket | Count |
|---|---:|
| Negative filing shock | 4 |
| Unclear / missing data | 296 |
| Positive filing shock | 0 |
| No recent filing event | Not measured against historical candidates; PIT SEC archive depth is missing. |

Candidate count: 300 shadow SEC rows.

Overlap with current production/pilot universe: 1 row, `TSLA` `10-K` with tag `unclear / missing data`.

Forward returns:

| Horizon | Count | Average | Median | Win rate |
|---|---:|---:|---:|---:|
| 5d | 0 | null | null | null |
| 10d | 0 | null | null | null |
| 20d | 0 | null | null | null |
| 60d | 0 | null | null | null |

Scarce-slot opportunity cost is not measurable. One current-universe overlap row and no closed forward-return sample cannot value a slot tie-breaker.

## Baseline Metrics

No backtester replay was run for this audit because production behavior did not change. Baseline is the accepted-stack fixed-window baseline from `data/backtest_results_20260502.json` / prior experiment records.

| Window | EV | Return | PnL | Sharpe daily | Max DD | Win rate | Trades | Generated | Survived | Survival | vs SPY | vs QQQ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `late_strong` | 3.4191 | 78.60% | 78,600.33 | 4.35 | 5.41% | 78.95% | 19 | 51 | 41 | 80.39% | 73.19% | 72.80% |
| `mid_weak` | 1.4415 | 55.02% | 55,015.08 | 2.62 | 8.79% | 52.38% | 21 | 53 | 42 | 79.25% | 29.58% | 21.51% |
| `old_thin` | 0.3179 | 24.64% | 24,642.07 | 1.29 | 8.05% | 40.91% | 22 | 60 | 55 | 91.67% | 31.37% | 32.13% |

Expected value score delta: `0.0`. This is a data audit only; no production/core strategy metric changed.

## Decision

Decision: `data_gap`.

The SEC/earnings filing-shock family remains conceptually valid, but this run found no new PIT-safe evidence after `exp-20260503-036`. Another same-archive shadow replay would only repeat the known blocker.

Production impact:

- `shared_policy_changed`: false
- `backtester_adapter_changed`: false
- `run_adapter_changed`: false
- `production_signal_path_changed`: false
- `replay_only`: true
- `parity_test_added`: false
- `production_impact`: data audit only

Next minimum action: wait for at least 5-10 new forward SEC archive days with ticker tags, or add a default-off PIT XBRL/companyfacts field-fill adapter, before rerunning filing-shock grading, breakout confirmation, or scarce-slot value tests.
