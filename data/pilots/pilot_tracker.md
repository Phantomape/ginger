# Pilot shadow tracker - as of 2026-08-30T04:13:00+00:00

Per-position shadow notional: $10,000. Read-only; no orders.
Measurement basis: paper-sleeve outcomes scaled to the fixed pilot notional; not broker-confirmed fills.
Paper verdicts retain the precommitted risk stop but are not eligible for live graduation/kill attribution.
Broker current-ticker overlap: 2/5; ticker presence is not lot or strategy attribution.
Graduate/kill rule (pre-committed): >= 20 closed AND sum rv_vs_SPY > 0 AND book DD < 15%.
Paper stop overlay: flag a shadow row at -15%; verify broker execution before acting.

## [!] Cross-pilot shadow concentration (one theme, stacked models)

- **Technology** (sector): 5 positions across 2 pilot(s) (CRDO, MU, NOW, PLTR, WDC) -> $50,000 (100% of actionable exposure)

## Paper-shadow scorecard

| pilot | closed | hit | realized $ | rv_cash | rv_SPY | rv_QQQ | book DD | verdict |
|---|--:|--:|--:|--:|--:|--:|--:|---|
| Source-priority allocator (TOP-1 only) | 28 | 43% | $-10,766 | $-10,766 | $-12,407 | $-8,967 | 115.0% | **KILL** |
| Distribution-day absorption leadership | 8 | 38% | $-1,648 | $-1,648 | $-3,732 | $-2,922 | 22.0% | **KILL** |
| Fundamental growth + RS | 22 | 46% | $-4,021 | $-4,021 | $-3,208 | $-1,846 | 53.1% | **KILL** |

## Today's paper-shadow signals (verify broker execution before acting)

### Source-priority allocator (TOP-1 only)  (`accepted_helper_source_priority_allocator`, max_concurrent=1)
- _new entries blocked: KILL verdict_
- **SHADOW SELL (EXIT_NEXT_SESSION; VERIFY BROKER)** WDC: hold elapsed (day 9/10); entry 503.75, last 462.00
- _skip_ FNV (SKIP_concurrency_cap)
- _skip_ AGI (SKIP_concurrency_cap)
- _skip_ DINO (SKIP_concurrency_cap)
- _skip_ HPQ (SKIP_concurrency_cap)
- _skip_ DDOG (SKIP_concurrency_cap)
- _skip_ EOG (SKIP_concurrency_cap)
- _skip_ CDW (SKIP_pilot_kill_verdict)

### Distribution-day absorption leadership  (`distribution_day_absorption_leadership`, max_concurrent=None)
- _new entries blocked: KILL verdict_
- _no position / no signal today_

### Fundamental growth + RS  (`fundamental_growth_rs`, max_concurrent=None)
- _new entries blocked: KILL verdict_
- **SHADOW SELL (EXIT_NEXT_SESSION; VERIFY BROKER)** MU: hold elapsed (day 9/10); entry 999.17, last 932.86
- shadow hold PLTR: day 5/10 (5 left); entry 174.07, last 186.29 (+7.0%)
- shadow hold NOW: day 4/10 (6 left); entry 128.12, last 144.71 (+13.0%)
- shadow hold CRDO: day 0/10 (10 left); entry 239.78, last 232.75 (-2.9%)

