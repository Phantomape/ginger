# Meta Learning State

This document is the contract for **pre-run prediction recording** and the
**diagnostic rules** for reading calibration output. It is not a strategy log,
not a trade signal, and not a replacement for `docs/current_state_snapshot.md`,
`docs/alpha-optimization-playbook.md`, or `docs/experiment_log.jsonl`.

Revision 2026-07-21 (exp-20260721-004): the previous version of this file
prescribed a "weekly consolidation" ritual over a report that had never been
generated. The ritual is removed. What remains is (a) the recording discipline,
which demonstrably works (100% ticket prediction coverage since 2026-07-14),
and (b) explicit guardrails for interpreting calibration aggregates, which the
first materialized report shows are necessary.

## 1. What must be recorded (unchanged, enforced)

Every `experiment.py new` reservation carries a `prediction` block:
`success_probability`, expected EV/PnL delta when estimable,
`main_failure_modes`, and `confidence_reason`. The value of this discipline is
mostly **local**: it forces the falsifier to be written before the result is
known and makes closeout reflections auditable. That value exists even if the
aggregates below are never read.

- Treat missing predictions as a process gap, not as neutral evidence.
- Do not backfill predictions for already-closed legacy experiments unless the
  repository proves the estimate predates the result.
- Use `scripts/experiment.py audit` to separate `legacy_pre_enforcement_*`
  gaps from `post_enforcement_*` gaps.

## 2. Generating the report

```powershell
.\.venv\Scripts\python.exe -B quant\experiment_history.py --output data\experiment_history_report_latest.json
```

First materialized 2026-07-21: 973 scored predictions, coverage 39.15%,
avg Brier 0.0710, direction counts 926 calibrated / 14 overconfident /
33 underconfident, spread across 476 families (~2 predictions per family).

## 3. Guardrails for reading `prediction_calibration`

These exist because the naive reading of the numbers above is wrong.

1. **The aggregate Brier is not evidence of good judgement.** With a heavily
   imbalanced base rate (accept ~0-25% for alpha, ~100% for measurement
   repairs), predicting the base rate with high confidence scores near-perfect
   Brier while carrying zero information. 0.0710 is dominated by easy calls.
   Judge skill only **relative to the family base rate** (a Brier skill score
   against the family's historical accept rate), never by raw Brier.
2. **Minimum sample floor.** Draw no family-level conclusion from fewer than
   ~20 scored post-enforcement predictions in that family, and no
   repo-level trend conclusion from fewer than ~50 new scored closes since the
   last reading. At ~2 predictions per family, `by_family` is currently noise;
   only `worst_brier_examples` (individual post-mortems) is readable today.
3. **The scoring target is non-stationary.** Predictions target Gate-4
   acceptance, but Gate 4 is a champion challenge: the ratchet raises the bar
   with every accept, and measurement repairs can lower the anchor (2026-07-15
   cash re-baseline, EV 12.27 -> 6.21). A "wrong" prediction may record a moved
   goalpost, not a world-model error. Before treating an overconfidence cluster
   as a judgement failure, check whether the anchor moved inside the cluster's
   window.
4. **Known gaming vector.** Agents that read this file are the agents being
   scored. Predicting rejection for every alpha ticket optimizes the tracked
   metric. If aggregate Brier keeps improving while accepted-alpha count stays
   flat, suspect herding first, insight second.

## 4. What calibration output may and may not drive

- Overconfidence clusters (after guardrails 1-3) justify **requiring stronger
  new evidence** for that family - the same lever as saturation governance,
  which usually fires first (12 trials / <=5% accept). If the saturation guard
  already froze the family, calibration adds nothing; do not cite both.
- Underconfidence clusters are prompts to audit the world model and the
  confidence habit, not automatic next-strategy priorities.
- Individual `worst_brier_examples` are the highest-value output: read them as
  post-mortems of judgement errors.
- Never use calibration scores for live ranking, sizing, filtering, or orders.
- Never use historical winner scores or accepted-family frequency to choose the
  next hypothesis family. History is a veto/anti-repeat surface, not a proposal
  distribution (see `docs/alpha_search_architecture.md` §1).

## 5. Cadence

There is no scheduled ritual. Regenerate and read the report when either
trigger fires:

- ~50 new scored closes since the last reading (check
  `records_with_prediction` against the number recorded in §2), or
- a specific family is suspected of systematic overestimation and has enough
  samples to clear guardrail 2.

If neither trigger fires, the correct amount of time to spend on this file is
zero.
