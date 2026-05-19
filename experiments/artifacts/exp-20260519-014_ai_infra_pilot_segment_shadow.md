# exp-20260519-014 AI Infra Pilot Segment Shadow

Decision: `rejected_ai_infra_pilot_segment_shadow`.

Single causal variable family: AI_INFRA_AGGRESSIVE pilot candidate-pool segment membership. Signal rules, ranking, sizing, exits, heat, slots, LLM/news, and live orders stay locked.

## Gate 1 Baseline Note

- baseline_alignment_passed: `False`
- reason: non-core AI infra candidates require the cached augmented OHLCV snapshot from `exp-20260501-008`; that augmented baseline drifts from the accepted canonical `exp-20260517-009` core metrics.
- consequence: this is replay-only scout evidence, not acceptance evidence for core promotion.

## Variant Scout

| Variant | Gate | Added | dEV | dPnL | Improved | Regressed | Candidate trades | Windows | Max DD worse |
|---|:---:|---|---:|---:|---|---|---:|---:|---:|
| pilot_compute_connectivity | FAIL | INTC, LITE | +2.3396 | $+42,004.78 | late_strong | mid_weak | 5 | 2 | +0.0132 |
| pilot_power_excluded | FAIL | APLD, INTC, LITE | +2.3396 | $+42,004.78 | late_strong | mid_weak | 5 | 2 | +0.0132 |
| pilot_optical_only | FAIL | LITE | +0.7899 | $+17,938.90 | late_strong | mid_weak | 3 | 2 | +0.0018 |
| pilot_compute_only | FAIL | INTC | +1.6746 | $+26,383.13 | late_strong, old_thin | - | 2 | 1 | +0.0132 |
| pilot_power_only | FAIL | APLD, BE | +1.0719 | $+23,631.56 | mid_weak | old_thin | 2 | 2 | +0.0000 |
| pilot_no_be | FAIL | APLD, INTC, LITE | +2.3396 | $+42,004.78 | late_strong | mid_weak | 5 | 2 | +0.0132 |
| pilot_no_lite | FAIL | APLD, BE, INTC | +2.4550 | $+45,500.82 | late_strong, mid_weak | old_thin | 4 | 3 | +0.0132 |

## Selected Variant

- selected: `pilot_no_lite`
- gate_passed: `False`
- EV delta: `2.455`
- PnL delta: `$45500.82`

## Interpretation

No current AI infra pilot segment bundle cleared the three-window candidate-pool shadow gate. Aggregate EV was positive in several variants, but every broad enough variant either regressed a window, worsened max drawdown beyond the guardrail, or had a thin one-window sample.

## Production Impact

```json
{
  "backtester_adapter_changed": false,
  "parity_test_added": false,
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

No JavaScript was used.
