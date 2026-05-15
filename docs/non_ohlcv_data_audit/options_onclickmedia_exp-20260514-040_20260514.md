# Options OnClickMedia Audit - exp-20260514-040

Generated: 2026-05-14T17:20:11+00:00

## Hypothesis

EOD options IV, skew, term structure, open-interest concentration, and put/call structure may add explanatory value only as a default-off overlay on existing Ginger breakout, event, and earnings candidates. The overlay should not create standalone entries or touch production.

## Historical Check

This family has already been tested. `exp-20260506-009` rejected naive historical call/OI and put-skew overlay promotion because historical option rows were not decision-grade PIT evidence and slot-conflict evidence was weak. `exp-20260507-091`, `exp-20260508-024`, `exp-20260509-017`, `exp-20260509-019`, `exp-20260510-017`, `exp-20260511-099`, `exp-20260512-099`, `exp-20260513-099`, and `exp-20260513-102` kept the branch shadow-only because forward outcomes had not closed.

## Data Source

- Source: OnClickMedia EOD options chain snapshots.
- Files used: `data/non_ohlcv/options_onclickmedia_chain_20260505.jsonl`, `20260506`, `20260507`, `20260508`, `20260511`, `20260512`, and `20260513`.
- Harness: `scripts/run_options_forward_ledger.py`.
- Output: `data/experiments/exp-20260514-040/options_forward_candidate_ledger_report.json`.

## Schema Coverage

Available fields include `ticker`, `date`, `expiry`, `strike`, `call_put`, `volume`, `open_interest`, `bid`, `ask`, `mid`, `implied_vol`, `delta`, `option_liquidity_score`, `usable_trade_date`, and `pit_safe_flag`.

Derived shadow fields include `put_call_volume_ratio`, `put_call_oi_ratio`, `skew_25delta_approx`, `term_structure_slope`, `call_oi_concentration`, `put_oi_concentration`, `squeeze_overlay`, and `downside_risk_overlay`.

Blocked or not wired:

- `iv_rank`
- `iv_percentile`
- `iv_minus_realized_vol`
- `earnings_iv_flag`
- current PIT-safe `short_interest` / borrow-fee / shares-available join

## Coverage And Liquidity

- Quote dates audited: 7.
- Usable shadow quote dates: 6 (`2026-05-06`, `2026-05-07`, `2026-05-08`, `2026-05-11`, `2026-05-12`, `2026-05-13`).
- Quarantined quote dates: 1 (`2026-05-05`) due sparse bid/ask/OI/delta fields.
- Candidate rows joined: 19.
- Options-covered candidates: 19.
- PIT-join-safe candidates: 11.
- Options scoring-allowed candidates: 9.
- Squeeze overlay tagged candidates: 6 scoring-allowed.
- Downside-risk overlay tagged candidates: 4 scoring-allowed.
- Earnings-vol overlay candidates: 0.

The 2026-05-13 option snapshot is present and liquid, but it maps to `usable_trade_date=2026-05-14`; `data/quant_signals_20260514.json` is not present, so it has no same-policy candidate join yet.

## PIT Status

Forward rows include `pit_safe`/`pit_safe_flag` and `usable_trade_date`, and the ledger joins candidates by `usable_trade_date` rather than quote date. That makes the forward ledger suitable for shadow accumulation.

`vendor_asof_available_rows` is 0 on all audited dates. Historical promotion or same-date replay evidence remains biased unless it respects the next-trading-day usable date and can be reconstructed from local daily snapshots.

## Shadow Performance

No tagged candidate has closed 5/10/20/60 trading-day outcomes in the available OHLCV snapshot. Forward return, future drawdown, future realized volatility, and scarce-slot opportunity-cost metrics are therefore null.

Required strategy metrics are not applicable because no replay or production behavior changed:

- `expected_value_score`: null
- `total_return` / `total_pnl`: null
- `sharpe_daily`: null
- `max_drawdown`: null
- `win_rate`: null
- `trade_count`: null
- `signals_generated` / `signals_survived` / `survival_rate`: null
- `vs SPY / QQQ`: null

## Decision

`shadow_only`. The data source exists and is worth continued forward accumulation, but there is no closed outcome evidence, no current short-interest join, no earnings-IV label, and no production-safe promotion case.

## Next Minimum Action

Collect `data/quant_signals_20260514.json` for the 2026-05-13 option snapshot join, then keep accumulating PIT-safe options, quant signals, and forward OHLCV until 5/10/20/60d outcomes and slot-conflict values close.
