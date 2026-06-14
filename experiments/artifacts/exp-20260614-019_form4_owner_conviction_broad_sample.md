# Form 4 Owner-Conviction Broad Sample

- experiment_id: `exp-20260614-019`
- timestamp: `2026-06-14T16:16:33+00:00`
- decision: `rejected_directional_but_unstable`
- status: `rejected`

## Hypothesis

Broad PIT Form 4 open-market purchases where the bought shares are at least 10% of the reporting owner's post-transaction holdings may isolate higher conviction insider demand than broad clustered buying, improving candidate-pool event-sleeve EV without adding noisy tickers.

## Three-Window Results

| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Event PnL | Event trades | Win rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.3199 | 0.1571 | $117,072.92 | $120,088.31 | $2,092.06 | 11 | 83.33% -> 72.41% |
| mid_weak | 2.1402 | 2.0639 | -0.0763 | $78,110.11 | $76,726.29 | $-1,656.92 | 12 | 52.38% -> 42.42% |
| old_thin | 0.5911 | 0.5284 | -0.0627 | $39,667.96 | $37,213.59 | $-2,454.36 | 11 | 40.91% -> 42.42% |

## Aggregate

```json
{
  "after_ev_sum": 7.9122,
  "after_pnl_sum": 234028.19,
  "after_trade_count": 95,
  "aggregate_ev_delta": 0.0181,
  "aggregate_ev_delta_pct": 0.002293,
  "aggregate_pnl_delta": -822.8,
  "aggregate_pnl_delta_pct": -0.003503,
  "baseline_ev_sum": 7.8941,
  "baseline_pnl_sum": 234850.99,
  "baseline_trade_count": 61,
  "event_trade_count": 34,
  "windows_ev_improved": 1,
  "windows_ev_regressed": 2,
  "windows_pnl_improved": 1,
  "windows_pnl_regressed": 2
}
```

## Gate

```json
{
  "aggregate_positive": false,
  "material_aggregate": false,
  "no_majority_ev_regression": false,
  "passed_replay_lead": false,
  "sample_guard_min_trades": 8,
  "sample_guard_passed": true,
  "selected_event_trades": 34,
  "single_ticker_positive_share": 0.3305,
  "single_ticker_positive_share_guard": "<= 0.50",
  "zero_ev_regression": false
}
```

## Decision

The owner-conviction discriminator had a positive partial read but failed the stability/sample gates, so it should not be promoted or retuned on this sample.

## Post-Run Reflection

- why_result_happened: Owner-conviction ratio selected commitment but not stable favorable drift: late_strong benefited, while mid_weak and old_thin both lost event PnL and regressed EV. The likely mechanism is that a large buy relative to a small post-transaction holding can identify insiders adding risk after weakness or in structurally stressed issuers, so the ratio is not a standalone quality edge.
- forbidden_near_neighbor_retry: Do not sweep the 10% owner-conviction floor, the $100k value floor, 10b5-1 handling, event capacity, notional, or hold days on the same broad archive.
- new_evidence_required: A valid retry needs a different evidence source, such as forward paper outcomes for this exact rule or an orthogonal quality signal like verified CEO/CFO non-plan buys paired with fundamental confirmation from a shared default-off helper.

## Production Impact

```json
{
  "alters_candidate_ranking": false,
  "alters_exits": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_sizing": false,
  "backtester_adapter_changed": false,
  "daily_snapshot_changed": false,
  "parity_test_added": false,
  "production_consistency_read": "No live/default production surface changed. A positive replay result is only a lead until the exact rule is moved to a shared default-off helper used by both historical replay and daily paper snapshots.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false,
  "trade_enabled": false
}
```
