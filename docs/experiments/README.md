# Experiment Documentation

This directory keeps the durable, human-readable side of experiment tracking.

- `logs/`: one structured JSON record per completed or observed experiment.
- `tickets/`: compact status summaries for automation and review.
- `artifacts/`: small markdown or JSON artifacts that are useful to read next
  to the logs.

Large result sets belong in `data/experiments/<experiment_id>/`. Executable
experiment scripts belong in `quant/experiments/`. Manual research workspaces
belong in the top-level `experiments/` directory.
