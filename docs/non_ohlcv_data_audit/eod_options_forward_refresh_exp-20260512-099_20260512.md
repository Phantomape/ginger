# EOD Options Forward Refresh - exp-20260512-099

## Scope

- Hypothesis: forward PIT-safe EOD options structure tags may add explanatory power only as an overlay on existing Ginger candidates.
- Non-OHLCV source: OnClickMedia EOD options chain snapshots.
- Mechanism family: `options_structure_overlay`.
- Single causal variable: forward options ledger quality gate and usable-date outcome refresh only.
- Mode: shadow/data audit only. No production path, replay path, ranking, sizing, entry, exit, or threshold changed.

## Historical Check

Prior options records show this is a refresh, not a new rule:

- `exp-20260503-044`: no PIT-safe structured options data.
- `exp-20260504-043`: no new options data.
- `exp-20260505-021`: no chain, IV/skew/OI, liquidity, short-interest, or earnings-aligned options rows.
- `exp-20260506-003`: default-off OnClickMedia data harness accepted for forward accumulation; historical backfill remains PIT-unsafe.
- `exp-20260506-009`: historical OnClickMedia overlay covered most candidates but was PIT-unsafe and rejected for promotion.
- `exp-20260511-099`: forward ledger joined 11 existing candidates and 6 scoring-allowed tags, with no closed outcomes.

## Data Availability And PIT Status

Local chain files:

- `data/non_ohlcv/options_onclickmedia_chain_20260505.jsonl`
- `data/non_ohlcv/options_onclickmedia_chain_20260506.jsonl`
- `data/non_ohlcv/options_onclickmedia_chain_20260507.jsonl`
- `data/non_ohlcv/options_onclickmedia_chain_20260508.jsonl`
- `data/non_ohlcv/options_onclickmedia_chain_20260511.jsonl`

Rows include `pit_safe`, `usable_trade_date`, `bid`, `ask`, `mid`, `implied_vol`, `delta`, `volume`, `open_interest`, `option_liquidity_score`, and `option_liquidity_pass`. Historical OnClickMedia rows still lack vendor-as-of evidence, so only append-only forward rows are decision-grade.

The `2026-05-08` quote date now joins strictly to `data/quant_signals_20260511.json`, increasing existing-candidate overlap from 11 to 14. The new `2026-05-11` quote date is liquid and PIT-tagged, but it requires `data/quant_signals_20260512.json`; that file is absent, so it cannot tag candidates yet.

Ticker-level option liquidity exists through `option_liquidity_score` and `option_liquidity_pass`. Earnings data exists in `data/earnings_snapshot_20260511.json`, but earnings date alignment is not wired into this ledger, so `earnings_vol_overlay` remains zero. Prior short-interest artifacts exist, but no current PIT short-interest join is wired.

Missing features for a richer options overlay:

- `iv_rank`
- `iv_percentile`
- `iv_minus_realized_vol`
- `earnings_iv_flag`
- current PIT short-interest join
- closed forward OHLCV outcomes

## Coverage And Liquidity

| Quote date | Rows | Tickers | Liquidity pass rate | Candidate count | Scoring allowed | Status |
|---|---:|---:|---:|---:|---:|---|
| 2026-05-05 | 4,767 | 48 | 0.000210 | 3 | 0 | quarantined |
| 2026-05-06 | 4,767 | 48 | 0.873925 | 2 | 1 | usable_for_shadow |
| 2026-05-07 | 4,783 | 48 | 0.851349 | 6 | 5 | usable_for_shadow |
| 2026-05-08 | 5,774 | 58 | 0.815552 | 3 | 1 | usable_for_shadow |
| 2026-05-11 | 5,755 | 58 | 0.868462 | 0 | 0 | usable_for_shadow_but_missing_20260512_candidate_file |

The `2026-05-05` collection remains quarantined because bid/ask/mid, open interest, and delta coverage are effectively empty despite nonzero IV/volume fields.

## Shadow Overlay Results

- Candidate count: 14 existing candidates.
- Options covered candidates: 14.
- Option-liquidity eligible candidates: 11.
- Scoring-allowed candidates: 7.
- PIT join safe candidates: 9.
- Squeeze overlay candidates: 5 overall; 4 scoring-allowed.
- Downside-risk overlay candidates: 6 overall; 4 scoring-allowed.
- Earnings-vol overlay candidates: 0.
- Outcome status: all 14 are blocked by missing post-signal OHLCV outcome snapshots.

Forward 5/10/20/60d returns, future drawdown, future realized volatility, and slot conflict value are unavailable because no tagged candidates have closed outcomes in the local data.

## Required Metrics

Strategy metrics such as `expected_value_score`, total return, total PnL, Sharpe, max drawdown, win rate, trade count, `signals_generated`, `signals_survived`, survival rate, and SPY/QQQ deltas are not applicable to this shadow audit. No strategy path changed and no default-off replay was promoted.

Candidate count, overlap, and slot-value readiness are recorded in `data/experiments/exp-20260512-099/options_forward_candidate_ledger_report.json`.

## Production Impact

```text
production_impact:
  shared_policy_changed: false
  backtester_adapter_changed: false
  run_adapter_changed: false
  replay_only: true
  parity_test_added: false
  production_signal_path_changed: false
```

## Decision

`shadow_only`.

The options data is present and partially usable for forward shadow tagging, but there are still no closed forward outcomes, no `2026-05-12` candidate join, no earnings-IV join, and no current short-interest join. The next minimum action is to rerun after `data/quant_signals_20260512.json` exists and enough later OHLCV history is available to close 5/10/20/60d outcomes.
