# exp-20260505-008 SEC Leadership Forward Queue

## Result

Accepted as a default-off observation harness. No trading rule was promoted.

The new branch tracks 8-K Item 5.02 leadership-change filings when the first
public SPY-relative reaction is at most -2%. It freezes the candidate and
same-day core alternatives, then advances a paper-only 10-session ledger.

| window | EV before | EV after | PnL delta | Sharpe daily delta | Win-rate delta | Trades delta |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 3.4191 | 0.00 | 0.00 | 0.0000 | 0 |
| mid_weak | 1.4415 | 1.4415 | 0.00 | 0.00 | 0.0000 | 0 |
| old_thin | 0.3179 | 0.3179 | 0.00 | 0.00 | 0.0000 | 0 |

## Decision

- Decision: accepted_observation_harness.
- Production impact: shared policy and run/report adapters changed, but signal generation, ranking, sizing, and orders remain unchanged.
- Backtest parity: all three canonical windows matched the documented baseline exactly.
- Next gate: closed forward paper outcomes must show positive replacement value versus frozen alternatives before any trade promotion.

## Why This Direction

LLM soft-ranking remains blocked by sparse joined outcomes. Recent source
composition, macro ETF, sector-cap, and moving-average gate experiments were
rejected or no-ops. The SEC leadership-change branch has prior shadow-positive
historical evidence, so the next alpha-search unit is forward replacement-value
capture rather than another frozen-sample threshold sweep.
