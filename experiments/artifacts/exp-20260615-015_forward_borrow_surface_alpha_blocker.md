# exp-20260615-015 Forward/Borrow Surface Alpha Blocker

## Decision

- Decision: `blocked_no_gate4_ready_nonrepeat_alpha_candidate`
- Accepted alpha: `false`
- Strategy code changed: `false`
- Production/live impact: `none`

## Gate 1-4

- Gate 1 baseline: `docs/backtesting.md`, aggregate EV `7.8941`, PnL `$234850.99`.
- Gate 2 fields: no executable rows created; future alpha still requires runtime `entry_date` and `target_price` checks.
- Gate 3 survival: no filter added; baseline min survival `0.7925`.
- Gate 4: no behavior changed; all three windows are identical before/after because the alpha launch is blocked.

| Window | EV Before | EV After | PnL Before | PnL After | Trades | Survival |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | 5.1628 | 5.1628 | $117072.92 | $117072.92 | 18 | 0.8039 |
| `mid_weak` | 2.1402 | 2.1402 | $78110.11 | $78110.11 | 21 | 0.7925 |
| `old_thin` | 0.5911 | 0.5911 | $39667.96 | $39667.96 | 22 | 0.8667 |

## Candidate Reviews

| Candidate | Decision | Why not run now |
| --- | --- | --- |
| `finra_sec_ftd_borrow_pressure_candidate_pool` | `blocked_all_candidates_frozen` | FINRA/IWM and SEC FTD confirmation already have accepted default-off adapters; the playbook freezes FINRA/FTD top-N, cooldown, hold, notional, and parameter retunes unless a new PIT borrow-cost or share-availability source appears. |
| `sec_item_502_leadership_or_governance_absorption` | `blocked_existing_default_off_sleeve_and_forward_sample_too_small` | Item 5.02 leadership changes are already represented by the SEC leadership default-off sleeve; closed leadership rows are 1 with closed PnL -175.58. A new item-code replay would be a near-duplicate without richer semantic provenance. |
| `forward_replacement_promotion_check` | `blocked_forward_sample_too_small_or_frozen` | State-surface forward rows are positive but only 3 closed rows; low-deployment ETF has more rows but threshold/list/hold/notional retunes are frozen. Neither is a valid new three-window policy bundle today. |
| `pit_analyst_revision_breadth_dispersion` | `blocked_data_surface_insufficient` | The accepted revision-surprise low-extension source is fixed in the shared allocator, but current revision trajectory data is still not matched enough for a fresh canonical three-window candidate-pool alpha. |
| `sec_customer_supplier_contract_economics` | `blocked_missing_materially_new_pit_semantic_field` | Generic SEC demand, backlog, restructuring, deleveraging, and guidance evidence spans were just rejected; current text rows do not expose a richer structured customer/supplier contract-economics field. |

## Conclusion

Optimize data-edge construction, not thresholds: prioritize PIT analyst revision breadth/dispersion or SEC customer/supplier contract economics, then run a shared-paper-first Gate 1-4 experiment.

## Repro

- Runner: `quant/experiments/exp_20260615_015_forward_borrow_surface_alpha_blocker.py`
- JSON artifact: `data/experiments/exp-20260615-015/forward_borrow_surface_alpha_blocker.json`
- Before artifact: `data/experiments/exp-20260615-015/before_baseline.json`
- After artifact: `data/experiments/exp-20260615-015/after_no_strategy_change.json`
- Log: `experiments/logs/exp-20260615-015.json`

No JavaScript was used.
