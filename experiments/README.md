# Experiments Directory

Top-level `experiments/` is for manual or exploratory research workspaces that
are not part of the production strategy path.

## Subdirectories

- `research/`: hand-run research packages with configs, notes, CSVs, and
  result files.

The other experiment stores are separate on purpose:

- `quant/experiments/`: executable experiment scripts.
- `data/experiments/`: heavy JSON/CSV outputs from those scripts.
- `docs/experiments/logs/`: structured experiment records.
- `docs/experiments/tickets/`: short status/ticket summaries.
- `docs/experiments/artifacts/`: small human-readable artifacts that belong
  with experiment documentation.

Most automation-generated experiments will not create a top-level folder here;
they should use `quant/experiments`, `data/experiments`, and
`docs/experiments` instead.
