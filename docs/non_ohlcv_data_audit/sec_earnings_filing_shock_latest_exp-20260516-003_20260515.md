# SEC / earnings / filing shock latest data audit (exp-20260516-003)

- run_timestamp: `2026-05-16T01:30:53+00:00`
- source_refresh_date: `2026-05-14`
- mode: `data_audit_shadow_only`
- mechanism_family: `SEC / earnings / filing shock event-confirmation overlay`
- single_causal_variable: `post_exp_20260515_002_sec_filing_20260514_feature_availability`
- production_change_allowed: `false`
- anti_js: `No JavaScript was used.`

## Hypothesis

SEC filing shock, financial surprise, 8-K/10-Q/10-K event type, and post-earnings drift may improve C-strategy grading or A/B event confirmation, but only if the 2026-05-14 SEC refresh adds PIT directional fields that touch candidates.

## Historical experiment check

- `docs_alpha_optimization_playbook`: SEC earnings semantic expansion is the top field-building item, but the playbook says fresh PIT directional filing-shock fields are still missing; SEC retunes without new semantic fields are invalid.
- `exp-20260511-001`: 138 historical A/B candidates: A=67, D=71, B/C=0, no earnings_event_long sample, raw filing-presence slot value negative.
- `exp-20260513-006`: 2026-05-11 refresh had event/text/feature rows and one pilot overlap, but zero same-accession rows and zero directional rows.
- `exp-20260514-005`: 2026-05-12 refresh remained a data gap: zero same-accession rows, zero directional rows, and zero production-core overlap.
- `exp-20260515-002`: 2026-05-13 refresh remained a data gap: 60 PIT-safe event rows, 40 feature rows, zero directional rows, and no B/C candidate-touch cohort.
- `exp-20260512-020`: Separate SEC financial-report T+1 sleeve is accepted default-off; this run does not retune or promote it.

## Coverage table

| source | rows | PIT/timestamp rows | directional rows | missing blocker |
|---|---:|---:|---:|---|
| SEC events 2026-05-14 | 62 | 62 | n/a | semantic fields absent from raw metadata |
| SEC text 2026-05-14 | 42 | n/a | n/a | unstructured text; no guidance/surprise adapter |
| SEC features 2026-05-14 | 42 | 42 | 0 | same-accession / EPS / revenue / guidance rows still absent |
| Earnings snapshot 2026-05-14 | 58 | replayable snapshot | n/a | no current EPS/revenue surprise vs PIT consensus |

## Shadow table

- shadow_event_table: `data/non_ohlcv/sec_earnings_filing_shock_shadow_events_exp-20260516-003.json`
- rows: `62`
- PIT-safe rows: `62`
- feature-present rows: `42`
- same-accession rows: `0`
- directional rows: `0`
- tag_counts: `{"D_unclear_or_missing_data": 62}`

## Tagged candidate forward returns

Fresh 2026-05-14 rows are not mature for 5/10/20/60d returns. Mature candidate-touch metrics are carried forward from `exp-20260511-001` via `exp-20260515-002`:

| tag | candidates | 5d avg | 10d avg | 20d avg | 60d avg |
|---|---:|---:|---:|---:|---:|
| `A_no_recent_filing_event` | 67 | 0.4767 | 1.7310 | 2.8450 | 0.9770 |
| `B_positive_filing_shock` | 0 | n/a | n/a | n/a | n/a |
| `C_negative_filing_shock` | 0 | n/a | n/a | n/a | n/a |
| `D_unclear_or_missing_data` | 71 | 0.8224 | 1.0909 | 2.8629 | 11.2336 |

## Candidate overlap and slot value

- current core signals: `0`; fresh SEC overlap: `0` (none)
- current pilot signals: `0`; fresh SEC overlap: `0` (none)
- open-position event overlap tickers: `AMD, COHR, GOOG, NVDA, TRIP`
- carried-forward scarce-slot value: avg 20d delta `-9.4314`, win_rate `0.2222`, comparable_count `9`

## Baseline metrics

- baseline: `data/experiments/exp-20260515-028/current_stack_core_confirmed_quality_risk.json`
- aggregate EV: `7.7345`
- aggregate PnL: `229636.73`
- min survival: `0.7925`
- expected_value_score_delta: `0.0`

## Decision

`data_gap`: the 2026-05-14 SEC refresh has PIT timestamp/text/feature coverage and two more feature rows than the prior audit, but still has zero same-accession rows, zero directional rows, and no B/C candidate-touch cohort. Do not enter a default-off C grading harness yet.

## Next minimal action

Repair same-accession Companyfacts joins for 2026-05-14 10-Q/10-K accessions or ingest PIT consensus/guidance fields, then rerun candidate-touch tagging before any default-off C-strategy grading harness.

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
