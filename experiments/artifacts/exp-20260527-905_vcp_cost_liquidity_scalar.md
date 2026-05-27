# exp-20260527-905 VCP Cost/Liquidity Scalar

Decision: `rejected_vcp_cost_liquidity_scalar`.

Single causal variable: high expected-cost paper-notional scalar on the
already accepted VCP top-2 rank-notional paper trades.

## Sweep

| Variant | Gate | Adjusted | dEV vs source | dPnL vs source | EV regressed | PnL regressed | Max DD worse |
|---|:---:|---:|---:|---:|---:|---:|---:|
| baseline_cost_scalar_1p00 | fail | 0 | +0.0000 | $+0.00 | - | - | +0.0000% |
| high_cost_scalar_0p80 | fail | 32 | -0.3404 | $-5,090.62 | late_strong,mid_weak,old_thin | late_strong,mid_weak,old_thin | +0.2400% |
| high_cost_scalar_1p10 | fail | 32 | +0.1606 | $+2,545.29 | - | - | +0.0000% |
| high_cost_scalar_1p20 | fail | 32 | +0.3158 | $+5,090.62 | - | - | -0.0100% |
| high_cost_scalar_1p30 | fail | 32 | +0.4808 | $+7,635.91 | - | - | -0.0100% |

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 5.2987 | 5.3489 | +0.0502 | $118,539.57 | $119,126.01 | $+586.44 |
| mid_weak | 4.0371 | 4.3984 | +0.3613 | $105,956.79 | $111,067.85 | $+5,111.06 |
| old_thin | 0.8496 | 0.9189 | +0.0693 | $47,997.15 | $49,935.56 | $+1,938.41 |

## Gate 4

```json
{
  "adjusted_guard_passed": true,
  "adjusted_trade_count": 32,
  "adjusted_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "aggregate_ev_delta_vs_source": 0.4808,
  "aggregate_pnl_delta_vs_source": 7635.91,
  "failed_reasons": [
    "did_not_lift_source_ev_by_5pct"
  ],
  "max_drawdown_worse_vs_source": -0.0001,
  "max_drawdown_worse_vs_source_guardrail": 0.005,
  "min_ev_lift_required": 0.50927,
  "min_ev_lift_vs_source": 0.05,
  "minimum_adjusted_trades": 20,
  "minimum_adjusted_windows": 3,
  "passed": false,
  "source_ev_sum": 10.1854,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.178763,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.104514,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "windows_ev_regressed": [],
  "windows_pnl_regressed": []
}
```

## Production Impact

```json
{
  "alters_candidate_ranking": false,
  "alters_core_sizing": false,
  "alters_exits": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "backtester_adapter_changed": false,
  "default_off_paper_only": true,
  "production_orders_changed": false,
  "production_signal_path_changed": false,
  "production_watchlist_changed": false,
  "promotion_blocker": "If retained, implement the same cost/liquidity scalar through quant/volatility_contraction_paper_sleeve.py plus parity tests. This replay does not alter production/default-off behavior.",
  "replay_only": true,
  "research_replay_alters_paper_notional": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false,
  "trade_enabled": false
}
```

No JavaScript was used.
