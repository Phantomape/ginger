# exp-20260727-006 — Two-tier PIT research admission

## Decision

Accepted as a measurement/governance repair. Strategy logic, orders, ranking,
sizing, exits, and the canonical Gate metrics are unchanged.

## Policy bundle tested

| PIT tier | Discovery use | Historical replay | Maximum authority |
| --- | --- | --- | --- |
| `not_pit` | Diagnostic only | No alpha evidence | Reject |
| `research_pit` | Candidate generation, D0-D3, independent debate | Hash-bound `private_replay_scout` | `observed_only`; no paper/live |
| `canonical_pit` | All discovery stages | Canonical Gate protocol | Existing accepted/default-off/live ladder |

`research_pit` is a temporal-use classification, not a new evidence grade. A
newly registered historical source remains `evidence_grade=lead`. Source PIT
identity requires authorized timestamped history, an explicit
`known_future_leakage=false` attestation, a stated vintage caveat, and a frozen
local artifact hash. Candidate overlap is checked at D0/admission rather than
used to relabel the source itself.

Known future leakage remains invalid. Current survivor membership joined
backward, restated/current values masquerading as historical vintages,
non-effective current mappings, and outcome-selected rules are `not_pit`.

## Machine enforcement

- EvidenceSurface permits `research_pit` only as a non-gate-ready lead.
- D0 rejects an explicit known-future-leakage surface and parks zero-overlap
  candidate replays.
- The debate layer can issue `admission_class=research_replay` only for an
  outcome-blind selected lead whose referenced surfaces are all
  `research_pit`/`canonical_pit`, with at least one research surface.
- The request is bound to panel, debate, registry, source readiness, and the
  actual local artifact SHA-256; the proposal must use
  `change_type=private_replay_scout`.
- Reservation, claim, close, audit, and self-registration revalidate the
  admission. Research tickets can close only `observed_only` or `rejected`.
- The full-stack verdict maps a positive research-PIT replay to
  `research_only`, never `accepted_paper_pending_forward` or `live_eligible`.
- The maintained full-stack template requires an explicit PIT authority block;
  legacy callers may omit it only for historical API compatibility, while the
  registry remains the final authority and recursively rejects nested
  paper/live verdicts on research tickets.
- Raw mapping inputs are normalized through the EvidenceSurface contract before
  D0 or panel freezing, so callers cannot bypass the research grade ceiling.
- Self-registered closeout cannot rewrite the original lane, creation clock, or
  admission anchor, and Gate-4/live flags must be literal booleans.
- Existing canonical requests and legacy full-stack callers remain compatible.

## Verification

- Alpha contract/engine/mechanism/digest tests: `121 passed`.
- Debate/registry/self-registration/full-stack tests: `139 passed`.
- Python compilation: passed for all changed Python modules.
- Scoped `git diff --check`: passed (line-ending notices only).
- `scripts/experiment.py audit --lean-strict`: `lean_quality_passed=true`,
  `lean_strict_passed=true`.
- A separate adversarial re-review found no remaining promotion-authority
  blocker after the bypass regression tests were added.
- Before/after canonical result artifact is intentionally identical; expected
  EV and PnL delta are zero because this ticket changes research authority, not
  trading behavior.

## Reproduction

```powershell
.\.venv\Scripts\python.exe -B -m pytest quant\test_alpha_search_contract.py quant\test_alpha_search_engine.py quant\test_alpha_mechanism_generator.py scripts\test_build_research_digest.py -q
.\.venv\Scripts\python.exe -B -m pytest quant\test_alpha_debate.py quant\test_experiment_registry.py quant\test_persist_self_registered_result.py quant\test_full_stack_candidate_pool.py -q
.\.venv\Scripts\python.exe -B scripts\experiment.py audit --lean-strict
```
