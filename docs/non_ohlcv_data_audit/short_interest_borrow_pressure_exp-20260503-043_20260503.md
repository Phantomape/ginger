# Short Interest / Borrow Pressure Data Audit

Experiment: `exp-20260503-043`
Run time: `2026-05-03T17:06:51+00:00`
Decision: `data_gap`
Production impact: `data_audit_only`

## Hypothesis

High short interest alone is not a long signal. The plausible Ginger use case is an overlay on existing candidates:

- `squeeze_setup_score`: high short crowding plus existing `breakout_long` / `trend_long` strength or positive event context.
- `fragile_short_score`: high short crowding plus negative filing, news, or earnings context.

This run did not test alpha. It only rechecked whether new point-in-time short interest or borrow-pressure evidence exists after `exp-20260503-039`.

## Mechanism Family

`short_interest_borrow_pressure_overlay`

This belongs to candidate overlay / ranking / risk context, not standalone entry. It does not belong in the production signal path until real point-in-time rows exist and a default-off shadow replay is positive across the canonical windows.

## Historical Experiment Check

Exact prior same-family records already exist: `exp-20260503-015`, `018`, `021`, `023`, `028`, `032`, `034`, `038`, and `039`.

Prior result: `0` structured short-interest rows, `0` FINRA adapter/files, `0` paid borrow rows, `0` PIT-safe rows, `0` usable trade-date rows, and `0` taggable candidates.

Mechanism insight check: `docs/alpha-optimization-playbook.md` ranks short interest / borrow pressure as a valid external overlay source, but only as shadow-quality until PIT data exists. It explicitly warns not to treat FINRA daily short volume as short interest.

This run is not a simple rerun because it does not rerun shadow scoring. It only checks for new local evidence after `exp-20260503-039`.

## Data Availability

Required fields: `ticker`, `settlement_date`, `publication_date`, `short_interest`, `short_interest_float`, `days_to_cover`, `short_interest_change`, `borrow_fee`, `shares_available`, `hard_to_borrow`, `daily_short_volume`, `total_volume`, `daily_short_volume_ratio`, `usable_trade_date`, `pit_safe`.

| Check | Result |
|---|---:|
| Structured short-interest files | 0 |
| Specific short/borrow field matches in `data` | 0 |
| FINRA adapter/files | 0 |
| FINRA daily short-volume files | 0 |
| Paid borrow files | 0 |
| Borrow-fee rows | 0 |
| Shares-available rows | 0 |
| Hard-to-borrow rows | 0 |
| Usable trade-date rows | 0 |
| PIT-safe short/borrow rows | 0 |
| Data / quant / script filename or adapter matches | 0 |
| `data/non_ohlcv` short/borrow files | 0 |
| News/archive files checked | 92 |
| Unstructured headline matches | 184 |
| Files with unstructured headline matches | 37 |

`data/non_ohlcv` currently contains only `data/non_ohlcv/sec_filing_schema.md` and `data/non_ohlcv/sec_filing_shadow_events_20260503.json`. The SEC shadow file contains generic `pit_safe` fields, but no short/borrow fields. It is not evidence for this mechanism.

## PIT Status

`pit_status`: `unavailable`

Bias constraints:

- Short-interest settlement dates are not tradable without publication dates.
- FINRA daily short volume is trading activity, not short positioning.
- Headline mentions are unstructured and biased; they are not borrow-pressure evidence.
- Without `borrow_fee` or `shares_available`, squeeze confidence must be downgraded.

## Shadow Metrics

Shadow tagging was blocked.

| Metric | Value |
|---|---:|
| Existing executed trades in accepted windows | 62 |
| Existing survived candidates in accepted windows | 138 |
| Taggable short/borrow candidates | 0 |
| Overlap with existing signals | 0 |
| Overlap ratio | 0.0 |
| Forward 5d return | null |
| Forward 10d return | null |
| Forward 20d return | null |
| Forward 60d return | null |
| Slot conflict value | null |

No false-positive examples were promoted because no PIT short/borrow rows exist. Unstructured news headlines mentioning short interest, squeeze, or borrow terms were not treated as evidence.

## Baseline Metrics

Baseline source: `data/backtest_results_20260502.json`

| Window | EV | Return | PnL | Sharpe daily | Max DD | Win rate | Trades | Generated | Survived | Survival | vs SPY | vs QQQ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 78.60% | 78600.33 | 4.35 | 5.41% | 78.95% | 19 | 51 | 41 | 80.39% | 73.19% | 72.80% |
| mid_weak | 1.4415 | 55.02% | 55015.08 | 2.62 | 8.79% | 52.38% | 21 | 53 | 42 | 79.25% | 29.58% | 21.51% |
| old_thin | 0.3179 | 24.64% | 24642.07 | 1.29 | 8.05% | 40.91% | 22 | 60 | 55 | 91.67% | 31.37% | 32.13% |

## Production Impact

- `shared_policy_changed`: false
- `backtester_adapter_changed`: false
- `run_adapter_changed`: false
- `production_signal_path_changed`: false
- `replay_only`: false
- `parity_test_added`: false

No OHLCV thresholds, entries, ranking, risk sizing, portfolio slots, LLM prompts, or production files changed.

## Decision

`data_gap`

The mechanism remains plausible, but this run found no new local PIT-safe short-interest, FINRA short-volume, borrow-fee, shares-available, or hard-to-borrow evidence after `exp-20260503-039`. Shadow scoring would be fabricated.

## Next Minimal Action

Choose one real default-off append-only short/borrow source and require `publication_date` plus `usable_trade_date` before rerunning shadow tagging. If only FINRA daily short volume is available, treat it as activity context, not short-interest positioning.
