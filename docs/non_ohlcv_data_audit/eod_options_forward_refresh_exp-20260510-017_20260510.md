# EOD Options Structure Overlay Audit

Experiment: `exp-20260510-017`
Date: 2026-05-10
Decision: `shadow_only`

## Hypothesis

EOD options structure may help interpret existing Ginger breakout/event/earnings
candidates as an overlay, especially where IV, skew, term structure, open
interest concentration, put/call structure, and option liquidity identify
squeeze support, downside risk, or earnings IV-crush risk. This remains an
overlay only, not a standalone entry or production gate.

## Historical Check

This is not a new mechanism. Prior records found:

- `exp-20260503-044`, `exp-20260504-043`, and `exp-20260505-021`: data gap.
- `exp-20260506-009`: historical OnClickMedia rows had high coverage, but
  naive call-support and downside-risk tags were not robust and were not
  historical PIT-safe enough for promotion.
- `exp-20260509-019`: forward PIT ledger produced 11 existing-candidate rows
  and 6 scoring-allowed tags, but zero closed forward outcomes.

This run found no options snapshot newer than `2026-05-08`.

## Data Availability

Local chain files exist for `2026-05-05` through `2026-05-08`:

- `data/non_ohlcv/options_onclickmedia_chain_20260505.jsonl`
- `data/non_ohlcv/options_onclickmedia_chain_20260506.jsonl`
- `data/non_ohlcv/options_onclickmedia_chain_20260507.jsonl`
- `data/non_ohlcv/options_onclickmedia_chain_20260508.jsonl`

The raw schema includes ticker/date/expiry/strike/call_put/volume/open_interest,
bid/ask/mid, implied_vol, delta, option_liquidity_score, usable_trade_date, and
pit_safe fields. `vendor_asof` is present as a field but unavailable in local
rows.

## PIT And Quality

The ledger uses `usable_trade_date`, not quote date, for candidate joins. The
`2026-05-08` options rows are usable on `2026-05-11`; strict joining still lacks
`data/quant_signals_20260511.json`.

Quality gate:

| Quote date | Rows | Tickers | Liquidity pass rate | Status |
|---|---:|---:|---:|---|
| 2026-05-05 | 4,767 | 48 | 0.021% | quarantined |
| 2026-05-06 | 4,767 | 48 | 87.39% | usable_for_shadow |
| 2026-05-07 | 4,783 | 48 | 85.13% | usable_for_shadow |
| 2026-05-08 | 5,774 | 58 | 81.56% | usable_for_shadow |

## Shadow Results

The default-off ledger joined 11 existing Ginger candidates. All overlap with
existing signal/candidate surfaces; no new ticker or standalone option signal
was created.

- Candidate count: 11
- Options covered candidates: 11
- Option-liquidity eligible candidates: 8
- Scoring-allowed candidates: 6
- PIT join-safe candidates: 8
- Squeeze overlay tags: 4
- Downside-risk overlay tags: 4
- Earnings-vol overlay tags: 0

Forward 5/10/20/60 day returns, future drawdown, future realized volatility,
and scarce-slot opportunity cost remain unavailable because no post-2026-05-08
OHLCV outcome snapshot exists and the strict `2026-05-11` candidate file is not
present.

## Blockers

- No `vendor_asof` metadata in local rows.
- No structured PIT short-interest or borrow-pressure join, so squeeze tags are
  incomplete.
- Earnings dates are not wired into the options ledger, so `earnings_iv_flag`
  remains unavailable.
- `iv_rank`, `iv_percentile`, and `iv_minus_realized_vol` are not implemented.
- No closed forward outcomes, so slot replacement value is not measurable.

## Production Impact

No production path changed. `quant/signal_engine.py`, `quant/risk_engine.py`,
`quant/portfolio_engine.py`, `quant/run.py`, and `quant/backtester.py` were not
touched. This is a default-off shadow artifact only.

## Next Minimum Action

After `data/quant_signals_20260511.json` and enough post-2026-05-08 OHLCV
history exist, rerun the forward ledger and report closed 5/10/20/60 day
returns plus slot replacement value for the six scoring-allowed tagged
candidates.
