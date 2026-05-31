# exp-20260531-029 Accepted-Source Consensus Adapter

Decision: `accepted_source_consensus_default_off_adapter`.

Single variable: promote exp026's accepted-source consensus candidate pool into a shared default-off adapter. No live orders, core ranking, sizing, exits, LLM/news, score weights, top-N, market gate, hold period, or base notional changed.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Consensus trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.4400 | +0.2772 | $117,072.92 | $120,619.16 | $+3,546.24 | -0.0010 | 9 |
| mid_weak | 2.1402 | 2.2948 | +0.1546 | $78,110.11 | $80,516.19 | $+2,406.08 | -0.0024 | 15 |
| old_thin | 0.5911 | 0.7165 | +0.1254 | $39,667.96 | $44,233.94 | $+4,565.98 | -0.0058 | 13 |

## Aggregate

- EV delta vs core: `0.5572` (`0.070584`)
- PnL delta vs core: `$10518.3` (`0.044787`)
- consensus trades: `37` across `3` windows
- consensus total PnL: `$10518.3`
- max single positive share: `0.256978`
- positive PnL HHI: `0.154989`

## Adapter Parity

```json
{
  "adapter_module": "quant/accepted_source_consensus_paper_sleeve.py",
  "alters_core_backtester": false,
  "alters_live_watchlists": false,
  "alters_production_orders": false,
  "backtester_adapter_changed": false,
  "default_enabled": false,
  "parity_note": "Production computes the same accepted-source consensus candidate field from same-day VBB and FINRA/IWM paper snapshots. The field only affects this separate default-off paper ledger.",
  "parity_test_added": true,
  "report_adapter_changed": true,
  "run_adapter_changed": true,
  "shared_adapter_changed": true,
  "source_snapshots": [
    "VOLUME_BREADTH_BREAKOUT_PAPER",
    "FINRA_IWM_CONFIRMED_PAPER"
  ],
  "trade_enabled": false
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [],
  "max_drawdown_worse": -0.001,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": true,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.256978,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.154989,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 37,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 3,
  "windows_ev_regressed": 0,
  "windows_pnl_regressed": 0
}
```

## Interpretation

Accepted as a production-visible default-off adapter. The 3-window economics are the positive exp026 replay result; this run does not activate live/default orders. The next evidence is forward replacement-value rows from the shared adapter, not another alpha_score/source-overlap retune.

No JavaScript was used.
