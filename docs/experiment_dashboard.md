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
  identity sources, not only `docs/experiment_registry.json`.
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

The dashboard supports text search, status filtering, source filtering, and an
`anomalies only` toggle.

## Dashboard Views

The UI borrows four Hugging Face Hub patterns and keeps them local/read-only:

- `Cards`: compact experiment cards with identity, status, family, changed
  variable, metrics, sources, anomalies, and related files.
- `Leaderboards`: EV/PnL delta leaderboards plus rejected-family counts, similar
  to benchmark result aggregation.
- `Dataset View`: column coverage and top-value distributions for the experiment
  table, similar to a dataset viewer for `docs/experiment_log.jsonl` and ticket
  metadata.
- `Collections`: curated slices such as accepted stack, default-off sleeves,
  measurement repair, active/proposed queue, and identity repair queue.

These views are generated from the same index and are not trading signals.

## Regenerate After Changes

The dashboard is static. Re-run:

```powershell
.\.venv\Scripts\python.exe -B scripts\build_experiment_dashboard.py
```

after creating, judging, or logging experiments.
