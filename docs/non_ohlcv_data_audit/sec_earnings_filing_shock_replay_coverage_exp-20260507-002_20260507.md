# SEC / Earnings / Filing-Shock Replay Coverage Audit (exp-20260507-002)

## Hypothesis
SEC / earnings / filing shock alpha can only be audited after the canonical fixed-window non-OHLCV replay dataset proves complete, PIT-disclosed coverage across all three windows.

## Data Source
Public SEC accepted filing metadata/text/features plus existing repo earnings snapshots. SEC tradability uses accepted_datetime -> usable_trade_date only.

## PIT Status
- Three-window coverage complete: True
- PIT caveats: SEC accepted_datetime/usable_trade_date is PIT-safe as EDGAR-public proxy, but not proof the production process observed the filing intraday., Historical earnings snapshots are repo/vendor snapshots and PIT-ish; EPS/revenue surprise remains null unless a trusted PIT consensus source exists., Directional filing-shock labels require same-row financial shock fields; form/item metadata alone is treated as unclear., First 20 trading days of the old_thin window are left-censored for recent-filing lookback because older non-OHLCV artifacts were not requested.

## Coverage Table
| window | dates | complete_fraction | complete_days | business_days | missing_by_artifact | biased_days |
|---|---:|---:|---:|---:|---|---:|
| late_strong | 2025-10-23..2026-04-21 | 1.0 | 129 | 129 | {} | 0 |
| mid_weak | 2025-04-23..2025-10-22 | 1.0 | 131 | 131 | {} | 0 |
| old_thin | 2024-10-02..2025-04-22 | 1.0 | 145 | 145 | {} | 0 |

## Shadow Tagging Summary
| window | selected signals | selected with recent filing | filing event candidates | deferred slot candidates | slot comparables |
|---|---:|---:|---:|---:|---:|
| late_strong | 19 | 10 | 345 | 0 | 0 |
| mid_weak | 21 | 12 | 315 | 4 | 1 |
| old_thin | 22 | 11 | 291 | 8 | 2 |

## Decision
shadow_only

## Next Action
Use the complete replay dataset to build a default-off candidate-row tagging harness that persists all generated candidates, not only selected trades and scarce-slot deferrals.
