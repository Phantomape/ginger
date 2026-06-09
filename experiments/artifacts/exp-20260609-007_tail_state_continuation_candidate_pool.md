# exp-20260609-007 Tail-State Winner-Continuation Candidate Pool

Verdict: `reject` (Gate 4 failed on `immaterial_effect`).

First end-to-end run of the full-stack candidate-pool mechanism
(`quant/full_stack_candidate_pool.py`) on playbook Research Queue #2
(tail-state classifier for broad winner-continuation). Read-only PIT
attribution; the playbook's prescribed first step before any adapter.

## Method (read-only, PIT)

Candidate pool = top-20% ret5 winners on the `exp-20260519-030` warehouse
`all_windows_full_liquid` universe, sampled every 5th day across the canonical
3 windows. A PIT tail-state filter labels a winner **resilient** when the day
is breadth-supported (share with ret20>0 >= 0.5), not in a momentum-crash
regime (median ret20 >= 0), and the candidate is not overextended
(ret5-ret20 <= pool median). Forward 10d skip-day close-to-close; one
round-trip cost. window_metrics fed to Gate 4 are a fixed-$10k-notional
return-based proxy for a backtester before/after.

## Result: real but immaterial separation

- Resilient (n=7,101) minus tail-risk (n=13,121) forward 10d: **+1.37%**.
- Resilient net of cost: **+1.54%**; excess over the all-winners comparator:
  **+0.89%** ($88.84 / trade), positive in **all 3 windows**
  (late_strong +0.29%, mid_weak +0.30%, old_thin +1.62%).
- Concentration excellent: single-ticker 3.3%, top-5 11.3%, HHI 0.006.
- **Gate 4 fails on `immaterial_effect` only**: the +0.89% / $88.84 excess over
  simply buying all winners is below the AGENTS.md scout materiality floor
  ($500/trade AND 5pp). The tail-state filter separates cleanly and robustly,
  but adds too little over the naive winner pool to matter.

## Verdict ladder (mechanism demonstration)

```
verdict: reject
gate4_passed: false   -> hard_failures: ["immaterial_effect"]
live_readiness: blocked (forward_rows 0/30, envelope declared, kill-switch parity pending)
next_step: roll back; log the failure; do not retune on the frozen sample
```

This is the intended one-shot behavior: a single read-only experiment reaches a
production/paper-sleeve verdict (`reject`) without a separate round.

## Side effect: a guard false-positive fixed

This runner dogfoods the sanctioned path
(`experiment_registry.persist_self_registered_result()`, no direct registry
write). It surfaced a false-positive in `self_registration_guard.self_registers`:
referencing the `experiment_registry.json` path (to pass to the helper) plus
writing its own artifact tripped the `.write_text` heuristic. Fixed by exempting
runners that call the helper (a `setdefault("experiments")` direct mutation still
flags regardless). Added two regression tests.

## Next evidence needed

- Tail-state separation is real but immaterial vs the naive winner pool; not
  worth a paper adapter. If revisited, test against the **low-deployment ETF
  comparator** (not the all-winners pool) and on a more selective top-N rather
  than the full top quintile, where per-trade magnitude could clear the floor.

## Files

- `quant/experiments/exp_20260609_007_tail_state_continuation_candidate_pool.py`
- `data/experiments/exp-20260609-007/tail_state_continuation_candidate_pool.json`
- `experiments/tickets/exp-20260609-007.json` (prediction + result + verdict)

Pre-run prediction (success_probability 0.20) anticipated this: failure modes
`tail_state_does_not_separate` / `not_incremental_over_ret20` /
`fails_etf_comparator_after_cost`. Outcome: it *did* separate but the edge was
immaterial -- closest to `not_incremental` in magnitude.

No JavaScript was used.
