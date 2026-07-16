# Pilot shadow tracker - as of 2026-07-16T05:40:36+00:00

Per-position shadow notional: $10,000. Read-only; no orders.
Measurement basis: paper-sleeve outcomes scaled to the fixed pilot notional; not broker-confirmed fills.
Paper verdicts retain the precommitted risk stop but are not eligible for live graduation/kill attribution.
Broker current-ticker overlap: 1/3; ticker presence is not lot or strategy attribution.
Graduate/kill rule (pre-committed): >= 20 closed AND sum rv_vs_SPY > 0 AND book DD < 15%.
Paper stop overlay: flag a shadow row at -15%; verify broker execution before acting.

## [!] Cross-pilot overlap (stacked exposure on one name)

- **DDOG**: shadow-held by 2 pilots (Source-priority allocator (TOP-1 only), Fundamental growth + RS) -> $20,000 modeled exposure
  - Source-priority allocator (TOP-1 only): HOLD, verdict KILL, new entries blocked
  - Fundamental growth + RS: EXIT_NEXT_SESSION, verdict KILL, new entries blocked

## [!] Cross-pilot shadow concentration (one theme, stacked models)

- **Technology** (sector): 4 positions across 2 pilot(s) (AMD, DDOG, MU) -> $40,000 (100% of actionable exposure)
- **Software - Application** (industry): 2 positions across 2 pilot(s) (DDOG) -> $20,000 (50% of actionable exposure)
- **Semiconductors** (industry): 2 positions across 1 pilot(s) (AMD, MU) -> $20,000 (50% of actionable exposure)

## Paper-shadow scorecard

| pilot | closed | hit | realized $ | rv_cash | rv_SPY | rv_QQQ | book DD | verdict |
|---|--:|--:|--:|--:|--:|--:|--:|---|
| Source-priority allocator (TOP-1 only) | 9 | 33% | $-5,469 | $-5,469 | $-6,072 | $-4,123 | 61.2% | **KILL** |
| Distribution-day absorption leadership | 4 | 25% | $-1,289 | $-1,289 | $-1,985 | $-1,218 | 18.1% | **KILL** |
| Fundamental growth + RS | 13 | 38% | $-3,584 | $-3,584 | $-2,687 | $-1,574 | 40.1% | **KILL** |

## Today's paper-shadow signals (verify broker execution before acting)

### Source-priority allocator (TOP-1 only)  (`accepted_helper_source_priority_allocator`, max_concurrent=1)
- _new entries blocked: KILL verdict_
- shadow hold DDOG: day 6/10 (4 left); entry 252.63, last 264.46 (+4.7%)
- _skip_ AFRM (SKIP_concurrency_cap)
- _skip_ CRS (SKIP_concurrency_cap)
- _skip_ RPRX (SKIP_concurrency_cap)
- _skip_ AKAM (SKIP_concurrency_cap)
- _skip_ NTAP (SKIP_concurrency_cap)
- _skip_ A (SKIP_concurrency_cap)
- _skip_ GGAL (SKIP_pilot_kill_verdict)

### Distribution-day absorption leadership  (`distribution_day_absorption_leadership`, max_concurrent=None)
- _new entries blocked: KILL verdict_
- _no position / no signal today_

### Fundamental growth + RS  (`fundamental_growth_rs`, max_concurrent=None)
- _new entries blocked: KILL verdict_
- **SHADOW SELL (EXIT_NEXT_SESSION; VERIFY BROKER)** DDOG: hold elapsed (day 9/10); entry 252.63, last 264.46
- shadow hold AMD: day 5/10 (5 left); entry 544.28, last 529.14 (-2.8%)
- shadow hold MU: day 5/10 (5 left); entry 965.56, last 904.28 (-6.3%)

