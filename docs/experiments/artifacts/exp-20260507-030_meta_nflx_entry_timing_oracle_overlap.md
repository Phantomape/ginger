# exp-20260507-030 META/NFLX Entry Timing Oracle Overlap

Decision: `observed_only_underpowered`
Overlap status: `underpowered_oracle_overlap`

## Read

The top daily timing tag has insufficient META/NFLX candidate overlap; treat it as an oracle feature to monitor, not a replayable strategy.

## Candidate Overlap

| Tag | Seed candidates | Seed entered | META candidates | NFLX candidates | Platform candidates |
|---|---:|---:|---:|---:|---:|
| pre_earnings_0_7 | 0 | 0 | 0 | 0 | 1 |
| pre_earnings_46_plus | 5 | 3 | 3 | 2 | 12 |
| gap_up_3pct | 5 | 3 | 3 | 2 | 11 |
| post_earnings_drift_1_10 | 4 | 2 | 3 | 1 | 10 |

## Oracle Implication

- Existing oracle tooling already has candidate-forward and selection oracles, not only perfect exit.
- What is missing is a reusable entry-state oracle layer that tags candidates with pre-entry lifecycle states.
- `pre_earnings_0_7` is promising in daily surface data, but has zero META/NFLX candidate overlap here.
- Do not replay or promote until candidate overlap or forward evidence exists.

## Guardrails

- No production path changed.
- No oracle_diagnostics shared module changed in this experiment.
- No entry, exit, ranking, sizing, universe, LLM/news, or order behavior changed.
