# EOD Options Structure Overlay Audit

Experiment: `exp-20260503-044`
Run mode: data audit only; no production change.

## Hypothesis

EOD options structure may improve Ginger only as an overlay for existing
`breakout_long`, short/squeeze, or earnings-event candidates. Useful signals
would come from IV, skew, term structure, OI concentration, put/call structure,
and option liquidity. This should not become a standalone entry engine.

## Historical Check

No prior structured options experiment was found in `docs/experiment_log.jsonl`
or `docs/experiments/logs`. The playbook ranks EOD options as a mid/late
external source: useful as confirmation, but high-risk for overfit unless
PIT-safe chain data and option-liquidity filters exist.

Related blockers:

- `exp-20260503-039`: short-interest / borrow-pressure linkage remains a data
  gap with zero PIT-safe rows.
- `exp-20260503-041`: earnings snapshots exist, but SEC/earnings filing-shock
  replay is still blocked by sparse PIT archives.

## Data Availability

Structured EOD options files: 0.
Options adapter/schema files: 0.
Option chain or summary rows: 0.
Rows with IV/skew/OI/put-call/term-structure fields: 0.
Rows with `usable_trade_date` and `pit_safe`: 0.

Existing adjacent data:

- Earnings snapshots exist through `data/earnings_snapshot_20260501.json`.
- `data/non_ohlcv` currently contains SEC filing artifacts only.
- Some universe-scout code has stock-level dollar-volume filters, but no
  option-liquidity score, spread filter, or option OI/volume gate.

## Required Schema

Raw chain fields:

- `ticker`
- `date`
- `expiry`
- `strike`
- `call_put`
- `volume`
- `open_interest`
- `bid`
- `ask`
- `mid`
- `implied_vol`
- `delta`
- `option_liquidity_score`
- `usable_trade_date`
- `pit_safe`

Feature fields:

- `iv_rank`
- `iv_percentile`
- `iv_minus_realized_vol`
- `put_call_volume_ratio`
- `put_call_oi_ratio`
- `skew_25delta_or_nearest`
- `term_structure_slope`
- `call_oi_concentration`
- `put_oi_concentration`
- `earnings_iv_flag`
- `option_liquidity_filter`

## PIT Risks

Open interest and vendor greeks can carry publication lag. The adapter must
store vendor timestamp, source date, and `usable_trade_date`; same-day use
should not be assumed. Illiquid chains can create false skew and OI signals, so
the option-liquidity filter is a prerequisite rather than a later enhancement.

## Shadow Overlay Status

`squeeze_overlay`: blocked. No option OI/skew data and no PIT short/borrow rows.

`downside_risk_overlay`: blocked. No put skew or negative-event joined options
data.

`earnings_vol_overlay`: blocked. Earnings dates exist, but no IV or term
structure rows exist to align to them.

Tagged candidates: 0.
Overlap with existing signals: 0.
Forward 5/10/20/60d returns: not measurable.
Scarce-slot opportunity cost: not measurable.

## Decision

`data_gap`. EOD options remain plausible as a future confirmation layer, but
there is no local point-in-time data to run even a shadow overlay now.

## Next Minimum Action

Create a default-off append-only options data contract and adapter for existing
Ginger candidates only. It must persist source metadata, `usable_trade_date`,
`pit_safe`, option-liquidity score, and earnings-date joins before any replay
or production discussion.
