# EOD Options Structure Overlay Audit - exp-20260513-099

## Hypothesis

EOD options IV, skew, term structure, open interest concentration, and put/call structure may thicken Ginger's existing breakout, event, and earnings candidates as a shadow overlay. This run does not test options as a standalone entry and does not change production.

## Mechanism Family

`options_structure_overlay`

Shadow overlays under observation:

- `squeeze_overlay`: existing positive breakout/event candidate plus call OI or skew support; short-interest linkage remains unavailable in this ledger.
- `downside_risk_overlay`: put skew/put structure label on existing candidates; not a mechanical bearish rule.
- `earnings_vol_overlay`: high-IV earnings context; not yet wired because earnings-IV features are missing.

## Historical Check

Prior options work already exists:

- `exp-20260503-044`, `exp-20260504-043`, `exp-20260505-021`: data unavailable or insufficient.
- `exp-20260506-003`: OnClickMedia default-off harness.
- `exp-20260506-009`: historical overlay rejected because it was not PIT-safe enough for production evidence.
- `exp-20260507-091`: quality gate and `usable_trade_date` join discipline.
- `exp-20260508-024`, `exp-20260509-019`, `exp-20260510-017`, `exp-20260511-099`, `exp-20260512-099`: forward evidence accumulation, still outcome-immature.

This run only refreshes the forward ledger after the 2026-05-12 options snapshot and the now-present `data/quant_signals_20260512.json`.

## Single Causal Variable

`forward_options_structure_ledger_refresh_20260512_quote_date`

Locked variables: no production change, no options threshold sweep, no OHLCV-only entry work, no standalone option strategy, no edits to `quant/signal_engine.py`, `quant/risk_engine.py`, or `quant/portfolio_engine.py`.

## Data Availability And PIT Status

Source files:

- `data/non_ohlcv/options_onclickmedia_chain_20260505.jsonl`
- `data/non_ohlcv/options_onclickmedia_chain_20260506.jsonl`
- `data/non_ohlcv/options_onclickmedia_chain_20260507.jsonl`
- `data/non_ohlcv/options_onclickmedia_chain_20260508.jsonl`
- `data/non_ohlcv/options_onclickmedia_chain_20260511.jsonl`
- `data/non_ohlcv/options_onclickmedia_chain_20260512.jsonl`

Required raw fields are present for chain-level shadow tagging: `ticker`, `date`, `expiry`/`expiration`, `strike`, `call_put`, `volume`, `open_interest`, `bid`, `ask`, `mid`, `implied_vol`, `delta`, `option_liquidity_score`, `usable_trade_date`, and `pit_safe`.

PIT caveat: rows include `pit_safe` and `usable_trade_date`, but `vendor_asof_available_rows` is 0 on all quote dates. The only acceptable join is next usable trade date; same-day quote-date scoring would be biased.

## Option Liquidity Report

| quote_date | rows | tickers | liquidity_pass_rate | scoring_status | candidates | scoring_allowed_candidates |
|---|---:|---:|---:|---|---:|---:|
| 2026-05-05 | 4,767 | 48 | 0.000210 | quarantined | 3 | 0 |
| 2026-05-06 | 4,767 | 48 | 0.873925 | usable_for_shadow | 2 | 1 |
| 2026-05-07 | 4,783 | 48 | 0.851349 | usable_for_shadow | 6 | 5 |
| 2026-05-08 | 5,774 | 58 | 0.815552 | usable_for_shadow | 3 | 1 |
| 2026-05-11 | 5,755 | 58 | 0.868462 | usable_for_shadow | 2 | 0 |
| 2026-05-12 | 5,755 | 58 | 0.865508 | usable_for_shadow | 0 | 0 |

The 2026-05-05 quote date is quarantined because bid/ask/mid, open interest, and delta rows are effectively sparse.

## Candidate Overlap And Shadow Metrics

- `candidate_count`: 16
- `options_covered_candidates`: 16
- `options_candidate_coverage_rate`: 1.0
- `option_liquidity_eligible_candidates`: 13
- `options_scoring_allowed_candidates`: 7
- `pit_join_safe_candidates`: 9
- `pit_join_safe_rate`: 0.5625
- `quality_quarantined_candidates`: 3
- `quality_usable_candidates`: 13
- `squeeze_overlay_candidates`: 7 overall, 4 scoring-allowed bucket rows
- `downside_risk_overlay_candidates`: 6 overall, 4 scoring-allowed bucket rows
- `earnings_vol_overlay_candidates`: 0
- `overlap_with_existing_signals`: 16

All candidates came from existing Ginger candidate surfaces; this run did not generate new option-driven entries.

## Forward Outcomes And Slot Value

All 16 tagged candidates currently have `ohlcv_snapshot_missing`. Closed forward 5d, 10d, 20d, and 60d counts are all 0.

Slot conflict value is therefore not measurable:

- `squeeze_overlay.conflict_count`: 0
- `squeeze_overlay.avg_slot_conflict_value_20d`: null
- `downside_risk_overlay.conflict_count`: 0
- `downside_risk_overlay.avg_slot_conflict_value_20d`: null

## Earnings And Short-Interest Linkage

`data/earnings_snapshot_20260512.json` exists and includes earnings-date fields for most tickers, but the options ledger does not yet compute `earnings_iv_flag`.

No current PIT-safe short-interest, borrow-fee, or shares-available join is wired. The squeeze overlay therefore cannot yet test the full "high short + positive event + call structure support" mechanism.

## Baseline Metrics

Baseline reference is the accepted exp-20260513-036 stack in `docs/current_state.md`:

| window | expected_value_score | total_return_pct | total_pnl | sharpe_daily | max_drawdown | win_rate | trade_count | signals_generated | signals_survived | survival_rate | SPY B&H | QQQ B&H |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.3768 | 0.9970 | 99,695.99 | 4.39 | 0.0602 | 0.7895 | 19 | 51 | 41 | 0.8039 | 0.0541 | 0.0580 |
| mid_weak | 1.6788 | 0.6264 | 62,644.67 | 2.68 | 0.0970 | 0.5238 | 21 | 53 | 42 | 0.7925 | 0.2544 | 0.3351 |
| old_thin | 0.4292 | 0.3156 | 31,563.29 | 1.36 | 0.0836 | 0.4091 | 22 | 60 | 55 | 0.9167 | -0.0672 | -0.0749 |

Aggregate baseline expected value score is 6.4848, with total PnL 193,903.95. No after/backtest delta is computed because this run is shadow-only and has no closed outcomes.

## Production Impact

```text
production_impact:
  shared_policy_changed: false
  backtester_adapter_changed: false
  run_adapter_changed: false
  replay_only: false
  shadow_artifact_only: true
  parity_test_added: false
```

No production signal path was touched.

## Decision

`shadow_only`

The data source is now present and mostly liquid after the quarantined 2026-05-05 date, but promotion is blocked by missing closed forward outcomes, missing earnings-IV label, missing PIT short/borrow join, and no measurable slot-conflict value.

## Next Minimum Action

Collect `data/quant_signals_20260513.json` and post-2026-05-12 OHLCV outcomes, then rerun the forward ledger. Before any default-off replay, wire earnings-date alignment and a PIT-safe short-interest or borrow proxy into the options overlay ledger.
