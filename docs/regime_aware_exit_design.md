# Regime-Aware Exit Design

## Goal

Test whether the current A+B-only system can improve `expected_value_score`
by changing **exit width only**, using market-state proxies that are available
on the signal day.

This experiment is intentionally narrow:

- keep entries unchanged
- keep risk sizing unchanged
- keep LLM unchanged
- keep earnings_event_long disabled
- change only the ATR target width used after entry

## Why This Is Tradable

The design avoids hindsight regime labeling.

It uses only the current day's:

- `spy_pct_from_ma`
- `qqq_pct_from_ma`
- `spy_10d_return`
- `qqq_10d_return`

These fields are observable at signal time and can be replayed historically.

## Core Idea

Instead of hard-switching between discrete regimes, compute a smooth
`regime_exit_score` from same-day index breadth/trend proxies:

`score = avg(index pct_from_200ma) + 0.5 * avg(index 10d momentum)`

Then map that score into a target width:

- weak / defensive tape -> narrower target
- balanced tape -> baseline target
- strong / risk-on tape -> wider target

Current experiment bounds:

- minimum target = `3.0 * ATR`
- maximum target = `4.5 * ATR`
- `NEUTRAL` caps the target at `3.75 * ATR`
- `BEAR` caps the target at `3.25 * ATR`

This keeps mistakes non-catastrophic:

- if we under-classify a strong tape, we mostly give up upside
- if we over-classify a weak tape, caps prevent excessive widening

## Why Entry-Day Only

This first experiment freezes the exit template at entry time.

It does **not** reclassify the market every day while the position is open.
That is deliberate:

- avoids noisy template flapping
- avoids hidden future information leakage
- keeps the causal variable clean
- makes per-trade attribution easy

If this version works, a later experiment can test slow-moving in-trade updates.

## Audit Requirements

Each closed trade should carry:

- `target_mult_used`
- `regime_exit_bucket`
- `regime_exit_score`

This lets future iterations answer:

- did weak tapes still hold winners too long?
- did strong tapes benefit from wider exits?
- was improvement concentrated in one window only?

## Acceptance Standard

The experiment only counts if it improves the north-star metric on the same
multi-window protocol used elsewhere:

- primary window
- at least 2 additional non-overlapping windows

Default success criterion:

- majority-window improvement in `expected_value_score`
- no material drawdown blowout
- no dependence on hindsight-only regime labels
