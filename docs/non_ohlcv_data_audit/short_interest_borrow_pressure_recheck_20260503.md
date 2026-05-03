# Short Interest / Borrow Pressure Recheck

Experiment: `exp-20260503-021`
Run time: `2026-05-03T02:04:50-07:00`

## Hypothesis

High short interest alone is not a long signal. The useful overlay would be high short crowding plus price/event confirmation, especially existing `breakout_long`, `trend_long`, or event-positive candidates. The fragile side would be high short crowding plus negative filing/news/earnings context.

## Mechanism Family

`short_interest_borrow_pressure_overlay`

This is a non-OHLCV confirmation/risk overlay. It is not a standalone entry, not an OHLCV threshold sweep, and not a production signal-path change.

## Historical Check

- Exact prior audits: `exp-20260503-015` and `exp-20260503-018`.
- Prior decision: `data_gap`.
- Prior result: 0 structured short-interest rows, 0 FINRA adapter/files, 0 paid borrow rows, 0 PIT-safe rows, and 0 taggable candidates.
- Current recheck found no new local short-interest, FINRA short-volume, paid borrow, hard-to-borrow, borrow-fee, shares-available, or squeeze source files after `exp-20260503-018`.
- `docs/alpha-optimization-playbook.md` still treats this source as plausible, but only as shadow-quality until PIT data exists. It also warns not to treat FINRA daily short volume as short interest.

## Data Availability

| Source | Local coverage | PIT status | Current decision |
| --- | ---: | --- | --- |
| Exchange-reported short interest | 0 files / 0 rows | unavailable | unchanged |
| FINRA daily short volume | 0 adapters / 0 files | unavailable | unchanged |
| Paid borrow / securities lending | 0 files / 0 rows | unavailable | unchanged |
| Borrow fee / shares available / hard-to-borrow | 0 files / 0 rows | unavailable | unchanged |
| News headline proxy | 26 files with text matches | biased / insufficient | not usable as borrow-pressure evidence |

Required fields remain missing: `ticker`, `settlement_date`, `publication_date`, `short_interest`, `short_interest_float`, `days_to_cover`, `short_interest_change`, `borrow_fee`, `shares_available`, `hard_to_borrow`, `daily_short_volume`, `total_volume`, `daily_short_volume_ratio`, `usable_trade_date`, and `pit_safe`.

## Baseline Reference

No new backtest was run because this is a duplicate data-gap recheck and no strategy behavior changed. The accepted-stack baseline remains:

| Window | EV | Return | PnL | Sharpe daily | Max DD | Win rate | Trades | Signals generated | Signals survived | Survival | vs SPY | vs QQQ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | 3.4191 | 78.60% | $78,600.33 | 4.35 | 5.41% | 78.95% | 19 | 51 | 41 | 80.39% | 73.19% | 72.80% |
| `mid_weak` | 1.4415 | 55.02% | $55,015.08 | 2.62 | 8.79% | 52.38% | 21 | 53 | 42 | 79.25% | 29.58% | 21.51% |
| `old_thin` | 0.3179 | 24.64% | $24,642.07 | 1.29 | 8.05% | 40.91% | 22 | 60 | 55 | 91.67% | 31.37% | 32.13% |

## Shadow Tagging Feasibility

No shadow scores were recomputed. Recomputing would reproduce the prior zero-row result.

| Metric | Value |
| --- | ---: |
| Existing survived candidates | 138 |
| Existing executed trades | 62 |
| Taggable short/borrow candidates | 0 |
| `overlap_with_existing_signals` | 0 / 138 |
| Tagged candidate forward 5d return | unavailable |
| Tagged candidate forward 10d return | unavailable |
| Tagged candidate forward 20d return | unavailable |
| Tagged candidate forward 60d return | unavailable |
| Scarce-slot opportunity cost | not measurable |

## Decision

`data_gap`

The mechanism remains worth keeping on the external-alpha roadmap, but this run should not repeat the same zero-data shadow audit. A valid retry requires new point-in-time source rows.

## Next Minimal Action

Add a default-off append-only adapter contract and archive location for publication-lagged short-interest rows. Keep FINRA daily short volume separate and label it as activity-only. Paid borrow fields should remain a distinct optional source before any squeeze-confidence score is trusted.
