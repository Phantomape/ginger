# exp-20260528-011 Fundamental Growth + RS Shared Adapter

Decision: `accepted_candidate_shared_default_off_forward_adapter`.

Single variable: add the shared production-visible default-off paper adapter for the accepted Companyfacts operating-profit + RS alpha. No threshold, ranking, sizing, exit, or live/default order behavior was changed.

## Three-Window Source Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 7.3793 | +2.2165 | $117,072.92 | $139,758.70 | $+22,685.78 | -0.0086 | 99 |
| mid_weak | 2.1402 | 5.5164 | +3.3762 | $78,110.11 | $127,402.51 | $+49,292.40 | -0.0204 | 116 |
| old_thin | 0.5911 | 2.3293 | +1.7382 | $39,667.96 | $78,958.71 | $+39,290.75 | -0.0048 | 121 |

## Aggregate

```json
{
  "expected_value_score_delta_sum": 7.3309,
  "target_trade_count": 336,
  "total_pnl_delta_sum": 111268.93,
  "windows_ev_improved": 3,
  "windows_ev_regressed": 0
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_checks": [],
  "max_drawdown_worse": -0.0048,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": true,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.391352,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.249167,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 336,
  "target_trade_count_min": 30,
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

## Production / Backtest Boundary

- Backtest evidence source: `experiments/logs/exp-20260528-008.json`.
- Production adapter is default-off paper only: no live orders, no core signal generation, no core ranking, no sizing, no exits.
- Known-at boundary is explicit: Companyfacts filed date and OHLCV date must be <= signal date; paper entry is next available open.
- Any live activation still needs a separate promotion experiment after forward paper outcomes pass the gate.

No JavaScript was used.
