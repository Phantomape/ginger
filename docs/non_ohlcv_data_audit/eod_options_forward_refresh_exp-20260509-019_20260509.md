# EOD options forward ledger refresh (exp-20260509-019)

## Hypothesis

Forward PIT-safe EOD options structure tags may add explanatory power as an overlay only when attached to existing Ginger candidates, not as standalone entries.

## Historical Check

Prior options work already exists. `exp-20260506-009` rejected naive historical call/OI and put-skew promotion: options coverage was high, but call-structure support underperformed and downside-risk structure was not stable across windows. `exp-20260507-091` added the quality gate and usable-date join, and `exp-20260508-024` refreshed the ledger through the 2026-05-07 quote date.

This run is not a repeat of that rejected mechanism. The single new variable is adding the 2026-05-08 options snapshot plus the now-present 2026-05-08 candidate join to the same default-off ledger.

## Source and PIT Status

- Source: OnClickMedia EOD options chain snapshots.
- Files: `data/non_ohlcv/options_onclickmedia_chain_20260505.jsonl, data/non_ohlcv/options_onclickmedia_chain_20260506.jsonl, data/non_ohlcv/options_onclickmedia_chain_20260507.jsonl, data/non_ohlcv/options_onclickmedia_chain_20260508.jsonl`.
- PIT rule: EOD option rows are joined by `usable_trade_date`, not same-day `quote_date`.
- PIT caveats: `vendor_asof` is unavailable, OI can lag, and 2026-05-08 rows are only usable from 2026-05-11.
- Option liquidity filter: `option_liquidity_pass` and `option_liquidity_score` exist and are enforced by the quality gate.
- Earnings alignment: `earnings_snapshot_20260508.json` exists, but the options ledger does not yet wire earnings date; `earnings_vol_overlay` remains null.
- Short-interest linkage: no true PIT borrow-fee or availability data is available locally; rejected free short-pressure proxies were not joined.

## Quality Gate

| Quote date | Usable date | Status | Rows | Tickers | Liquidity pass rate | Liquid tickers >=10 rows | Ask > bid rate | OI > 0 rate | Delta nonzero rate |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026-05-05 | 2026-05-06 | quarantined | 4767 | 48 | 0.00021 | 0 | 0.00021 | 0.00021 | 0.00021 |
| 2026-05-06 | 2026-05-07 | usable_for_shadow | 4767 | 48 | 0.873925 | 48 | 0.99979 | 0.98154 | 0.512272 |
| 2026-05-07 | 2026-05-08 | usable_for_shadow | 4783 | 48 | 0.851349 | 48 | 0.999373 | 0.984529 | 0.509513 |
| 2026-05-08 | 2026-05-11 | usable_for_shadow | 5774 | 58 | 0.815552 | 58 | 0.996363 | 0.969692 | 0.511084 |

The 2026-05-05 snapshot remains quarantined. The 2026-05-06, 2026-05-07, and 2026-05-08 snapshots pass shadow-quality gates.

## Candidate Overlap

- Candidate count: 11.
- Options-covered candidates: 11.
- PIT-safe candidate joins: 8.
- Quality-usable candidates: 8.
- Option-liquidity eligible candidates: 8.
- Options scoring allowed candidates: 6.
- Overlap with existing signals/candidates: 11.

Scoring-allowed candidate diagnostics:

- LITE (2026-05-06 -> 2026-05-07, event_sleeve_bundle): squeeze=false, downside=false, put/call OI=1.044968, skew25=-0.05988, call OI conc=0.09225.
- INTC (2026-05-07 -> 2026-05-08, pilot_signals): squeeze=true, downside=false, put/call OI=0.648795, skew25=-0.0039, call OI conc=0.147589.
- MCD (2026-05-07 -> 2026-05-08, sec_event_queue): squeeze=false, downside=true, put/call OI=1.289838, skew25=-0.1455, call OI conc=0.094583.
- GE (2026-05-07 -> 2026-05-08, sec_leadership_event_queue): squeeze=true, downside=true, put/call OI=0.317042, skew25=0.07226, call OI conc=0.177886.
- GE (2026-05-07 -> 2026-05-08, event_sleeve_bundle): squeeze=true, downside=true, put/call OI=0.317042, skew25=0.07226, call OI conc=0.177886.
- MCD (2026-05-07 -> 2026-05-08, event_sleeve_bundle): squeeze=false, downside=true, put/call OI=1.289838, skew25=-0.1455, call OI conc=0.094583.

## Shadow Performance

No closed forward outcomes are available yet. The local OHLCV outcome snapshot does not cover horizons after the May 2026 candidate dates, so forward 5/10/20/60d returns, future drawdown, future realized volatility, and slot conflict value are pending.

| Metric | Value |
| --- | ---: |
| Scoring-allowed candidates | 6 |
| Squeeze overlay candidates | 4 |
| Scoring-allowed squeeze bucket | 3 |
| Downside-risk overlay candidates | 4 |
| Earnings-vol overlay candidates | 0 |
| Closed 5d outcomes | 0 |
| Closed 10d outcomes | 0 |
| Closed 20d outcomes | 0 |
| Closed 60d outcomes | 0 |
| Slot conflict count | 0 |

Important diagnostic caution: GE is tagged by both the simple squeeze and downside definitions. This confirms the overlay cannot be used mechanically; it needs closed outcome evidence and likely richer context before any scoring claim.

## Baseline and EV Impact

Baseline remains the accepted three-window A/B stack: aggregate EV `6.0452`, aggregate PnL `$177676.93`, and aggregate trade count `62`. This run changed no production or backtest policy, so production EV delta is `0.0`; shadow EV delta is not measurable yet.

## Decision

`shadow_only`. The options source has usable forward rows and now six scoring-allowed candidate joins, but there is no closed outcome evidence and no slot replacement value. Do not promote to ranking, sizing, filters, exits, or production signal path.

## Next Minimum Action

Collect `data/quant_signals_20260511.json` and post-2026-05-08 OHLCV outcomes. Then close 5/10/20/60d returns for the six scoring-allowed candidates before revisiting overlay value.
