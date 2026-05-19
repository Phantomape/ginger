# exp-20260511-014 space_official_no_addons

## Hypothesis

Disable follow-through add-ons only for the accepted 0.75x Space official-catalyst sleeve. If the sleeve's edge is mainly first-entry convexity, this should reduce concentration and drawdown without damaging aggregate EV.

## Gate Answers

- Hypothesis category: risk allocation / lifecycle allocation on the Space official-catalyst sleeve; this follows the playbook because exp-20260511-011 is the strongest current non-LLM alpha lead.
- Prior related work: exp-20260511-010 full-risk official Space pool was rejected on drawdown; exp-20260511-011 accepted 0.75x default-off; exp-20260511-012 rejected blanket trend-only refinement; no prior Space-specific add-on eligibility test exists.
- Single variable: add-on eligibility for official Space tickers only; pool, 0.75x risk scalar, core universe, signal generation, ranking, exits, news/LLM, and live slots stay locked.
- Success criterion: beat accepted exp-20260511-011 on aggregate EV and PnL with at least two EV-improved windows, while keeping positive aggregate EV vs core and avoiding unacceptable drawdown damage.
- Reproducibility: this script writes JSON, ticket, artifact, and experiment_log JSONL with all parameters and three-window metrics.

## Three-Window Result

| window | before EV | after EV | dEV vs before | dEV vs core | before pnl | after pnl | blocked add-ons |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.4465 | 4.4465 | 0.0000 | 0.2125 | 97942.41 | 97942.41 | 0 |
| mid_weak | 2.7096 | 2.5458 | -0.1638 | 0.8769 | 73829.93 | 71307.66 | 3 |
| old_thin | 0.6919 | 0.6561 | -0.0358 | 0.2708 | 44928.42 | 43452.54 | 1 |

## Aggregate

- after vs accepted exp-011: EV delta -0.1996, PnL delta -3998.15, max drawdown delta 0.0000 pp
- after vs core baseline: EV delta 1.3602, PnL delta 28258.19, max drawdown delta 0.0071 pp
- decision: rejected_no_addon_refinement_keep_exp_20260511_011
- rejection_reason: Blanket Space official-catalyst add-on disablement did not beat the accepted exp-20260511-011 0.75x lifecycle with enough three-window EV/PnL evidence.

## Production Impact

```text
production_impact:
  shared_policy_changed: false
  backtester_adapter_changed: false
  run_adapter_changed: false
  replay_only: true
  parity_test_added: false
```
