# Pilot shadow tracker - as of 2026-10-07T01:57:42+00:00

Per-position shadow notional: $10,000. Read-only; no orders.
Measurement basis: paper-sleeve outcomes scaled to the fixed pilot notional; not broker-confirmed fills.
Paper verdicts retain the precommitted risk stop but are not eligible for live graduation/kill attribution.
Broker current-ticker overlap: 1/6; ticker presence is not lot or strategy attribution.
Graduate/kill rule (pre-committed): >= 20 closed AND sum rv_vs_SPY > 0 AND book DD < 15%.
Paper stop overlay: flag a shadow row at -15%; verify broker execution before acting.

## [!] Cross-pilot overlap (stacked exposure on one name)

- **AMD**: shadow-held by 2 pilots (Distribution-day absorption leadership, Fundamental growth + RS) -> $20,000 modeled exposure
  - Distribution-day absorption leadership: HOLD, verdict KILL, new entries blocked
  - Fundamental growth + RS: HOLD, verdict KILL, new entries blocked

## [!] Cross-pilot shadow concentration (one theme, stacked models)

- **Technology** (sector): 5 positions across 2 pilot(s) (AMD, MU, NOW, PLTR) -> $50,000 (71% of actionable exposure)
- **Semiconductors** (industry): 3 positions across 2 pilot(s) (AMD, MU) -> $30,000 (43% of actionable exposure)

## Paper-shadow scorecard

| pilot | closed | hit | realized $ | rv_cash | rv_SPY | rv_QQQ | book DD | verdict |
|---|--:|--:|--:|--:|--:|--:|--:|---|
| Distribution-day absorption leadership | 12 | 50% | $346 | $346 | $-1,633 | $-1,936 | 22.0% | **KILL** |
| Fundamental growth + RS | 29 | 48% | $-4,693 | $-4,693 | $-3,539 | $-3,145 | 83.2% | **KILL** |

## Today's paper-shadow signals (verify broker execution before acting)

### Distribution-day absorption leadership  (`distribution_day_absorption_leadership`, max_concurrent=None)
- _new entries blocked: KILL verdict_
- shadow hold BRKR: day 7/10 (3 left); entry 61.93, last 60.50 (-2.3%)
- shadow hold AMD: day 6/10 (4 left); entry 547.64, last 649.42 (+18.6%)

### Fundamental growth + RS  (`fundamental_growth_rs`, max_concurrent=None)
- _new entries blocked: KILL verdict_
- shadow hold NOW: day 8/10 (2 left); entry 139.22, last 135.62 (-2.6%)
- shadow hold META: day 6/10 (4 left); entry 682.78, last 751.66 (+10.1%)
- shadow hold PLTR: day 1/10 (9 left); entry 189.29, last 189.67 (+0.2%)
- shadow hold AMD: day 1/10 (9 left); entry 634.86, last 649.42 (+2.3%)
- shadow hold MU: day 0/10 (10 left); entry 1065.01, last 1045.56 (-1.8%)
- _skip_ NVDA (SKIP_pilot_kill_verdict)

