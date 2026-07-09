# Core Entry Admission And External Strategy Plan

Last updated: 2026-07-08.

This plan converts the July 8 discussion into a handoff-ready experiment queue.
The starting concern is that the core `breakout_long` and `trend_long`
strategies can still enter weak contexts even when existing risk scalars and
stops reduce the damage. The next work should test whether some contexts should
be blocked before entry, and whether simple external strategy families can
serve as stronger baselines than more threshold tuning.

This is a plan, not accepted alpha evidence. Any strategy-affecting change must
still reserve an experiment ID, pass the novelty gate, run Gate 1-4 from
`docs/backtesting.md`, and close with artifacts.

## Current Diagnosis

- Core winners remain large enough that broad deactivation is the wrong
  default. The failure mode is uneven entry quality, especially where a weak
  context is already visible before the order.
- Repeated tuning of breakout/trend thresholds, stops, and risk multipliers is
  now low-value unless it introduces a genuinely new gate shape or new evidence
  surface.
- A risk scalar answers "how small should this position be?" It does not answer
  "should this order exist at all?" The missing layer is an auditable admission
  decision between signal generation and execution.
- External strategy research is useful mainly as benchmark and gate-shape
  discipline. It should not become a license to add opaque indicators.

## First Experiment To Start

Reserved experiment:

- `exp-20260708-021`
- Status: `observed_only_rejected_severe_haircut_no_entry_diagnostic`.
- Runner: `quant/experiments/exp_20260708_021_core_trend_long_severe_haircut_no_entry_admission.py`
- Result: the fixed severe-haircut no-entry diagnostic blocked 14 saved
  `trend_long` trades, but the blocked cohort had positive aggregate PnL
  (`+$2,251.60`), no canonical window improved, and the additive
  counterfactual reduced total PnL from `$234,850.99` to `$232,599.39`.
- Decision: do not promote a rule that simply converts existing severe
  risk-haircut flags into no-entry. The next admission work needs an
  independent field, a shared-helper Gate 1-4 with a different predeclared
  gate shape, or movement to the external baseline queue below.

Experiment theme:

```text
existing severe-risk haircut -> no-entry admission diagnostic
```

Fixed hypothesis:

> When the current core system has already assigned a severe production-visible
> risk haircut to a `trend_long` trade, a pre-entry admission gate would avoid
> more weak-context loss than it sacrifices in opportunity cost.

Single attributable decision:

- Convert existing severe risk-haircut evidence into a no-entry diagnostic.
- Do not add new indicators, retune trend/breakout thresholds, change stops,
  change position sizing, or alter live/default orders in this first test.

Initial rule for the diagnostic:

- Candidate trade is `strategy == "trend_long"`.
- The saved trade has any `sizing_multipliers` item whose key contains
  `risk_multiplier_applied` and whose numeric value is `<= 0.25`.
- Such trades are treated as "blocked before entry" in a read-only
  counterfactual over canonical saved trades.

Why this is first:

- It directly tests the user question: can the system avoid bad entries instead
  of entering and relying on stops?
- It uses production-known fields that already existed before entry.
- It is a new gate shape: admission/no-entry from severe risk evidence, not a
  threshold retune of raw momentum or breakout variables.
- It is deliberately read-only. A positive result is only a lead; promotion
  requires a shared backtest/production helper and full Gate 1-4 replay.

Expected artifact:

- Per canonical window: baseline trades/PnL/win rate, blocked trade count,
  blocked PnL/opportunity cost, remaining trade count, and approximated
  counterfactual PnL.
- Aggregate blocked-trade attribution and concentration checks.
- Explicit `diagnostic_only: true` and `strategy_code_changed: false`.

Observed-only lead criteria:

- Blocked trades have negative aggregate PnL.
- At least two of the three canonical windows improve on additive trade PnL.
- Trade count is not reduced below statistical usefulness.
- No single ticker or one window explains the entire result.

Required follow-up if positive:

- Implement a shared admission helper used by both historical replay and
  production/default-off decision paths.
- Rerun full Gate 1-4 with real slot displacement, cash drag, exits, and
  ranking effects. The read-only counterfactual cannot accept strategy behavior.

