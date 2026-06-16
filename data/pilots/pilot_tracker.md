# Pilot tracker - as of 2026-06-16T07:01:16+00:00

Per-position book: $10,000. Read-only; manual execution.
Graduate/kill rule (pre-committed): >= 20 closed AND sum rv_vs_SPY > 0 AND book DD < 15%.
Manual stop overlay: cut a held position at -15% from entry (does not change the sleeve).

## [!] STOP-LOSS alerts - cut by hand today (stop = -15%)

- **SELL AVGO** (Fundamental growth + RS): -20.4% from entry 495.03 -> last 393.94

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
- hold CRDO: day 2/10 (8 left); entry 270.13, last next-open (n/a)
- _skip_ SBUX (SKIP_concurrency_cap)
- _skip_ WDC (SKIP_concurrency_cap)

### Distribution-day absorption leadership  (`distribution_day_absorption_leadership`, max_concurrent=None)
- _no position / no signal today_

### Fundamental growth + RS  (`fundamental_growth_rs`, max_concurrent=None)
- **SELL (EXIT_NEXT_SESSION)** AVGO: hold elapsed (day 9/10); entry 495.03, last 393.94
- **BUY (next open)** MU (signal None); time exit after ? trading days held; rank=None score=None
- hold AMD: day 5/10 (5 left); entry 503.70, last 547.26 (+8.6%)
- hold CRDO: day 1/10 (9 left); entry 270.13, last 259.41 (-4.0%)

