# Alpha Optimization Playbook

This document is a durable decision map for alpha iteration. It is not an
experiment log, a daily status page, or an inventory of every accepted helper.
It should answer four questions:

1. What mechanism-level lessons should guide the next experiment?
2. What are the next one to three high-value research directions?
3. Which families are frozen, and what genuinely new evidence can reopen them?
4. What must be true before a paper result can influence production?

The default north-star metric is:

```text
expected_value_score = strategy_total_return_pct * abs(sharpe_daily)
```

Return determines the sign; absolute daily Sharpe scales the magnitude. Risk,
sample size, survival, concentration, cash feasibility, and benchmark-relative
performance remain hard constraints. Exact Gate 1-4 definitions live in
`docs/backtesting.md`.

## Document Contract

Use each repository surface for one time scale of memory:

| Information | Single source of truth |
|---|---|
| Exact trial hypothesis, metrics, artifacts, hashes, decision, and reflection | `experiments/logs/*.json`, `experiments/tickets/*.json`, and `docs/experiment_log.jsonl` |
| Compact current state and recent work | `docs/alpha_context_pack.md` and `docs/current_state_snapshot.md` |
| Machine-enforced frozen families and reopen text | `docs/frozen_families.jsonl` |
| Recurring mechanism lessons with supporting history | `docs/lessons/*.md` |
| Baselines, canonical windows, metrics, and Gates | `docs/backtesting.md` |
| Experiment lifecycle and novelty rules | `docs/agent_experiment_protocol.md` |
| Production/backtest behavior contracts | `docs/production_backtest_parity.md` and `docs/production_backtest_parity_matrix.md` |
| External research mapped to replayable fields | `docs/alpha_external_research_map.md` |

If a statement needs an exact run date, PnL, EV delta, row count, artifact hash,
or single-trial disposition, it normally belongs in the experiment record, not
here. The only exception is a quantitative parked-surface condition whose loss
would allow an invalid reopen; those exceptions are listed below.

Default work is `alpha_search`. A `measurement_repair` may take priority only
when a missing or incorrect measurement blocks trustworthy alpha evaluation or
production parity. Strategy behavior changes still require the full protocol;
this file never substitutes for a reserved experiment, Gate 1-4 evidence, or a
closeout record.

## Durable Alpha Priors

1. **Candidate formation usually has more remaining edge than another hard
   filter.** Raw Companyfacts ratio and tag enumeration is saturated. Prefer
   sources that create candidates or change ranking through real economic
   information. Representative evidence: `exp-20260528-017`.

2. **The retained product is a shared, default-off paper policy.** A private
   replay can scout uncertain data shape, but it cannot establish accepted
   alpha until the same helper and policy are visible to historical replay and
   daily paper production. Representative evidence: `exp-20260611-007`.

3. **Relations help only when the relation is itself informative.** Peer,
   customer, supplier, theme, or cross-source confirmation must add information
   beyond issuer popularity and must survive allocator and replacement-value
   accounting. Representative evidence: `exp-20260611-005`.

4. **Cash feasibility is part of alpha, not a reporting adjustment.** Candidate
   conflicts, incumbent displacement, buying-power scarcity, and order timing
   can reverse an apparently attractive signal. The cash-feasible anchor in
   `docs/backtesting.md` is the only valid Gate-1 comparator. Representative
   evidence: `exp-20260715-010`.

5. **Risk reduction is not automatically value creation.** Covariance filters,
   quarantine, delayed ownership/venue/short-interest exclusions, rotation, and
   notional cuts may suppress winners. Judge them on EV, PnL, opportunity cost,
   executable touch count, and tail behavior together. Representative evidence:
   `exp-20260720-003`.

6. **Market state is sleeve-specific.** A state feature may explain one
   candidate family while damaging another; portfolio-wide chop or regime
   tilts are therefore frozen by default. Representative evidence:
   `exp-20260622-017`.

7. **Forward sample size means independent economic decisions.** Horizon rows,
   comparators, repeated observations, and same-issuer duplicates do not create
   independent evidence. Mature ledgers need settled cash, SPY, and QQQ
   replacement values. Representative evidence: `exp-20260714-010`.

