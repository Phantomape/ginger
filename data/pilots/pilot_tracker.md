# Pilot shadow tracker - as of 2026-07-14T05:15:35+00:00

Per-position shadow notional: $10,000. Read-only; no orders.
Measurement basis: paper-sleeve outcomes scaled to the fixed pilot notional; not broker-confirmed fills.
Paper verdicts retain the precommitted risk stop but are not eligible for live graduation/kill attribution.
Broker current-ticker overlap: 2/6; ticker presence is not lot or strategy attribution.
Graduate/kill rule (pre-committed): >= 20 closed AND sum rv_vs_SPY > 0 AND book DD < 15%.
Paper stop overlay: flag a shadow row at -15%; verify broker execution before acting.

## [!] Cross-pilot shadow concentration (one theme, stacked models)

- **Technology** (sector): 5 positions across 2 pilot(s) (AMD, CRDO, DDOG, MU, WDC) -> $50,000 (83% of actionable exposure)
- **Semiconductors** (industry): 3 positions across 1 pilot(s) (AMD, CRDO, MU) -> $30,000 (50% of actionable exposure)

## Paper-shadow scorecard

| pilot | closed | hit | realized $ | rv_cash | rv_SPY | rv_QQQ | book DD | verdict |
|---|--:|--:|--:|--:|--:|--:|--:|---|
| Source-priority allocator (TOP-1 only) | 7 | 29% | $-4,352 | $-4,352 | $-4,721 | $-3,246 | 49.8% | **KILL** |
| Distribution-day absorption leadership | 3 | 0% | $-1,812 | $-1,812 | $-2,345 | $-1,706 | 18.1% | **KILL** |
| Fundamental growth + RS | 12 | 42% | $-2,615 | $-2,615 | $-1,702 | $-599 | 40.1% | **KILL** |

## Today's paper-shadow signals (verify broker execution before acting)

### Source-priority allocator (TOP-1 only)  (`accepted_helper_source_priority_allocator`, max_concurrent=1)
- _new entries blocked: KILL verdict_
- **SHADOW SELL (EXIT_NEXT_SESSION; VERIFY BROKER)** WDC: hold elapsed (day 9/10); entry 632.76, last 555.55
- _skip_ DDOG (SKIP_concurrency_cap)
- _skip_ AFRM (SKIP_concurrency_cap)
- _skip_ CRS (SKIP_concurrency_cap)
- _skip_ RPRX (SKIP_concurrency_cap)
- _skip_ AKAM (SKIP_concurrency_cap)
- _skip_ A (SKIP_concurrency_cap)
- _skip_ JAZZ (SKIP_concurrency_cap)

### Distribution-day absorption leadership  (`distribution_day_absorption_leadership`, max_concurrent=None)
- _new entries blocked: KILL verdict_
- **SHADOW SELL (EXIT_NEXT_SESSION; VERIFY BROKER)** MOH: hold elapsed (day 9/10); entry 228.68, last 242.88

### Fundamental growth + RS  (`fundamental_growth_rs`, max_concurrent=None)
- _new entries blocked: KILL verdict_
- shadow hold CRDO: day 8/10 (2 left); entry 249.98, last 236.88 (-5.2%)
- shadow hold DDOG: day 6/10 (4 left); entry 252.63, last 260.24 (+3.0%)
- shadow hold AMD: day 2/10 (8 left); entry 544.28, last 534.39 (-1.8%)
- shadow hold MU: day 2/10 (8 left); entry 965.56, last 937.00 (-3.0%)

