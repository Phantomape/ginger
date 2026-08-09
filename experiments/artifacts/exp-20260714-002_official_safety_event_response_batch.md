# exp-20260714-002 Official Safety Event Response Batch

- Decision: rejected_official_safety_event_response_batch
- Binding policy: pooled NHTSA + CPSC
- Pooled trades / tickers / windows: 22 / 12 / 3
- Aggregate EV / PnL delta: -0.0188 / USD -153.64
- Gate 3 survival: 32.05%
- Gate 4 failures: non_positive_aggregate_ev, non_positive_aggregate_pnl, insufficient_ev_improved_windows, ev_regressed_windows, top_5_contribution_pct_cap, window_pnl_regression, accepted_distribution_ev_comparator_not_beaten, accepted_distribution_pnl_comparator_not_beaten
- Gate 5: not_computable, fail-closed because six prior same-lane return series cannot be reconstructed.

## Diagnostic shards

- NHTSA: events=42, trades=14, EV delta=-0.1506, PnL=USD -1,736.87.
- CPSC: events=36, trades=8, EV delta=0.152, PnL=USD 1,583.24.

NHTSA uses ODATE and CPSC uses max(RecallDate, LastPublishDate). Both use exact issuer maps and the same strict-after/top1/cooldown/next-open/tenth-close policy.
Any pass remains an observed-only lead: no shared helper, daily snapshot, adapter, or live order path changed.
Preflight selected 25 candidates; 22 are settled inside their canonical windows. NHTSA GM on 2025-10-22 enters outside mid_weak; CPSC RH on 2025-10-20 and GNRC on 2026-04-20 have tenth closes outside their windows. Gate 3 uses 25 selected rows; Gate 4 uses 22 settled trades.
Residual source caveat: the 78 curated rows and their calculation inputs are hash-bound, but the complete official responses are represented only by response hashes, not stored raw bytes; NHTSA report-date version history is therefore unknown.

## Window deltas

- late_strong: trades=6, EV delta=+0.0160, PnL delta=USD +442.21, drawdown delta=-0.0009.
- mid_weak: trades=7, EV delta=+0.0014, PnL delta=USD +35.86, drawdown delta=+0.0001.
- old_thin: trades=9, EV delta=-0.0362, PnL delta=USD -631.71, drawdown delta=+0.0000.

## Closeout

Related trials: exp-20260711-019, exp-20260711-020, exp-20260711-023, exp-20260712-009, exp-20260713-008, exp-20260713-010.
Decision: reject and park this fixed recipe. Reopen only after at least three newly audit-ready official sources each have all three canonical windows and at least 20 expected settled trades, then consume them in one batch; a materially different gate shape is the other legal exit.
Reproduce: .\.venv\Scripts\python.exe -B quant\experiments\exp_20260714_002_official_safety_event_response_batch.py