8. **A new source must pass a source contract before price evaluation.** Require
   an immutable vintage or archive, publication clock, point-in-time issuer
   mapping, legal/attribution provenance, and outcome-blind density and
   concentration checks. A derived join of already-used sources is not itself a
   new data source. Otherwise the right result is an observer or identity
   repair, not alpha. Representative evidence: `exp-20260720-002`.

9. **Prove gross economic mapping before building elaborate plumbing.** If a
   simple, causal response has no gross edge or no candidate intersection,
   execution detail and response retuning will not rescue the source.
   Representative evidence: `exp-20260717-004`.

10. **LLMs are bounded semantic infrastructure, not trading authority.** Their
    inputs, chronology, taxonomy, abstentions, versions, outputs, and fallbacks
    must be replayable. Use them to extract or classify evidence, then apply a
    deterministic policy. Representative evidence: `exp-20260417-004`.

11. **A surface reopens only on the condition that made the old conclusion
    non-identifying.** More total rows, a new threshold, or a new response does
    not override a stricter subtype, density, touch, or publication-time
    condition. Representative evidence: `exp-20260716-007`.

12. **Simplification also needs holdout evidence.** An in-sample near-zero
    ablation can still remove a protective interaction out of sample. Prefer
    independent windows and live-realistic counterfactuals before deleting
    policy. Representative evidence: `exp-20260717-006`.

## Current Direction

- Treat the cash-feasible baseline named in `docs/backtesting.md` as the
  champion. Older leverage-tolerant or pre-repair results are historical
  evidence only.
- The strongest recurring opportunity is production-visible, default-off
  candidate or relation evidence with settled replacement values, not another
  issuer-level exclusion rule.
- Accepted paper infrastructure is not live-ready alpha. Mature it with forward
  decisions, candidate-touch evidence, cash conflict accounting, realistic
  execution envelopes, and parity before considering activation.
- New official or public sources start with source-contract and density
  preflight. Do not spend an experiment ID merely to discover that the archive,
  issuer map, permission, candidate overlap, or legal new-evidence axis is
  absent.
- Stale or low-touch risk surfaces should begin as context, attribution, or a
  default-off admission audit; hard exclusions need enough executable touches
  and replacement value to prove they are not deleting scarce winners.
- Global regime overlays, generic cash rotation, and threshold retuning on
  rejected surfaces remain parked. State and relation work must be specific to
  a sleeve and must explain a causal change in replacement value.

This section is replaced when priorities change; dated status paragraphs are
never appended to it. The generated context pack is the current accepted-helper
and recent-experiment inventory.

## Active Research Queue

### Lane 1: Mature accepted default-off evidence

- **Money hypothesis:** some accepted candidate, relation, or source adapters
  contain incremental information that survives cash and benchmark replacement
  once evaluated on independent forward decisions.
- **Evidence unit:** one outcome-blind decision per issuer and decision clock,
  with policy/source version, displaced alternative, costs, closed H5/H10/H20
  outcomes, cash/SPY/QQQ replacement values, and concentration metadata.
- **Next work:** choose the highest-density accepted adapter from the current
  state snapshot and append settled forward evidence under its frozen policy.
- **Accept:** aggregate and window evidence remains useful after realistic cash,
  cost, concentration, and execution constraints; shared historical/daily parity
  holds.
- **Stop:** rows are duplicate decisions, candidate intersections stay absent,
  or the fixed policy loses replacement value. Do not retune the same surface.

### Lane 2: Add real point-in-time economic information

- **Money hypothesis:** offering/dilution/refinancing state, borrow
  availability/utilization, customer/supplier/segment economics, and revision
  trajectories can change candidate quality more directly than static labels or
  raw ratios.
- **Preflight:** immutable or hash-bound history, publication clock,
  effective-dated issuer map, permission/attribution, adequate density, and
  acceptable issuer/source concentration.
- **Next work:** prefer one source with a complete contract and a shared
  default-off helper; test a single causal candidate or ranking response.
- **Accept:** the field creates real candidate touches or comparisons and beats
  the cash-feasible baseline without concentration or parity failure.
- **Stop:** the field is reconstructed from today's membership, is merely a new
  code/tag on a saturated source, or has no outcome-blind candidate overlap.

