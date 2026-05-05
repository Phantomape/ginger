# SEC / Earnings / Filing Shock Consolidation Audit

Experiment: `exp-20260504-040`

## Scope

This is a data audit and shadow evidence consolidation. It does not alter orders, signal generation, ranking, sizing, exits, `run.py`, `signal_engine.py`, `risk_engine.py`, or `portfolio_engine.py`.

Single causal variable: `post-governance SEC earnings filing shock evidence-state consolidation`.

Mechanism family: `earnings_sec_filing_shock_event_confirmation_overlay`.

## Historical Check

This family has already been tested heavily.

| Branch | Prior result | Current decision |
|---|---|---|
| Positive earnings/results 8-K reaction | `exp-20260504-002`: 21 candidates, avg 10d excess `-1.8280%`, slot replacement `-9.8719pp` | Do not revive as C strategy |
| Companyfacts context | `exp-20260504-014`: same-accession Companyfacts coverage `0/16`; latest-prior facts were stale | Do not repeat stale-background buckets |
| Leadership-change negative reaction | `exp-20260504-015` / `018`: avg 10d excess `+3.8135%`, low A/B overlap | Shadow-promising, not promoted |
| Agreement/debt event packet | `exp-20260504-019`: avg 10d excess `-0.8619%`, unstable windows | Rejected |
| Residual other filing mild negative reaction | `exp-20260504-022`: avg 10d excess `+2.5478%`, replacement proxy `-9.7802%` on 2 samples | Candidate scout only |
| Current candidate filing tags | `exp-20260504-037`: no current persisted candidates or closed outcomes | Data gap |
| Duplicate no-new-evidence audit | `exp-20260504-038`: no fresh PIT-safe evidence after exp-037 | Data gap |
| Governance/procedural overlay | `exp-20260504-039`: aggregate EV `+8.29%`, PnL `+5.18%` as a 10k satellite overlay | Default-off candidate, needs parity and ledger |

This run is not a simple repeat because it incorporates the newer `exp-20260504-039` governance/procedural result and explicitly demotes the broad SEC/earnings filing-shock family while preserving the narrow follow-up.

## Coverage

| Source | Coverage | PIT status |
|---|---:|---|
| SEC submissions backfill | `1,286` rows, `1,286` PIT-proxy rows, 51/52 tickers mapped | Public SEC `accepted_at` proxy; not proof production observed each filing |
| SEC filing text | `306` Item 2.02 8-K rows, 48 tickers, 12.0M chars | Replay context only |
| SEC Companyfacts | `17,109` rows, 51 CIK-mapped tickers | Filed-date PIT proxy, but stale for same-event 8-K grading |
| Earnings snapshots | `138` snapshots, 6,081 rows, 5,239 rows with EPS estimate/surprise history | Available from `2025-10-23`; older windows remain snapshot-limited |
| Current SEC shadow event table | `300` rows, 284 ticker-mapped, 4 negative shock, 296 unclear/missing | Current feed only; no closed forward outcomes |

## Field Status

Available fields: `ticker`, `event_date`, `usable_trade_date`, `form_type`, `accepted_datetime`, `eight_k_item_type`, `data_source`, `pit_safe`.

Partial or biased fields: `fiscal_period_end`, `eps_surprise`, `eps_estimate`, `gross_margin_delta`, `fcf_to_net_income_gap`, `inventory_growth`, `receivables_growth`.

Missing or not audited: `revenue_surprise`, `guidance_raise_cut`, `same_accession_xbrl_event_link`, persistent SEC queue paper/outcome ledger.

## Tagged Candidate Evidence

| Tag | Forward return evidence | Slot value |
|---|---|---|
| A. no recent filing event | Not measured because full historical pre-entry candidate dumps are not persisted | Not measurable |
| B. positive filing shock | `exp-20260504-002`: avg 5d `-1.1756%`, 10d `-1.8280%`, 20d `+1.3323%` excess | Same-day conflict rate `30.56%`; slot replacement `-9.8719pp` |
| C. negative filing shock | SEC text negative reaction: 16 candidates, 10d net excess `+4.7408%`; leadership negative reaction: 25 candidates, 10d excess `+3.8135%`; governance/procedural: 24 candidates, 13 selected overlay trades, event win rate `61.54%` | Text packet active-slot proxy `+0.9943pp`; leadership slot replacement `-6.9495pp`; governance/procedural needs ledger |
| D. unclear / missing data | Current shadow table has 296 unclear/missing rows | Not tradable evidence |

## Baseline Metrics

No strategy path changed. Baseline metrics remain the accepted three-window stack:

| Window | EV | Return | PnL | Sharpe daily | Max DD | Win rate | Trades | Generated/Survived | Survival | vs SPY | vs QQQ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 78.60% | 78600.33 | 4.35 | 5.41% | 78.95% | 19 | 51/41 | 80.39% | 73.19% | 72.80% |
| mid_weak | 1.4415 | 55.02% | 55015.08 | 2.62 | 8.79% | 52.38% | 21 | 53/42 | 79.25% | 29.58% | 21.51% |
| old_thin | 0.3179 | 24.64% | 24642.07 | 1.29 | 8.05% | 40.91% | 22 | 60/55 | 91.67% | 31.36% | 32.13% |

Expected value score delta for this audit: `0.0`.

## Decision

Decision: `default_off_candidate`.

The broad SEC/earnings filing-shock family should not be re-run on the same sample and should not be connected to production. The narrow governance/procedural branch from `exp-20260504-039` is worth the next default-off step, but only after a shared event-sleeve policy and persistent SEC paper/outcome ledger exist.

Next minimum action: implement a shared default-off SEC event-sleeve adapter plus a persistent SEC paper/outcome ledger that freezes same-day A/B and cash alternatives. Then wait for forward replacement-value outcomes before any production capital or ranking change.
