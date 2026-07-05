# Pilot tracker - as of 2026-07-05T03:27:53+00:00

Per-position book: $10,000. Read-only; manual execution.
Graduate/kill rule (pre-committed): >= 20 closed AND sum rv_vs_SPY > 0 AND book DD < 15%.
Manual stop overlay: cut a held position at -15% from entry (does not change the sleeve).

## [!] STOP-LOSS alerts - cut by hand today (stop = -15%)

- **SELL CRDO** (Fundamental growth + RS): -16.6% from entry 290.11 -> last 241.91
- **SELL MU** (Fundamental growth + RS): -20.9% from entry 1233.97 -> last 975.56

## Scorecard

| pilot | closed | hit | realized $ | rv_cash | rv_SPY | rv_QQQ | book DD | verdict |
|---|--:|--:|--:|--:|--:|--:|--:|---|
| Source-priority allocator (TOP-1 only) | 2 | 50% | $630 | $630 | $730 | $963 | 9.4% | **COLLECTING** |
| Distribution-day absorption leadership | 0 | - | $0 | $0 | $0 | $0 | 0.0% | **COLLECTING** |
| Fundamental growth + RS | 8 | 50% | $-802 | $-802 | $613 | $900 | 24.4% | **KILL** |

## Today's signals (BUY / HOLD / SELL)

### Source-priority allocator (TOP-1 only)  (`accepted_helper_source_priority_allocator`, max_concurrent=1)
- hold WDC: day 3/10 (7 left); entry 632.76, last 539.00 (-14.8%)
- _skip_ INTC (SKIP_concurrency_cap)
- _skip_ MU (SKIP_concurrency_cap)
- _skip_ NVMI (SKIP_concurrency_cap)
- _skip_ SITM (SKIP_concurrency_cap)
- _skip_ SBUX (SKIP_concurrency_cap)
- _skip_ JAZZ (SKIP_concurrency_cap)

### Distribution-day absorption leadership  (`distribution_day_absorption_leadership`, max_concurrent=None)
- hold GE: day 6/10 (4 left); entry 367.83, last 377.52 (+2.6%)
- hold AAL: day 4/10 (6 left); entry 17.50, last 18.15 (+3.7%)
- hold CAT: day 5/10 (5 left); entry 1032.37, last 963.53 (-6.7%)
- hold MOH: day 3/10 (7 left); entry 228.68, last 232.55 (+1.7%)

### Fundamental growth + RS  (`fundamental_growth_rs`, max_concurrent=None)
- _new entries blocked: KILL verdict_
- **SELL (EXIT_NEXT_SESSION)** CRDO: hold elapsed (day 9/10); entry 290.11, last 241.91
- **SELL (EXIT_NEXT_SESSION)** MU: hold elapsed (day 9/10); entry 1233.97, last 975.56
- hold DDOG: day 7/10 (3 left); entry 225.05, last 260.36 (+15.7%)
- hold AMD: day 2/10 (8 left); entry 557.81, last 517.82 (-7.2%)

