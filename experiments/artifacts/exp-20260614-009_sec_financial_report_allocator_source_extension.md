# exp-20260614-009 SEC financial-report allocator source extension

Decision: `rejected_sec_financial_report_allocator_source_extension`

## Hypothesis

candidate_pool/allocation: SEC financial-report positive T+1 drift may add distinct free event-information replacement value when admitted as a fixed rank-2 source inside the accepted allocator.

## Three-Window Direct Result

| Window | Accepted EV | SEC EV | dEV | Accepted PnL | SEC PnL | dPnL | SEC selected | Changed selections |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.674900 | 5.754500 | +0.079600 | $123,101.71 | $124,023.06 | $+921.35 | 15 | 10 |
| mid_weak | 2.897700 | 2.897400 | -0.000300 | $91,406.39 | $91,398.28 | $-8.11 | 7 | 5 |
| old_thin | 1.035900 | 1.020200 | -0.015700 | $54,522.11 | $53,978.63 | $-543.48 | 15 | 11 |

## Aggregate

- Direct EV delta vs accepted allocator: `+0.063600`
- Direct PnL delta vs accepted allocator: `$+369.76`
- Aggregate EV delta vs core: `+1.778000`
- Aggregate PnL delta vs core: `$+34,548.98`
- Numeric Gate 4 passed: `False`
- Gate failed reasons: `direct_window_ev_regression_vs_accepted_allocator, direct_window_pnl_regression_vs_accepted_allocator, direct_drawdown_drift_too_high, accepted_allocator_ev_comparator_not_beaten, accepted_allocator_pnl_comparator_not_beaten, accepted_allocator_window_comparator_regression`

## Production Impact

{
  "adapter_status": "replay_only_sec_financial_report_allocator_source_scout",
  "alters_candidate_ranking": false,
  "alters_exits": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_sizing": false,
  "backtester_adapter_changed": false,
  "daily_snapshot_exposed": false,
  "default_off_paper_only": true,
  "execution_envelope": {
    "base_notional": 4000.0,
    "daily_entry_slots": 1,
    "hold_days": 10,
    "kill_switch_drawdown_pct": 0.15,
    "max_concurrent": 8,
    "order_semantics": "next_open_paper_only_no_orders_emitted",
    "same_ticker_cooldown_days": 12
  },
  "live_ready": false,
  "live_realism_evaluated": true,
  "parity_note": "Replay-only source-extension scout. SEC source rows are rebuilt from the existing financial-report positive T+1 queue and replayed under the accepted allocator's $4k, 10-day envelope. No shared allocator helper or run.py source snapshot is changed unless Gate 4 passes and the behavior is promoted through shared daily parity.",
  "parity_test_added": false,
  "production_orders_changed": false,
  "production_signal_path_changed": false,
  "production_watchlist_changed": false,
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false,
  "trade_enabled": false,
  "uses_free_non_ohlcv": true,
  "uses_free_ohlcv_only": false,
  "uses_llm": false
}

## Post-Run Reflection

{
  "forbidden_near_neighbor_retry": "Do not retry by changing SEC source rank, T+1 excess threshold, SEC event notional, allocator top-N, notional, hold days, cooldown, or accepted source ranks on the frozen windows.",
  "negative_reflection": "If rejected, SEC financial-report drift should stay in its standalone sleeve rather than being forced into the accepted allocator. If positive, no retention is valid without shared daily allocator-source parity.",
  "new_evidence_required": "A retry needs closed forward source-competition replacement rows, a materially different PIT SEC event-quality field, or a shared-helper promotion only if this exact fixed bundle first passes Gate 4.",
  "why_result_happened": "The standalone SEC financial-report sleeve can remain useful, but its event rows did not add robust incremental replacement value after lagged consensus and the accepted allocator stack. The likely failure mode is overlap or displacement rather than bad SEC data."
}
