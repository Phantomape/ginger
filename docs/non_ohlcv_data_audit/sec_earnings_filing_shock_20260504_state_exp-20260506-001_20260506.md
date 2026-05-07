# SEC / Earnings / Filing Shock 2026-05-04 State Audit

Experiment: `exp-20260506-001`  
Timestamp: `2026-05-06T01:23:39Z`  
Decision: `data_gap`

## Hypothesis

SEC filing shock and earnings surprise may improve C-strategy grading or A/B event confirmation only if the fresh 2026-05-04 PIT SEC/earnings/event-sleeve state contains non-null financial shock fields or forward-paper candidates with frozen alternatives.

## Mechanism Family

`earnings_sec_filing_shock_event_confirmation_overlay`

## Single Causal Variable

Fresh PIT-safe 2026-05-04 SEC earnings filing-shock evidence availability.

This run is data audit + shadow tagging only. It did not touch production signal generation, ranking, sizing, exits, OHLCV thresholds, SEC event thresholds, event notionals, capacity, holding periods, or LLM prompts.

## Historical Experiment Check

This family has been audited repeatedly. The most relevant prior records are `exp-20260504-040`, `exp-20260504-050`, `exp-20260504-054`, `exp-20260505-001`, `exp-20260505-003`, and the accepted observation harness `exp-20260505-008`. The anti-repeat guardrail still applies: do not retune SEC reaction thresholds, keyword lists, event source composition, holding periods, notional, or capacity on the same frozen sample.

This run is not a simple repeat because `data/non_ohlcv/daily_non_ohlcv_snapshot_20260504.json`, `data/earnings_snapshot_20260504.json`, `data/quant_signals_20260504.json`, and the SEC paper state files now exist. The new evidence is a state/coverage update, not a production alpha claim.

## Coverage Table

| Source | Coverage | PIT status | Main gap |
|---|---:|---|---|
| SEC submissions/events | 48 rows / 27 tickers | accepted_at/accession public PIT proxy | Timestamp and item metadata only; not same-accession financial shock |
| SEC filing text | 31 8-K text rows / 26 tickers | usable after accepted_at; fetched as replayable public archive | Unstructured; no persisted LLM filing grades |
| Earnings snapshots | 48 tickers; 41 with EPS estimate; 41 with surprise history | PIT as of 2026-05-04 snapshot | No revenue/guidance/same-accession shock |
| SEC paper ledgers | governance pending 1; negative pending 0; leadership pending 0; closed 0 | Default-off forward paper state | No closed outcome / replacement value yet |
| Current core candidates | signals 0; pilot 0; available core slots 0 | Production daily decision file | No candidate overlap sample on 2026-05-04 |

## Shadow Tagged Candidate Forward Returns

Artifact: `data/non_ohlcv/sec_earnings_filing_shock_shadow_events_exp-20260506-001.json`

| Tag | Candidate rows | Forward 5d | Forward 10d | Forward 20d | Forward 60d | Note |
|---|---:|---:|---:|---:|---:|---|
| `A_no_recent_filing_event` | 0 | n/a | n/a | n/a | n/a | No current core or pilot candidates were persisted on 2026-05-04. |
| `B_positive_filing_shock` | 0 | n/a | n/a | n/a | n/a | No positive filing-shock row emitted by current SEC queues. |
| `C_negative_filing_shock` | 1 | n/a | n/a | n/a | n/a | One GS governance/procedural mild negative-reaction row is pending paper entry; no closed outcome yet. |
| `D_unclear_missing_data` | 47 | n/a | n/a | n/a | n/a | Financial shock fields are missing or not same-accession aligned. |

Forward returns are intentionally `n/a`: the one tagged negative-filing-shock row is still `pending_next_session_open`, and no closed SEC paper outcome exists. Filling forward returns from future OHLCV would be non-PIT for this audit.

## Field Missingness

Non-null shadow fields: `{'accepted_datetime': 48, 'accession_number': 48, 'avg_historical_surprise_pct': 40, 'data_source': 48, 'eight_k_item_type': 31, 'eps_estimate': 40, 'event_date': 48, 'fiscal_period_end': 48, 'form_type': 48, 'forward_return_status': 48, 'overlap_with_pilot_signals': 48, 'overlap_with_selected_signals': 48, 'paper_status': 1, 'pit_caveat': 48, 'pit_safe': 48, 'reaction_bucket': 1, 'semantic_subcategory': 1, 'shock_source': 1, 'tag': 48, 'ticker': 48, 'usable_trade_date': 48}`.

Financial shock fields still unusable for C grading: `eps_surprise`, `revenue_surprise`, `gross_margin_delta`, `fcf_to_net_income_gap`, `inventory_growth`, `receivables_growth`, `guidance_raise_cut`, and `same_accession_xbrl_event_link` are absent or null for same-accession event grading.

## Candidate Overlap And Slot Value

| Metric | Value |
|---|---:|
| Current core selected signals | 0 |
| Current pilot selected signals | 0 |
| Signals before entry filters | 0 |
| Signals after entry filters | 0 |
| Active positions / max positions | 12 / 5 |
| Available core slots | 0 |
| Filing rows overlapping selected signals | 0 |
| Filing rows overlapping pilot signals | 0 |
| SEC governance pending paper rows | 1 |
| SEC negative pending paper rows | 0 |
| SEC leadership pending paper rows | 0 |
| Closed SEC paper outcomes | 0 |

Scarce-slot opportunity cost is not computable yet. The GS governance/procedural row froze cash as its only alternative, no core A/B candidate existed on 2026-05-04, and there is no closed forward outcome.

## Baseline Metrics

No replay or production logic changed. Expected-value delta is `0.0` by construction.

| Window | EV | Return | PnL | Sharpe daily | Max DD | Win rate | Trades | Survived/generated | Survival | vs SPY | vs QQQ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `late_strong` | 3.4191 | 78.60% | $78600.33 | 4.35 | 5.41% | 78.95% | 19 | 41/51 | 80.39% | 73.19% | 72.80% |
| `mid_weak` | 1.4415 | 55.02% | $55015.08 | 2.62 | 8.79% | 52.38% | 21 | 42/53 | 79.25% | 29.58% | 21.51% |
| `old_thin` | 0.3179 | 24.64% | $24642.07 | 1.29 | 8.05% | 40.91% | 22 | 55/60 | 91.67% | 31.37% | 32.13% |

## PIT Status

SEC `accepted_at` and accession metadata are public PIT proxies. The 2026-05-04 earnings snapshot is PIT for EPS estimate and historical EPS-surprise context, but not same-accession financial shock. Current SEC filing text is replayable after `accepted_at`, but no structured filing-grade or LLM semantic field has been persisted for C-strategy grading.

## Production Impact

`production_impact = shadow_data_audit_only`: no shared policy, backtester adapter, run adapter, signal generation, ranking, sizing, orders, or LLM prompt changed.

## Decision

`data_gap`. The fresh files prove the daily non-OHLCV refresh and default-off SEC paper ledgers are working, but they do not yet provide enough evidence for a default-off C-strategy grading harness. The only live state is one pending GS governance/procedural paper candidate with no closed return and no core alternative.

## Next Minimal Action

Let the default-off SEC paper ledgers fill and close the GS governance row, then rerun replacement-value attribution. For C-strategy grading specifically, add same-accession PIT XBRL or structured filing/LLM grades before any replay or production candidate is considered.
