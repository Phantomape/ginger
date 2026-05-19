# Short Interest / Borrow Pressure Data Audit

Experiment: `exp-20260503-015`
Run time: `2026-05-03T00:06:03-07:00`

## Hypothesis

High short interest alone is not a long signal. The useful overlay would be high short crowding plus price/event confirmation, especially existing `breakout_long` or event-positive candidates. The fragile side would be high short crowding plus negative filing/news/earnings context. This round only audits whether the repository has point-in-time data needed to tag existing candidates.

## Mechanism Family

`short_interest_borrow_pressure_overlay`

This is a non-OHLCV confirmation/risk overlay, not a standalone entry, not an OHLCV threshold sweep, and not a production signal-path change.

## Historical Check

- `docs/alpha-optimization-playbook.md` ranks `Short interest / borrow pressure` as an external alpha source worth researching after earnings/SEC, analyst revisions, and insider transactions.
- The playbook explicitly warns not to treat FINRA daily short volume as short interest.
- `docs/experiment_log.jsonl` and `experiments/logs` contain no prior structured `short_interest`, `borrow_fee`, `FINRA`, `hard_to_borrow`, `daily_short_volume`, or `squeeze_setup` experiment.
- Incidental news/headline matches such as "short interest" or "squeeze" exist, but they are unstructured text and cannot supply publication-lagged numeric fields.

## Data Availability

| Source | Local coverage | PIT status | Notes |
| --- | ---: | --- | --- |
| Exchange-reported short interest | 0 files / 0 rows | unavailable | No `settlement_date`, `publication_date`, `short_interest`, `short_interest_float`, or `days_to_cover` table exists. |
| FINRA daily short volume | 0 adapters / 0 files | unavailable | No local adapter or archive found. If added later, it must remain distinct from short interest. |
| Paid borrow / securities lending | 0 files / 0 rows | unavailable | No `borrow_fee`, `shares_available`, or `hard_to_borrow` fields found. |
| News headline proxy | text only | biased / insufficient | Headlines are not numeric borrow pressure data and should not drive production or replay evidence. |

Required fields are currently missing:

- `ticker`
- `settlement_date`
- `publication_date`
- `short_interest`
- `short_interest_float`
- `days_to_cover`
- `short_interest_change`
- `borrow_fee`
- `shares_available`
- `hard_to_borrow`
- `daily_short_volume`
- `total_volume`
- `daily_short_volume_ratio`
- `usable_trade_date`
- `pit_safe`

## Baseline Reference

No new backtest was run because this is a data audit and no strategy behavior changed. The accepted-stack baseline used for candidate-count context is the latest canonical three-window baseline recorded in `experiments/logs/exp-20260503-011.json`:

| Window | EV | Return | PnL | Sharpe daily | Max DD | Win rate | Trades | Signals generated | Signals survived | Survival | vs SPY | vs QQQ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | 3.4191 | 78.60% | $78,600.33 | 4.35 | 5.41% | 78.95% | 19 | 51 | 41 | 80.39% | 73.19% | 72.80% |
| `mid_weak` | 1.4415 | 55.02% | $55,015.08 | 2.62 | 8.79% | 52.38% | 21 | 53 | 42 | 79.25% | 29.58% | 21.51% |
| `old_thin` | 0.3179 | 24.64% | $24,642.07 | 1.29 | 8.05% | 40.91% | 22 | 60 | 55 | 91.67% | 31.37% | 32.13% |

Aggregate existing survived candidates across the three windows: `138`.
Aggregate executed trades across the three windows: `62`.

## Shadow Tagging Feasibility

Shadow scores could not be computed because all required short/borrow rows are missing.

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

False-positive notes:

- A headline saying short interest increased is not equivalent to a PIT exchange short-interest row with settlement and publication dates.
- A headline using "squeeze" for supply, AI memory, or cash-flow pressure is not a short-squeeze setup.
- Daily short volume, if added later, must be treated as trading activity, not as short positioning.

## Required Shadow Schema

Future data should be append-only and use `publication_date` to derive `usable_trade_date`; `settlement_date` alone is not tradable information.

Minimum row shape:

```json
{
  "ticker": "XYZ",
  "settlement_date": "YYYY-MM-DD",
  "publication_date": "YYYY-MM-DD",
  "usable_trade_date": "YYYY-MM-DD",
  "short_interest": 0,
  "short_interest_float": null,
  "days_to_cover": null,
  "short_interest_change": null,
  "borrow_fee": null,
  "shares_available": null,
  "hard_to_borrow": null,
  "daily_short_volume": null,
  "total_volume": null,
  "daily_short_volume_ratio": null,
  "pit_safe": true,
  "source": "exchange_short_interest_or_paid_borrow_feed"
}
```

Shadow score fields:

- `short_crowding_score`
- `short_change_score`
- `squeeze_setup_score`
- `fragile_short_score`

Borrow data is required to avoid overclaiming squeeze confidence. Without `borrow_fee`, `shares_available`, or a hard-to-borrow flag, squeeze confidence must be capped or marked low.

## Decision

`data_gap`

This direction remains mechanism-valid but cannot become a shadow alpha result, default-off replay, or production candidate until point-in-time short-interest and borrow-pressure data exists.

## Next Minimal Action

Add a default-off data adapter contract and archive location for publication-lagged short-interest rows. If free data is used first, keep FINRA daily short volume separate and label it as activity-only. Paid borrow fields should be recorded as a distinct optional source before any squeeze-confidence scoring is trusted.
