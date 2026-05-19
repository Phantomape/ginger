# EOD options quality gate and outcome close audit (exp-20260507-091)

## Hypothesis

A forward options overlay needs a candidate usable-date join, daily collection quarantine, and outcome-closing summaries before any alpha decision is credible.

## Historical check

Checked AGENTS.md, docs/alpha-optimization-playbook.md, docs/experiment_log.jsonl, experiments/logs, and universe-scout memory. Prior options evidence rejects naive historical call/put OI or skew promotion. This run changes only the forward measurement harness.

## What changed

- `scripts/run_options_forward_ledger.py` now defaults to joining candidates by option `usable_trade_date`, not option `quote_date`.
- Added a per-quote-date collection quality gate.
- Added quarantine artifacts and outcome-close summaries for forward 5/10/20/60d returns and slot conflict value.
- No production signal, risk, portfolio, run, or backtester path changed.

## Quality gate

| quote_date | usable dates | status | pass rate | liquid tickers >=10 rows | ask>bid rate | OI>0 rate | delta nonzero rate | reasons |
|---|---|---|---:|---:|---:|---:|---:|---|
| 2026-05-05 | 2026-05-06 | quarantined | 0.00021 | 0 | 0.00021 | 0.00021 | 0.00021 | liquidity_pass_rate_below_floor, too_few_tickers_with_10_liquid_rows, bid_ask_mid_market_rows_sparse, open_interest_rows_sparse, delta_rows_sparse |
| 2026-05-06 | 2026-05-07 | usable_for_shadow | 0.873925 | 48 | 0.99979 | 0.98154 | 0.512272 | none |

## Candidate overlap

- Candidate count: 3.
- Options-covered candidates: 3.
- PIT join safe candidates: 2.
- Quality-usable candidates: 0.
- Quarantined candidates: 3.
- Options scoring allowed candidates: 0.
- 2026-05-05 options correctly joined 2026-05-06 candidates but were quarantined.
- 2026-05-06 options are usable for shadow, but require `data/quant_signals_20260507.json`, which is not present locally.

## Outcome close

Closed 5/10/20/60d outcome counts are all zero in this run because post-2026-05-06 OHLCV outcomes are unavailable. Slot conflict value is therefore pending.

## Decision

`shadow_only`. The harness is ready; alpha evidence is not. Continue daily collection and rerun after usable quote dates have matching candidate files and closed forward returns.