## External Baseline Queue

Each lane below must be a separate experiment or fixed policy bundle. Do not
combine them unless the experiment explicitly declares a portfolio allocator
test.

### 1. Donchian / Turtle Breakout Baseline

Experiment:

- `exp-20260708-022`
- Status: `observed_only_rejected_donchian_turtle_breakout_baseline`.
- Runner: `quant/experiments/exp_20260708_022_donchian_turtle_breakout_external_baseline.py`
- Result: fixed Donchian/Turtle 55-day breakout / 20-day exit produced
  51 trades and positive aggregate PnL (`+$26,999.79`), but it lost badly to
  current `breakout_long` (`+$102,854.01`), won zero canonical windows versus
  `breakout_long`, and hit a `31.339%` max window drawdown in `old_thin`.
- Decision: do not replace or benchmark-promote core `breakout_long` with
  vanilla Donchian/Turtle 55/20 on these windows. The next breakout-family
  retry needs a genuinely different external evidence axis, not another
  lookback, cost, universe, sizing, or channel-exit retune.

Purpose:

- Challenge `breakout_long` against a canonical price-channel breakout family.

Implementable shape:

- Fixed Donchian channel lookback and exit rule selected before the run.
- Same canonical windows, costs, liquidity constraints, and position limits as
  core.
- Compare to current `breakout_long`, not only to cash.

Avoid:

- Sweeping channel windows until one wins.
- Adding filters that are just the current breakout logic under new names.

### 2. 12-1 Or Residual Momentum Baseline

Experiment:

- `exp-20260708-024`
- Status: `observed_only_rejected_cross_sectional_12_1_momentum_external_baseline`.
- Runner: `quant/experiments/exp_20260708_024_cross_sectional_12_1_momentum_external_baseline.py`
- Result: fixed 12-1 monthly cross-sectional momentum produced 75 trades and
  aggregate PnL `+$143,385.65` versus current `trend_long` `+$131,996.98`,
  winning `mid_weak` and `old_thin`, but failed the drawdown guard with
  `29.4481%` max drawdown in `late_strong` and lost that window badly
  (`+$16,166.91` versus `trend_long` `+$42,082.01`).
- Decision: do not replace or benchmark-promote core `trend_long` with vanilla
  12-1 monthly momentum on these windows. Do not retune lookback, skip month,
  monthly cadence, top-N, hold, liquidity, universe, costs, notional, or
  tie-breaks on the same OHLCV surface.

Purpose:

- Challenge `trend_long` against standard cross-sectional momentum rather than
  another local trend threshold.

Implementable shape:

- Exclude the most recent month from the momentum measurement when the data
  shape supports it.
- Optional later variant: residual momentum versus sector or broad-market
  beta, but only as a separate predeclared gate shape.

Avoid:

- Blending it immediately into existing trend rankers.
- Treating one strong recent window as acceptance.

### 3. PEAD / Revision Event Sleeve

Historical boundary:

- This lane is not an untested blank slate. Ginger already has accepted
  default-off post-earnings and revision helpers, including the shared
  post-earnings underpriced drift adapter and revision surprise low-extension
  sleeve referenced in `docs/production_backtest_parity_matrix.md`.
- There are also many rejected PEAD/revision retunes and support overlays in
  the June experiment history. A new experiment here needs a genuinely new
  PIT event-quality field, materially more closed forward replacement-value
  rows, or a separate activation/envelope test. Do not reserve a generic
  "PEAD baseline" ID just because this plan mentions the family.

Purpose:

- Add a short-to-medium horizon event-driven sleeve that does not depend on
  generic trend continuation.

Implementable shape:

- Point-in-time earnings surprise or analyst-revision event rows.
- Fixed holding window and after-cost replacement value versus displaced
  candidates.
- Default-off paper first unless the data surface is already shared and mature.

Avoid:

- Same-day leakage around earnings availability.
- Free-form LLM "earnings sounded good" hard decisions.

### 4. Low-Volatility / Quality Admission Overlay

Experiment:

