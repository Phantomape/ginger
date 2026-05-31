# exp-20260531-025 Alpha-Score Source-Consensus Adapter

Decision: `accepted_alpha_score_source_consensus_default_off_adapter`.

Single variable: promote exp024's source-consensus 1.25x paper-notional support into the shared default-off adapter. No live orders, core ranking, sizing, exits, LLM/news, score weights, top-N, market gate, hold period, or base notional changed.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Consensus trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.7556 | +0.5928 | $117,072.92 | $124,854.08 | $+7,781.16 | +0.0000 | 52 | 5 |
| mid_weak | 2.1402 | 2.8788 | +0.7386 | $78,110.11 | $91,103.22 | $+12,993.11 | -0.0029 | 62 | 9 |
| old_thin | 0.5911 | 1.0206 | +0.4295 | $39,667.96 | $54,004.65 | $+14,336.69 | -0.0074 | 37 | 10 |

## Aggregate

- EV delta vs core: `1.7609` (`0.223065`)
- PnL delta vs core: `$35110.96` (`0.149503`)
- incremental EV vs accepted exp021: `0.117`
- incremental PnL vs accepted exp021: `$2340.44`
- supported trades: `24` across `3` windows
- incremental support PnL: `$2340.43`
- max single positive share: `0.276114`
- positive PnL HHI: `0.187684`

## Adapter Parity

```json
{
  "adapter_module": "quant/alpha_score_market_regime_paper_sleeve.py",
  "alters_core_backtester": false,
  "alters_live_watchlists": false,
  "alters_production_orders": false,
  "backtester_adapter_changed": false,
  "default_enabled": false,
  "parity_note": "Production computes the source-consensus support from the same-day default-off VBB and FINRA/IWM paper snapshots before alpha-score pending entries are created. The field only changes paper notional and metadata.",
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
  "max_drawdown_worse": 0.0,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": true,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.276114,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.187684,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 151,
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

Accepted as a production-visible default-off adapter increment. The 3-window economics are the accepted exp024 replay result; this run does not activate live/default orders. The next evidence is forward replacement-value rows from the shared adapter, not another alpha_score threshold/notional retune.

No JavaScript was used.
