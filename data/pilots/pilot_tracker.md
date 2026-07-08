# Pilot tracker - as of 2026-07-08T06:07:11+00:00

Per-position book: $10,000. Read-only; manual execution.
Graduate/kill rule (pre-committed): >= 20 closed AND sum rv_vs_SPY > 0 AND book DD < 15%.
Manual stop overlay: cut a held position at -15% from entry (does not change the sleeve).

## [!] STOP-LOSS alerts - cut by hand today (stop = -15%)

- **SELL WDC** (Source-priority allocator (TOP-1 only)): -15.9% from entry 632.76 -> last 532.10

## [!] Cross-pilot theme concentration (one theme, stacked books)

- **Technology** (sector): 3 positions across 2 pilot(s) (AMD, CRDO, WDC) -> $30,000 (43% of actionable exposure)
- **Industrials** (sector): 3 positions across 1 pilot(s) (AAL, CAT, GE) -> $30,000 (43% of actionable exposure)

## Scorecard

| pilot | closed | hit | realized $ | rv_cash | rv_SPY | rv_QQQ | book DD | verdict |
|---|--:|--:|--:|--:|--:|--:|--:|---|
| Source-priority allocator (TOP-1 only) | 4 | 25% | $-2,715 | $-2,715 | $-2,762 | $-1,946 | 33.5% | **KILL** |
| Distribution-day absorption leadership | 0 | - | $0 | $0 | $0 | $0 | 0.0% | **COLLECTING** |
| Fundamental growth + RS | 11 | 46% | $-2,376 | $-2,376 | $-1,418 | $-486 | 40.1% | **KILL** |

## Today's signals (BUY / HOLD / SELL)

### Source-priority allocator (TOP-1 only)  (`accepted_helper_source_priority_allocator`, max_concurrent=1)
- _new entries blocked: KILL verdict_
- hold WDC: day 5/10 (5 left); entry 632.76, last 532.10 (-15.9%) **[STOP_HIT -> SELL]**
- _skip_ AFRM (SKIP_concurrency_cap)
- _skip_ CRS (SKIP_concurrency_cap)
- _skip_ NVMI (SKIP_concurrency_cap)
- _skip_ SITM (SKIP_concurrency_cap)
- _skip_ SBUX (SKIP_concurrency_cap)
- _skip_ JAZZ (SKIP_concurrency_cap)
- _skip_ DDOG (SKIP_pilot_kill_verdict)

### Distribution-day absorption leadership  (`distribution_day_absorption_leadership`, max_concurrent=None)
- hold GE: day 8/10 (2 left); entry 367.83, last 366.98 (-0.2%)
- hold AAL: day 6/10 (4 left); entry 17.50, last 17.20 (-1.7%)
- hold CAT: day 7/10 (3 left); entry 1032.37, last 940.12 (-8.9%)
- hold MOH: day 5/10 (5 left); entry 228.68, last 232.90 (+1.8%)

### Fundamental growth + RS  (`fundamental_growth_rs`, max_concurrent=None)
- _new entries blocked: KILL verdict_
- hold AMD: day 6/10 (4 left); entry 557.81, last 516.11 (-7.5%)
- hold CRDO: day 1/10 (9 left); entry 249.98, last 246.40 (-1.4%)
- _skip_ DDOG (SKIP_pilot_kill_verdict)