- `exp-20260708-026`
- Status: `observed_only_rejected_low_vol_quality_core_admission_overlay`.
- Runner: `quant/experiments/exp_20260708_026_low_vol_quality_core_admission_overlay.py`
- Result: the fixed high-volatility/high-beta no-entry diagnostic blocked
  8 of 61 saved core trades, but the blocked cohort had positive aggregate
  PnL (`+$40,315.44`). The additive counterfactual reduced total PnL from
  `$234,850.99` to `$194,535.55`, and zero canonical windows improved.
- Decision: do not promote a broad rule that blocks core trades solely because
  both 60-session realized volatility and 60-session SPY beta rank in the
  same-day top quintile. Do not retune the lookback, percentile threshold,
  beta/vol rank formula, universe exclusions, strategy scope, or window slices
  on the same saved-trade/OHLCV surface.

Purpose:

- Test whether crowded momentum entries should be blocked or downweighted when
  realized volatility, beta, or drawdown structure says the trade is poor
  quality.

Implementable shape:

- Admission or risk-quality gate with production-known volatility/beta fields.
- Compare no-entry versus current scalar behavior.

Avoid:

- Retuning stop width or ATR multipliers on the same trades.
- Calling it accepted if it only reduces drawdown by deleting too many trades.

### 5. Short-Cycle Mean-Reversion Or Pairs Sleeve

Experiment:

- `exp-20260708-023`
- Status: `rejected_chop_regime_mean_reversion_sleeve`.
- Runner: `quant/experiments/exp_20260708_023_chop_regime_mean_reversion_sleeve.py`
- Result: chop-day reversion closed 41 trades with only `+$82.13` PnL; the
  mirror trade did not clear the predeclared frozen-window bar.
- Decision: do not retune RSI threshold, SMA windows, hold days, lot caps,
  notional, or the same chop-regime axis on these frozen windows. Reopen needs
  forward chop-day rows via a daily default-off snapshot or a different
  unsaturated short-cycle entry family.

Purpose:

- Explore a genuinely different short-horizon source so the system is not only
  long breakout/trend.

Implementable shape:

- Separate default-off sleeve with its own universe, spread/z-score rule,
  borrow/liquidity checks if short exposure is used, and turnover/cost model.
- Initially evaluate replacement value and correlation to core returns.

Avoid:

- Letting a short-cycle sleeve consume core slots before it has paper evidence.
- Ignoring slippage and borrow friction.

## Anti-Repeat Rules For This Plan

- Do not spend experiment IDs on small edits to breakout/trend thresholds,
  ATR stops, DTE buckets, or scalar response curves unless a new evidence axis
  is documented.
- Do not use ticker blacklists as the first admission gate. They are likely to
  overfit historical losers and are hard to generalize.
- Do not use canonical window labels as production rules. They can diagnose
  weak regimes but cannot be entry-time features.
- Do not claim a read-only trade-dropping diagnostic as accepted strategy
  behavior. It ignores slot replacement, cash drag, and live order semantics.
- Every promotion candidate must state whether it is `entry`, `ranking`,
  `risk_allocation`, `capital_allocation`, `exit`, `candidate_pool`, or
  `LLM_event_scoring`.

## Handoff Checklist

Before another agent continues this plan, they should check:

1. Whether the first severe-haircut admission diagnostic has an experiment ID,
   artifact, and closeout.
2. Whether its result was positive enough to justify a shared helper. If not,
   move to the external baseline queue rather than retuning the same rule.
3. Whether a proposed next experiment has a valid new evidence axis under
   `AGENTS.md` saturation governance.
4. Whether any implementation would affect production/live orders. If yes,
   include the live-realistic execution envelope before running Gate 4.

## Source Notes

External strategy families discussed on 2026-07-08:

- Donchian/Turtle-style channel breakout.
- Cross-sectional momentum, including 12-1 and residual momentum variants.
- Time-series momentum / trend following.
- Post-earnings-announcement drift and revision drift.
- Low-volatility / Betting Against Beta style quality effects.
- Pairs/stat-arb and short-cycle mean reversion.

These sources are research priors only. Local acceptance depends on Ginger's
canonical artifacts and experiment protocol.
