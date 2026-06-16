# exp-20260616-002 Earnings Field Surface Alpha Blocker

## Decision

- Decision: `blocked_no_gate4_ready_nonrepeat_alpha_candidate`
- Accepted alpha: `false`
- Strategy code changed: `false`
- Production/live impact: `none`
- No JavaScript was used.

## Gate 1-4

- Gate 1 baseline: `data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json`.
- Gate 2: no executable rows created; future alpha must validate `entry_date` and `target_price`.
- Gate 3: no filter added; baseline survival `0.8232`.
- Gate 4: before/after identical because launch was rejected.

| Window | EV Before | EV After | PnL Before | PnL After | Trades | Survival |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | 5.1628 | 5.1628 | $117072.92 | $117072.92 | 18 | 0.8039 |
| `mid_weak` | 2.1402 | 2.1402 | $78110.11 | $78110.11 | 21 | 0.7925 |
| `old_thin` | 0.5911 | 0.5911 | $39667.96 | $39667.96 | 22 | 0.8667 |

## Candidate Reviews

| Candidate | Decision | Why not run now |
| --- | --- | --- |
| `pit_analyst_revision_breadth_dispersion` | `blocked_missing_required_historical_fields` | The historical snapshots cover the windows but lack analyst-count, revenue-estimate, dispersion, fiscal-period, and vendor-as-of fields. EPS-only revision is already the accepted default-off revision helper, so a replay would be a frozen retune. |
| `form4_role_or_cluster_candidate_pool` | `blocked_recent_negative_and_near_neighbor_frozen` | The latest CEO/CFO/President plus low-liability Form4 replay was negative versus core across all three canonical windows; nearby role, threshold, cluster, and conviction retunes are explicitly frozen without a new relation-quality field. |
| `options_or_intraday_free_data_edge` | `blocked_no_closed_options_outcomes_and_intraday_skipped` | Options remain shadow-only with zero closed candidate outcomes in the latest overlay, while Kova intraday rows are skipped/unusable for canonical historical replay. |
| `sec13f_or_ownership_candidate_pool` | `blocked_empty_surface_and_recent_rejection` | The latest Kova 13F surface has skipped or unusable rows, and the recent low-crowding leadership scout failed the three-window gate. |
| `space_catalyst_theme_candidate_pool` | `blocked_saturated_forward_only_theme_surface` | Space already has a shared observe-only surface with many metadata/risk helpers; promotion requires closed replacement evidence, not another historical theme retune. |
| `sec_customer_supplier_contract_economics` | `blocked_latest_named_counterparty_replay_failed` | The named-counterparty contract-economics replay produced only one target trade and negative aggregate EV/PnL; generic SEC text demand/backlog variants are also frozen. |
| `ohlcv_or_allocator_retune` | `blocked_all_candidates_frozen` | Accepted allocator rank/top-N/notional/hold/cooldown and price-only relabels are frozen without a materially new PIT field or forward displacement evidence. |

## Conclusion

Prioritize analyst revision breadth/dispersion data construction, not strategy retuning. If that cannot be sourced, the next best alpha search is structured SEC counterparty economics with value/duration fields and shared daily parity.

## Repro

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260616_002_earnings_field_surface_alpha_blocker.py
```
