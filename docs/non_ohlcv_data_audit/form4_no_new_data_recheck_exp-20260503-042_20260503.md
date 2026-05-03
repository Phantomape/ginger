# Form 4 Insider Overlay Data Audit - exp-20260503-042

## Scope

- Source: SEC Form 4 insider ownership filings.
- Mechanism family: non-OHLCV event confirmation for existing `trend_long` / `breakout_long` candidates.
- Single causal variable: new PIT-safe Form 4 transaction-level evidence since `exp-20260503-040`.
- Mode: data audit only; no production change.

## Historical Check

This is the same family as `exp-20260503-017`, `exp-20260503-020`,
`exp-20260503-025`, `exp-20260503-026`, `exp-20260503-030`,
`exp-20260503-033`, `exp-20260503-037`, and `exp-20260503-040`.

Prior result: CIK mapping was mostly usable, but no PIT-safe transaction-level
Form 4 archive existed. Transaction XML fields were missing, meaningful
insider-buy candidates were 0, and scarce-slot value could not be measured.

This run found no new local PIT-safe Form 4 inputs after `exp-20260503-040`.

## Data Availability

- `data/non_ohlcv` currently contains SEC filing schema/shadow files only.
- Structured Form 4 files in `data/non_ohlcv`: 0.
- Latest news archive: `data/news_20260502.json`.
- Latest source stats archive: `data/news_source_stats_20260502.json`.
- SEC source stats cover 8-K, 10-Q, and 10-K feeds with `owner=exclude`.
- No `owner=include&type=4` feed output was observed.
- SEC submissions cache exists, but it is a latest snapshot and is not a PIT historical archive.

CIK mapping status from the prior Form 4 audit remains usable enough for a
future adapter:

- Core mapped: 43/45; missing `IWM`, `SNXX`.
- Pilot mapped: 3/3.
- Observation mapped: 13/13.

## Required Field Status

Available:

- `ticker`
- `cik`
- `accession_number`
- `filing_datetime`

Missing:

- `transaction_date`
- `officer_title`
- `is_director`
- `is_officer`
- `is_10pct_owner`
- `transaction_code`
- `shares`
- `price`
- `transaction_value`
- `direct_or_indirect`
- `ownership_nature`
- `10b5_1_flag`
- `option_exercise_flag`
- `open_market_purchase_flag`
- `usable_trade_date`
- `pit_safe_flag`

## PIT Status

Not point-in-time safe for historical overlay performance.

Reason: local data does not include append-only daily Form 4 transaction XML
rows. The current SEC submissions cache can show historical filing metadata,
but as a latest snapshot it cannot prove what was known at each historical
trade date.

## Shadow Metrics

- Meaningful insider-buy candidates: 0.
- Existing signals with meaningful insider-buy tag: 0.
- Insider buy but no signal: 0.
- Overlap with existing signals: not measurable.
- Scarce-slot opportunity cost: not measurable.
- Forward 5/10/20/60/90d return of tagged candidates: no sample.

## Decision

`data_gap`.

The mechanism remains plausible, but running another Form 4 overlay replay on
unchanged data would fabricate confidence. The next valid action is to build a
default-off append-only Form 4 adapter that fetches SEC `owner=include&type=4`
feeds, persists transaction XML rows, computes `usable_trade_date`, and marks
each row with `pit_safe`.

No production signal path, risk engine, portfolio engine, LLM prompt, news
veto, or OHLCV entry rule was changed.
