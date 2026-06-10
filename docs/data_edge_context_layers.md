# Data Edge / Context Layers

This document is the agent-facing index for the passive intelligence, data-edge, ranking, and attribution tools added around the context-memory roadmap.

These modules are mostly **read-only** by design. They exist to accumulate replayable market context, run attribution, and evaluate whether new data surfaces deserve future strategy experiments. Unless explicitly promoted through `docs/backtesting.md` and `docs/experiment_log.jsonl`, they must not alter entries, exits, rankings, sizing, orders, or live capital.

---

## Operating principle

The current direction is to increase alpha density by accumulating high-information context, not by adding more ad hoc strategy rules.

Preferred workflow:

1. For unknown data surfaces, produce daily context snapshots in production.
2. Keep snapshots append-only and replayable.
3. Run attribution against historical trades / backtests.
4. Promote only the small subset that proves incremental value through Gate
   1-4.
5. If the field is already PIT-safe, replayable, and easy for the daily path to
   emit, do not force a passive-only staging round. Start the first serious
   alpha test as a shared default-off paper helper with both historical replay
   and daily snapshot semantics.
6. Do not use these tools for live decisions until a separate Gate 1-4
   activation experiment accepts the change.

---

## Priority Surfaces

Default research priority remains alpha density from replayable, production-visible context rather than ad hoc rules.

Current high-value surface families:

- earnings estimate revision and expectation trajectory;
- breadth / internal market structure;
- post-earnings drift and follow-through;
- theme density, crowding, and exhaustion;
- relative strength and residual leadership surfaces.

## Code Is The Catalog

Concrete surfaces, sidecars, sleeves, attribution scripts, artifact schemas, and
meta-research tools live in code, tests, experiment artifacts, and generated
lessons. Do not duplicate module-by-module explanations here.

Use `rg` over `quant/`, `experiments/`, and `data/` when selecting a concrete
surface. Update this document only when the operating principle, promotion
boundary, or pre-experiment checklist changes.

## Agent checklist before using these tools in a strategy experiment

Before turning any context field into entry / exit / ranking / sizing logic, answer:

1. Is the field produced in production, not just in a research script?
2. Is the field saved in an append-only, replayable daily artifact?
3. Does the backtester have point-in-time access to it?
4. Has attribution shown monotonic or otherwise interpretable predictive value?
5. Does the proposed change alter only one independent causal variable?
6. Does the change pass `docs/backtesting.md` Gate 1-4?
7. Is the experiment recorded in `docs/experiment_log.jsonl` whether accepted or rejected?

If the answer to 1-4 is no, keep the surface read-only and continue accumulating history.
