# SEC / Earnings Filing Shock Post-exp053 Audit

Experiment: `exp-20260504-054`
Timestamp: `2026-05-04T23:09:08+00:00`
Decision: `data_gap`

## Hypothesis

SEC filing shock and earnings surprise may improve C-strategy grading or A/B event confirmation only if fresh PIT-safe evidence exists after `exp-20260504-053`.

Mechanism family: `earnings_sec_filing_shock_event_confirmation_overlay`

Single causal variable: fresh PIT-safe SEC earnings filing-shock evidence availability after `exp-20260504-053`.

This is a data audit and shadow-tagging guardrail only. Production signal generation, ranking, sizing, exits, OHLCV thresholds, SEC event thresholds, queue policy, event notionals, and LLM prompts were intentionally unchanged.

## Historical Check

This direction has already been tested enough that another broad filing-shock replay would be a repeat:

| Experiment | Relevant conclusion |
|---|---|
| `exp-20260503-002` | Earnings/SEC surprise schema was created, but SEC-backed trade count was 0. |
| `exp-20260503-005` | SEC CIK/ticker mapping improved feed usability. |
| `exp-20260504-040` | Broad SEC/earnings filing-shock family was exhausted. |
| `exp-20260504-049` | Default-off event overlay bundle was promising replay-only; next step is forward replacement value. |
| `exp-20260504-050` | No fresh PIT-safe filing-shock evidence; normalized 300-row shadow table created. |
| `exp-20260504-052` | Post-SEC-negative-ledger audit again found no fresh filing-shock evidence. |
| `exp-20260504-053` | Event bundle attribution became production-visible but needs a new daily run to create state/outcomes. |

Mechanism guardrail: do not repeat reaction-threshold sweeps, stale Companyfacts background buckets, filing keyword tuning, event notional/capacity tests, or direct production promotion before closed forward paper outcomes exist.

## Coverage Table

| Source | Rows / coverage | PIT status | Missing for filing-shock alpha |
|---|---:|---|---|
| SEC submissions | 1,286 rows | `accepted_datetime` is a PIT-safe public availability proxy; backfill does not prove production observed it live. | Same-accession XBRL, guidance semantics, financial-surprise fields |
| SEC Companyfacts/XBRL selected facts | 17,109 rows | Filed date is PIT-safe for background facts, but too stale for same-day shock grading. | Same-accession match, event-date deltas |
| SEC filing text | 306 rows | Usable after accepted time; fixed keyword scoring was already shadow-tested and not promoted. | Structured LLM filing grades, guidance labels |
| Earnings snapshots | 138 files, 6,081 ticker rows | PIT-safe for dates with snapshots; latest is `earnings_snapshot_20260503.json`. | Revenue surprise, guidance raise/cut, gross margin delta, SEC accession link |
| Shadow filing-shock table | 300 rows | Timestamp-safe but financial-shock fields are all null. | Closed forward outcomes and non-null financial shock fields |

Latest daily file check: the latest production snapshot is still `data/quant_signals_20260503.json`; it has 0 core signals, 0 pilot signals, 0 Form 4 candidates, and 0 SEC negative queue candidates. It also predates the event-bundle section added in `exp-20260504-053`.

No `20260504` earnings snapshot, news archive, SEC paper state, SEC paper snapshot log, or event-bundle paper state exists in `data/`.

## Shadow Tags

The run reuses `data/non_ohlcv/sec_earnings_filing_shock_shadow_events_exp-20260504-050.json` and writes a manifest at `data/non_ohlcv/sec_earnings_filing_shock_shadow_events_exp-20260504-054.json`.

| Tag | Rows | Interpretation |
|---|---:|---|
| `A_no_recent_filing_event` | 0 | Not measured because full historical candidate dumps are not persisted. |
| `B_positive_filing_shock` | 0 | No positive filing-shock rows in the current normalized table. |
| `C_negative_filing_shock` | 4 | No new closed outcome or slot replacement evidence. |
| `D_unclear_missing_data` | 296 | Financial-shock fields remain null. |

Non-null financial shock fields: 0. `accepted_datetime`, `usable_trade_date`, and `pit_safe` are populated for all 300 rows; `eight_k_item_type` is populated for 100 rows.

## Shadow Metrics

| Metric | Value |
|---|---:|
| Current core trade candidates | 0 |
| Current pilot candidates | 0 |
| Current SEC negative queue candidates | 0 |
| Normalized shadow rows | 300 |
| Shadow table production/pilot universe overlap rows | 1 |
| Candidate overlap with current selected signals | 0 |
| Scarce-slot opportunity cost | Not computable |
| Forward 5/10/20/60d return of newly tagged candidates | Not computable |

Reason: no fresh tagged candidates, no current selected signals, and no closed forward paper outcomes exist after `exp-20260504-053`.

## Baseline Metrics

No replay was run and no strategy behavior changed. Baseline metrics are unchanged:

| Window | EV | Return | PnL | Sharpe daily | Max DD | Win rate | Trades | Signals survived | Survival |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `late_strong` | 3.4191 | 78.60% | 78600.33 | 4.35 | 5.41% | 78.95% | 19 | 41/51 | 80.39% |
| `mid_weak` | 1.4415 | 55.02% | 55015.08 | 2.62 | 8.79% | 52.38% | 21 | 42/53 | 79.25% |
| `old_thin` | 0.3179 | 24.64% | 24642.07 | 1.29 | 8.05% | 40.91% | 22 | 55/60 | 91.67% |

Expected value score delta: `0.0` in all windows.

## PIT Status

SEC timestamps are usable as a point-in-time availability proxy, but the current evidence cannot grade filing shocks because it lacks same-accession XBRL, revenue surprise, gross margin delta, FCF-to-net-income gap, inventory/receivables growth, guidance raise/cut labels, structured LLM filing grades, and closed forward outcomes.

`quant/feature_layer.py` and `quant/data_layer.py` currently support earnings timing and EPS-estimate/surprise-history fields, but not the financial filing-shock fields needed for this hypothesis. `quant/backtester.py` already discloses earnings snapshot coverage and uses walk-forward snapshots when present.

## Decision

`data_gap`.

Do not start another SEC/earnings filing-shock replay or default-off candidate promotion from this same frozen sample. The next minimum action is to run the daily production pipeline after `exp-20260504-053` so the default-off event-bundle and SEC paper attribution surfaces can create state files and eventually closed outcomes. After that, audit the new state/outcome files before any replay or promotion test.