### Lane 3: Explain sleeve-specific tail states and dynamic relations

- **Money hypothesis:** a full-fidelity tail state or time-varying economic
  relation may identify when a specific sleeve's candidate has better
  replacement value.
- **Preflight:** define the sleeve, causal state/edge, decision clock, coverage,
  and counterfactual before reading outcomes. Static sector, peer, theme, or
  portfolio-wide regime labels do not qualify.
- **Next work:** use forward or truly point-in-time relation/state evidence and
  evaluate it as a candidate, ranking, or bounded allocation policy.
- **Accept:** improvement is not a single-window or single-name artifact and
  survives cash, SPY, QQQ, costs, and tail-risk checks.
- **Stop:** the work collapses into another global tilt, threshold sweep, static
  relation label, or observed-only slice without enough independent decisions.

## Candidate Decision Checklist

Before reserving an alpha experiment, answer all of the following:

1. What economic mechanism should create profit, and which decision surface
   changes: entry, exit, ranking, capital/risk allocation, LLM event scoring, or
   candidate pool?
2. Is the evidence axis genuinely new under `AGENTS.md` and the novelty gate?
3. Does an open ticket already own this hypothesis?
4. Is the source point-in-time, replayable, permitted, mapped, dense, and not
   dominated by one issuer or one query?
5. Does the proposed signal touch real candidates or cash conflicts before any
   price replay?
6. Is the policy shared, default-off, parity-testable, and live-realistic?
7. What exact condition will accept, reject, park, or reopen the family?

If questions 2-5 cannot be answered, run a cheap preflight or change direction;
do not reserve a speculative plumbing ticket.

## Frozen Zones

The per-experiment anti-repeat source of truth is
`docs/frozen_families.jsonl`. Consult the originating experiment record when its
reopen text is missing or truncated; do not copy the whole record here.

A frozen family may reopen only with at least one allowed evidence axis:

- a genuinely new data source;
- a genuinely new gate shape or decision surface;
- materially more settled forward decisions meeting the recorded quantitative
  condition; or
- an unprecedented field on an unsaturated source.

New thresholds, subtype or form-code enumeration, issuer slices, response
functions, holding periods, refreshed same-day rows, or restated mechanisms are
not new evidence. The following table is a mechanism index, not a list of every
trial:

| Family | Frozen pattern | Valid way forward |
|---|---|---|
| OHLCV pattern relabeling | Repeated breakout, chop, drawdown, recovery, volatility, or chart-shape thresholds on the same bars | A new state source, a different decision surface, or materially new settled forward decisions |
| Universe and ranking | Sector/bucket/top-k reshuffles, static quality scores, and issuer exclusions that do not create information | A candidate-generating source or real replacement comparisons under a causal ranking field |
| Allocator and cash arbitration | Scalar/cap sweeps, generic incumbent eviction, cash rotation, and conflict ranking on the same candidates | A new allocator mechanism or enough new actual cash-conflict decisions |
| Exit, lifecycle, and risk | Stop/target/trailing/hold retunes and broad risk overlays on the same cohort | The exact lifecycle cohort condition below, or a new causal exit state |
| Companyfacts and XBRL | Raw ratio, tag, item, filing-quarter, and field enumeration | New point-in-time economic content, not another derivation from the same facts |
| SEC form, item, and text | Form/item/event subtype loops and fixed text-response templates | A new semantic source or gate plus independent settled decisions |
| Ownership and insider flow | Static holder, Form 4, 13F, concentration, and insider threshold variants | Timely point-in-time ownership change with a new causal response and adequate decisions |
| Borrow, options, flow, and fills | CTB/short-volume/options/fill threshold retunes after no overlap or no edge | New availability/utilization/locate fields, a new gate, or registry-qualified forward candidate touches |
| Relation and peer propagation | Static peer/theme/entity maps, co-mentions, and fixed neighbor propagation | Dynamic economic relations with point-in-time provenance and replacement-value evidence |
| Macro, regime, and calendar | One-indicator-at-a-time relief, global chop tilts, calendar relabeling, and fixed response loops | Sleeve-specific causal state or a genuinely different source/gate |
| News, attention, and prediction | Headline/query/popularity threshold sweeps and generic attention acceleration | Corrected forward collection or new semantic/economic content meeting the registry condition |
| Official/public source admission | One source per ID before archive, permission, issuer map, density, or concentration is known | Batch source-contract preflight, then reserve only a qualified source |
| Forward readiness and measurement plumbing | Repeated joins, refreshes, readiness audits, and manual ledger materialization without gate-ready rows | Automated routine wiring, the recorded settled-row threshold, or a new surface |

