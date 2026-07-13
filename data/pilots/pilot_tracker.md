# Pilot shadow tracker - as of 2026-07-13T03:31:33+00:00

Per-position shadow notional: $10,000. Read-only; no orders.
Measurement basis: paper-sleeve outcomes scaled to the fixed pilot notional; not broker-confirmed fills.
Paper verdicts retain the precommitted risk stop but are not eligible for live graduation/kill attribution.
Broker current-ticker overlap: 2/7; ticker presence is not lot or strategy attribution.
Graduate/kill rule (pre-committed): >= 20 closed AND sum rv_vs_SPY > 0 AND book DD < 15%.
Paper stop overlay: flag a shadow row at -15%; verify broker execution before acting.

## [!] Cross-pilot shadow concentration (one theme, stacked models)

- **Technology** (sector): 5 positions across 2 pilot(s) (AMD, CRDO, DDOG, MU, WDC) -> $50,000 (71% of actionable exposure)
- **Semiconductors** (industry): 3 positions across 1 pilot(s) (AMD, CRDO, MU) -> $30,000 (43% of actionable exposure)

## Paper-shadow scorecard

| pilot | closed | hit | realized $ | rv_cash | rv_SPY | rv_QQQ | book DD | verdict |
|---|--:|--:|--:|--:|--:|--:|--:|---|
| Source-priority allocator (TOP-1 only) | 7 | 29% | $-4,352 | $-4,352 | $-4,721 | $-3,246 | 49.8% | **KILL** |
| Distribution-day absorption leadership | 2 | 0% | $-1,093 | $-1,093 | $-1,532 | $-1,227 | 10.9% | **COLLECTING** |
| Fundamental growth + RS | 12 | 42% | $-2,615 | $-2,615 | $-1,702 | $-599 | 40.1% | **KILL** |

## Today's paper-shadow signals (verify broker execution before acting)

### Source-priority allocator (TOP-1 only)  (`accepted_helper_source_priority_allocator`, max_concurrent=1)
- _new entries blocked: KILL verdict_
- shadow hold WDC: day 8/10 (2 left); entry 632.76, last 582.59 (-7.9%)
- _skip_ DDOG (SKIP_concurrency_cap)
- _skip_ AFRM (SKIP_concurrency_cap)
- _skip_ CRS (SKIP_concurrency_cap)
- _skip_ RPRX (SKIP_concurrency_cap)
- _skip_ AKAM (SKIP_concurrency_cap)
- _skip_ A (SKIP_concurrency_cap)
- _skip_ JAZZ (SKIP_concurrency_cap)

### Distribution-day absorption leadership  (`distribution_day_absorption_leadership`, max_concurrent=None)
- **SHADOW SELL (EXIT_NEXT_SESSION; VERIFY BROKER)** AAL: hold elapsed (day 9/10); entry 17.50, last 16.95
- shadow hold MOH: day 8/10 (2 left); entry 228.68, last 233.31 (+2.0%)

### Fundamental growth + RS  (`fundamental_growth_rs`, max_concurrent=None)
- _new entries blocked: KILL verdict_
- shadow hold CRDO: day 6/10 (4 left); entry 249.98, last 257.79 (+3.1%)
- shadow hold DDOG: day 4/10 (6 left); entry 252.63, last 257.54 (+1.9%)
- shadow hold AMD: day 0/10 (10 left); entry 544.28, last 557.89 (+2.5%)
- shadow hold MU: day 0/10 (10 left); entry 965.56, last 979.30 (+1.4%)

