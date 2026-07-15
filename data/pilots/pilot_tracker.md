# Pilot shadow tracker - as of 2026-07-15T03:41:06+00:00

Per-position shadow notional: $10,000. Read-only; no orders.
Measurement basis: paper-sleeve outcomes scaled to the fixed pilot notional; not broker-confirmed fills.
Paper verdicts retain the precommitted risk stop but are not eligible for live graduation/kill attribution.
Broker current-ticker overlap: 2/4; ticker presence is not lot or strategy attribution.
Graduate/kill rule (pre-committed): >= 20 closed AND sum rv_vs_SPY > 0 AND book DD < 15%.
Paper stop overlay: flag a shadow row at -15%; verify broker execution before acting.

## [!] Cross-pilot overlap (stacked exposure on one name)

- **DDOG**: shadow-held by 2 pilots (Source-priority allocator (TOP-1 only), Fundamental growth + RS) -> $20,000 modeled exposure
  - Source-priority allocator (TOP-1 only): HOLD, verdict KILL, new entries blocked
  - Fundamental growth + RS: HOLD, verdict KILL, new entries blocked

## [!] Cross-pilot shadow concentration (one theme, stacked models)

- **Technology** (sector): 5 positions across 2 pilot(s) (AMD, CRDO, DDOG, MU) -> $50,000 (100% of actionable exposure)
- **Semiconductors** (industry): 3 positions across 1 pilot(s) (AMD, CRDO, MU) -> $30,000 (60% of actionable exposure)

## Paper-shadow scorecard

| pilot | closed | hit | realized $ | rv_cash | rv_SPY | rv_QQQ | book DD | verdict |
|---|--:|--:|--:|--:|--:|--:|--:|---|
| Source-priority allocator (TOP-1 only) | 8 | 25% | $-5,489 | $-5,489 | $-5,955 | $-4,276 | 61.2% | **KILL** |
| Distribution-day absorption leadership | 4 | 25% | $-1,289 | $-1,289 | $-1,985 | $-1,218 | 18.1% | **KILL** |
| Fundamental growth + RS | 12 | 42% | $-2,615 | $-2,615 | $-1,702 | $-599 | 40.1% | **KILL** |

## Today's paper-shadow signals (verify broker execution before acting)

### Source-priority allocator (TOP-1 only)  (`accepted_helper_source_priority_allocator`, max_concurrent=1)
- _new entries blocked: KILL verdict_
- shadow hold DDOG: day 5/10 (5 left); entry 252.63, last 270.73 (+7.2%)
- _skip_ AFRM (SKIP_concurrency_cap)
- _skip_ CRS (SKIP_concurrency_cap)
- _skip_ RPRX (SKIP_concurrency_cap)
- _skip_ AKAM (SKIP_concurrency_cap)
- _skip_ A (SKIP_concurrency_cap)
- _skip_ JAZZ (SKIP_concurrency_cap)
- _skip_ NTAP (SKIP_pilot_kill_verdict)

### Distribution-day absorption leadership  (`distribution_day_absorption_leadership`, max_concurrent=None)
- _new entries blocked: KILL verdict_
- _no position / no signal today_

### Fundamental growth + RS  (`fundamental_growth_rs`, max_concurrent=None)
- _new entries blocked: KILL verdict_
- **SHADOW SELL (EXIT_NEXT_SESSION; VERIFY BROKER)** CRDO: hold elapsed (day 9/10); entry 249.98, last 236.18
- shadow hold DDOG: day 7/10 (3 left); entry 252.63, last 270.73 (+7.2%)
- shadow hold AMD: day 3/10 (7 left); entry 544.28, last 548.13 (+0.7%)
- shadow hold MU: day 3/10 (7 left); entry 965.56, last 983.12 (+1.8%)

