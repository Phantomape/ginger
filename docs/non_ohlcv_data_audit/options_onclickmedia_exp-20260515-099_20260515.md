# Options OnClickMedia Audit - exp-20260515-099

Date: 2026-05-15

## Hypothesis

EOD options IV, skew, term structure, open-interest concentration, and put/call structure may add explanatory value only as a default-off overlay on existing Ginger breakout, event, and earnings candidates. It should not be a standalone entry.

## Mechanism Family

`non_ohlcv_options_structure_overlay`

Shadow overlays audited:

- `squeeze_overlay`: positive existing candidate plus supportive call OI/skew structure, eventually requiring PIT-safe short-interest linkage.
- `downside_risk_overlay`: put skew / downside structure tag on existing candidates.
- `earnings_vol_overlay`: earnings IV / post-event IV crush tag; not wired yet.

## Historical Check

This direction has already been tried. Earlier runs found no data (`exp-20260503-044`, `exp-20260504-043`, `exp-20260505-021`), then created the OnClickMedia harness (`exp-20260506-003`). `exp-20260506-009` rejected historical overlay promotion because the evidence was PIT-unsafe and slot value was weak. The forward ledger family through `exp-20260514-040` stayed shadow-only because candidate overlap was sparse and no 5/10/20/60d outcomes had closed.

A prior same-day options artifact was written under `exp-20260515-033`, but that ID collided with an unrelated experiment record. This run uses a clean experiment ID and does not retune option thresholds.

## Data Availability

Local chain files are present through `data/non_ohlcv/options_onclickmedia_chain_20260514.jsonl`.

Required schema is mostly present: `ticker`, `date`, `expiry`, `strike`, `call_put`, `volume`, `open_interest`, `bid`, `ask`, `mid`, `implied_vol`, `delta`, `option_liquidity_score`, `usable_trade_date`, and `pit_safe_flag`.

Still missing or not wired:

- `iv_rank`
- `iv_percentile`
- `iv_minus_realized_vol`
- `earnings_iv_flag`
- PIT-safe short-interest / borrow / shares-available join

## PIT Status

Forward rows carry `pit_safe` and `usable_trade_date`; the ledger joins candidates on the usable trade date, not same-day quote date. `vendor_asof_available_rows` is 0, so historical same-day replay promotion remains biased. This is safe only as a forward shadow ledger.

The 2026-05-14 options snapshot maps to usable trade date 2026-05-15, but `data/daily/signals/quant/quant_signals_20260515.json` is not present.

## Liquidity Report

Collection quality gate:

- Overall status: `usable_shadow_dates_present`
- Usable quote dates: 2026-05-06, 2026-05-07, 2026-05-08, 2026-05-11, 2026-05-12, 2026-05-13, 2026-05-14
- Quarantined quote dates: 2026-05-05
- 2026-05-14 rows: 5755
- 2026-05-14 tickers: 58
- 2026-05-14 option liquidity pass rows: 4831
- 2026-05-14 option liquidity pass rate: 0.839444

The 2026-05-05 file remains quarantined because bid/ask/mid, OI, delta, and liquidity-pass rows were effectively sparse.

## Shadow Candidate Metrics

| metric | value |
|---|---:|
| candidate_count | 21 |
| options_covered_candidates | 21 |
| options_candidate_coverage_rate | 1.0 |
| option_liquidity_eligible_candidates | 18 |
| options_scoring_allowed_candidates | 9 |
| pit_join_safe_candidates | 11 |
| pit_join_safe_rate | 0.52381 |
| quality_quarantined_candidates | 3 |
| squeeze_overlay_candidates | 12 |
| downside_risk_overlay_candidates | 6 |
| earnings_vol_overlay_candidates | 0 |
| overlap_with_existing_signals | 21 |

Forward outcome status:

- closed 5d outcomes: 0
- closed 10d outcomes: 0
- closed 20d outcomes: 0
- closed 60d outcomes: 0
- slot conflict count: 0
- average slot conflict value: None

The available OHLCV snapshot is `data/ohlcv_snapshot_20251023_20260501_with_pilot.json`, so the May 2026 signal dates do not yet have closed forward returns in this run.

## Baseline Context

No strategy replay was run because this is a shadow/audit refresh, not a default-off replay. Current accepted core fixed-window context from `docs/backtesting.md`:

| window | EV | Sharpe | PnL | Return | Max DD | Win rate | Trades | Survival |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1064 | 4.39 | $116,319.10 | 116.32% | 6.65% | 78.95% | 19 | 80.39% |
| mid_weak | 2.0987 | 2.76 | $76,035.04 | 76.04% | 10.63% | 52.38% | 21 | 79.25% |
| old_thin | 0.5294 | 1.42 | $37,282.59 | 37.28% | 10.01% | 40.91% | 22 | 86.67% |

Because no production or replay behavior changed, `expected_value_score_delta`, `total_return`, `total_pnl`, `sharpe_daily`, `max_drawdown`, `win_rate`, `trade_count`, `signals_generated`, `signals_survived`, `survival_rate`, `vs_spy`, and `vs_qqq` are not applicable for this experiment.

## Production Impact

No production change.

```text
production_impact:
  shared_policy_changed: false
  backtester_adapter_changed: false
  run_adapter_changed: false
  replay_only: true
  parity_test_added: false
  live_slots_changed: false
```

## Decision

`shadow_only`

Options data is present and joins to existing candidates with usable-date discipline, but it still has no closed forward returns, no measurable scarce-slot opportunity cost, no wired earnings IV tag, and no current PIT-safe short-interest join. It is worth continuing as a short-squeeze / earnings overlay research branch, but not a production candidate.

## Next Minimum Action

After `quant_signals_20260515.json` and later OHLCV snapshots exist, rerun the same ledger and compute closed 5/10/20/60d returns, future drawdown, future realized vol, and slot-conflict value. Do not promote until the overlay has closed forward evidence plus PIT-safe short-interest and earnings-date joins.
