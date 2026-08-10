# exp-20260729-004 — fail-closed candidate amendment lineage

Decision: **accepted measurement repair**.

The alpha-search contract could not represent a same-session, outcome-blind completion of missing evaluation artifacts while keeping the original candidate visible to D3. That forced an unsafe choice between hiding the parent with an incomplete history snapshot and treating every non-semantic completion as a permanent duplicate.

This repair adds one generic, depth-one lineage contract. The child embeds and hashes the canonical parent candidate; binds the parent candidate and selection scope; declares that no outcome was accessed and no experiment was reserved; and lists the exact changed paths. D3 recomputes the parent/child diff and permits only a closed set of evaluation-artifact additions. Alpha semantics—including mechanism, treatment policy, thresholds, ranking, horizon, comparator rule, notional, and execution—remain immutable.

The historical projection now authenticates the parent candidate snapshot and amendment metadata. A lineaged candidate must use a canonical history snapshot that can be rebuilt from repository ledgers; a legacy list or merely self-consistent isolated snapshot is rejected. Freeze and strict verification preserve every row in that bound snapshot. This closes a second-neighbor masking bug in which converting a verified snapshot back into the legacy list path could de-duplicate two distinct records with the same fingerprint.

Evaluation attachments are repository-contained typed files, not descriptive locators: preflight opens them, recomputes their SHA-256, enforces a closed comparator-allocation or endpoint-preflight schema, and recursively rejects outcome fields. Each document binds the exact parent ID/hash and must satisfy `attachment.data_cutoff <= preflight.data_cutoff` and `attachment.created_at <= amendment.declared_at`. Temporal contamination makes the preflight explicitly `outcome_blind=false`. The lineage declaration clock must also equal the child candidate creation clock.

Acceptance evidence:

- authenticated, depth-one, allowlisted completion passes and strictly reverifies;
- missing/hash-mismatched/scope-mismatched parents fail;
- policy rewrites, malformed attachment hashes, wrong schemas, outcome-bearing content, future-cutoff attachments, and nested or competing children fail;
- a second non-parent neighbor remains a D3 veto;
- tampering with lineage inside a frozen panel fails strict verification;
- 171 contract/history/engine/CLI/debate tests pass in the final combined run;
- a repository integration check rebuilt the canonical 1,398-record history and produced an outcome-blind parent-specific D3 pass (the overall synthetic check remained rejected on unrelated PIT/source readiness, as expected).
- an independent final review found no remaining blocking issue.

No candidate return, price outcome, strategy Gate result, live order, strategy rule, ranking, sizing, or risk setting was read or changed. `quant/run.py`, `quant/backtester.py`, the frozen Massive candidate/panel, and the active Gate-1 baseline remain byte-identical to their safety anchors.

The existing Massive v3 candidate is deliberately **not** auto-approved. Against the complete 1,397-record snapshot it still rejects at D3 on `cand-d3d84780295914d0f19a` with score `0.9688`. A fresh candidate must satisfy the new strict lineage diff, bind the missing 89-row comparator map, and pass the remaining pre-reservation review before any scout can be reserved.
