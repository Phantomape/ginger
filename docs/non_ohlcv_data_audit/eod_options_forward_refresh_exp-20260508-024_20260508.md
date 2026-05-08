# EOD options forward ledger refresh (exp-20260508-024)

## Hypothesis

Forward PIT-safe EOD options structure tags may add explanatory power as an overlay only when attached to existing Ginger candidates, not as standalone entries.

## Historical check

Prior options work already exists. `exp-20260506-009` rejected naive historical call/OI and put-skew promotion: options coverage was high, but call-structure support underperformed and downside-risk structure was not stable across windows. `exp-20260507-091` added the current quality gate and usable-trade-date join. This run only refreshes the forward ledger with the new 2026-05-07 option snapshot and the now-present 2026-05-07 candidate file.

This does not retry nearby call/put OI thresholds, simple call dominance, simple put-skew vetoes, or same-sample historical promotion.

## Source and PIT status

- Source: OnClickMedia EOD options chain snapshots.
- Files: `data/non_ohlcv/options_onclickmedia_chain_20260505.jsonl`, `data/non_ohlcv/options_onclickmedia_chain_20260506.jsonl`, `data/non_ohlcv/options_onclickmedia_chain_20260507.jsonl`.
- PIT rule: EOD option rows are joined by `usable_trade_date`, not same-day `quote_date`.
- PIT caveats: `vendor_asof` is unavailable, and option open interest can lag.
- Option liquidity filter: available through `option_liquidity_pass` and `option_liquidity_score`.
- Earnings alignment: not wired; `earnings_vol_overlay` remains null.
- Short-interest linkage: not available locally; prior audits still show no structured PIT short/borrow rows.

## Quality gate

| Quote date | Usable date | Status | Rows | Tickers | Liquidity pass rate | Liquid tickers >=10 rows | Ask > bid rate | OI > 0 rate | Delta nonzero rate |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026-05-05 | 2026-05-06 | quarantined | 4767 | 48 | 0.00021 | 0 | 0.00021 | 0.00021 | 0.00021 |
| 2026-05-06 | 2026-05-07 | usable_for_shadow | 4767 | 48 | 0.873925 | 48 | 0.999790 | 0.981540 | 0.512272 |
| 2026-05-07 | 2026-05-08 | usable_for_shadow | 4783 | 48 | 0.851349 | 48 | 0.999373 | 0.984529 | 0.509513 |

The 2026-05-05 snapshot remains quarantined. The 2026-05-06 and 2026-05-07 snapshots pass shadow-quality gates.

## Candidate overlap

- Candidate count: 5.
- Options-covered candidates: 5.
- PIT-safe candidate joins: 3.
- Quality-usable candidates: 2.
- Option-liquidity eligible candidates: 2.
- Options scoring allowed candidates: 1.
- Overlap with existing signals/candidates: 5.

The only scoring-allowed row is `LITE` from the 2026-05-06 quote date joined to the 2026-05-07 `event_sleeve_bundle` candidate. It has `put_call_oi_ratio = 1.044968`, `skew_25delta_approx = -0.05988`, `call_oi_concentration = 0.09225`, and `put_oi_concentration = 0.134496`. It did not trigger squeeze, downside-risk, or earnings-vol tags.

## Shadow performance

No closed forward outcomes are available yet. The local OHLCV snapshots end before these May 2026 candidate dates, so forward 5/10/20/60d returns, future drawdown, future realized volatility, and slot conflict value are all pending.

| Metric | Value |
| --- | ---: |
| Scoring-allowed candidates | 1 |
| Squeeze overlay candidates | 0 |
| Downside-risk overlay candidates | 0 |
| Earnings-vol overlay candidates | 0 |
| Closed 5d outcomes | 0 |
| Closed 10d outcomes | 0 |
| Closed 20d outcomes | 0 |
| Closed 60d outcomes | 0 |
| Slot conflict count | 0 |

## Baseline and EV impact

Baseline remains the accepted three-window A/B stack: aggregate EV `5.6272`, aggregate PnL `$167,347.95`, and aggregate trade count `62`. This run changed no production or backtest policy, so production EV delta is `0.0`; shadow EV delta is not measurable yet.

## Decision

`shadow_only`. The options source now has usable forward rows, but there is no closed outcome evidence and no overlay tag fired on the only scoring-allowed candidate. Do not promote to ranking, sizing, filters, exits, or production signal path.

## Next minimum action

Keep collecting options snapshots and `quant_signals`. The immediate missing join is `data/quant_signals_20260508.json` for the 2026-05-07 option snapshot. After enough rows close, compute 5/10/20/60d returns, future drawdown, future realized volatility, and same-day slot conflict value before revisiting overlay value.
