# exp-20260616-006 Seasoned New-Listing Independent Data Readiness

## Decision

- Decision: `blocked_seasoned_new_listing_independent_data_absent`
- Accepted alpha: `false`
- Strategy code changed: `false`
- Production/live impact: `none`
- No JavaScript was used.

## Hypothesis

Seasoned new-listing leadership remains the strongest recent positive lead, but it is executable only if an independent PIT data surface can separate it from the frozen first-seen/RS/MA/ADV retune family.

## Gate 1-4

- Gate 1 baseline: `data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json`.
- Gate 2: no executable rows created; future alpha must validate `entry_date` and `target_price`.
- Gate 3: no filter added; baseline survival `0.8232`.
- Gate 4: before/after identical because launch was blocked by missing independent PIT data.

| Window | EV Before | EV After | PnL Before | PnL After | Trades | Survival |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | 5.1628 | 5.1628 | $117072.92 | $117072.92 | 18 | 0.8039 |
| `mid_weak` | 2.1402 | 2.1402 | $78110.11 | $78110.11 | 21 | 0.7925 |
| `old_thin` | 0.5911 | 0.5911 | $39667.96 | $39667.96 | 22 | 0.8667 |

## Candidate Reviews

| Candidate | Decision | Why not run now |
| --- | --- | --- |
| `seasoned_new_listing_leadership_retry` | `blocked_without_independent_evidence` | The lead was positive across three windows but failed drawdown. Its own closeout bans nearby age, RS, moving-average, close-location, ADV, hold-day, notional, and cooldown retunes without a materially new PIT field. |
| `true_listing_lockup_float_confirmation` | `blocked_missing_local_pit_surface` | No local PIT true listing, IPO, lockup, or float surface was found; the warehouse only offers first-seen-style observables. |
| `revision_confirmation_for_young_leaders` | `blocked_no_matched_candidate_rows` | The latest revision ledger has 0 matched candidate rows; a historical launch would be backtest-only or empty. |
| `13f_sponsorship_confirmation` | `blocked_near_neighbor_and_negative_history` | 13F sponsorship variants already failed or remained lead-only, and using them only as another filter would be a near-neighbor retry. |
| `form4_or_current_daily_confirmation` | `blocked_not_three_window_pit_alpha` | Form4 role/liability variants are freshly rejected and current daily files do not create a three-window PIT replay surface. |

## Conclusion

Prioritize a free PIT data edge for listing/float/lockup or analyst revision breadth. If that cannot be sourced, shift to structured customer/supplier contract economics with value/duration fields and shared daily parity, not another SEC keyword or allocator retune.

## Repro

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260616_006_seasoned_new_listing_independent_data_readiness.py
```
