# Experiments Directory

Top-level `experiments/` is the durable experiment workspace. It holds
lightweight records and manual research packages. Keep `docs/` for protocols,
state summaries, and format documentation.

## Layout

- `logs/`: one structured JSON closeout per completed, rejected, or observed
  experiment. Use `logs/<experiment_id>.json`.
- `tickets/`: compact machine-readable status summaries used for review and
  automation. Use `tickets/<experiment_id>.json`.
- `artifacts/`: small human-readable notes, markdown summaries, and lightweight
  sidecar artifacts that are useful next to the logs.
- `research/`: hand-run research packages with configs, notes, CSVs, and
  result files.

Do not add ad hoc `experiments/<experiment_id>/` directories for generated
experiment output. If an experiment needs multiple generated files, keep small
durable notes in `artifacts/` and put bulky replay outputs under
`data/experiments/<experiment_id>/`.

## Storage Rules

- Large result sets and bulky JSON replay artifacts belong in
  `data/experiments/<experiment_id>/`.
- Executable experiment scripts belong in `quant/experiments/`.
- Long-lived protocols and summaries belong in `docs/`.
- Temporary lock files are ignored by `.gitignore` and should not be treated as
  experiment records.

## Closeout Checklist

When closing an experiment, make sure the durable trail can be found by id:

1. Append the structured result to `docs/experiment_log.jsonl`.
2. Add or update `logs/<experiment_id>.json` when a per-experiment JSON closeout
   exists.
3. Add or update `tickets/<experiment_id>.json` when the run needs automation
   or review status.
4. Put small markdown summaries in `artifacts/`.
5. Put large generated outputs in `data/experiments/<experiment_id>/` and point
   any `artifact` field there.
