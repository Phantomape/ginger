# exp-20260714-003 FDIC Call Report deposit repair

- Decision: `rejected_fdic_call_report_deposit_repair_candidate_pool`
- Full-stack verdict: `reject`
- Target trades / tickers / effective quarter clusters: `28` / `16` / `6`
- Aggregate EV delta: `-0.074500`
- Aggregate PnL delta: `$-492.09`
- Gate 3 survival: `4.28%`
- Available comparators: `CASH, SPY, QQQ`
- Failed comparators: `XLF, KBE, CASH`
- Numeric Gate 4 failures: `non_positive_aggregate_ev, non_positive_aggregate_pnl, ev_regressed_windows, drawdown_worse_guardrail, top_5_contribution_pct_cap, window_pnl_regression, gate3_survival_below_5pct, required_cash_spy_qqq_xlf_kbe_comparator_missing_or_not_beaten, accepted_candidate_pool_ev_comparator_not_beaten, accepted_candidate_pool_pnl_comparator_not_beaten`
- Measurement-validity failures: `historical_fdic_first_release_vintage_not_reconstructed, historical_parent_cert_security_mapping_not_reconstructed`
- Binding Gate 4 failures: `non_positive_aggregate_ev, non_positive_aggregate_pnl, ev_regressed_windows, drawdown_worse_guardrail, top_5_contribution_pct_cap, window_pnl_regression, gate3_survival_below_5pct, required_cash_spy_qqq_xlf_kbe_comparator_missing_or_not_beaten, accepted_candidate_pool_ev_comparator_not_beaten, accepted_candidate_pool_pnl_comparator_not_beaten, historical_fdic_first_release_vintage_not_reconstructed, historical_parent_cert_security_mapping_not_reconstructed`
- Accepted candidate-pool comparator: actual EV / required EV `-0.074500` / `>+0.528600`; actual PnL / required PnL `$-492.09` / `>$+10,432.91` (`exp-20260611-007`).
- Gate 5 / DSR: `blocked` / `not_computable`
- Evaluator selection-pool complete: `False`

## Window deltas

- late_strong: trades=9, EV=+0.009300, PnL=$-40.95, drawdown=-0.000300.
- mid_weak: trades=9, EV=+0.011300, PnL=$+891.67, drawdown=+0.001700.
- old_thin: trades=10, EV=-0.095100, PnL=$-1,342.81, drawdown=+0.007500.

## Unsettled selected rows

- none

## Calculation identity

- runner: `quant/experiments/exp_20260714_003_fdic_call_report_deposit_repair.py` sha256 `6a399472c2dcdc55409a3c9050e3aec5010251dd182c2f67b644facae86e9fa9`
- shared_selection_helper: `quant/fdic_call_report_deposit_repair_paper_sleeve.py` sha256 `65c61809f865e0e50440ccd536055330574fb390c8a967f776bda09222db41a7`
- combine_window_owner: `quant/experiments/exp_20260713_008_clinicaltrials_phase3_results_green_spy_relative_top1_10d_v1.py` sha256 `f3383c5877542cbb60518e7d66e92ed92958149068df71130ad81c862146a277`
- full_stack_candidate_pool: `quant/full_stack_candidate_pool.py` sha256 `f96d4f69648bf2ef945acfa02350daedbfd6e8b60b6177508be78d3e92688234`
- evaluator_gates: `quant/evaluator_gates.py` sha256 `9e0fac697d2cd9ebf79ad6e9c80c2d549f267e518b4b3aebb5d0461de0a6f37e`
- sharpe_inference: `quant/sharpe_inference.py` sha256 `a0e0e9aeb56f8a9dfbc446c21378b271c6a5fbd083f0624a197a67c8a45b92b2`
- deflated_sharpe_adapter: `scripts/deflated_sharpe.py` sha256 `35170a0d40022260e020478e9eaf830c1c22d8a848cf2bbc8f96aa1ffab28662`
- frozen_auxiliary_ohlcv: `data/experiments/exp-20260714-003/auxiliary_ohlcv.json` file sha256 `b6c8eb0a8f0a2675b42a142783ff9f9acd3b23e761de45c434a948d6dfc1fb8a`, rowset sha256 `63acfec1a8948c8a1c2ad61259eee7ab4fdbf9a0953b88e2ca016b1d928323c0`

## Evidence limits

The 28 settled rows are only 6 quarterly release clusters. FDIC financials are current-vintage and the exact current SEC/FDIC parent map is carried backward; neither first-release amendments nor historical ownership are reconstructed.

Historical replay and the one-shot default-off paper snapshot call the same shared selection helper. Because the alpha was rejected, no run.py/report/ledger daily wiring or automatic forward collection was retained. No live order, core ranking, sizing, or exit path changed.

Reproduce offline: `.\.venv\Scripts\python.exe -B quant\experiments\exp_20260714_003_fdic_call_report_deposit_repair.py --offline`
