# exp-20260531-023 Alpha-Score Market-Regime Paper Adapter

Decision: `accepted_alpha_score_market_regime_default_off_adapter`.

Single variable: add a shared production-visible default-off adapter for the fixed exp021 alpha_score market-regime $4,000 paper source. No score weights, thresholds, hold period, market gate, core ranking, sizing, exits, LLM/news, watchlists, or live orders changed.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.7091 | +0.5463 | $117,072.92 | $124,108.18 | $+7,035.26 | +0.0000 | 52 | 154 |
| mid_weak | 2.1402 | 2.8448 | +0.7046 | $78,110.11 | $90,603.09 | $+12,492.98 | -0.0024 | 62 | 287 |
| old_thin | 0.5911 | 0.9841 | +0.3930 | $39,667.96 | $52,910.24 | $+13,242.28 | -0.0062 | 37 | 174 |

## Aggregate

- EV delta: `1.6439` (`0.208244`)
- PnL delta: `$32770.52` (`0.139537`)
- target trades: `151` across `3` windows
- max drawdown delta max: `0.0`
- max single positive share: `0.274512`
- positive PnL HHI: `0.18724`

## Adapter Parity

```json
{
  "adapter_module": "quant/alpha_score_market_regime_paper_sleeve.py",
  "alters_core_backtester": false,
  "alters_live_watchlists": false,
  "alters_production_orders": false,
  "backtester_adapter_changed": false,
  "default_enabled": false,
  "parity_note": "The adapter writes only default-off paper candidates, ledger state, daily artifact fields, and report text. Core entry ranking, sizing, exits, LLM/news, watchlists, and order paths do not read it.",
  "parity_test_added": true,
  "report_adapter_changed": true,
  "run_adapter_changed": true,
  "shared_adapter_added": true,
  "source_replay_artifact": "experiments/artifacts/exp-20260531-021_full_universe_alpha_score_market_regime_safe_notional.md",
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
    "max_single_positive_pnl_share": 0.274512,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.18724,
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

Accepted as a production-visible default-off paper adapter. The 3-window economics are the accepted exp021 replay result; this run does not activate live/default orders. The next evidence is forward replacement-value rows from the shared adapter, not another threshold/notional retune.

No JavaScript was used.
