# Pilot shadow tracker - as of 2026-07-18T04:41:00+00:00

Per-position shadow notional: $10,000. Read-only; no orders.
Measurement basis: paper-sleeve outcomes scaled to the fixed pilot notional; not broker-confirmed fills.
Paper verdicts retain the precommitted risk stop but are not eligible for live graduation/kill attribution.
Broker current-ticker overlap: 1/3; ticker presence is not lot or strategy attribution.
Graduate/kill rule (pre-committed): >= 20 closed AND sum rv_vs_SPY > 0 AND book DD < 15%.
Paper stop overlay: flag a shadow row at -15%; verify broker execution before acting.

## [!] Cross-pilot overlap (stacked exposure on one name)

- **DDOG**: shadow-held by 2 pilots (Source-priority allocator (TOP-1 only), Fundamental growth + RS) -> $20,000 modeled exposure
  - Source-priority allocator (TOP-1 only): HOLD, verdict KILL, new entries blocked
  - Fundamental growth + RS: HOLD, verdict KILL, new entries blocked

## [!] Cross-pilot shadow concentration (one theme, stacked models)

- **Technology** (sector): 4 positions across 2 pilot(s) (AMD, DDOG, MU) -> $40,000 (100% of actionable exposure)
- **Software - Application** (industry): 2 positions across 2 pilot(s) (DDOG) -> $20,000 (50% of actionable exposure)
- **Semiconductors** (industry): 2 positions across 1 pilot(s) (AMD, MU) -> $20,000 (50% of actionable exposure)

## Paper-shadow scorecard

| pilot | closed | hit | realized $ | rv_cash | rv_SPY | rv_QQQ | book DD | verdict |
|---|--:|--:|--:|--:|--:|--:|--:|---|
| Source-priority allocator (TOP-1 only) | 9 | 33% | $-5,469 | $-5,469 | $-6,072 | $-4,123 | 61.2% | **KILL** |
| Distribution-day absorption leadership | 4 | 25% | $-1,289 | $-1,289 | $-1,985 | $-1,218 | 18.1% | **KILL** |
| Fundamental growth + RS | 14 | 43% | $-3,241 | $-3,241 | $-2,400 | $-1,200 | 40.1% | **KILL** |

## Today's paper-shadow signals (verify broker execution before acting)

### Source-priority allocator (TOP-1 only)  (`accepted_helper_source_priority_allocator`, max_concurrent=1)
- _new entries blocked: KILL verdict_
- shadow hold DDOG: day 8/10 (2 left); entry 252.63, last 258.69 (+2.4%)
- _skip_ AFRM (SKIP_concurrency_cap)
- _skip_ CRS (SKIP_concurrency_cap)
- _skip_ RPRX (SKIP_concurrency_cap)
- _skip_ AKAM (SKIP_concurrency_cap)
- _skip_ NTAP (SKIP_concurrency_cap)
- _skip_ A (SKIP_concurrency_cap)
- _skip_ GGAL (SKIP_concurrency_cap)

### Distribution-day absorption leadership  (`distribution_day_absorption_leadership`, max_concurrent=None)
- _new entries blocked: KILL verdict_
- _no position / no signal today_

### Fundamental growth + RS  (`fundamental_growth_rs`, max_concurrent=None)
- _new entries blocked: KILL verdict_
- shadow hold AMD: day 8/10 (2 left); entry 544.28, last 495.76 (-8.9%)
- shadow hold MU: day 8/10 (2 left); entry 965.56, last 848.95 (-12.1%)
- shadow hold DDOG: day 1/10 (9 left); entry 256.40, last 258.69 (+0.9%)

