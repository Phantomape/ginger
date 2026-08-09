# Pilot shadow tracker - as of 2026-08-09T04:08:41+00:00

Per-position shadow notional: $10,000. Read-only; no orders.
Measurement basis: paper-sleeve outcomes scaled to the fixed pilot notional; not broker-confirmed fills.
Paper verdicts retain the precommitted risk stop but are not eligible for live graduation/kill attribution.
Broker current-ticker overlap: 2/5; ticker presence is not lot or strategy attribution.
Graduate/kill rule (pre-committed): >= 20 closed AND sum rv_vs_SPY > 0 AND book DD < 15%.
Paper stop overlay: flag a shadow row at -15%; verify broker execution before acting.

## [!] Cross-pilot shadow concentration (one theme, stacked models)

- **Technology** (sector): 4 positions across 2 pilot(s) (BSY, DDOG, NOW, PLTR) -> $40,000 (80% of actionable exposure)
- **Software - Application** (industry): 3 positions across 2 pilot(s) (BSY, DDOG, NOW) -> $30,000 (60% of actionable exposure)

## Paper-shadow scorecard

| pilot | closed | hit | realized $ | rv_cash | rv_SPY | rv_QQQ | book DD | verdict |
|---|--:|--:|--:|--:|--:|--:|--:|---|
| Source-priority allocator (TOP-1 only) | 21 | 43% | $-7,763 | $-7,763 | $-8,360 | $-4,266 | 96.4% | **KILL** |
| Distribution-day absorption leadership | 7 | 29% | $-2,196 | $-2,196 | $-3,823 | $-2,704 | 22.0% | **KILL** |
| Fundamental growth + RS | 18 | 44% | $-4,023 | $-4,023 | $-3,427 | $-1,832 | 42.8% | **KILL** |

## Today's paper-shadow signals (verify broker execution before acting)

### Source-priority allocator (TOP-1 only)  (`accepted_helper_source_priority_allocator`, max_concurrent=1)
- _new entries blocked: KILL verdict_
- shadow hold ALLE: day 2/10 (8 left); entry 169.48, last 168.94 (-0.3%)
- _skip_ ERIE (SKIP_concurrency_cap)
- _skip_ CDW (SKIP_concurrency_cap)
- _skip_ RBA (SKIP_concurrency_cap)
- _skip_ CPB (SKIP_concurrency_cap)
- _skip_ NICE (SKIP_pilot_kill_verdict)

### Distribution-day absorption leadership  (`distribution_day_absorption_leadership`, max_concurrent=None)
- _new entries blocked: KILL verdict_
- shadow hold BSY: day 7/10 (3 left); entry 34.23, last 35.21 (+2.9%)

### Fundamental growth + RS  (`fundamental_growth_rs`, max_concurrent=None)
- _new entries blocked: KILL verdict_
- shadow hold DDOG: day 4/10 (6 left); entry 273.12, last 233.93 (-14.3%)
- shadow hold PLTR: day 2/10 (8 left); entry 162.13, last 172.01 (+6.1%)
- shadow hold NOW: day 1/10 (9 left); entry 113.06, last 124.88 (+10.5%)

