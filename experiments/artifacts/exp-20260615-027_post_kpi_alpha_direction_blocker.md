# exp-20260615-027 Post-KPI Alpha Direction Blocker

## Decision

- Decision: `rejected_no_gate4_ready_nonrepeat_alpha_candidate`
- Accepted alpha: `false`
- Strategy code changed: `false`
- Production/live impact: `none`

## Gate 1-4

- Gate 1 baseline: `data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json`.
- Gate 2 fields: no executable rows created; any future alpha must validate `entry_date` and `target_price` at runtime.
- Gate 3 survival: no filter added; baseline survival `0.8232`.
- Gate 4: no behavior changed; all three windows are identical before/after because launch is rejected.

| Window | EV Before | EV After | PnL Before | PnL After | Trades | Survival |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | 5.1628 | 5.1628 | $117072.92 | $117072.92 | 18 | 0.8039 |
| `mid_weak` | 2.1402 | 2.1402 | $78110.11 | $78110.11 | 21 | 0.7925 |
| `old_thin` | 0.5911 | 0.5911 | $39667.96 | $39667.96 | 22 | 0.8667 |

## Candidate Reviews

| Candidate | Decision | Why not run now |
| --- | --- | --- |
| `sec_saas_operating_kpi_text` | `blocked_recent_negative_near_neighbor` | exp-20260615-026 was rejected: aggregate EV delta -0.0440, only four event trades, and late_strong regressed; it also failed to beat the accepted SEC financial-report RS20 comparator. |
| `form4_ceo_cfo_low_liability` | `blocked_recent_negative_near_neighbor` | exp-20260615-024 regressed all three windows versus core with aggregate EV delta -0.1888 and PnL delta -$1361.40. |
| `pit_regime_chop_state_risk_allocation` | `blocked_forward_rows_and_parity` | exp-20260615-021 had a positive replay lead, but was rejected because current forward choppy replacement rows were zero and no shared daily regime artifact exists for promotion. |
| `accepted_allocator_source_retune` | `blocked_repeat_risk_without_new_field` | The accepted lagged consensus allocator already supplies the current strongest shared helper; playbook guidance freezes source/order/scalar retunes unless a materially new PIT field is added. |
| `pit_analyst_revision_breadth_dispersion` | `best_next_data_edge_not_gate4_ready` | The latest summary has usable forward rows but matched_candidate_rows is zero, so there is no all-window candidate-matched PIT feature set for a trustworthy Gate 1-4 alpha replay. |
| `options_onclickmedia_flow_surface` | `blocked_forward_only_or_pit_unsafe_history` | The adapter explicitly marks historical backfills PIT unsafe; current usable data is forward daily only and covers too few dates/tickers for the canonical windows. |
| `sec_companyfacts_quality_or_growth_retest` | `blocked_frozen_threshold_family` | The data surface is broad, but recent Companyfacts quality, growth, and threshold variants are frozen/rejected unless a materially different PIT economic field is added. |

## Conclusion

Optimize candidate-pool data edges, not thresholds. First priority is PIT analyst revision breadth/dispersion matched to historical candidates; second priority is structured SEC customer/supplier contract economics. Either must be implemented shared-paper-first before acceptance.

## Repro

- Runner: `quant/experiments/exp_20260615_027_post_kpi_alpha_direction_blocker.py`
- JSON artifact: `data/experiments/exp-20260615-027/post_kpi_alpha_direction_blocker.json`
- Before artifact: `data/experiments/exp-20260615-027/before_baseline.json`
- After artifact: `data/experiments/exp-20260615-027/after_no_strategy_change.json`
- Log: `experiments/logs/exp-20260615-027.json`

No JavaScript was used.
