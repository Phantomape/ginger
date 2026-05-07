# EOD Options OnclickMedia Harness Audit

Experiment: `exp-20260506-003`

## Hypothesis

EOD options structure can eventually work as a non-standalone overlay for
existing Ginger breakout, event, and earnings candidates. The immediate
blocker from prior audits was not alpha logic; it was the absence of any
append-only options chain source with IV, greeks, OI, bid/ask, liquidity, and
PIT metadata.

## Source

- Source: OnclickMedia historical EOD options chain API
- Docs: `https://www.onclickmedia.com/Documentation`
- Local adapter: `quant/options_onclickmedia.py`
- Local production snapshot: `data/non_ohlcv/options_onclickmedia_chain_YYYYMMDD.jsonl`
- Local historical CLI: `python quant/options_onclickmedia.py --start YYYY-MM-DD --end YYYY-MM-DD --tickers TSLA,NVDA --full-chain`
- Raw API cache: `data/options_onclickmedia_cache/` (ignored by git)

OnclickMedia is free and no-key, but it is still a public-source aggregation
feed. Treat this as an audit/backfill source until coverage, vendor timing, OI
lag, and row quality are measured.

## Historical Check

Prior options records were all data gaps:

- `exp-20260503-044`: no structured options files or PIT-safe rows.
- `exp-20260504-043`: no new options chain, IV/skew/OI, liquidity, short-interest linkage, or earnings-aligned options rows.
- `exp-20260505-021`: no new local options rows; next action was an append-only EOD options source adapter.

This run is not another no-data audit. It implements that missing source
adapter and writes a real smoke dataset.

## Schema Status

Present in normalized rows:

- `ticker`
- `date` / `quote_date`
- `expiry` / `expiration`
- `strike`
- `call_put`
- `volume`
- `open_interest`
- `bid`
- `ask`
- `mid`
- `implied_vol`
- `delta` and other greeks when available
- `option_liquidity_score`
- `option_liquidity_pass`
- `usable_trade_date`
- `pit_safe`
- `pit_safe_flag`
- `pit_caveat`

Not yet produced:

- `iv_rank`
- `iv_percentile`
- `iv_minus_realized_vol`
- `put_call_volume_ratio`
- `put_call_oi_ratio`
- `skew_25delta`
- `term_structure_slope`
- `call_oi_concentration`
- `put_oi_concentration`
- `earnings_iv_flag`

Those are downstream ticker-day feature summaries and should be computed only
after enough rows exist for candidate-day joins.

## PIT Status

Forward daily production rows are marked:

- `collection_mode = forward_daily`
- `pit_safe = true`
- `usable_trade_date = next weekday after quote_date`

Historical backfill rows are marked:

- `collection_mode = historical_backfill`
- `pit_safe = false`
- `usable_trade_date = next weekday after quote_date`
- `pit_safe_flag = historical_backfill_vendor_asof_missing`

Reason: the free source does not expose vendor publication/as-of metadata. This
is conservative and avoids pretending the historical backfill is fully
point-in-time proof.

## Smoke Result

Command:

```bash
python quant/options_onclickmedia.py --start 2025-01-13 --end 2025-01-13 --tickers TSLA --max-expirations 1 --max-strikes-per-side 0 --sleep-seconds 0 --output data/non_ohlcv/options_onclickmedia_chain_exp-20260506-003_smoke.jsonl --summary-output data/non_ohlcv/options_onclickmedia_summary_exp-20260506-003_smoke.json
```

Result:

- Ticker/date: `TSLA` / `2025-01-13`
- Expiration pulled: `2025-01-17`
- Requests attempted: `3`
- Rows written: `430`
- Error count: `0`
- Option-liquidity pass rows: `362`
- Option-liquidity pass rate: `84.19%`
- PIT-safe rows: `0`
- PIT-unsafe rows: `430`

The zero PIT-safe row count is expected for historical backfill mode.

## Production Impact

Production now calls the data collector from `quant/run.py` through
`persist_daily_non_ohlcv_snapshots(...)`, passing the current data universe and
latest OHLCV close prices for ATM strike-window filtering.

This changes data accumulation only:

- Signal generation: unchanged
- Candidate ranking: unchanged
- Sizing: unchanged
- Orders: unchanged
- Backtester: unchanged
- `quant/signal_engine.py`: untouched
- `quant/risk_engine.py`: untouched
- `quant/portfolio_engine.py`: untouched

## Decision

Decision: `default_off_candidate`.

The source is good enough to start accumulating data and to backfill coverage
audits, but not good enough to promote an options overlay into production
signals. The next experiment must join option rows to existing candidates and
report candidate overlap, 5/10/20/60d forward returns, future drawdown, future
realized vol, and scarce-slot value.
