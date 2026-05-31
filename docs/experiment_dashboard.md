# Experiment Dashboard

This dashboard is a read-only local UI for inspecting experiment identity,
registry coverage, ticket/log drift, and ID allocation risk. It does not change
strategy behavior, tickets, logs, orders, rankings, sizing, or backtest results.

## Build And Open

From the repository root:

```powershell
cd D:\Github\ginger

# Rebuild the static dashboard snapshot.
.\.venv\Scripts\python.exe -B scripts\build_experiment_dashboard.py

# Serve the generated files locally.
cd experiments\dashboard
D:\Github\ginger\.venv\Scripts\python.exe -m http.server 8765 --bind 127.0.0.1
```

Then open:

```text
http://127.0.0.1:8765/index.html
```

If port `8765` is already in use, change both the server command and browser URL
to another local port, such as `8766`.

## Reserve IDs Before Work

Use a Hugging Face Hub-style reservation flow: create the experiment identity
first, then write runners, artifacts, data, and logs under the reserved ID.
Do not copy `Next exp-...` from the dashboard as an allocation lock; the
dashboard is a static snapshot.

Preferred command:

```powershell
.\.venv\Scripts\python.exe -B scripts\experiment.py new `
  --lane measurement_repair `
  --hypothesis "Make experiment identity collision-proof before artifacts are written." `
  --change-type identity_reservation `
  --single-causal-variable experiment_identity_reservation `
  --file-slug identity_reservation
```

The command writes a proposed ticket under `experiments/tickets/` and updates
`docs/experiment_registry.json` under the registry lock. It also writes an
Experiment Card under `experiments/cards/` and a Revision Manifest under
`experiments/manifests/`. The returned `experiment_id` is the only ID to use in
runner filenames, data directories, artifact names, and log rows.

To reserve a specific ID, pass `--experiment-id exp-YYYYMMDD-NNN`. The command
fails if that ID already appears anywhere the allocator scans: registry,
JSONL, tickets, per-experiment logs, cards, manifests, data experiment
directories, artifacts, or experiment runner filenames. This mirrors the useful part of
Hugging Face Hub's `create_repo(..., exist_ok=False)` behavior: names are
claimed centrally before content is pushed.

## Files

The builder writes:

```text
experiments/dashboard/index.html
experiments/dashboard/experiment_index.json
```

`index.html` contains the browser UI. `experiment_index.json` is the generated
machine-readable index behind the UI.

## What To Check

- `Next exp-...`: the next collision-safe experiment ID inferred from all known
  identity sources, not only `docs/experiment_registry.json`. This is a
  diagnostic preview, not a reservation. Use `scripts\experiment.py new`
  before starting a new runner or artifact.
- `Anomaly Rows`: actionable identity problems, such as filename/payload ID
  mismatches, divergent mirrored tickets, active/proposed work missing registry
  coverage, or registry rows missing tickets.
- `Identity Notes`: non-blocking historical coverage notes, such as archival
  JSONL/data/artifact rows that predate full registry coverage or ticket files
  mirrored through legacy path aliases.
- `experiments/tickets` and `experiments/logs` are the canonical dashboard
  paths. Legacy `docs/experiments/tickets` and `docs/experiments/logs` inputs
  are normalized to those canonical paths before source and anomaly checks, so
  duplicate path conventions do not create split-brain rows.
- Text references to experiment IDs inside another experiment's JSONL/log/ticket
  payload are indexed as `jsonl_ref`, `log_ref`, or `ticket_ref`. They are useful
  for search, but they do not count as that experiment's own JSONL row, log file,
  or ticket file.
- `split_brain_ticket_paths`: reserved for true ticket identity conflicts after
  canonical path normalization, not for the legacy docs/experiments alias.
- `missing_from_registry`: active/proposed work appears in ticket or
  per-experiment log files but not in `docs/experiment_registry.json`.
- `jsonl_without_per_experiment_log`: a JSONL record exists without a matching
  `experiments/logs/<experiment_id>.json` file. Historical JSONL-only rows are
  identity notes unless they are still open coordination records.

The dashboard supports text search, status filtering, source filtering,
sorting, density switching, clickable metadata filters, local pinning, copy-ID
actions, and an `anomalies only` toggle. These browser interactions are local
UI state; they do not write experiment state.

## Dashboard Views

The UI uses a Hugging Face Hub-style layout with an Atom One Dark-inspired
palette, compact cards, and collapsed secondary detail so the first scan favors
identity, state, changed variable, and outcome signal over raw metadata volume.
It keeps everything local/read-only:

- `Experiments`: the default card-first browser. The left rail contains
  discovery filters, sort, density, and reset controls. The center column lists
  compact experiment cards with clickable tags, Pin, and Copy actions. The
  right detail panel shows selected metrics, anomalies, notes, pinned compare
  rows, and a collapsed indexed-file list.

- `Cards`: compact experiment cards with identity, status, family, changed
  variable, metric deltas, and anomaly/note counts. Sources and files stay in
  the right-side detail panel.
- `Rejected Upside`: rejected experiments with `after_expected_value_score > 10`
  and rejected experiments with positive EV or PnL deltas. This is the primary
  place to review high-return failures that may contain reusable alpha clues but
  failed Gate 4, concentration, drawdown, evidence, or parity requirements.
- `Leaderboards`: after-EV, EV/PnL delta, rejected high-upside, and
  rejected-family tables, similar to benchmark result aggregation.
- `Dataset View`: column coverage and top-value distributions for the experiment
  table, similar to a dataset viewer for `docs/experiment_log.jsonl` and ticket
  metadata. Top-value labels are clickable and apply a search filter.
- `Collections`: curated slices such as rejected high-upside, accepted stack,
  default-off sleeves, measurement repair, active/proposed queue, and identity
  repair queue.
- `Prod Compare`: a read-only production/backtest activation view. It parses the
  current activation map, live open-position file, paper sleeve states, and pilot
  decision ledger to show which surfaces are executing, which are accumulating
  forward evidence, and how many closed forward outcomes remain before review.
  Its default view is a low-density HF-style evidence curve built from paper
  sleeve snapshots; the detailed activation map and ledger are collapsed below
  the chart. The x-axis is snapshot date from each sleeve's `snapshots.jsonl`;
  the y-axis is evidence maturity toward the sleeve's forward gate.

These views are generated from the same index and are not trading signals.

## Regenerate After Changes

The dashboard is static. Re-run:

```powershell
.\.venv\Scripts\python.exe -B scripts\build_experiment_dashboard.py
```

after creating, judging, or logging experiments.
