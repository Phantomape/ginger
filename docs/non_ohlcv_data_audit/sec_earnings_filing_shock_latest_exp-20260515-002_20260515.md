# SEC / earnings / filing shock non-OHLCV audit (exp-20260515-002)

Date: 2026-05-15
Mode: data audit + shadow tagging only
Decision: `data_gap`

## Hypothesis

SEC filing shock, financial surprise, 8-K/10-Q/10-K event type, and post-earnings drift may improve C-strategy grading or A/B event confirmation, but only if the 2026-05-13 SEC refresh adds PIT directional fields that touch candidates.

## Mechanism And Variable

- Mechanism family: `SEC / earnings / filing shock event-confirmation overlay`
- Single causal variable: `post_exp_20260514_005_sec_filing_20260513_feature_availability`
- Production change allowed: false
- Production impact: no shared policy, run adapter, backtester adapter, signal generation, ranking, sizing, or order path changed.

## Historical Check

| Experiment | Finding |
|---|---|
| `exp-20260511-001` | 138 historical A/B candidates; B/C filing-shock cohorts empty; no earnings_event_long sample; raw filing-presence slot value negative. |
| `exp-20260513-006` | 2026-05-11 refresh had events/text/features and 1 pilot overlap, but zero same-accession rows and zero directional rows. |
| `exp-20260514-005` | 2026-05-12 refresh had events/text/features and zero production-core overlap, but still zero same-accession rows and zero directional rows. |
| Playbook/current state | SEC filing shock is blocked by missing directional same-accession fields; do not retune SEC T+1 sleeve here. |

## Coverage Table

| Source | Rows | PIT-safe / timestamp rows | Tickers | Useful directional fields | PIT status |
|---|---:|---:|---:|---:|---|
| `sec_filing_events_20260513.jsonl` | 60 | 60 | 33 | n/a | accepted_at + usable_trade_date present; public PIT proxy only |
| `sec_filing_text_20260513.jsonl` | 40 | 40 | 31 | 0 structured | replayable 8-K text, no structured guidance/surprise adapter |
| `sec_filing_features_20260513.jsonl` | 40 | 40 | 31 | 0 | feature rows exist, but same-accession directional data missing |
| `earnings_snapshot_20260513.json` | 58 | repo snapshot | 58 | 0 current surprise | EPS estimate/history only; not PIT consensus surprise evidence |

Form coverage: `{'8-K': 40, '10-Q': 20}`.

## Shadow Tags And Forward Returns

Fresh shadow table rows: 60. Tags: `{'D_unclear_or_missing_data': 60}`. Fresh rows are not mature for 5/10/20/60d forward returns and are not candidate-linked to a B/C directional cohort.

Carried-forward tagged candidate returns from `exp-20260511-001` remain the only mature candidate-touch sample:

| Tag | Candidates | 5d avg | 10d avg | 20d avg | 60d avg |
|---|---:|---:|---:|---:|---:|
| A_no_recent_filing_event | 67 | 0.4767 | 1.731 | 2.845 | 0.977 |
| B_positive_filing_shock | 0 | null | null | null | null |
| C_negative_filing_shock | 0 | null | null | null | null |
| D_unclear_or_missing_data | 71 | 0.8224 | 1.0909 | 2.8629 | 11.2336 |

## Candidate Overlap And Slot Value

- Fresh current core signal overlap: 0 rows / tickers `[]`.
- Fresh pilot signal overlap: 0 rows / tickers `[]`.
- Fresh open position overlap: 6 rows / tickers `['AMD', 'COHR', 'GOOG', 'NVDA', 'TRIP', 'UNH']`.
- Historical overlap from prior closed candidates: `{'breakout_long_candidates': 53, 'breakout_long_recent_filing': 26, 'earnings_event_long_candidates': 0, 'entered_rows': 63, 'entered_with_negative_filing_shock': 0, 'entered_with_positive_filing_shock': 0, 'entered_with_recent_filing': 34, 'trend_long_candidates': 85}`.
- Scarce-slot value carried forward: same-day comparable count `9`, overall 20d delta `{'avg_pct': -9.4314, 'best_pct': 0.5953, 'count': 9, 'median_pct': -4.7594, 'win_rate': 0.2222, 'worst_pct': -26.2463}`.

## Baseline Metrics

Baseline source: `data/experiments/exp-20260514-050/gold_trend_near_high_cap.json`. This audit did not replay or change strategy behavior.

| Aggregate metric | Value |
|---|---:|
| expected_value_score_sum | 6.9654 |
| total_pnl_sum | 209695.69 |
| trade_count_sum | 62 |
| signals_generated_sum | 164 |
| signals_survived_sum | 138 |
| survival_rate_min | 0.7925 |
| max_drawdown_pct_max | 0.1014 |

Expected value score delta: `0.0` because this was a data audit only.

## Data Gap

The gap is field availability, not tradable timestamp plumbing. The 2026-05-13 refresh has accepted datetime, usable trade date, filing text, and feature rows. It still has zero same-accession financial-quality rows, zero EPS/revenue surprise rows, zero guidance raise/cut rows, and zero B/C directional candidate-touch cohorts.

## Next Minimal Action

Repair same-accession Companyfacts joins for 2026-05-13 10-Q/10-K accessions or ingest PIT-safe EPS/revenue consensus and structured guidance fields. Only then rerun candidate-touch tagging before any default-off C-strategy grading harness.
