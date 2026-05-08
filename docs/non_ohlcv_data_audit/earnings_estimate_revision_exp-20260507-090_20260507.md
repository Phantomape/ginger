# Earnings Estimate Revision Data Audit (exp-20260507-090)

## Decision

`data_gap` for analyst-revision alpha. Local earnings snapshots have broad EPS/surprise field coverage, but they are not a point-in-time analyst-estimate revision history and cannot support production or default-off replay evidence for estimate revisions.

## Hypothesis

Daily EPS estimate snapshots might support a PIT analyst-revision / earnings-quality shadow tag for existing `trend_long` and `breakout_long` candidates.

## Mechanism Family

`analyst_estimate_revision_earnings_quality_overlay`

## Single Causal Variable

`EPS estimate snapshot revision availability and PIT status`

## Data Source

Local `data/earnings_snapshot_YYYYMMDD.json` files generated from yfinance earnings-date data via `quant/backfill_earnings_snapshots.py` and `quant/earnings_snapshot.py`.

## Coverage

- Snapshot files: 417 (`earnings_snapshot_20241002.json` -> `earnings_snapshot_20260506.json`)
- Unique tickers: 48
- Total ticker rows: 18645
- EPS estimate coverage: 15850 rows (85.01%)
- Surprise-history coverage: 15850 rows (85.01%)
- Snapshot files whose file mtime is after snapshot date: 403

Window coverage:

| Window | Snapshot files | EPS estimate coverage | Surprise coverage |
|---|---:|---:|---:|
| late_strong | 129 | 86.17% | 86.17% |
| mid_weak | 131 | 84.44% | 84.44% |
| old_thin | 145 | 84.44% | 84.44% |

## PIT Status

`biased_for_revision_alpha`.

Critical blockers:

- Historical snapshot files were written after their simulated as-of dates for 403 files.
- Backfill prefetched one current yfinance earnings dataset per ticker and projected it across historical dates; that is not a historical analyst-estimate tape.
- Snapshot schema omits `next_earnings_date` and `fiscal_period`, so an EPS estimate change cannot be tied to the same earnings event.
- Snapshot schema omits `estimate_asof_datetime`, `vendor_asof`, and source identifiers.

## Revision Feasibility

- Tickers with EPS observations: 41
- Tickers with any EPS value change: 39
- Total EPS value changes detected: 401
- Same-event revision identifiable: `false`

These value changes are not valid alpha evidence because they may reflect event roll-forward rather than same-quarter estimate revision, and the historical estimate values are not PIT.

## Accepted Candidate Coverage

- Accepted A/B trades audited: 62
- Unique accepted tickers: 30
- Trades with snapshot row: 62
- Trades with EPS estimate: 50 (80.65%)
- Trades with surprise history: 50 (80.65%)

Biased audit-only grouping, not production evidence:

| Group | Trades | Avg PnL % | Win rate | Total PnL |
|---|---:|---:|---:|---:|
| has EPS estimate | 50 | 4.03% | 48.00% | $102,806.05 |
| no EPS estimate | 12 | 8.92% | 91.67% | $55,451.43 |
| positive avg surprise history | 45 | 3.81% | 48.89% | $88,272.37 |
| not positive or missing surprise | 17 | 8.09% | 76.47% | $69,985.11 |

The biased grouping does not support a bullish EPS-availability or positive-surprise overlay. More importantly, it cannot answer the intended analyst-revision question.

## Production Impact

None. No production signal path, backtester path, run adapter, sizing, risk, ranking, entry, exit, LLM, or universe logic changed.

## Next Minimum Action

Add a default-off forward estimate-revision ledger that persists, for every daily production snapshot:

- `ticker`
- `as_of_date`
- `source_retrieved_at`
- `vendor_asof` if available
- `next_earnings_date`
- `fiscal_period`
- `eps_estimate`
- `revenue_estimate` if available
- `prior_snapshot_eps_estimate`
- `eps_estimate_delta_7d / 30d`
- `pit_safe_flag`

Only after 30-60 forward trading days should Ginger evaluate whether revision tags improve A/B candidate forward returns or scarce-slot replacement value.
