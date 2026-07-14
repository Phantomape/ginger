# exp-20260714-004 EIA WPSR de-stocking energy basket

- Decision: `rejected_eia_wpsr_destocking_energy_basket_candidate_pool`
- Full-stack verdict: `reject`
- Settled EIA events / stock legs: `11` / `110`
- Aggregate EV delta: `+0.0707`
- Aggregate PnL delta: `$+1,380.90`
- Gate 3 event survival: `16.05%`
- Failed matched benchmarks: `USO`
- Numeric Gate 4 failures: `ev_regressed_windows, insufficient_adjusted_sample, top_5_contribution_pct_cap, window_pnl_regression, settled_event_count_below_12, required_xle_uso_spy_qqq_cash_comparator_not_beaten, accepted_candidate_pool_ev_comparator_not_beaten, accepted_candidate_pool_pnl_comparator_not_beaten`
- Binding Gate 4 failures: `ev_regressed_windows, insufficient_adjusted_sample, top_5_contribution_pct_cap, window_pnl_regression, settled_event_count_below_12, required_xle_uso_spy_qqq_cash_comparator_not_beaten, accepted_candidate_pool_ev_comparator_not_beaten, accepted_candidate_pool_pnl_comparator_not_beaten`
- Gate 5 / DSR: `blocked` / `not_computable`

## Window deltas

- old_thin: settled_events=4, legs=40, EV=-0.0302, PnL=$-437.05, drawdown=+0.0003.
- mid_weak: settled_events=3, legs=30, EV=+0.0042, PnL=$+253.03, drawdown=+0.0003.
- late_strong: settled_events=4, legs=40, EV=+0.0967, PnL=$+1,564.92, drawdown=+0.0000.

## Evidence contract

The source bundle contains 390 versioned first-release issues. The 2023-12-28 arithmetic mismatch is accepted only under the frozen official EIA errata notice; every other issue remains fail-closed.

Stock legs are used for PnL and concentration, but the independent sample unit is the settled weekly EIA release event. XLE, USO, SPY, QQQ, and cash are compared event-equally from the same entry open to the shared scheduled tenth-session close with the same 35 bps cost.

The daily snapshot is a one-shot default-off parity artifact. No run.py wiring, automatic forward collection, live order, core ranking, sizing, or exit path changed.

Reproduce offline: `.\.venv\Scripts\python.exe -B quant\experiments\exp_20260714_004_eia_wpsr_destocking_energy_basket.py --offline`
