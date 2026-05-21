# exp-20260520-033 prior_scalar_evidence_backfill_v1

Decision: `blocked_strict_state_surface_gate_not_met`.

## Hypothesis

State-surface concentration work should not add another scalar unless the aggregate EV improvement exceeds the strict >10% gate.

## Trial Accounting

- mechanism_family: `state_surface_concentration`
- trial_family: `state_surface_concentration_context`
- changed_variable: `state_surface_trend_stability_support_notional`
- prior_trial_count: `21`
- multiple_testing_risk_bucket: `minimal`

## Metric Evidence

```json
{
  "decision": "rejected_state_surface_trend_stability_support_notional",
  "evidence_type": "state_surface_paper_replay_and_tail_gate",
  "rejection_reason": "Failed Gate 4 under the strict state-surface scalar standard: aggregate EV delta pct 0.0349 did not exceed 0.10.",
  "source_artifact": "data/experiments/exp-20260520-006/state_surface_trend_stability_notional.json",
  "source_experiment": "exp-20260520-006",
  "strict_state_surface_gate": {
    "actual_aggregate_ev_delta_pct": 0.03487,
    "aggregate_ev_delta": 0.5528,
    "aggregate_pnl_delta": 10140.4,
    "minimum_aggregate_ev_delta_pct": 0.1,
    "passed": false,
    "windows_ev_improved": 3,
    "windows_ev_regressed": 0
  },
  "tail_gate_reference": {
    "block_reasons": [
      "tail_gate"
    ],
    "closed_trades": 24,
    "passed": false,
    "realized_pnl": 48529.4,
    "source_artifact": "data/experiments/exp-20260518-006/state_surface_forward_tail_gate.json",
    "source_experiment": "exp-20260518-006",
    "win_rate": 0.7917
  }
}
```

## Next Evidence Needed

Use the new concentration context field to explain queue concentration before another scalar/profile test.
