# exp-20260526-014 Shared Volume-Breadth Breakout Paper Adapter

Decision: `accepted_shared_volume_breadth_breakout_paper_adapter`.

Single variable: move the accepted replay definition into a shared default-off paper adapter with production/report exposure. The thresholds, top-1 ranking, $10k paper notional, next-open entry, and 10-trading-day close exit are unchanged from exp-20260526-013.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Breadth days | Tickers |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.5780 | +0.4152 | $117,072.92 | $121,255.25 | $+4,182.33 | -0.0022 | 8 | 12 | 23 |
| mid_weak | 2.1402 | 2.2780 | +0.1378 | $78,110.11 | $80,780.62 | $+2,670.51 | -0.0011 | 17 | 21 | 29 |
| old_thin | 0.5911 | 0.7505 | +0.1594 | $39,667.96 | $46,040.62 | $+6,372.66 | -0.0033 | 22 | 23 | 32 |

## Aggregate

- EV delta: `0.7124` (`0.090245`)
- PnL delta: `$13225.5` (`0.056314`)
- target trades: `47` across `3` windows
- max single positive share: `0.230268`
- positive PnL HHI: `0.151383`

## Shared Adapter Parity

```json
{
  "actual_metrics": {
    "expected_value_score_delta_sum": 0.7124,
    "target_trade_count": 47,
    "total_pnl_delta_sum": 13225.5
  },
  "checks": {
    "ev_delta_matches_exp013": true,
    "pnl_delta_matches_exp013": true,
    "shared_rule_version_present": true,
    "trade_count_matches_exp013": true
  },
  "failed": [],
  "passed": true,
  "reference_experiment": "exp-20260526-013",
  "reference_metrics": {
    "expected_value_score_delta_sum": 0.7124,
    "target_trade_count": 47,
    "total_pnl_delta_sum": 13225.5
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": -0.0011,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": true,
  "shared_adapter_replay_parity": {
    "actual_metrics": {
      "expected_value_score_delta_sum": 0.7124,
      "target_trade_count": 47,
      "total_pnl_delta_sum": 13225.5
    },
    "checks": {
      "ev_delta_matches_exp013": true,
      "pnl_delta_matches_exp013": true,
      "shared_rule_version_present": true,
      "trade_count_matches_exp013": true
    },
    "failed": [],
    "passed": true,
    "reference_experiment": "exp-20260526-013",
    "reference_metrics": {
      "expected_value_score_delta_sum": 0.7124,
      "target_trade_count": 47,
      "total_pnl_delta_sum": 13225.5
    }
  },
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.230268,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.151383,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 47,
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

## Production Impact

Shared default-off paper adapter only. `run.py`, the daily report, and default-off attribution can expose the same helper output, but trade_enabled remains false and no live/default order path changes.

No JavaScript was used.
