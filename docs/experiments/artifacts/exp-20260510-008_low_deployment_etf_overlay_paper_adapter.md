# exp-20260510-008 Low-deployment ETF Overlay Paper Adapter

Decision: `accepted_default_off_paper_adapter`

## Hypothesis

The low-deployment dynamic ETF overlay is the strongest current non-LLM,
non-retune alpha direction. Production should observe it as paper-only
replacement-value attribution before any live order path exists.

## Why This Alpha Direction

- `exp-20260510-007` improved EV in all three canonical windows with aggregate
  EV `+0.3141` and PnL `+$10376.82`.
- LLM soft-ranking remains sample-limited, SEC filing-shock is blocked by
  missing directional fields, and recent event/state/local retunes are already
  exhausted on the frozen sample.
- This path extends candidate-pool exposure through liquid ETFs only when the
  accepted A/B core is under-deployed, without adding noisy core tickers.

## Single Causal Variable

Added a default-off production paper ledger/report surface for the exact
low-deployment dynamic ETF overlay. Core signals, ranking, sizing, exits,
filters, follow-through add-ons, LLM/news behavior, and universe membership
stay unchanged.

## Three-window Core No-drift Check

| Window | Before EV | After EV | EV delta | Before PnL | After PnL | Survival |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 4.0674 | 4.0674 | 0.0000 | $90,788.88 | $90,788.88 | 80.39% |
| mid_weak | 1.6195 | 1.6195 | 0.0000 | $59,540.63 | $59,540.63 | 79.25% |
| old_thin | 0.3583 | 0.3583 | 0.0000 | $27,347.42 | $27,347.42 | 91.67% |

Risk distribution stayed unchanged: `worst_trade_pct`, `max_consecutive_losses`,
and `tail_loss_share` match the accepted baseline in all three windows.

## Gate 4

The adapter passed only as a default-off paper implementation:

- core EV/PnL/trades/survival did not move in the canonical windows;
- no live/default orders, sizing, ranking, or signal generation changed;
- the prior positive replay evidence remains `exp-20260510-007`, not a new
  parameter sweep;
- live promotion remains blocked until forward paper outcomes, cash semantics,
  explicit trade adapter, and parity tests pass.

## Verification

- `pytest quant/test_low_deployment_etf_overlay.py -q`: 3 passed.
- `pytest quant/test_low_deployment_etf_overlay.py quant/test_event_sleeve_bundle.py quant/test_state_surface_sleeve.py quant/test_platform_rs20_watch.py quant/test_sec_10k_forward_watch.py -q`: 26 passed.
- AST parse of `quant/low_deployment_etf_overlay.py`, `quant/run.py`, and `quant/report_generator.py`: passed.
- Canonical three-window CLI rerun: core metrics unchanged and all primary windows converged 8/8.

## Commit Status

Commit was attempted but blocked by repository filesystem permissions. The
normal index path failed to create `.git/index.lock`; the alternate index path
failed to write a new index file. The experiment is recorded but not committed.

## Production Impact

```text
production_impact:
  shared_policy_changed: true
  backtester_adapter_changed: false
  run_adapter_changed: true
  replay_only: false
  parity_test_added: true
```

`shared_policy_changed` means a shared paper attribution module was added. It
does not change the core trading policy or order path.

## Next Evidence Needed

Collect closed forward paper ETF overlay outcomes with same-day deployment and
cash context. Do not enable live/default ETF overlay orders until the cash
semantics and explicit trade adapter are implemented and tested against
backtester parity.
