# EOD Options Forward Refresh - exp-20260511-099

## Scope

- Hypothesis: forward PIT-safe EOD options structure tags may add explanatory power only as an overlay on existing Ginger candidates.
- Mechanism family: `options_structure_overlay`.
- Single causal variable: forward options ledger quality gate and usable-date outcome close only.
- Mode: shadow/data audit only. No production path, replay path, ranking, sizing, entry, exit, or threshold changed.

## Historical Check

Prior options records show the same direction has already been audited:

- `exp-20260503-044`: no PIT-safe structured options data.
- `exp-20260504-043`: no new options data.
- `exp-20260505-021`: no chain, IV/skew/OI, liquidity, short-interest, or earnings-aligned options rows.
- `exp-20260506-009`: historical OnClickMedia overlay covered most backtest candidates but was PIT-unsafe and rejected for promotion.
- `exp-20260509-019`: forward ledger joined 11 existing candidates and 6 scoring-allowed tags, with no closed outcomes.
- `exp-20260510-017`: no newer option snapshot, strict 2026-05-11 candidate join, or closed outcomes.

This run is a refresh, not a new options rule.

## Data Availability And PIT Status

Local chain files:

- `data/non_ohlcv/options_onclickmedia_chain_20260505.jsonl`
- `data/non_ohlcv/options_onclickmedia_chain_20260506.jsonl`
- `data/non_ohlcv/options_onclickmedia_chain_20260507.jsonl`
- `data/non_ohlcv/options_onclickmedia_chain_20260508.jsonl`

Latest quote date remains `2026-05-08`; no newer options snapshot exists. Rows include `pit_safe` and `usable_trade_date`, but historical OnClickMedia rows still lack `vendor_asof`, so only append-only forward use is decision-grade. The strict join for 2026-05-08 rows needs `data/quant_signals_20260511.json`, which is absent.

Ticker-level option liquidity fields exist: `option_liquidity_pass` and `option_liquidity_score`. Earnings date data exists in `data/earnings_snapshot_20260508.json`, but it is not wired into the options ledger. No current PIT short-interest join is wired; only a prior short-interest experiment artifact was found.

## Coverage And Liquidity

| Quote date | Rows | Tickers | Liquidity pass rate | Scoring allowed | Status |
|---|---:|---:|---:|---|---|
| 2026-05-05 | 4,767 | 48 | 0.00021 | false | quarantined |
| 2026-05-06 | 4,767 | 48 | 0.873925 | true | usable_for_shadow |
| 2026-05-07 | 4,783 | 48 | 0.851349 | true | usable_for_shadow |
| 2026-05-08 | 5,774 | 58 | 0.815552 | true | usable_for_shadow |

The 2026-05-05 collection is quarantined because bid/ask/mid, open interest, and delta coverage are effectively empty despite nonzero IV/volume fields.

## Shadow Overlay Results

- Candidate count: 11 existing candidates.
- Options covered candidates: 11.
- Option-liquidity eligible candidates: 8.
- Scoring-allowed candidates: 6.
- PIT join safe candidates: 8.
- Squeeze overlay candidates: 4.
- Downside-risk overlay candidates: 4.
- Earnings-vol overlay candidates: 0.
- Outcome status: all 11 are blocked by missing post-signal OHLCV outcome snapshots.

Forward 5/10/20/60d returns, future drawdown, future realized volatility, and slot conflict value are unavailable because no tagged candidates have closed outcomes in the local data.

## Required Metrics

Strategy metrics such as `expected_value_score`, total return, total PnL, Sharpe, max drawdown, win rate, trade count, `signals_generated`, `signals_survived`, survival rate, and SPY/QQQ deltas are not applicable to this shadow audit. No strategy path changed and no default-off replay was promoted. Candidate count, overlap, and slot-value readiness are recorded in `data/experiments/exp-20260511-099/options_forward_candidate_ledger_report.json`.

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

The options data is present and partially usable for forward shadow tagging, but there is no new snapshot, no strict 2026-05-11 candidate file, no earnings-IV join, no short-interest join, and no closed forward outcome or scarce-slot value. The next minimum action is to rerun only after `data/quant_signals_20260511.json` plus enough later OHLCV history exist to close 5/10/20/60d outcomes.
