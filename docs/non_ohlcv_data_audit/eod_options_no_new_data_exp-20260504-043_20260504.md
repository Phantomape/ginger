# EOD Options Structure Overlay Recheck

Experiment: `exp-20260504-043`
Run mode: data audit only; no production change.

## Hypothesis

EOD options structure could improve Ginger only as an overlay for existing
`breakout_long`, squeeze/event, or `earnings_event_long` candidates. The useful
information would be IV, skew, term structure, OI concentration, put/call
structure, and option liquidity. It should not be a standalone entry engine.

This run rechecked whether any PIT-safe options data appeared after
`exp-20260503-044`.

## Historical Check

`exp-20260503-044` already audited this mechanism and found a data gap:

- 0 structured EOD options files.
- 0 option chain or summary rows.
- 0 IV/skew/OI/put-call/term-structure rows.
- 0 option-liquidity rows.
- 0 `usable_trade_date` / `pit_safe` rows.

The current playbook still ranks EOD options as a mid/late external alpha
source, best used as overlay/confirmation rather than standalone entry. This
recheck is not a new shadow replay; it is a duplicate guardrail confirming that
there is still no taggable data.

## Current Data Availability

Structured EOD options files: 0.
Options adapter/schema files: 0.
Option chain or summary rows: 0.
Rows with IV/skew/OI/put-call/term-structure fields: 0.
Rows with `usable_trade_date` and `pit_safe`: 0.

Files matching options terms in scoped repo data/docs/quant search:

- `docs/non_ohlcv_data_audit/eod_options_20260503.md`

This is a prior audit document, not data.

Existing adjacent data:

- Earnings snapshots exist: 138 files, from `data/earnings_snapshot_20251023.json`
  through `data/earnings_snapshot_20260503.json`.
- `data/non_ohlcv` contains Form 4 and SEC filing/companyfacts artifacts, but no
  options chain, IV, skew, OI, put/call, or term-structure artifacts.
- Short-interest / borrow-pressure linkage remains blocked by
  `exp-20260503-039`: 0 structured short-interest rows, 0 borrow-fee rows,
  0 shares-available rows, and 0 PIT-safe rows.

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

Open interest can be reported with exchange/vendor lag. The adapter must store
vendor timestamp, source date, and `usable_trade_date`; same-day use should not
be assumed. Vendor greeks and IV surfaces need as-of metadata. Illiquid chains
can fabricate skew and OI signals, so option-liquidity scoring is a prerequisite.

Squeeze interpretation also needs structured short-interest or borrow-pressure
data. Headlines are not a substitute for borrow fee, shares available, or
published short-interest fields.

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
there is still no local point-in-time data to run even a shadow overlay.

## Next Minimum Action

Do not rerun this overlay until nonzero PIT-safe options rows exist. The next
valid step is a default-off append-only options data contract and adapter for
existing Ginger candidates only, with source metadata, `usable_trade_date`,
`pit_safe`, option-liquidity score, and earnings-date joins.
