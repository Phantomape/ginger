# exp-20260506-030: event/state slot replacement replay

## Decision

- status: closed
- decision: rejected_for_promotion
- Gate 4: FAIL
- production impact: replay_only=True, shared_policy_changed=False

## Hypothesis

Event/state-qualified shadow candidates may provide positive scarce-slot replacement value versus the accepted core stack.

## Three-window baseline and replay evidence

| Window | EV | Sharpe daily | PnL | Trades | Selected | Same-day comps | Nearby comps | Median 10d excess | Median nearby replacement |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 4.35 | 78600.33 | 19 | 7 | 0 | 4 | 0.01 | 848.98 |
| mid_weak | 1.4415 | 2.62 | 55015.08 | 21 | 7 | 1 | 4 | 0.09 | 1176.78 |
| old_thin | 0.3179 | 1.29 | 24642.07 | 22 | 6 | 0 | 5 | -0.01 | 63.07 |

## Aggregate

- selected candidates: 20
- unique tickers: 12
- same-day comparable count: 1
- nearby comparable count: 13
- windows with positive median 10d excess: 2/3
- windows with positive median nearby replacement value: 3/3
- aggregate median nearby replacement value per 10k: 462.54

## Closeout

Closed rejected_for_promotion: standalone forward returns remain interesting, but the evidence still does not prove scarce-slot replacement value.

The experiment did not modify production or backtest strategy logic. The next valid retry needs more same-day slot-pressure evidence or a true substitution replay, not another broader ticker list.
