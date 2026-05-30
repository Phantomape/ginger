# exp-20260530-004 VCP Forward Replacement-Value Readiness Audit

Decision: `observed_only_vcp_forward_replacement_value_not_ready`.

The VCP forward replacement-value surface is wired but not activation ready: current production snapshots contain no forward candidate or closed outcome sample, so the accepted paper sleeve must continue observing instead of being promoted or retuned.

## Readiness

- Latest snapshot as-of: `2026-05-28`.
- Snapshot rows: `6`.
- Latest candidate count: `0`.
- Max candidate count: `0`.
- Closed forward outcomes: `0` / `20` required.
- Closed PnL: `0.0`.
- Forward gate passed: `False`.
- Default-off attribution surface present: `True`.
- Blockers: `max_single_ticker_positive_share, max_top5_positive_share, min_closed_trades, min_win_rate, needs_closed_forward_outcomes, needs_replacement_value_vs_core_or_cash, positive_net_pnl`.

## Snapshot Summary

```json
{
  "asof_end": "2026-05-28",
  "asof_start": "2026-05-25",
  "duplicate_asof_dates": [
    "2026-05-25",
    "2026-05-26"
  ],
  "exists": true,
  "forward_gate_passed_count": 0,
  "gate_blocker_counts": {
    "max_single_ticker_positive_share": 6,
    "max_top5_positive_share": 6,
    "min_closed_trades": 6,
    "min_win_rate": 6,
    "positive_net_pnl": 6
  },
  "latest": {
    "asof_date": "2026-05-28",
    "candidate_count": 0,
    "closed_position_count": 0,
    "forward_paper_gate": {
      "checks": {
        "max_single_ticker_positive_share": false,
        "max_top5_positive_share": false,
        "min_closed_trades": false,
        "min_win_rate": false,
        "positive_net_pnl": false
      },
      "metrics": {
        "closed_trades": 0,
        "realized_pnl": 0,
        "single_ticker_positive_share": null,
        "top5_positive_share": null,
        "win_rate": null
      },
      "passed": false,
      "reasons": [
        "min_closed_trades",
        "positive_net_pnl",
        "min_win_rate",
        "max_single_ticker_positive_share",
        "max_top5_positive_share"
      ],
      "status": "blocked",
      "trade_enabled_after_gate": false
    },
    "generated_at": "2026-05-29T04:07:41+00:00",
    "market_confirmation": {
      "alters_orders": false,
      "asof_date": "2026-05-28",
      "known_at": "after_signal_date_close_before_next_open_paper_entry",
      "lookback_trading_days": 20,
      "passed": true,
      "qqq_asof_date": "2026-05-28",
      "qqq_minus_spy_return_20d": 0.051443,
      "qqq_return_20d": 0.1119,
      "rule_version": "volatility_contraction_qqq_gt_spy20_v1",
      "spy_asof_date": "2026-05-28",
      "spy_return_20d": 0.060457,
      "status": "ok",
      "trade_enabled": false
    },
    "open_position_count": 0,
    "pending_count": 0,
    "realized_pnl_to_date": 0.0,
    "replacement_value_report": {
      "alters_orders": false,
      "by_ticker": {},
      "candidate_count": 0,
      "closed_count": 0,
      "closed_pnl": 0,
      "displaced_resource_default": "paper_cash_slot",
      "forward_outcome_horizon_days": 10,
      "open_count": 0,
      "open_unrealized_pnl": 0,
      "pending_count": 0,
      "positive_closed_pnl": 0,
      "promotion_blockers": [
        "needs_closed_forward_outcomes",
        "needs_replacement_value_vs_core_or_cash"
      ],
      "read_only": true,
      "rule_version": "volatility_contraction_forward_replacement_value_v1",
      "schema_version": 1,
      "skipped_count": 0,
      "top_ticker_positive_pnl_share": null,
      "trade_enabled": false
    },
    "unrealized_pnl": 0.0
  },
  "market_confirmation_passed_count": 6,
  "max_candidate_count": 0,
  "path": "data/paper_sleeves/volatility_contraction/snapshots.jsonl",
  "replacement_blocker_counts": {
    "needs_closed_forward_outcomes": 6,
    "needs_replacement_value_vs_core_or_cash": 6
  },
  "snapshot_count": 6,
  "total_candidate_count_across_snapshots": 0,
  "total_closed_today_count": 0,
  "total_filled_count": 0,
  "total_new_pending_count": 0,
  "unique_asof_dates": 4
}
```

## Gate 4 Evidence

```json
{
  "blockers": [
    "max_single_ticker_positive_share",
    "max_top5_positive_share",
    "min_closed_trades",
    "min_win_rate",
    "needs_closed_forward_outcomes",
    "needs_replacement_value_vs_core_or_cash",
    "positive_net_pnl"
  ],
  "candidate_observation_mature": false,
  "closed_forward_outcomes": 0,
  "closed_outcomes_ok": false,
  "closed_pnl": 0.0,
  "closed_pnl_positive": false,
  "default_off_attribution_surface_present": true,
  "default_off_surface_gate_passed": false,
  "forward_paper_gate_passed": false,
  "forward_paper_gate_present": true,
  "gate_blockers": [
    "min_closed_trades",
    "positive_net_pnl",
    "min_win_rate",
    "max_single_ticker_positive_share",
    "max_top5_positive_share"
  ],
  "latest_asof_date": "2026-05-28",
  "latest_candidate_count": 0,
  "ledger_present": true,
  "max_candidate_count": 0,
  "min_closed_forward_outcomes": 20,
  "replacement_blockers": [
    "needs_closed_forward_outcomes",
    "needs_replacement_value_vs_core_or_cash"
  ],
  "replacement_value_report_has_no_blockers": false,
  "replacement_value_report_present": true,
  "snapshot_count": 6,
  "snapshots_present": true,
  "state_closed_positions": 0,
  "state_open_positions": 0,
  "state_pending_entries": 0,
  "surface_blockers": [
    "max_single_ticker_positive_share",
    "max_top5_positive_share",
    "min_closed_trades",
    "min_win_rate",
    "positive_net_pnl"
  ]
}
```

## Repro

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260530_004_vcp_forward_replacement_value_readiness_audit.py
```

## Related Files

- `quant/experiments/exp_20260530_004_vcp_forward_replacement_value_readiness_audit.py`
- `data/paper_sleeves/volatility_contraction/state.json`
- `data/paper_sleeves/volatility_contraction/snapshots.jsonl`
- `data/daily/signals/quant/quant_signals_20260528.json`
- `data/experiments/exp-20260530-004/vcp_forward_replacement_value_readiness_audit.json`
- `experiments/logs/exp-20260530-004.json`
- `experiments/tickets/exp-20260530-004.json`
- `docs/experiments/tickets/exp-20260530-004.json`
- `experiments/cards/exp-20260530-004.md`
- `experiments/artifacts/exp-20260530-004_vcp_forward_replacement_value_readiness_audit.md`
- `experiments/manifests/exp-20260530-004.json`
