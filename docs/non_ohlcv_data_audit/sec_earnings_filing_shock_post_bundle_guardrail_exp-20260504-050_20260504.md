# SEC / Earnings / Filing Shock Post-Bundle Guardrail

Experiment: `exp-20260504-050`

## Scope

This is a data availability audit plus shadow tagging refresh. It does not alter
orders, signal generation, ranking, sizing, exits, `run.py`, `signal_engine.py`,
`risk_engine.py`, or `portfolio_engine.py`.

Single causal variable: fresh PIT-safe SEC / earnings filing-shock evidence
availability after `exp-20260504-049`.

Mechanism family: `earnings_sec_filing_shock_event_confirmation_overlay`.

## Historical Check

This branch is already heavily covered. The relevant mechanism conclusions are:

| Prior experiment | Result | Current implication |
|---|---|---|
| `exp-20260504-040` | Broad SEC / earnings filing-shock evidence was exhausted; governance/procedural branch was the only default-off candidate | Do not restart broad C-strategy filing-shock tuning |
| `exp-20260504-044` | Default-off SEC governance/procedural queue and paper-ledger code path added observe-only | Wait for forward outcomes |
| `exp-20260504-046` | No new PIT-safe SEC/earnings artifact or closed forward ledger outcome | Data gap persisted |
| `exp-20260504-048` | No new source files or closed outcomes after `exp-046` | Data gap persisted |
| `exp-20260504-049` | Frozen Form 4 + SEC negative-reaction + SEC governance/procedural overlay bundle improved replay EV/PnL, but replay-only | Next step is shared ledger/forward replacement value, not retuning filing shock |

This run is not a simple repeat because it only normalizes the existing current
SEC shadow rows into the required A/B/C/D tag contract and checks whether any
fresh evidence appeared after the replay-only bundle.

## Coverage

| Source | Coverage | PIT status |
|---|---:|---|
| SEC submissions backfill | `1,286` rows; `1,286` PIT-proxy rows | `accepted_at` is a public EDGAR availability proxy; not proof local production observed each filing |
| SEC filing text | `306` rows | Replay context after `accepted_at`; keyword scoring already shadow-tested and not promoted |
| SEC Companyfacts | `17,109` rows | Filed-date PIT proxy for background facts, but too stale for same-event 8-K grading |
| Earnings snapshots | `138` files, `6,081` ticker rows, last file `earnings_snapshot_20260503.json` | Snapshot-backed mainly for late window; no `earnings_snapshot_20260504.json` exists |
| Normalized shadow table | `300` rows, `284` ticker-mapped, `279` unique tickers | Timestamp-safe current-feed shadow rows; financial-shock fields remain null |

Normalized shadow table:
`data/non_ohlcv/sec_earnings_filing_shock_shadow_events_exp-20260504-050.json`

## Tag Counts

| Tag | Count |
|---|---:|
| A. no recent filing event | 0 |
| B. positive filing shock | 0 |
| C. negative filing shock | 4 |
| D. unclear / missing data | 296 |

All rows have `accepted_datetime`, `usable_trade_date`, and `pit_safe`.
Financial shock fields are still all null: `eps_surprise`, `revenue_surprise`,
`gross_margin_delta`, `fcf_to_net_income_gap`, `inventory_growth`,
`receivables_growth`, and `guidance_raise_cut`.

## Candidate / Forward Return Audit

Current tagged Ginger candidate count: `0`.

Current overlap with existing selected signals: `0`.

Scarce-slot opportunity cost: not computable because there are no current
new-trade candidates and no closed SEC paper outcomes after `exp-20260504-049`.

Forward 5/10/20/60d return of newly tagged candidates: not generated. There are
no fresh tagged candidates or closed forward outcomes. Prior SEC evidence remains
the only context:

| Branch | Prior forward evidence | Slot value |
|---|---|---|
| Leadership-change negative reaction | `23` valid 10d outcomes, avg `+3.8135%` excess, `60.87%` positive | Replacement proxy `-6.9495pp` |
| Other filing mild negative | `20` valid 10d outcomes, avg `+2.5478%` excess | Replacement proxy `-9.7802pp` on 2 samples |
| Governance/procedural overlay | `13` event trades, `$7,333.02` event PnL, `61.54%` event win rate | Needs closed forward paper outcomes |
| Default-off event bundle | Aggregate EV `+23.29%`, PnL `+12.67%` in replay-only bundle | Not live-promoted |

## Baseline Metrics

No strategy path changed. Baseline and after metrics are identical.

| Window | EV | Return | PnL | Sharpe daily | Max DD | Win rate | Trades | Generated/Survived | Survival | vs SPY | vs QQQ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 78.60% | 78600.33 | 4.35 | 5.41% | 78.95% | 19 | 51/41 | 80.39% | 73.19% | 72.80% |
| mid_weak | 1.4415 | 55.02% | 55015.08 | 2.62 | 8.79% | 52.38% | 21 | 53/42 | 79.25% | 29.58% | 21.51% |
| old_thin | 0.3179 | 24.64% | 24642.07 | 1.29 | 8.05% | 40.91% | 22 | 60/55 | 91.67% | 31.37% | 32.13% |

Expected value score delta: `0.0`.

## Decision

Decision: `data_gap`.

No fresh PIT-safe SEC/earnings filing-shock evidence, same-accession XBRL,
analyst revision data, structured LLM filing grades, or closed SEC paper outcomes
were found after `exp-20260504-049`.

Next minimum action: stop repeating SEC/earnings filing-shock rechecks until one
of these exists: closed forward paper outcomes from the SEC event ledger,
same-accession/same-day XBRL fields, PIT analyst revisions, or persisted
structured LLM filing-text grades joined to forward outcomes.
