# exp-20260520-028 context_field_v1

Decision: `observed_only_launch_recorded`.

## Hypothesis

State-surface scalar mining should pause until candidates expose a PIT-safe concentration field for same ticker, sector, theme, recent winner contribution, and queue independence.

## Trial Accounting

- mechanism_family: `state_surface_concentration`
- trial_family: `state_surface_concentration_context`
- changed_variable: `state_surface_concentration_context`
- prior_trial_count: `21`
- multiple_testing_risk_bucket: `minimal`

## Current Evidence

```json
{
  "current_snapshot": {
    "asof_date": "2026-05-19",
    "candidate_count": 0,
    "closed_outcome_count": null,
    "closed_position_count": 0,
    "data_source": {
      "decision_date": "2026-05-19",
      "source": "ohlcv_by_ticker",
      "status": "loaded",
      "ticker_count": 57
    },
    "forward_paper_gate": {
      "checks": {
        "min_closed_trades": false,
        "min_win_rate": false,
        "positive_net_pnl": false,
        "tail_gate": true
      },
      "metrics": {
        "closed_trades": 0,
        "realized_pnl": 0,
        "win_rate": null
      },
      "passed": false,
      "reasons": [
        "min_closed_trades",
        "min_win_rate",
        "positive_net_pnl"
      ],
      "status": "blocked",
      "tail_diagnostics": {
        "gate_report": {
          "hard_failures": [
            "insufficient_sample",
            "non_positive_expected_value"
          ],
          "passed": false,
          "preferred_distribution_prefix": "pnl",
          "thresholds": {
            "max_drawdown_pct": 0.12,
            "max_excess_kurtosis": 12.0,
            "max_hhi_concentration": 0.35,
            "max_live_vs_backtest_r_gap": 0.5,
            "max_top_5_contribution_pct": 0.6,
            "min_avg_r_multiple": 0.0,
            "min_expected_value_usd": 0.0,
            "min_sharpe_ratio": 0.75,
            "min_skewness": -1.5,
            "min_tail_ratio": 0.8,
            "min_trades_for_promotion": 15
          },
          "warnings": []
        },
        "metrics_for_gates": {
          "expected_value_usd": 0.0,
          "pnl_excess_kurtosis": null,
          "pnl_hhi_concentration": null,
          "pnl_skewness": null,
          "pnl_tail_ratio": null,
          "pnl_top_5_contribution_pct": null,
          "total_pnl": 0,
          "total_trades": 0,
          "win_rate": null
        },
        "notes": [
          "True R-multiple is unavailable for this default-off paper sleeve; PnL distribution is used for forward promotion diagnostics.",
          "This diagnostics block does not alter orders, candidates, rank, notional, or paper fills."
        ],
        "read_only": true,
        "schema_version": 1,
        "scope": "state_surface_forward_paper_closed_positions"
      },
      "trade_enabled_after_gate": false
    },
    "open_position_count": 3,
    "path": "data/paper_sleeves/state_surface/snapshots.jsonl",
    "pending_count": 0,
    "primary_closed_outcome_count": null,
    "realized_inverse_pnl_to_date": null,
    "realized_no_trade_value_to_date": null,
    "realized_pnl_to_date": 0
  },
  "field_status": "implemented_in_shared_paper_sleeve_next_snapshot",
  "sample_concentration_context": {
    "alters_orders": false,
    "alters_sizing": false,
    "notes": "Observation field only; future scalar/profile changes still need the strict state-surface aggregate EV gate.",
    "pit_safe": true,
    "queue_candidate_count": 2,
    "queue_independence_bucket": "low",
    "read_only": true,
    "recent_winner_contribution": {
      "closed_winner_count": 0,
      "positive_pnl_total": 0,
      "same_sector_closed_winner_count": 0,
      "same_sector_positive_pnl": 0,
      "same_sector_positive_pnl_share": null,
      "same_ticker_closed_winner_count": 0,
      "same_ticker_positive_pnl": 0,
      "same_ticker_positive_pnl_share": null
    },
    "rule_version": "state_surface_concentration_context_v1",
    "same_sector_candidate_count": 2,
    "same_sector_queue_share": 1.0,
    "same_surface_candidate_count": 2,
    "same_surface_queue_share": 1.0,
    "same_ticker_candidate_count": 1,
    "schema_version": 1,
    "sector": "Technology",
    "theme": "rotation",
    "ticker": "SAMPLE",
    "top_queue_sector": "Technology",
    "top_queue_sector_count": 2,
    "top_queue_surface": "rotation",
    "top_queue_surface_count": 2,
    "trade_enabled": false
  }
}
```

## Next Evidence Needed

Wait for selected paper candidates carrying the field, then only test scalars if the strict >10% aggregate EV gate is pre-registered.
