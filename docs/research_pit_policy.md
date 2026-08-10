# Research PIT Policy

This document separates **historical research eligibility** from **promotion
eligibility**. `canonical_pit` is no longer required merely to ask whether a
timestamped historical signal has gross edge. It remains mandatory before that
edge can be accepted into a default-off paper path or any live path.

## Tiers

| Tier | Minimum contract | Allowed use | Maximum disposition |
| --- | --- | --- | --- |
| `not_pit` | Decision time is missing, or a known future revision, survivor-only universe, current mapping, future adjustment, or other oracle value enters the decision input. | Diagnostics that do not claim return evidence. | Invalid evidence / reject. |
| `research_pit` | Authorized historical rows have a usable decision timestamp; joins obey `known_at <= simulated decision time`; the frozen local dataset is hash-bound; and `known_future_leakage=false` is explicitly attested. Historical vintages or revision history may still be unverified. | Candidate generation, outcome-blind D0-D3, hash-bound promotion, and, after candidate-overlap preflight, a `private_replay_scout` historical backtest. | `observed_only` / positive lead; never accepted paper or live. |
| `canonical_pit` | The value actually available at each historical decision is reconstructable through immutable/as-published vintages or an append-only observer, with effective-dated mappings, revision policy, source contract, and replay/daily parity. | Everything above plus canonical Gate evaluation, default-off paper acceptance, activation, and live eligibility. | Existing Gate 1-5 ladder. |

`research_pit` is a temporal-use tier, not an evidence-maturity grade. A newly
registered research surface remains `evidence_grade=lead`; `observer` and
`observed_only` continue to mean forward collection maturity. A positive
research replay remains a lead until the data is upgraded to `canonical_pit`.

## Classification rules

A source with historical dates is provisionally `research_pit` only when all of
these facts are recorded:

- `research_pit_basis` names the row-level timestamp used at the simulated
  decision and states the unresolved vintage/revision limitation;
- `known_future_leakage` is explicitly `false`;
- source authorization and availability are `pass`;
- `independent_count > 0`, and `as_of` is not after the search cutoff;
- the exact downloaded artifact is locally hash-bound for reproducibility.

`candidate_overlap_count` is deliberately not part of the source's PIT identity.
It is checked by D0 and replay admission for the selected hypothesis. Zero
overlap parks that replay; it does not relabel an otherwise timestamped source.

The local artifact hash proves what was tested; it does **not** prove that the
vendor would have returned the same value historically. That stronger claim is
the canonical upgrade.

Known leakage is never “research PIT with a caveat.” Static current index
membership joined backward, restated current fundamentals presented as old
values, current issuer mappings without effective dates, or a signal selected
using its future return must be classified `not_pit` and cannot produce alpha
evidence. Future returns used only after the candidate, rule, and entry clock
are frozen are evaluation outputs, not decision-time leakage.

## Research replay admission

A research replay still requires the normal complete candidate pool and an
outcome-blind D0-D3 pass. Multi-model debate is optional and carries no
admission authority. The hash-bound request records:

```yaml
admission_class: research_replay
selected_evidence_grade: lead
result_ceiling: observed_only
paper_live_eligible: false
change_type: private_replay_scout
```

The experiment registry revalidates that request at reserve, claim, audit, and
close. A research replay cannot close as `accepted` (including any
`accepted_*` variant), cannot emit `accepted_paper_pending_forward`, and cannot
become `live_eligible`, even when its historical Gate metrics are positive.

## Canonical upgrade

A positive research lead may be upgraded only by supplying the missing
as-known evidence: immutable vintages or an append-only forward ledger,
effective-dated mappings, revision semantics, shared replay/daily behavior, and
the normal execution/parity contract. The upgrade is a new evidence axis; it
does not erase the original trial from multiple-testing accounting.

Closed historical decisions are not relabeled. New unqualified uses of “PIT”
default to research-only unless the registered surface satisfies the explicit
`canonical_pit` invariants.
