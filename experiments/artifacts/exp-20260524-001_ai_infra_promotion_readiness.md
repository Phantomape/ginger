# exp-20260524-001 - AI Infra Promotion Readiness Surface

## Decision

Accepted as `measurement_repair`. This does not change entries, exits,
filters, ranking, sizing, risk allocation, LLM behavior, or production orders.

## AGENTS Gate Questions

1. Alpha hypothesis: `AI_INFRA_AGGRESSIVE` is the highest-priority
production-relevant alpha lane, but additional pilot capital or promotion
should only occur after positive closed replacement-value evidence.
2. Prior experiments: recent core allocation retunes
`exp-20260523-013`, `exp-20260523-014`, and `exp-20260523-015` failed Gate 4.
Pilot expansion is separately constrained by
`docs/universe_promotion_protocol.md`.
3. Single causal variable: no strategy variable changed. The only change is a
read-only promotion-readiness diagnostic inside the existing AI infra
attribution surface.
4. Acceptance standard: measurement repair passes if it exposes the current
promotion blockers, keeps order behavior unchanged, and passes focused pilot
sleeve tests.
5. Reproducibility: the current live ledger has four
`AI_INFRA_AGGRESSIVE` decision snapshots and zero closed outcome records when
summarized by sleeve; the surface probe reports the corresponding blockers.

## Change

`quant/pilot_sleeve.py` now adds
`ai_infra_aggressive_attribution.promotion_readiness`, covering the
`pilot -> limited_production` checks from
`docs/universe_promotion_protocol.md`:

- closed pilot outcomes
- direct pilot PnL
- replacement value
- risk-adjusted replacement value
- single-trade profit concentration
- sleeve drawdown
- theme-beta explanation
- event-risk clearance
- live slippage

The current production evidence remains blocked because there are no closed
pilot outcomes for the AI infra sleeve.

## Verification

- `py_compile` passed for `quant/pilot_sleeve.py` and
  `quant/test_pilot_sleeve.py`
- `pytest quant/test_pilot_sleeve.py quant/test_backtester_pilot_sleeve.py`
  passed: 20 tests
- Surface probe: `decision_snapshots=4`, `outcome_records=0`, and all
  promotion-readiness requirements are blocked or pending

## Production Status

No `run.py` change. No order-generation change. The daily attribution surface
now makes the pilot promotion blocker explicit before any future alpha attempt
to increase slots, risk, or universe status.
