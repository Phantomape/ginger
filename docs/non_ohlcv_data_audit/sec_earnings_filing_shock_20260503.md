# SEC / Earnings / Filing Shock Non-OHLCV Audit - exp-20260503-016

## Hypothesis

SEC filing shock, financial surprise, 8-K event type, and post-earnings drift may become a stronger C-strategy event grading layer or A/B event-confirmation overlay. This run tests only data availability and PIT readiness.

## Mechanism Family

`earnings_sec_filing_shock_event_confirmation_overlay`

## Single Causal Variable

`SEC / earnings filing-shock data availability and PIT status only`

## Historical Experiment Check

- `exp-20260503-002`: first earnings + SEC surprise schema; coverage-blocked, zero SEC-backed trade contexts.
- `exp-20260503-004`: SEC archive audit found zero persisted SEC rows before diagnostics.
- `exp-20260503-005`: CIK-to-ticker mapping works on live SEC feeds; 284/300 rows mapped, current universe overlap was one row.
- `exp-20260503-006`: broad filing scout showed broad SEC filings are not alpha; 10-K and ADV >= $5M were the only useful branch.
- `exp-20260503-011`: liquidity-gated 10-K scout was shadow-only/replay-candidate but not PIT qualified.
- `exp-20260503-013`: explicitly rejected another static universe scout without new PIT/forward evidence.

This run does not repeat a static scout. It formalizes the current data gap and writes a normalized shadow table from the existing forward SEC archive.

## Data Availability And PIT Status

| Source | Current local coverage | PIT status | Blocking gap |
|---|---:|---|---|
| Earnings snapshots | 137 files, 6033 ticker rows | Snapshot PIT for archived dates | No revenue/margin/FCF/inventory/receivables fields |
| Earnings EPS estimate | 5198 rows (86.2%) | PIT if snapshot date <= trade date | Vendor/parser quality not independently audited |
| Earnings surprise history | 5198 rows (86.2%) | PIT if snapshot date <= trade date | Some extreme surprise values need winsor/audit before scoring |
| SEC Atom filings | 300 items in `data/news_20260502.json` | Forward archive only | One archive day is not enough for historical replay |
| SEC ticker mapping | 284/300 rows mapped, 279 unique tickers | Current cache, not historical ledger | Historical mapping as-of date not frozen |
| Current trade-universe overlap | 1 rows | Forward-observable | Too sparse for C/A/B overlay conclusions |
| SEC XBRL/companyfacts metrics | 0 local normalized rows | Missing | Need adapter before quality-of-surprise grading |


## Baseline Metrics

No production logic changed. Baseline metrics are the accepted-stack canonical windows used by the prior same-family SEC scout.

| Window | EV | Return | PnL | Sharpe daily | Max DD | Win rate | Trades | Signals gen/surv | Survival | vs SPY | vs QQQ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 78.60% | $78,600.33 | 4.35 | 5.41% | 78.95% | 19 | 51/41 | 80.39% | 73.19% | 72.80% |
| mid_weak | 1.4415 | 55.02% | $55,015.08 | 2.62 | 8.79% | 52.38% | 21 | 53/42 | 79.25% | 29.58% | 21.51% |
| old_thin | 0.3179 | 24.64% | $24,642.07 | 1.29 | 8.05% | 40.91% | 22 | 60/55 | 91.67% | 31.37% | 32.13% |

## Shadow Event Table

- Table: `data/non_ohlcv/sec_filing_shadow_events_20260503.json`
- Rows: 300
- Ticker-mapped rows: 284
- Unique tickers: 279
- Shock tag counts: {'unclear / missing data': 296, 'negative filing shock': 4}
- Form counts: {'10-K': 100, '8-K': 100, '10-Q': 100}

Current core/pilot overlap:

| Ticker | Form | Event date | Usable trade date | Tag | Reason |
|---|---|---|---|---|---|
| TSLA | 10-K | 2026-04-30 | 2026-05-01 | unclear / missing data | statement_without_xbrl_metric_parse |

## Shadow / Replay Metrics

Current run forward returns are not measured because the only normalized SEC archive is a forward archive dated 2026-05-02, so 5/10/20/60d outcomes are not yet known. Expected value score delta is `0.0` because this is a data audit and no strategy path changed.

Prior static reference, not promotion evidence: `exp-20260503-011` found 354 liquidity-gated 10-K candidates, 10d excess return avg `0.003765`, win rate `0.5339`, same-day core conflict count `7`, and replacement proxy avg `0.02484`. It remains non-PIT and shadow-only.

## Candidate Overlap And Slot Value

- Current forward SEC archive overlap with production/pilot universe: 1 row.
- Scarce-slot opportunity cost: not measurable in this run. One forward overlap row and no closed forward returns cannot justify a slot tie-breaker.
- Existing historical candidate tagging: blocked. The archive does not yet cover the three canonical windows with SEC rows carrying PIT ticker/form/accepted datetime.

## Missing Fields

- `revenue_surprise`
- `gross_margin_delta`
- `fcf_to_net_income_gap`
- `inventory_growth`
- `receivables_growth`
- filing body / XBRL facts needed to classify 10-K / 10-Q quality shock
- stable PIT historical CIK-to-ticker mapping ledger
- forward 5/10/20/60d outcomes for current SEC-tagged rows

## Decision

`data_gap`

Do not promote to production, default-off replay, or C-strategy grading yet. The useful next step is not another ranking variant; it is accumulating forward SEC archives with ticker tags plus a PIT XBRL/companyfacts adapter stub that can fill the currently null quality fields.

## Production Impact

```json
{
  "shared_policy_changed": false,
  "backtester_adapter_changed": false,
  "run_adapter_changed": false,
  "replay_only": true,
  "parity_test_added": false,
  "production_impact": "shadow_only"
}
```
