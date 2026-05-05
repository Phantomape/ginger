# SEC / Earnings / Filing Shock Audit (exp-20260504-021)

## Decision

Decision: `shadow_only`.

This run made no production change and did not add a new entry, filter, ranking rule, sizing rule, or threshold. The SEC/earnings data layer is now materially available for shadow research, but prior same-family experiments block production promotion without new information content.

## Hypothesis

SEC filing shock, earnings surprise, 8-K event type, and post-event drift may improve C-strategy grading or confirm existing trend/breakout candidates. The current run only audits data availability, PIT status, prior shadow results, overlap, and slot value.

## Mechanism Family

`Earnings + SEC filings + financial surprise / event confirmation overlay`

Single causal variable: `SEC earnings filing-shock data availability and prior-shadow synthesis`.

## Coverage Table

| Source | Coverage | PIT Status | Main Gap |
|---|---:|---|---|
| SEC submissions/events | 1286 rows, 1286 PIT-proxy rows, 51/52 tickers mapped | EDGAR `accepted_at` public proxy | Does not prove local production pipeline observed the filing |
| Earnings snapshots | 138 files, 6081 ticker rows, 5239 EPS estimates, 5239 surprise-history rows | Production snapshots from 20251023 to 20260503 | Older fixed windows still lack earnings snapshots |
| SEC Companyfacts | 17109 selected rows across 51/52 mapped tickers | Filed-date public proxy | Latest-prior facts are stale for same-day 8-K reaction grading |
| SEC filing text | 306/306 Item 2.02 text rows, 1224 docs, 12024232 chars | SEC archive text for accepted filings | Keyword proxies are not promotion-quality; use as LLM context |

## Prior Shadow Results

| Branch | Candidate Count | 10d Forward / Slot Result | Decision |
|---|---:|---|---|
| Results 8-K + positive first reaction | 21 (20 valid 10d) | avg 10d excess -1.83%; slot proxy -9.87pp | observed only / reject as C revival |
| Companyfacts simple quality | 292 (218 price-covered) | high-quality was not monotonic vs warning-quality | observed only |
| Item 2.02 keyword text | 302 (232 price-covered) | positive language failed; negative language was the only interesting branch | observed only |
| Negative text + negative first reaction | 16 | avg 10d net excess 4.74%; active-slot proxy 0.99pp | default-off queue already exists |
| Leadership-change negative reaction | 25 (23 valid 10d) | avg 10d excess 3.81%; slot proxy -6.95pp | shadow only |
| Agreement/debt 8-K packet | 39 (38 valid 10d) | avg 10d excess -0.86% | observed only / not promoted |

## Tag Interpretation

- `A_no_recent_filing_event`: not fully measured against all pre-entry candidates because a complete three-window candidate dump is not persisted.
- `B_positive_filing_shock`: tested via results 8-K + positive reaction and rejected for production use.
- `C_negative_filing_shock`: the only promising family, but current evidence supports default-off observation and LLM semantic grading, not core slot promotion.
- `D_unclear_or_missing_data`: missingness is mainly ticker/price coverage, same-accession XBRL, and structured semantic fields such as guidance raise/cut.

## Baseline Metrics

| Window | EV | Return | Sharpe Daily | Max DD | Win Rate | Trades | Signals | Survival | vs SPY | vs QQQ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 0.7860 | 4.35 | 0.0541 | 0.7895 | 19 | 51/41 | 0.8039 | 0.7319 | 0.7280 |
| mid_weak | 1.4415 | 0.5502 | 2.62 | 0.0879 | 0.5238 | 21 | 53/42 | 0.7925 | 0.2958 | 0.2151 |
| old_thin | 0.3179 | 0.2464 | 1.29 | 0.0805 | 0.4091 | 22 | 60/55 | 0.9167 | 0.3136 | 0.3213 |

Expected value score delta: `0.0` in every window because this is a read-only audit.

## Next Minimum Action

Do not rerun nearby positive-reaction, keyword, or Companyfacts score sweeps. The next valid step is either:

1. collect forward replacement-value outcomes from the existing default-off SEC queue, or
2. test LLM semantic grading on the frozen filing-text packet to separate recoverable pressure from true deterioration.
