# Pilot tracker - as of 2026-06-30T05:46:43+00:00

Per-position book: $10,000. Read-only; manual execution.
Graduate/kill rule (pre-committed): >= 20 closed AND sum rv_vs_SPY > 0 AND book DD < 15%.
Manual stop overlay: cut a held position at -15% from entry (does not change the sleeve).

## [!] STOP-LOSS alerts - cut by hand today (stop = -15%)

- **SELL CRDO** (Fundamental growth + RS): -15.3% from entry 290.11 -> last 245.68

## [!] Cross-pilot overlap (stacked exposure on one name)

- **DDOG**: held by 2 pilots (Source-priority allocator (TOP-1 only), Fundamental growth + RS) -> $20,000 real exposure
  - Source-priority allocator (TOP-1 only): HOLD, verdict COLLECTING
  - Fundamental growth + RS: HOLD, verdict KILL, new entries blocked

## Scorecard

| pilot | closed | hit | realized $ | rv_cash | rv_SPY | rv_QQQ | book DD | verdict |
|---|--:|--:|--:|--:|--:|--:|--:|---|
| Source-priority allocator (TOP-1 only) | 1 | 0% | $-945 | $-945 | $-929 | $-990 | 9.4% | **COLLECTING** |
| Distribution-day absorption leadership | 0 | - | $0 | $0 | $0 | $0 | 0.0% | **COLLECTING** |
| Fundamental growth + RS | 7 | 43% | $-2,178 | $-2,178 | $-631 | $-232 | 24.4% | **KILL** |

## Today's signals (BUY / HOLD / SELL)

### Source-priority allocator (TOP-1 only)  (`accepted_helper_source_priority_allocator`, max_concurrent=1)
- hold DDOG: day 7/10 (3 left); entry 224.15, last 248.57 (+10.9%)
- _skip_ INTC (SKIP_concurrency_cap)
- _skip_ MU (SKIP_concurrency_cap)
- _skip_ NVMI (SKIP_concurrency_cap)
- _skip_ SITM (SKIP_concurrency_cap)
- _skip_ SBUX (SKIP_concurrency_cap)
- _skip_ WDC (SKIP_concurrency_cap)
- _skip_ JAZZ (SKIP_concurrency_cap)

### Distribution-day absorption leadership  (`distribution_day_absorption_leadership`, max_concurrent=None)
- hold GE: day 3/10 (7 left); entry 367.83, last 373.71 (+1.6%)
- hold AAL: day 2/10 (8 left); entry 17.50, last 17.92 (+2.4%)
- hold CAT: day 2/10 (8 left); entry 1032.37, last 1033.19 (+0.1%)
- hold MOH: day 1/10 (9 left); entry 228.68, last 229.54 (+0.4%)

### Fundamental growth + RS  (`fundamental_growth_rs`, max_concurrent=None)
- _new entries blocked: KILL verdict_
- **SELL (EXIT_NEXT_SESSION)** AMD: hold elapsed (day 9/10); entry 508.83, last 539.49
- hold CRDO: day 4/10 (6 left); entry 290.11, last 245.68 (-15.3%) **[STOP_HIT -> SELL]**
- hold MU: day 4/10 (6 left); entry 1233.97, last 1145.28 (-7.2%)
- hold DDOG: day 2/10 (8 left); entry 225.05, last 248.57 (+10.4%)

