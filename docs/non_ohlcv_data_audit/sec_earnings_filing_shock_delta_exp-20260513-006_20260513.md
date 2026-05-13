# SEC / earnings / filing shock delta audit (exp-20260513-006)

- timestamp: `2026-05-13T01:33:19+00:00`
- mode: `data_audit_shadow_only`
- mechanism_family: `SEC / earnings / filing shock event-confirmation overlay`
- single_causal_variable: `post_exp_20260512_003_sec_filing_20260511_feature_availability`
- production_change_allowed: `false`

## Hypothesis

SEC filing shock, financial surprise, 8-K/10-Q/10-K event type, and post-earnings drift may improve C-strategy grading or A/B event confirmation, but only if the post-exp-20260512-003 SEC refresh adds PIT directional fields that touch candidates.

## Historical experiment check

- `docs_alpha_optimization_playbook`: SEC filing shock remains blocked by missing directional same-accession fields; accepted SEC T+1 paper sleeve should not be retuned here.
- `exp-20260510-002`: Refreshed 2026-05-07/08 SEC filing-shock rows were all D_unclear_or_missing_data with zero same-accession rows and zero directional numeric rows.
- `exp-20260511-001`: Full current audit: 138 A/B candidates, B/C filing-shock cohorts empty, no earnings_event_long candidates, and raw filing-presence slot value negative.
- `exp-20260512-003`: 2026-05-10 refresh added timestamp/text coverage but no feature file or directional fields; not retuned here.
- `exp-20260512-020`: Separate SEC financial-report T+1 sleeve accepted as default-off risk allocation; this run does not change or retune it.

## Coverage table

| source | rows | PIT/timestamp | directional rows | missing blocker |
|---|---:|---:|---:|---|
| SEC events 2026-05-11 | 65 | 65 | n/a | semantic fields absent from raw metadata |
| SEC text 2026-05-11 | 41 | n/a | n/a | unstructured text; no guidance adapter |
| SEC features 2026-05-11 | 41 | 41 | 0 | zero same-accession / EPS / revenue / guidance rows |
| Earnings snapshot 2026-05-11 | 58 | replayable snapshot | n/a | no current EPS/revenue surprise vs PIT consensus |

## PIT status

- `accepted_at` and `usable_trade_date` are present on SEC event rows.
- `report_date` / `fiscal_period_end` was not used as a tradable date.
- Companyfacts filed dates remain public-availability proxies, not proof of local production observation.
- Earnings snapshots are replayable repo artifacts, not vendor-grade PIT consensus surprise evidence.

## Shadow table

- shadow_event_table: `data/non_ohlcv/sec_earnings_filing_shock_shadow_events_exp-20260513-006.json`
- rows: `65`
- PIT-safe rows: `65`
- feature-present rows: `41`
- same-accession rows: `0`
- directional rows: `0`
- tag_counts: `{"D_unclear_or_missing_data": 65}`

## Tagged candidate forward returns

Fresh 2026-05-11 rows are not mature for 5/10/20/60d candidate returns and are not linked to canonical-window candidates. Carried-forward historical candidate tags from `exp-20260511-001`:

| tag | candidates | 5d avg | 10d avg | 20d avg | 60d avg |
|---|---:|---:|---:|---:|---:|
| `A_no_recent_filing_event` | 67 | 0.4767 | 1.7310 | 2.8450 | 0.9770 |
| `B_positive_filing_shock` | 0 | n/a | n/a | n/a | n/a |
| `C_negative_filing_shock` | 0 | n/a | n/a | n/a | n/a |
| `D_unclear_or_missing_data` | 71 | 0.8224 | 1.0909 | 2.8629 | 11.2336 |

## Overlap and slot value

- current core signals: `0`; fresh SEC overlap: `0`
- current pilot signals: `1`; fresh SEC overlap: `1`
- open-position event overlap tickers: `AMD, GOOG, NVDA, TRIP, UNH`
- carried-forward scarce-slot value: avg 20d delta `-9.4314`, win_rate `0.2222`, comparable_count `9`

## Decision

`data_gap`: the 2026-05-11 refresh has timestamp/text/feature coverage but zero same-accession rows, zero directional rows, and no B/C candidate-touch cohort. Do not enter a default-off C grading harness yet.

## Next minimal action

Run a same-accession Companyfacts join coverage repair for 2026-05-11 10-Q/10-K accessions or ingest PIT consensus/guidance fields, then rerun candidate-touch tagging before any default-off C-strategy grading harness.

## Production impact

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

## Ticket note

scripts/create_experiment_ticket.py was invoked first, but the registry lacked existing exp-20260513-001..003 filesystem tickets and attempted a colliding ID. The colliding ticket was restored, and this audit uses non-conflicting exp-20260513-006.
