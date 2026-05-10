# exp-20260510-015 TRIP Sector Taxonomy

Decision: `accepted_shared_policy_small`

## Hypothesis

TRIP is a travel/platform equity whose missing sector classification pushes it through Unknown-sector enrichment. Mapping it to Consumer Discretionary lets the existing shared sector-aware risk allocation and attribution handle it without changing thresholds, entries, exits, ranking, LLM/news, or universe.

## History Check

This is not a blind repeat of exp-20260501-018: the current accepted stack now has shared sector-dispersion enrichment and RS20 entry-state allocation paths that actually consume sector metadata. The before/after artifact shows 12 existing trades changed, aggregate EV moved +0.0171, and no window regressed.

## Gate Summary

- Gate 1: baseline uses the current three fixed windows from `docs/backtesting.md`.
- Gate 2: no new runtime fields; `entry_date` and `target_price` were present in current operator positions.
- Gate 3: no filter added; survival rates are unchanged.
- Gate 4: three-window before/after below.

## Aggregate

| Metric | Before | After | Delta |
|---|---:|---:|---:|
| EV sum | 6.2711 | 6.2882 | 0.0171 |
| PnL sum | $184040.96 | $184444.42 | $403.46 |
| Trades | 62 | 62 | 0 |
| Survived signals | 138 | 138 | 0 |

## Windows

| Window | EV before | EV after | EV delta | PnL delta | DD delta | Trades delta | Survival delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.234 | 4.234 | 0.0 | 0.0 | 0.0 | 0 | 0.0 |
| mid_weak | 1.6678 | 1.6689 | 0.0011 | 44.45 | 0.0 | 0 | 0.0 |
| old_thin | 0.3693 | 0.3853 | 0.016 | 359.01 | -0.01 | 0 | 0.0 |

## Production Impact

Shared `risk_engine.SECTOR_MAP` changed. Both production and backtest enrichment consume this map, and no replay-only branch was introduced.

## Decision Rationale

Accepted as a small shared-policy alpha/data-quality improvement: EV and PnL improved where the trade exists, no window regressed, drawdown did not worsen, and trade count plus survival stayed unchanged. The lift is too small to justify ticker-by-ticker mining, but the classification itself is production-real and removes an Unknown-sector allocation path.
