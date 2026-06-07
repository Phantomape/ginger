# Meta Learning State

This document is the weekly consolidation surface for research judgement
quality. It is not a strategy log, not a trade signal, and not a replacement
for `docs/current_state_snapshot.md`, `docs/alpha-optimization-playbook.md`, or
`docs/experiment_log.jsonl`.

Use it to answer four questions after enough predicted experiments have closed:

1. Which predictions were most wrong?
2. Which mechanism families were repeatedly overestimated?
3. Which low-confidence experiments worked and deserve a world-model update?
4. Which next-week priorities should be raised or lowered because of
   calibration evidence?

Primary source:

```powershell
.\.venv\Scripts\python.exe quant\meta_research_engine.py --output data\meta_research_report_latest.json
```

Read `prediction_calibration` in the generated report. The key fields are:

| Field | Meaning |
| --- | --- |
| `prediction_coverage` | Share of closed accepted/rejected experiments with a pre-run prediction. |
| `avg_brier_score` | Average probability calibration error; lower is better. |
| `direction_counts.overconfident` | High-confidence predictions that failed. |
| `direction_counts.underconfident` | Low-confidence predictions that passed. |
| `by_family` | Mechanism-family calibration summary. |
| `worst_brier_examples` | Experiments most worth reviewing as judgement errors. |

Rules:

- Treat missing predictions as a process gap, not as neutral evidence.
- Do not backfill predictions for already-closed legacy experiments unless the
  repository contains a source that proves the estimate was recorded before the
  result was known.
- Use `scripts/experiment.py audit` to separate
  `legacy_pre_enforcement_*` gaps from `post_enforcement_*` gaps.
- Treat overconfidence clusters as a reason to require stronger new evidence.
- Treat underconfidence clusters as candidate mechanisms for playbook updates.
- Never use calibration scores for live ranking, sizing, filtering, or orders.
