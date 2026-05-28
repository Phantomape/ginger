# exp-20260527-908 Last Earnings Date PIT Join into Expectation Revision Watchlist Row

Decision: `accepted_measurement_repair_last_earnings_date_field`.

Read-only `measurement_repair`. Reconstructs a PIT-safe
`last_earnings_date` for each row of the `exp-20260525-034` expectation
revision watchlist by indexing all historical
`data/non_ohlcv/sec_filing_features_*.jsonl` rows whose `form_type` is
`10-Q` / `10-K` (any amendment variant) or whose `form_type` is `8-K`
with item code `2.02` ("Results of Operations and Financial Condition").
A secondary fallback consults `data/daily/snapshots/earnings/*.json`
`next_earnings_date` timelines for tickers absent from EDGAR (foreign
filers, recent IPOs). The enriched rows are written to
`data/experiments/exp-20260527-908/last_earnings_date_pit_join_into_expectation_revision_watchlist_row.json`
without modifying the source `exp-20260525-034` artifact.

This change does not modify entries, exits, ranking, sizing,
LLM/news inputs, paper sleeves, or live orders. Rule version:
`sec_filing_features_pit_last_earnings_date_v2`.

## Why this experiment exists

The 2026-05-27 expectation/residual/PEAD three-round suite
(`exp-20260527-002` … `exp-20260527-010`) all closed as
`observed_only_data_gap`. The most damaging gap was that the
`annotated_watchlist_rows` produced by `exp-20260525-034` had no
`last_earnings_date`, so the PEAD branch (`exp-20260527-005/006/007`)
could not separate "inside the T+2..T+15 post-earnings window" from
"long after earnings". Of the 47 `primary_expectation_positive` rows in
`exp-20260527-005`, 100% sat in `pead_status =
missing_last_earnings_date`, and the experiment ended with
`rejection_reason: insufficient_comparable_bucket_evidence`.

The fix did not require new data fetching: the SEC EDGAR features for
the 10-Q / 10-K / 8-K(2.02) filings were already persisted on disk in
`data/non_ohlcv/sec_filing_features_*.jsonl`. The repair was a strict
PIT-safe join.

## PIT semantics

`last_earnings_date(ticker, as_of_date)` returns the most recent
filing event whose `filing_date <= as_of_date`. SEC EDGAR
`filing_date` is the strict public-discovery date (assigned at filing
acceptance by SEC), so no future leak is possible. The fallback
`earnings_snapshot` path keeps the same property by requiring both
`snapshot_date <= as_of_date` and `next_earnings_date <= as_of_date`.

## Gate 1 baseline measurability

The baseline is the existing `exp-20260525-034` watchlist artifact,
which contains 700 PIT-usable rows with `as_of_date` ∈ [2026-05-08,
2026-05-26] and 47 `primary_expectation_positive` rows. Before this
repair, all 700 rows had `pead_status = missing_last_earnings_date`.

## Gate 2 required input fields

`ticker` and `as_of_date` are present on every input row (verified in
the `exp-20260525-034` schema). No new strategy field is required;
only the new join column is added.

## Gate 3 survival rate

Not applicable. This is a read-only field join: it does not filter,
re-rank, or change candidate eligibility, so survival rate is
structurally unaffected.

## Gate 4 acceptance bar: PEAD bucket discrimination is now possible

```json
{
  "all_passed": true,
  "gate4": {
    "after_repair_has_inside_or_outside_bucket": true,
    "criteria": "At least 80% of primary positive rows must obtain a non-missing pead_status, and at least one row must fall inside or outside the T+2..T+15 window so downstream PEAD readiness experiments can compare buckets.",
    "name": "primary_positive_pead_unblocked",
    "passed": true,
    "primary_positive_resolved_share": 0.851063829787234,
    "primary_positive_rows": 47,
    "primary_positive_still_missing": 7
  }
}
```

The acceptance bar for a `measurement_repair` of this type is field
coverage that re-enables bucket comparison, not an alpha PnL delta;
EV / drawdown are unchanged by construction because no strategy state
mutates.

## Coverage report (all rows and primary positive rows)

