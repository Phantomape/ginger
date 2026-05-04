# Form 4 Entry-Skip Oracle Overlap

- experiment_id: `exp-20260503-049`
- generated_at: `2026-05-03T20:09:56+00:00`
- production_impact: `shadow_oracle_overlap_analysis_only`
- candidate_scope: `top_skipped_opportunities from entry_skip_oracle, 15 per window`
- top skipped candidates: `45`

| Lookback | Matched candidates | Matched avg max forward | Unmatched avg max forward | Matched tickers |
|---|---:|---:|---:|---|
| 20d | 0 | n/a% | 14.21% | none |
| 60d | 0 | n/a% | 14.21% | none |
| 90d | 0 | n/a% | 14.21% | none |
| 120d | 0 | n/a% | 14.21% | none |

## Read

This is an oracle triage join over the saved top skipped opportunities.
It uses future upper-bound returns from the oracle diagnostic, so it is not
a tradable rule. A sparse overlap means Form 4 is not currently explaining
most known high-value skipped opportunities.
