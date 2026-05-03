# SEC / Earnings / Filing Shock No-New-Evidence Guardrail - exp-20260503-024

## Hypothesis

SEC filing shock, financial surprise, 8-K event type, and post-earnings drift may improve C-strategy grading or A/B event confirmation. This run only checks whether new PIT-safe evidence arrived after `exp-20260503-022`.

## Mechanism Family

`earnings_sec_filing_shock_event_confirmation_overlay`

## Single Causal Variable

`new PIT-safe SEC / earnings filing-shock evidence since exp-20260503-022`

## Historical Experiment Check

- `exp-20260503-002`: first earnings + SEC surprise schema; coverage-blocked.
- `exp-20260503-004`: SEC archive audit found zero persisted SEC rows before diagnostics.
- `exp-20260503-005`: CIK-to-ticker mapping works on live SEC feeds.
- `exp-20260503-006`: broad filing scout showed broad filings are not alpha; 10-K and ADV >= $5M were the useful branch.
- `exp-20260503-011`: liquidity-gated 10-K scout was positive but static/shadow and not PIT-qualified.
- `exp-20260503-013`: rejected another static universe scout without new PIT/forward evidence.
- `exp-20260503-016`: exact SEC / earnings / filing-shock audit; produced the normalized shadow table and concluded `data_gap`.
- `exp-20260503-019`: duplicate guardrail recheck; found no new SEC source archive or XBRL/companyfacts field coverage.
- `exp-20260503-022`: duplicate guardrail recheck; again found no new SEC source archive or XBRL/companyfacts field coverage.

Playbook check: earnings + SEC + financial surprise remains the top-ranked external alpha source, but C-strategy single-field/checklist repair is downgraded. This run therefore does not rerun scoring or slot tie-breakers on unchanged data.

## Data Availability And PIT Status

| Source | Current local coverage | PIT status | Blocking gap |
|---|---:|---|---|
| Earnings snapshots | 137 files, 6033 ticker rows | Snapshot PIT for archived dates | No revenue/margin/FCF/inventory/receivables fields |
| Earnings EPS estimate | 5198 rows (86.16%) | PIT if snapshot date <= trade date | Vendor/parser quality not independently audited |
| Earnings surprise history | 5198 rows (86.16%) | PIT if snapshot date <= trade date | Extreme values still need winsor/audit before scoring |
| SEC Atom filings | Existing `data/news_20260502.json` only | Forward archive only | No new archive since `exp-20260503-022` |
| SEC source diagnostics | Existing `data/news_source_stats_20260502.json` only | Forward diagnostic only | Need multiple forward days |
| SEC submissions cache | 100 CIK files | Static cache only | Not a historical as-of ledger |
| SEC XBRL/companyfacts metrics | 0 local normalized rows | Missing | Need adapter before quality-of-surprise grading |

## Baseline Metrics

No production logic changed. Baseline remains the accepted canonical stack:

| Window | EV | Return | PnL | Sharpe daily | Max DD | Win rate | Trades | Signals gen/surv | Survival | vs SPY | vs QQQ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 78.60% | $78,600.33 | 4.35 | 5.41% | 78.95% | 19 | 51/41 | 80.39% | 73.19% | 72.80% |
| mid_weak | 1.4415 | 55.02% | $55,015.08 | 2.62 | 8.79% | 52.38% | 21 | 53/42 | 79.25% | 29.58% | 21.51% |
| old_thin | 0.3179 | 24.64% | $24,642.07 | 1.29 | 8.05% | 40.91% | 22 | 60/55 | 91.67% | 31.37% | 32.13% |

## Shadow Event Table

This run reused the existing normalized shadow table:

- Table: `data/non_ohlcv/sec_filing_shadow_events_20260503.json`
- Rows: 300
- Ticker-mapped rows: 284
- Unique tickers: 279
- Form counts: `10-K=100, 10-Q=100, 8-K=100`
- Shock tag counts: `negative filing shock=4, unclear / missing data=296`
- Current production/pilot universe overlap rows: 1
- New rows since `exp-20260503-022`: 0

## Shadow Metrics

Forward returns are still not measurable. The only normalized SEC archive is dated `2026-05-02`, no new archive appeared after the previous recheck, and no 5/10/20/60d outcome window has closed.

Candidate overlap and slot value:

- Existing shadow candidate count: 300
- New shadow candidate count since prior recheck: 0
- Current production/pilot overlap: 1 row (`TSLA`, `10-K`, `unclear / missing data`)
- Historical A/B overlap: blocked by missing PIT SEC archives across canonical windows
- Scarce-slot opportunity cost: not measurable
- Expected value score delta: `0.0`

## Decision

`data_gap`

The SEC/earnings filing-shock branch remains worth watching, but another same-archive replay would repeat `exp-20260503-016`, `exp-20260503-019`, and `exp-20260503-022`. Do not promote to production, default-off replay, C-strategy grading, or slot tie-breaker until new forward SEC archive days or PIT XBRL/companyfacts rows exist.

## Production Impact

```json
{
  "shared_policy_changed": false,
  "backtester_adapter_changed": false,
  "run_adapter_changed": false,
  "replay_only": true,
  "parity_test_added": false,
  "production_impact": "data_audit_only"
}
```

## Next Minimum Action

Accumulate at least 5-10 new forward SEC archive days with ticker tags, or add a PIT XBRL/companyfacts field-fill adapter. Only then rerun filing-shock grading, breakout confirmation, or scarce-slot value tests.
