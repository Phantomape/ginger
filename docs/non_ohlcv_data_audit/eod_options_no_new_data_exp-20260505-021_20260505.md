# EOD Options Structure Overlay Recheck

Experiment: `exp-20260505-021`
Run mode: data audit only; no production change.

## Hypothesis

EOD options structure could improve Ginger only as an overlay for existing
`breakout_long`, squeeze/event, or `earnings_event_long` candidates. Useful
fields would include IV, skew, term structure, OI concentration, put/call
structure, and option liquidity. It should not become a standalone entry engine.

This run rechecked whether any PIT-safe options data appeared after
`exp-20260504-043`.

## Historical Check

Prior records already audited this mechanism:

- `exp-20260503-044`: 0 structured EOD options files, rows, IV/skew/OI fields,
  option-liquidity fields, usable trade dates, or PIT-safe rows.
- `exp-20260504-043`: no new PIT-safe options rows after the first audit.

The playbook still ranks EOD options as a mid/late external source best used as
confirmation, not entry. This run is a duplicate guardrail and data freshness
check, not a new shadow replay.

## Current Data Availability

Structured EOD options files: 0.
Options adapter/schema files: 0.
Option chain or summary rows: 0.
Rows with IV/skew/OI/put-call/term-structure fields: 0.
Rows with `usable_trade_date` and `pit_safe`: 0.

New local non-OHLCV data after the prior audit contains SEC/Form 4 artifacts and
`daily_non_ohlcv_snapshot_20260504.json`, but no options-market structure rows.
The only option-related field found is Form 4 option exercise count; that is an
insider-transaction exclusion field, not options chain, IV, skew, OI, or flow
data.

Existing adjacent data:

- Earnings snapshots exist: 139 files, from `data/earnings_snapshot_20251023.json` through `data/earnings_snapshot_20260504.json`.
- `data/non_ohlcv` contains Form 4, SEC filing/text, and companyfacts artifacts,
  but no options chain, IV, skew, OI, put/call, or term-structure artifacts.
- Short-interest / borrow-pressure linkage remains blocked by `exp-20260504-041`:
  0 structured short-interest rows, 0 borrow-fee rows, 0 shares-available rows,
  and 0 PIT-safe rows.

## Required Schema

Raw chain fields: `ticker`, `date`, `expiry`, `strike`, `call_put`, `volume`,
`open_interest`, `bid`, `ask`, `mid`, `implied_vol`, `delta`,
`option_liquidity_score`, `usable_trade_date`, `pit_safe`.

Feature fields: `iv_rank`, `iv_percentile`, `iv_minus_realized_vol`,
`put_call_volume_ratio`, `put_call_oi_ratio`, `skew_25delta_or_nearest`,
`term_structure_slope`, `call_oi_concentration`, `put_oi_concentration`,
`earnings_iv_flag`, `option_liquidity_filter`.

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
