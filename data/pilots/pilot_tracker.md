# Pilot tracker - as of 2026-06-24T10:15:37+00:00

Per-position book: $10,000. Read-only; manual execution.
Graduate/kill rule (pre-committed): >= 20 closed AND sum rv_vs_SPY > 0 AND book DD < 15%.
Manual stop overlay: cut a held position at -15% from entry (does not change the sleeve).

## [!] Cross-pilot overlap (stacked exposure on one name)

- **DDOG**: held by 2 pilots (Source-priority allocator (TOP-1 only), Fundamental growth + RS) -> $20,000 real exposure
  - Source-priority allocator (TOP-1 only): HOLD, verdict COLLECTING
  - Fundamental growth + RS: HOLD, verdict KILL, new entries blocked

## Scorecard

| pilot | closed | hit | realized $ | rv_cash | rv_SPY | rv_QQQ | book DD | verdict |
|---|--:|--:|--:|--:|--:|--:|--:|---|
| Source-priority allocator (TOP-1 only) | 0 | - | $0 | $0 | $0 | $0 | 0.0% | **COLLECTING** |
| Distribution-day absorption leadership | 0 | - | $0 | $0 | $0 | $0 | 0.0% | **COLLECTING** |
| Fundamental growth + RS | 5 | 60% | $-1,228 | $-1,228 | $-230 | $-54 | 24.3% | **KILL** |

## Today's signals (BUY / HOLD / SELL)

### Source-priority allocator (TOP-1 only)  (`accepted_helper_source_priority_allocator`, max_concurrent=1)
- hold DDOG: day 3/10 (7 left); entry 224.15, last 220.57 (-1.6%)
- _skip_ INTC (SKIP_concurrency_cap)
- _skip_ MU (SKIP_concurrency_cap)
- _skip_ CRDO (SKIP_concurrency_cap)
- _skip_ NVMI (SKIP_concurrency_cap)
- _skip_ SITM (SKIP_concurrency_cap)
- _skip_ SBUX (SKIP_concurrency_cap)
- _skip_ WDC (SKIP_concurrency_cap)

### Distribution-day absorption leadership  (`distribution_day_absorption_leadership`, max_concurrent=None)
- _no position / no signal today_

### Fundamental growth + RS  (`fundamental_growth_rs`, max_concurrent=None)
- _new entries blocked: KILL verdict_
- hold MU: day 8/10 (2 left); entry 1099.93, last 1051.77 (-4.4%)
- hold DDOG: day 7/10 (3 left); entry 230.19, last 220.57 (-4.2%)
- hold AMD: day 2/10 (8 left); entry 508.83, last 519.85 (+2.2%)

