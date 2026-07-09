# Pilot tracker - as of 2026-07-09T04:58:34+00:00

Per-position book: $10,000. Read-only; manual execution.
Graduate/kill rule (pre-committed): >= 20 closed AND sum rv_vs_SPY > 0 AND book DD < 15%.
Manual stop overlay: cut a held position at -15% from entry (does not change the sleeve).

## [!] Cross-pilot theme concentration (one theme, stacked books)

- **Technology** (sector): 4 positions across 2 pilot(s) (AMD, CRDO, DDOG, WDC) -> $40,000 (50% of actionable exposure)
- **Industrials** (sector): 3 positions across 1 pilot(s) (AAL, CAT, GE) -> $30,000 (38% of actionable exposure)

## Scorecard

| pilot | closed | hit | realized $ | rv_cash | rv_SPY | rv_QQQ | book DD | verdict |
|---|--:|--:|--:|--:|--:|--:|--:|---|
| Source-priority allocator (TOP-1 only) | 5 | 40% | $-2,441 | $-2,441 | $-2,412 | $-1,214 | 33.5% | **KILL** |
| Distribution-day absorption leadership | 0 | - | $0 | $0 | $0 | $0 | 0.0% | **COLLECTING** |
| Fundamental growth + RS | 11 | 46% | $-2,376 | $-2,376 | $-1,418 | $-486 | 40.1% | **KILL** |

## Today's signals (BUY / HOLD / SELL)

### Source-priority allocator (TOP-1 only)  (`accepted_helper_source_priority_allocator`, max_concurrent=1)
- _new entries blocked: KILL verdict_
- hold WDC: day 6/10 (4 left); entry 632.76, last 550.30 (-13.0%)
- _skip_ DDOG (SKIP_concurrency_cap)
- _skip_ AFRM (SKIP_concurrency_cap)
- _skip_ CRS (SKIP_concurrency_cap)
- _skip_ NVMI (SKIP_concurrency_cap)
- _skip_ SITM (SKIP_concurrency_cap)
- _skip_ JAZZ (SKIP_concurrency_cap)
- _skip_ RPRX (SKIP_pilot_kill_verdict)

### Distribution-day absorption leadership  (`distribution_day_absorption_leadership`, max_concurrent=None)
- **SELL (EXIT_NEXT_SESSION)** GE: hold elapsed (day 9/10); entry 367.83, last 356.03
- hold AAL: day 7/10 (3 left); entry 17.50, last 16.52 (-5.6%)
- hold CAT: day 8/10 (2 left); entry 1032.37, last 948.08 (-8.2%)
- hold MOH: day 6/10 (4 left); entry 228.68, last 230.94 (+1.0%)

### Fundamental growth + RS  (`fundamental_growth_rs`, max_concurrent=None)
- _new entries blocked: KILL verdict_
- hold AMD: day 8/10 (2 left); entry 557.81, last 517.41 (-7.2%)
- hold CRDO: day 3/10 (7 left); entry 249.98, last 258.69 (+3.5%)
- hold DDOG: day 1/10 (9 left); entry 252.63, last 261.09 (+3.4%)

