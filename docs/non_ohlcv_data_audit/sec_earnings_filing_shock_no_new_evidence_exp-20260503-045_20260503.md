# SEC / Earnings / Filing-Shock Data Audit

Experiment: `exp-20260503-045`
Date: 2026-05-03
Decision: `data_gap`
Production impact: `data_audit_only`

## Hypothesis

SEC filing shock, financial surprise, 8-K item type, and post-earnings drift
may improve C-strategy grading or serve as an event confirmation overlay for
`trend_long` / `breakout_long`. This run only checked whether new PIT-safe
evidence arrived after `exp-20260503-041`.

## Historical Check

This is the same mechanism family already covered by:

| Experiment | Result |
|---|---|
| `exp-20260503-002` | Schema-ready earnings + SEC surprise round; coverage-blocked. |
| `exp-20260503-004` | SEC source observability audit; prior archives had zero persisted SEC rows. |
| `exp-20260503-005` | SEC CIK-to-ticker mapping works on live SEC rows. |
| `exp-20260503-006` | Broad filing scout was not alpha; 10-K / ADV branch identified. |
| `exp-20260503-011` | Liquidity-gated 10-K scout was shadow-positive but static/PIT-blocked. |
| `exp-20260503-013` | Duplicate static universe scout blocked without new PIT evidence. |
| `exp-20260503-016/019/022/024/027/029/031/035/036/041` | Repeated no-new-evidence SEC/earnings filing-shock audits. |

Mechanism insight check: `docs/alpha-optimization-playbook.md` ranks
earnings + SEC + financial surprise as the top external alpha source, but only
after new PIT archive depth or normalized XBRL/companyfacts fields exist. This
run found neither.

## Coverage Table

| Source / field family | Current coverage | PIT status | Use now |
|---|---:|---|---|
| Latest SEC archive | `data/news_20260502.json` | Forward-observation PIT timestamp exists | Audit only |
| SEC rows | 300 | One forward archive only | Audit only |
| SEC rows with ticker | 284 | Uses current CIK map; historical as-of map missing | Audit only |
| SEC form mix | 100 `8-K`, 100 `10-Q`, 100 `10-K` | Feed rows have accepted timestamps | Audit only |
| Current production/pilot overlap | 1 row (`TSLA` `10-K`) | No closed forward return | Not enough for slot value |
| Filing shock tags | 296 unclear, 4 negative | Body/XBRL parse missing | Not enough for grading |
| Earnings snapshots | 137 files, 6033 ticker rows | Walk-forward snapshots exist | Usable for EPS/surprise only |
| EPS estimate / surprise history | 5198 rows each, 86.16% coverage | Snapshot-backed | Usable with sparsity warning |
| XBRL/companyfacts financials | 0 rows | Missing | Data gap |
| Revenue / margin / FCF / inventory / receivables | 0 rows | Missing | Data gap |

## PIT Risk

The SEC shadow rows have accepted timestamps for the single forward archive,
but canonical historical replay is not PIT-safe yet. The blockers are:

- no new SEC source archive after `data/news_20260502.json`
- no new `news_source_stats` after `data/news_source_stats_20260502.json`
- no normalized XBRL/companyfacts table
- no stable historical as-of CIK-to-ticker ledger
- no closed 5/10/20/60d forward returns for the SEC-tagged rows

Do not use `period_end_date` as a tradable date. This audit only uses
accepted/published timestamps and the existing `usable_trade_date` shadow field.

## Shadow Metrics

| Metric | Value |
|---|---:|
| Existing shadow rows | 300 |
| New rows since `exp-20260503-041` | 0 |
| Ticker-mapped rows | 284 |
| Unique tickers | 279 |
| Existing production/pilot overlap | 1 |
| Tagged candidates with closed 5d return | 0 |
| Tagged candidates with closed 10d return | 0 |
| Tagged candidates with closed 20d return | 0 |
| Tagged candidates with closed 60d return | 0 |
| Scarce-slot value measurable | false |

The only current-universe overlap row remains `TSLA`, event date
`2026-04-30`, usable trade date `2026-05-01`, form `10-K`, tag
`unclear / missing data`, reason `statement_without_xbrl_metric_parse`.

## Baseline Metrics

No production or replay metric changed. The accepted-stack baseline remains:

| Window | EV | Return | PnL | Sharpe daily | Max DD | Win rate | Trades | Signals generated/survived | Survival | vs SPY | vs QQQ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `late_strong` | 3.4191 | 78.60% | 78600.33 | 4.35 | 5.41% | 78.95% | 19 | 51 / 41 | 80.39% | 73.19% | 72.80% |
| `mid_weak` | 1.4415 | 55.02% | 55015.08 | 2.62 | 8.79% | 52.38% | 21 | 53 / 42 | 79.25% | 29.58% | 21.51% |
| `old_thin` | 0.3179 | 24.64% | 24642.07 | 1.29 | 8.05% | 40.91% | 22 | 60 / 55 | 91.67% | 31.37% | 32.13% |

Expected value score delta: `0.0`.

## Conclusion

Decision: `data_gap`.

This branch remains plausible, but a replay now would only measure archive
sparsity. The next minimum action is either:

1. accumulate at least 5-10 new forward SEC archive days with ticker tags and
   closed forward returns, or
2. add a default-off PIT XBRL/companyfacts field-fill adapter before rerunning
   filing-shock grading, breakout confirmation, or scarce-slot value tests.
