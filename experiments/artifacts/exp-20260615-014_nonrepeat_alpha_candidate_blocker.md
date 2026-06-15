# exp-20260615-014 Nonrepeat Alpha Candidate Blocker

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
| `sec_text_demand_or_cost_or_liquidity_evidence` | `blocked_all_candidates_frozen` | The latest SEC text lanes rejected both generic and quantified backlog/order evidence plus restructuring and deleveraging/liquidity variants; another keyword/evidence-span replay would be a frozen near-neighbor without new semantics. |
| `companyfacts_quality_growth_or_cash_conversion` | `blocked_near_neighbor_overfit_risk` | Coverage exists, but the last two days already tested cash conversion, accruals, low asset growth, cash-backed low asset growth, industry-relative asset growth, FCF capex coverage, gross profitability, and share contraction with mostly rejected Gate 4 behavior or drawdown drift. |
| `13f_or_form4_ownership_pressure` | `blocked_data_surface_insufficient_and_recently_rejected` | The current Kova 13F surface has skipped/empty rows, and the latest low-crowding 13F leadership scout was rejected; Form4/Form144 variants are already frozen without a new relation-quality discriminator. |
| `analyst_estimate_revision_or_pead_extension` | `blocked_data_surface_insufficient` | The current estimate summary has no matched candidate rows, so a three-window Gate 4 replay would be empty or dominated by stale/current-only observations. |
| `options_or_intraday_free_data_edge` | `blocked_no_closed_outcomes_or_api_backfill` | Options work remains observed-only without enough closed outcomes, while current Kova intraday rows are skipped/empty and cannot support a PIT historical replay. |
| `ohlcv_only_candidate_pool_or_allocator_retune` | `blocked_all_candidates_frozen` | The playbook freezes OHLCV relabels, state/ranking threshold sweeps, and allocator arbitration retunes unless there is new data; the current RS proxy snapshot is narrow and not a new production-visible data edge. |
| `accepted_default_off_adapter_maturation` | `blocked_not_a_new_gate4_alpha_optimization` | This is the right monitoring lane, but it is observed-only until enough closed true-trigger rows exist; it should not be sold as a new historical alpha optimization. |

## Conclusion

Prioritize new data-edge construction over strategy retuning: build PIT analyst revision breadth/dispersion or SEC customer/supplier contract-economics features, then implement shared-paper-first historical replay plus daily default-off parity.

## Repro

- Runner: `quant/experiments/exp_20260615_014_nonrepeat_alpha_candidate_blocker.py`
- JSON artifact: `data/experiments/exp-20260615-014/nonrepeat_alpha_candidate_blocker.json`
- Before artifact: `data/experiments/exp-20260615-014/before_baseline.json`
- After artifact: `data/experiments/exp-20260615-014/after_no_strategy_change.json`
- Log: `experiments/logs/exp-20260615-014.json`

No JavaScript was used.
