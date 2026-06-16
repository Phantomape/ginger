# Pilot tracker - as of 2026-06-15T03:21:41+00:00

Per-position book: $10,000. Read-only; manual execution.
Graduate/kill rule (pre-committed): >= 20 closed AND sum rv_vs_SPY > 0 AND book DD < 15%.

## [!] Cross-pilot overlap (stacked exposure on one name)

- **CRDO**: held by 2 pilots (Source-priority allocator (TOP-1 only), Fundamental growth + RS) -> $20,000 real exposure

## Scorecard

| pilot | closed | hit | realized $ | rv_cash | rv_SPY | rv_QQQ | book DD | verdict |
|---|--:|--:|--:|--:|--:|--:|--:|---|
| Source-priority allocator (TOP-1 only) | 0 | - | $0 | $0 | $0 | $0 | 0.0% | **COLLECTING** |
| Distribution-day absorption leadership | 0 | - | $0 | $0 | $0 | $0 | 0.0% | **COLLECTING** |
| Fundamental growth + RS | 2 | 50% | $260 | $260 | $985 | $1,218 | 7.2% | **COLLECTING** |

## Today's signals (BUY / HOLD / SELL)

### Source-priority allocator (TOP-1 only)  (`accepted_helper_source_priority_allocator`, max_concurrent=1)
- hold CRDO: day 1/10 (9 left); entry 270.13, last next-open
- _skip_ SBUX (SKIP_concurrency_cap)

### Distribution-day absorption leadership  (`distribution_day_absorption_leadership`, max_concurrent=None)
- _no position / no signal today_

### Fundamental growth + RS  (`fundamental_growth_rs`, max_concurrent=None)
- hold AVGO: day 8/10 (2 left); entry 495.03, last 382.07
- hold AMD: day 4/10 (6 left); entry 503.70, last 511.57
- hold CRDO: day 0/10 (10 left); entry 270.13, last 250.81

