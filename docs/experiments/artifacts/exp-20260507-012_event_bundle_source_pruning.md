# exp-20260507-012 Event-Bundle Source Pruning

Replay-only alpha search. This tests whether source pruning improves the already promising default-off event bundle.

## Variant Summary

| Variant | Sources | EV Sum | EV Delta vs Core | PnL Delta vs Core | Event Trades | Decision Note |
|---|---|---:|---:|---:|---:|---|
| full_bundle | form4_meaningful_purchase, sec_negative_reaction, sec_governance_procedural | 6.6147 | 0.9875 | $16,275.66 | 27 | passes_core_gate |
| sec_negative_only | sec_negative_reaction | 6.1842 | 0.5570 | $8,942.65 | 14 | passes_core_gate |
| sec_governance_only | sec_governance_procedural | 6.0737 | 0.4465 | $8,216.50 | 13 | passes_core_gate |
| form4_only | form4_meaningful_purchase | 5.6272 | 0.0000 | $0.00 | 0 | does_not_clear_core_gate |
| sec_negative_plus_governance | sec_negative_reaction, sec_governance_procedural | 6.6147 | 0.9875 | $16,275.66 | 27 | passes_core_gate |
| sec_negative_plus_form4 | sec_negative_reaction, form4_meaningful_purchase | 6.1842 | 0.5570 | $8,942.65 | 14 | passes_core_gate |
| governance_plus_form4 | sec_governance_procedural, form4_meaningful_purchase | 6.0737 | 0.4465 | $8,216.50 | 13 | passes_core_gate |

## Full Bundle vs Best Pruned

```json
{
  "by_window": {
    "late_strong": {
      "drawdown_improvement_pct": 0.0,
      "ev_delta_pct": 0.0,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.0,
      "sharpe_daily_delta": 0.0,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "mid_weak": {
      "drawdown_improvement_pct": 0.0,
      "ev_delta_pct": 0.0,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.0,
      "sharpe_daily_delta": 0.0,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "old_thin": {
      "drawdown_improvement_pct": 0.0,
      "ev_delta_pct": 0.0,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.0,
      "sharpe_daily_delta": 0.0,
      "trade_count_increased_with_win_rate_not_down": false
    }
  },
  "delta": {
    "after_ev_sum": 6.6147,
    "after_pnl_sum": 183623.61,
    "aggregate_ev_delta": 0.0,
    "aggregate_ev_delta_pct": 0.0,
    "aggregate_pnl_delta": 0.0,
    "aggregate_pnl_delta_pct": 0.0,
    "before_ev_sum": 6.6147,
    "before_pnl_sum": 183623.61,
    "by_window": {
      "late_strong": {
        "expected_value_score": 0.0,
        "max_drawdown_pct": 0.0,
        "sharpe_daily": 0.0,
        "survival_rate": 0.0,
        "total_pnl": 0.0,
        "total_return_pct": 0.0,
        "trade_count": 0.0,
        "win_rate": 0.0
      },
      "mid_weak": {
        "expected_value_score": 0.0,
        "max_drawdown_pct": 0.0,
        "sharpe_daily": 0.0,
        "survival_rate": 0.0,
        "total_pnl": 0.0,
        "total_return_pct": 0.0,
        "trade_count": 0.0,
        "win_rate": 0.0
      },
      "old_thin": {
        "expected_value_score": 0.0,
        "max_drawdown_pct": 0.0,
        "sharpe_daily": 0.0,
        "survival_rate": 0.0,
        "total_pnl": 0.0,
        "total_return_pct": 0.0,
        "trade_count": 0.0,
        "win_rate": 0.0
      }
    },
    "windows_ev_improved": 0,
    "windows_ev_regressed": 0,
    "windows_pnl_improved": 0,
    "windows_pnl_regressed": 0
  },
  "passed": false,
  "rule": "EV first across the three canonical backtesting.md windows; no EV regression, majority-window improvement, plus one Gate 4 materiality trigger.",
  "sources": [
    "sec_negative_reaction",
    "sec_governance_procedural"
  ],
  "variant": "sec_negative_plus_governance"
}
```

## Decision

Rejected: the best pruned source set (sec_negative_plus_governance) did not beat the full three-source frozen event bundle across the canonical windows. Source pruning adds selection complexity without improving the current strongest event alpha surface.