### Quantitative Parked-Surface Exceptions

These five conditions remain here because the current structured registry does
not yet encode them completely. Remove each row once the registry carries and
validates the same condition.

| Surface | Minimum evidence required before reopen |
|---|---|
| CISA KEV | Immutable `old_thin` bars for at least 2 independent mapped issuer-weeks, plus an explicit short-borrow and execution envelope |
| Exit lifecycle | A fixed post-2026-06-30 cohort with at least 101 settled entries, including at least 20 advisory exits and 8 hard-stop exits |
| FIRST EPSS | Source preflight in every canonical window: at least 20 issuer-weeks, 10 tickers, and top-1 share <=30%; performance reopen: at least 30 prospective PIT-correct settled events across 10 tickers under a frozen shared observer |
| PyPI release acceleration | An immutable distribution archive, bilateral effective-dated package-to-issuer evidence, and in every window at least 20 issuer-weeks, 10 tickers, and top-1 share <=30% |
| GH Archive development acceleration | Authorized audit-grade history, a hash-bound gap-free manifest, an effective-dated ownership map, the same per-window `20 / 10 / <=30%` density bars, and at least 10 actual cash-conflict comparisons |

All other source-specific counts, dates, and reopen clauses belong in the
registry and originating experiment record, including ORTEX, Hacker News,
prediction-market, entity/theme, short-volume, NVD, DrugsFDA, and USAspending
surfaces.

## Update Discipline

A statement may enter this playbook only when at least one of these is true:

1. an accepted result changes a mechanism or production policy;
2. at least three independent experiments materially change a durable prior;
3. a family becomes formally frozen and gains a valid new-evidence rule; or
4. the next one to three research lanes change.

Everything else closes into the experiment log, a mechanism lesson, or a
generated current-state document. A single rejected experiment normally does
not earn a paragraph here.

Edits use replacement semantics. The key is the prior number, queue lane,
frozen-family name, or quantitative-exception surface. Replace the keyed
statement and delete superseded wording; never append a dated readout or status
chronicle. Experiment runners and closeout scripts must not write this file.
`scripts/alpha_playbook_guard.py` is the single machine validator used by
pytest, `experiment.py audit --lean-strict`, pre-commit, and the repository
workflow. The commit guard validates Git-index blobs and fails closed, so
partial staging cannot hide or invent a violation.

Hard content budget:

- at most 450 lines;
- at most 12 durable priors;
- at most 3 active research lanes;
- at most 13 frozen-family summaries;
- at most 5 quantitative exceptions;
- at most one representative experiment per prior and 24 experiment-ID
  references in the whole file.

Review this map after a real priority/prior change or in a periodic synthesis
pass, not after every closeout. Validate changes with:

```powershell
.\.venv\Scripts\python.exe -m pytest quant\test_alpha_playbook_contract.py
.\.venv\Scripts\python.exe -B scripts\experiment.py audit --lean-strict
```

## Why the Old Version Became a Chronicle

The old file combined four different clocks: durable lessons, current state,
exact experiment outcomes, and anti-repeat safeguards. High experiment
throughput then made appending the latest facts the locally safest action:
deleting anything felt like losing evidence. Later, generated context files and
the frozen-family registry took over much of that job, but the duplicated prose
was never retired. The file also had no admission threshold, replacement key,
size budget, or lint guard, and some historical runners wrote to it directly.

The failure was therefore structural, not editorial: experiment facts were made
hard to forget, while durable knowledge was never required to pass a
consolidation and forgetting gate. The document contract, replacement rules,
machine registry, quantitative exceptions, and static budget above are the
guardrails against recurrence.

<!-- PLAYBOOK_END -->