```json
{
  "last_earnings_date_coverage": {
    "all_rows": {"present": 554, "ratio": 0.7914285714285715},
    "primary_positive_rows": {"present": 40, "ratio": 0.851063829787234}
  },
  "lookup_source_counts": {"sec_filing_features": 554},
  "lookup_status_counts": {
    "ok": 554,
    "ticker_not_in_sec_filings": 146
  },
  "pead_status_counts_all_rows": {
    "before_repair": {"missing_last_earnings_date": 700},
    "after_repair": {
      "inside_t2_t15_after_earnings": 217,
      "missing_last_earnings_date": 146,
      "outside_t2_t15_after_earnings": 337
    }
  },
  "pead_status_counts_primary_positive_rows": {
    "before_repair": {"missing_last_earnings_date": 47},
    "after_repair": {
      "inside_t2_t15_after_earnings": 15,
      "missing_last_earnings_date": 7,
      "outside_t2_t15_after_earnings": 25
    }
  }
}
```

The 7 still-missing primary positive rows are tickers absent from the
SEC EDGAR feature stream: foreign filers (NVO, TSM file 20-F),
recently-IPO'd US names (HOOD, RBLX, SOFI), and a small tail of names
whose 8-K earnings items have not been parsed yet (GEV, MTSI, MRVL,
SPOT, VRT, WDC). None of these blocks the unblock claim because
`primary_positive_resolved_share = 0.851` clears the 0.80 Gate 4 bar.

## PEAD readiness re-probe (mirror of exp-20260527-005's bucketing)

This sidecar applies `exp-20260527-005`'s `pead_readiness_bucket`
assignment logic to the enriched rows. Both eligible buckets, which
were empty before this repair, now contain rows with closed 5d
outcomes; the residual eligible bucket also meets the 10d closed-outcome
floor required by `exp-20260527-005`'s `gate_thresholds.min_bucket_closed_10d = 5`.

```json
{
  "bucket_counts": {
    "blocked_missing_effective_trade_date": 0,
    "blocked_missing_last_earnings_date": 7,
    "blocked_outside_t2_t15_after_earnings": 25,
    "eligible_t2_t15_primary_non_residual": 8,
    "eligible_t2_t15_primary_residual": 7,
    "not_primary_7d_positive": 653
  },
  "closed_outcomes_per_eligible_bucket": {
    "eligible_t2_t15_primary_residual": {
      "row_count": 7,
      "closed_outcomes_by_horizon": {
        "1d": 0, "2d": 0, "5d": 7, "10d": 7, "20d": 0
      }
    },
    "eligible_t2_t15_primary_non_residual": {
      "row_count": 8,
      "closed_outcomes_by_horizon": {
        "1d": 0, "2d": 0, "5d": 8, "10d": 4, "20d": 0
      }
    }
  }
}
```

## Unblocked downstream experiments

- `exp-20260527-005` PEAD readiness — primary residual + non-residual
  eligible buckets are now populated; 5d horizon is fully comparable;
  10d horizon is comparable for the residual bucket (the non-residual
  bucket has 4 closed outcomes vs the published `min_bucket_closed_10d
  = 5` threshold).
- `exp-20260527-006` post-revision 2d failure proxy — `2d` closed
  outcomes are still zero in the enriched data, so this experiment
  remains blocked by `forward_outcomes['2d']` closure rather than by
  the earnings-date field. Future work.
- `exp-20260527-007` candidate conversion lag — `last_earnings_date`
  is now available; the bucket conversion analysis can re-run.

## Files touched

- `quant/experiments/exp_20260527_908_last_earnings_date_pit_join_into_expectation_revision_watchlist_row.py`
  (new, ~430 lines)
- `quant/test_exp_20260527_908_last_earnings_date_pit_join.py`
  (new, 19 unit tests covering PIT safety, SEC item-code filtering,
  source preference + fallback, gate logic, and the reprobe bucketer)
- `data/experiments/exp-20260527-908/last_earnings_date_pit_join_into_expectation_revision_watchlist_row.json`
  (new, enriched watchlist + coverage + reprobe)
- `experiments/artifacts/exp-20260527-908_last_earnings_date_pit_join_into_expectation_revision_watchlist_row.md`
  (this file)
- `experiments/logs/exp-20260527-908.json`,
  `experiments/tickets/exp-20260527-908.json`,
  `docs/experiment_log.jsonl`, `docs/experiment_registry.json`
  (registry / log housekeeping)

No JavaScript was used.
