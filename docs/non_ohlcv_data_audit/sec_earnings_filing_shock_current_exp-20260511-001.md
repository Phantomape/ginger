# SEC / earnings filing shock audit (exp-20260511-001)

## Decision
`data_gap`: keep this branch shadow-only; do not enter a default-off C-strategy grading harness yet.

## Hypothesis
SEC filing shock, financial surprise, 8-K/10-Q/10-K event type, and post-earnings drift may improve C-strategy grading or A/B event confirmation, but only if PIT directional fields touch candidates.

## Historical Check
- `exp-20260503-016`: Initial SEC/earnings filing-shock schema/table audit: forward SEC archive existed, directional fields absent, data_gap.
- `exp-20260503-019/022`: Duplicate guardrail rechecks: no new PIT-safe evidence then; do not rerun same archive.
- `exp-20260507-004`: Candidate filing-shock tags persisted: A=67, D=71, B/C=0; D had positive 60d drift but no directional shock grade.
- `exp-20260507-030/031`: Same-accession Companyfacts feature repair partially worked: 25 same-accession rows, 18 directional rows.
- `exp-20260507-093`: Same-accession candidate-touch audit: repaired directional rows did not touch A/B candidates inside the 20-trading-day lookback; B/C candidates stayed 0.
- `exp-20260510-002`: Refreshed 2026-05-07/08 filing-shock rows remained all D_unclear_or_missing_data; no same-accession rows in the fresh live-ish slice.
- `exp-20260510-023/024/025/027`: Separate SEC financial-report positive T+1 drift family found a default-off forward queue candidate; this audit does not retune that label or queue.
- `playbook_guardrail`: Do not repeat raw filing recency, C-sleeve re-enable, Companyfacts score-weight sweeps, or T+1 cohort retunes on the same frozen sample.

## Coverage Table

| Source | Rows / files | PIT status | Useful fields | Blocking gap |
|---|---:|---|---|---|
| SEC filing events | 11690 rows / 417 files | accepted + usable 11690/11690 | form type, item codes, accession | no EPS/revenue/guidance |
| SEC filing features | 7899 raw / 1029 unique events | pit_safe raw 7899/7899 | same-accession unique 3, directional unique 2 | directional rows do not touch candidates |
| Earnings snapshots | 18809 rows / 420 files | repo replayable, not vendor consensus | eps_estimate 0.8503, surprise_history 0.8503 | no revenue surprise / guidance |
| Companyfacts selected | 17689 rows | public-availability proxy | selected XBRL facts | sparse same-accession event joins |

## Candidate Tags And Returns

| Tag | Candidates | 5d | 10d | 20d | 60d |
|---|---:|---|---|---|---|
| `A_no_recent_filing_event` | 67 | n=64, avg=0.4767%, med=-0.2365%, win=45.3% | n=63, avg=1.731%, med=0.7066%, win=55.6% | n=59, avg=2.845%, med=1.3767%, win=55.9% | n=43, avg=0.977%, med=-0.8401%, win=48.8% |
| `B_positive_filing_shock` | 0 | n=0 | n=0 | n=0 | n=0 |
| `C_negative_filing_shock` | 0 | n=0 | n=0 | n=0 | n=0 |
| `D_unclear_or_missing_data` | 71 | n=69, avg=0.8224%, med=0.7413%, win=50.7% | n=67, avg=1.0909%, med=0.5349%, win=53.7% | n=65, avg=2.8629%, med=0.1546%, win=50.8% | n=46, avg=11.2336%, med=8.1302%, win=63.0% |

## Candidate Overlap / Slot Value

- Candidate count: `138`.
- Entered rows: `63`; entered with recent filing context: `34`; entered B/C filing shocks: `0` / `0`.
- Breakout candidates: `53`; breakout with recent filing context: `26`; directional B/C breakout candidates: `0`.
- Earnings-event candidates in persisted shadow rows: `0`.
- Slot-conflict candidates: `25`; comparable same-day slot-value rows: `9`; 20d delta distribution: `n=9, avg=-9.4314%, med=-4.7594%, win=22.2%`.

## PIT / Bias Notes
- `event_timestamp_status`: SEC accepted_datetime and usable_trade_date are present on local event/feature rows and are the only tradable-date source used here.
- `companyfacts_status`: Same-accession Companyfacts fields are derived for a tiny number of rows; filed date is only a public-availability proxy and does not prove production observation.
- `earnings_snapshot_status`: Earnings snapshots are replayable repo artifacts with EPS/surprise-history coverage, but not vendor-grade PIT consensus for actual EPS/revenue surprise.
- `biased_or_blocked_fields`: ['eps_surprise', 'revenue_surprise', 'guidance_raise_cut', 'broad same-accession candidate touches']
- `do_not_use_as_production_evidence`: True

## Production Impact
```json
{
  "shared_policy_changed": false,
  "backtester_adapter_changed": false,
  "run_adapter_changed": false,
  "parity_test_added": false,
  "replay_only": true,
  "default_off_harness_changed": false,
  "production_signal_path_changed": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_candidate_ranking": false,
  "alters_sizing": false,
  "must_not_touch_respected": [
    "quant/signal_engine.py",
    "quant/risk_engine.py",
    "quant/portfolio_engine.py"
  ]
}
```

## Next Minimal Action
Add or ingest a PIT source that can produce EPS/revenue surprise, guidance raise/cut, or same-accession financial fields on actual candidate dates; then rerun candidate-touch tagging before any default-off C grading harness.
