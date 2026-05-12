# SEC / Earnings / Filing Shock Refresh Audit (exp-20260512-003)

## Decision
`data_gap`: keep filing-shock C-strategy grading shadow-only. The fresh 2026-05-10 SEC refresh adds metadata/text coverage, but no feature file or directional financial shock fields.

## Protocol

| Field | Value |
|---|---|
| hypothesis | SEC filing shock, financial surprise, 8-K/10-Q/10-K event type, and post-earnings drift may improve C-strategy grading or A/B event confirmation, but only if fresh PIT directional fields touch candidates. |
| mechanism_family | SEC / earnings / filing shock event-confirmation overlay |
| single_causal_variable | post_exp_20260511_001_sec_filing_refresh_field_availability |
| mode | data_audit_plus_fresh_shadow_event_table |
| production_change_allowed | false |
| production impact | no signal, ranking, sizing, order, run, backtester, risk, or portfolio change |

## Historical Experiment Check

| Experiment | Result to preserve |
|---|---|
| exp-20260510-002 | Refreshed SEC filing-shock rows for 2026-05-07/08 were all D_unclear_or_missing_data; zero same-accession rows and zero directional numeric rows. |
| exp-20260511-001 | Full current audit: 138 historical A/B candidates, B/C filing-shock cohorts empty, no earnings_event_long candidate sample, slot-value tie-break negative. |
| exp-20260511-112 | Separate SEC financial-report positive T+1 paper sleeve capacity accepted as default-off max=3; not retuned here. |
| exp-20260512-001 | Separate SEC financial-report T+1 excess floor accepted at >=1%; not retuned here. |
| exp-20260512-002 | SEC financial-report hold-day sweep rejected; keep accepted 10-day lifecycle. |
| post_news_family | PEAD/post-news continuation remains forward-watch only; item-composition, surprise_direction, and RS20 context gates did not create a production C strategy. |

## Coverage Table

| Source | Rows / files | PIT status | Useful fields | Blocking gap |
|---|---:|---|---|---|
| SEC filing events 2026-05-10 | 72 rows / 1 file | accepted + usable 72/72; public PIT proxy | form type, item codes, accession, accepted_at, usable_trade_date | no financial surprise/guidance fields |
| SEC filing text 2026-05-10 | 42 rows / 1 file | archive public-PIT proxy, not proof local observation | 8-K text and item codes | unstructured; no guidance raise/cut adapter |
| SEC filing features 2026-05-10 | 0 rows / missing file | not available | none | no same-accession, margin, FCF, inventory, receivables, EPS/revenue surprise fields |
| Earnings snapshot 2026-05-10 | 58 tickers / 1 file | replayable repo snapshot, not vendor consensus | EPS estimate and historical surprise for 51 tickers | no current EPS/revenue surprise or guidance field |

## Fresh Shadow Event Table

- Rows written: `72` to `data\non_ohlcv\sec_earnings_filing_shock_shadow_events_exp-20260512-003.json`.
- Tag counts: `{'D_unclear_or_missing_data': 72}`.
- Directional rows: `0`; same-accession rows: `0`; EPS/revenue surprise rows: `0`; guidance rows: `0`.
- Form counts: `{'8-K': 42, '10-Q': 29, '10-K/A': 1}`.
- Usable trade-date counts: `{'2026-04-30': 2, '2026-05-01': 13, '2026-05-04': 8, '2026-05-05': 7, '2026-05-06': 10, '2026-05-07': 11, '2026-05-08': 16, '2026-05-11': 5}`.
- Fresh forward returns: not measured; rows are not candidate-linked and feature extraction is missing.

## Tagged Candidate Forward Returns

Carried forward from `exp-20260511-001` because the fresh data is after the canonical windows and does not touch historical candidates.

| Tag | Candidates | 5d avg | 10d avg | 20d avg | 60d avg |
|---|---:|---:|---:|---:|---:|
| `A_no_recent_filing_event` | 67 | 0.4767 | 1.731 | 2.845 | 0.977 |
| `B_positive_filing_shock` | 0 | None | None | None | None |
| `C_negative_filing_shock` | 0 | None | None | None | None |
| `D_unclear_or_missing_data` | 71 | 0.8224 | 1.0909 | 2.8629 | 11.2336 |

## Candidate Overlap And Slot Value

- Historical candidate count: `138`.
- Historical overlap: `{'breakout_long_candidates': 53, 'breakout_long_recent_filing': 26, 'earnings_event_long_candidates': 0, 'entered_rows': 63, 'entered_with_negative_filing_shock': 0, 'entered_with_positive_filing_shock': 0, 'entered_with_recent_filing': 34, 'trend_long_candidates': 85}`.
- Historical scarce-slot 20d delta: `{'avg_pct': -9.4314, 'best_pct': 0.5953, 'count': 9, 'median_pct': -4.7594, 'win_rate': 0.2222, 'worst_pct': -26.2463}`.
- Fresh 2026-05-10 core signal overlap: `0` rows because `quant_signals_20260510.json` has `0` core signals.
- Fresh SEC financial-report T+1 queue candidates: `0`; this run did not retune that separate default-off paper queue.

## Baseline Metrics

No backtest was rerun because this was a data audit. Accepted core metrics are carried forward from `data/experiments/exp-20260510-015/trip_sector_taxonomy.json`.

| Window | EV | Return % | PnL | Sharpe daily | Max DD % | Win % | Trades | Signals survived/generated | Survival % | vs SPY pp | vs QQQ pp |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `late_strong` | 4.234 | 94.09 | 94086.91 | 4.5 | 5.48 | 78.95 | 19 | 41.0/51.0 | 80.39 | 88.682 | 88.2933 |
| `mid_weak` | 1.6689 | 61.81 | 61813.4 | 2.7 | 9.41 | 52.38 | 21 | 42.0/53.0 | 79.25 | 36.3699 | 28.3023 |
| `old_thin` | 0.3853 | 28.54 | 28544.11 | 1.35 | 8.15 | 40.91 | 22 | 55.0/60.0 | 91.67 | 35.2629 | 36.0282 |

## PIT / Bias Notes

- SEC accepted_at and usable_trade_date are present and are the only tradable-date fields used here.
- report_date / fiscal_period_end is context only and was not used as an entry date.
- SEC text is fetched from public archives after the fact, so it is replayable public-PIT proxy data, not proof of local production observation.
- No `sec_filing_features_20260510.jsonl` exists; fresh rows cannot be promoted beyond `D_unclear_or_missing_data`.
- Earnings snapshot fields are useful for P-ERN context, but they do not supply vendor-grade current EPS/revenue surprise or guidance.

## Production Impact

```json
{
  "alters_candidate_ranking": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_sizing": false,
  "backtester_adapter_changed": false,
  "default_off_harness_changed": false,
  "must_not_touch_respected": [
    "quant/signal_engine.py",
    "quant/risk_engine.py",
    "quant/portfolio_engine.py"
  ],
  "parity_test_added": false,
  "production_signal_path_changed": false,
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

## Conclusion

The branch remains blocked by directional feature availability, not by SEC timestamp plumbing. The separate SEC financial-report positive T+1 default-off queue already has its own accepted observation path, so this run should not trigger another T+1 cohort retune.

## Next Minimal Action

Run or build the sec_filing_features extractor for the 2026-05-10 SEC refresh and then rerun same-accession candidate-touch tagging; do not retune SEC T+1 or C-strategy rules first.
