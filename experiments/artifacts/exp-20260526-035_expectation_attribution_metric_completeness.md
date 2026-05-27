# exp-20260526-035 Attribution Metric Completeness Probe

Decision: `observed_only_data_gap`.

Observed-only alpha research. No entries, exits, ranking, sizing, LLM/news, paper sleeves, or orders changed.

## Gate

```json
{
  "decision": "observed_only_data_gap",
  "missing_promotion_metrics": [
    "avg_R",
    "max_drawdown_contribution",
    "replacement_value_vs_next_core_slot"
  ],
  "promotion_gate_passed": false,
  "reason": "promotion_critical_metrics_missing"
}
```

## Coverage

```json
{
  "available_proxy_metrics": {
    "10d_avg_pnl_proxy": 80.45,
    "10d_total_pnl_proxy": 1287.16,
    "5d_avg_pnl_proxy": 7.64,
    "5d_total_pnl_proxy": 251.97
  },
  "metric_completeness": {
    "available_metrics": {
      "avg_pnl_proxy": {
        "available": true,
        "source": "forward_outcomes.*.pnl_proxy"
      },
      "avg_return": {
        "available": true,
        "source": "forward_outcomes.*.return"
      },
      "max_single_ticker_positive_contribution": {
        "available": true,
        "source": "forward_outcomes.*.pnl_proxy"
      },
      "tail_loss": {
        "available": true,
        "source": "forward_outcomes.*.return"
      },
      "top5_positive_contribution": {
        "available": true,
        "source": "forward_outcomes.*.pnl_proxy"
      },
      "total_pnl_proxy": {
        "available": true,
        "source": "forward_outcomes.*.pnl_proxy"
      },
      "win_rate": {
        "available": true,
        "source": "forward_outcomes.*.return"
      },
      "worst_row": {
        "available": true,
        "source": "forward_outcomes.*.return"
      }
    },
    "missing_promotion_metrics": {
      "avg_R": {
        "available": false,
        "missing_fields": [
          "entry_price",
          "initial_stop",
          "initial_risk_per_share"
        ]
      },
      "max_drawdown_contribution": {
        "available": false,
        "missing_fields": [
          "trade_equity_curve",
          "portfolio_drawdown_contribution"
        ]
      },
      "replacement_value_vs_next_core_slot": {
        "available": false,
        "missing_fields": [
          "old_alpha_score_rank",
          "next_rejected_core_candidate",
          "slot_queue_state"
        ]
      }
    }
  },
  "primary_positive_7d_rows": 41
}
```

## Next Evidence Needed

Join watchlist rows to PIT entry risk, portfolio equity contribution, and next-core-slot queue state.

No JavaScript was used.
