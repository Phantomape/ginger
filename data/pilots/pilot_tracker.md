# Pilot tracker - as of 2026-07-07T06:34:59+00:00

Per-position book: $10,000. Read-only; manual execution.
Graduate/kill rule (pre-committed): >= 20 closed AND sum rv_vs_SPY > 0 AND book DD < 15%.
Manual stop overlay: cut a held position at -15% from entry (does not change the sleeve).

## [!] Cross-pilot theme concentration (one theme, stacked books)

- **Technology** (sector): 3 positions across 2 pilot(s) (AMD, DDOG, WDC) -> $30,000 (43% of actionable exposure)
- **Industrials** (sector): 3 positions across 1 pilot(s) (AAL, CAT, GE) -> $30,000 (43% of actionable exposure)

## Scorecard

| pilot | closed | hit | realized $ | rv_cash | rv_SPY | rv_QQQ | book DD | verdict |
|---|--:|--:|--:|--:|--:|--:|--:|---|
| Source-priority allocator (TOP-1 only) | 3 | 33% | $-1,181 | $-1,181 | $-1,084 | $-544 | 18.1% | **KILL** |
| Distribution-day absorption leadership | 0 | - | $0 | $0 | $0 | $0 | 0.0% | **COLLECTING** |
| Fundamental growth + RS | 10 | 40% | $-3,746 | $-3,746 | $-2,576 | $-1,869 | 40.1% | **KILL** |

## Today's signals (BUY / HOLD / SELL)

### Source-priority allocator (TOP-1 only)  (`accepted_helper_source_priority_allocator`, max_concurrent=1)
- _new entries blocked: KILL verdict_
- hold WDC: day 4/10 (6 left); entry 632.76, last 577.46 (-8.7%)
- _skip_ INTC (SKIP_concurrency_cap)
- _skip_ NVMI (SKIP_concurrency_cap)
- _skip_ SITM (SKIP_concurrency_cap)
- _skip_ SBUX (SKIP_concurrency_cap)
- _skip_ JAZZ (SKIP_concurrency_cap)
- _skip_ AFRM (SKIP_pilot_kill_verdict)
- _skip_ CRS (SKIP_pilot_kill_verdict)

### Distribution-day absorption leadership  (`distribution_day_absorption_leadership`, max_concurrent=None)
- hold GE: day 7/10 (3 left); entry 367.83, last 378.68 (+2.9%)
- hold AAL: day 5/10 (5 left); entry 17.50, last 17.75 (+1.4%)
- hold CAT: day 6/10 (4 left); entry 1032.37, last 969.92 (-6.0%)
- hold MOH: day 4/10 (6 left); entry 228.68, last 227.70 (-0.4%)

### Fundamental growth + RS  (`fundamental_growth_rs`, max_concurrent=None)
- _new entries blocked: KILL verdict_
- **SELL (EXIT_NEXT_SESSION)** DDOG: hold elapsed (day 9/10); entry 225.05, last 255.37
- hold AMD: day 4/10 (6 left); entry 557.81, last 552.05 (-1.0%)
- _skip_ CRDO (SKIP_pilot_kill_verdict)

