# exp-20260508-005 Event State Score Floor

Decision: `rejected`

Alpha search. Tests whether the current non-generic positive state-surface event add-on should require a higher PIT state-score floor.

## Best Variant Vs Current Score>0 Rule

| Window | Current EV | Variant EV | Delta EV | Current PnL | Variant PnL | Delta PnL | Eligible trades | Event PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.4473 | 4.4703 | +0.0230 | $93,038.80 | $93,130.86 | $+92.06 | 1 | $+10,449.98 |
| mid_weak | 2.2741 | 2.3007 | +0.0266 | $70,187.00 | $70,574.42 | $+387.42 | 5 | $+13,268.16 |
| old_thin | 0.3959 | 0.4259 | +0.0300 | $28,900.28 | $29,990.48 | $+1,090.20 | 2 | $+3,747.80 |

## Variant Summary Vs Current

| Variant | EV Sum Delta | PnL Delta | Windows EV Improved | Windows EV Regressed | Passed |
|---|---:|---:|---:|---:|---|
| non_generic_score_gt_025_2x | -0.0018 | $-130.57 | 0 | 1 | False |
| non_generic_score_gt_050_2x | +0.0796 | $+1,569.68 | 3 | 0 | False |
| non_generic_score_gt_075_2x | -0.0267 | $-17.15 | 2 | 1 | False |
| non_generic_score_gt_100_2x | -0.0267 | $-17.15 | 2 | 1 | False |

## Best Variant Vs Full Bundle

```json
{
  "after_ev_sum": 7.1969,
  "after_pnl_sum": 193695.76,
  "aggregate_ev_delta": 0.7078,
  "aggregate_ev_delta_pct": 0.109075,
  "aggregate_pnl_delta": 11609.7,
  "aggregate_pnl_delta_pct": 0.063759,
  "baseline_ev_sum": 6.4891,
  "baseline_pnl_sum": 182086.06,
  "by_window": {
    "late_strong": {
      "expected_value_score": 0.3507,
      "max_drawdown_pct": 0.0,
      "sharpe_daily": 0.15,
      "survival_rate": 0.0,
      "total_pnl": 4536.54,
      "total_return_pct": 0.0454,
      "trade_count": 0.0,
      "win_rate": 0.0
    },
    "mid_weak": {
      "expected_value_score": 0.2988,
      "max_drawdown_pct": -0.0016,
      "sharpe_daily": 0.22,
      "survival_rate": 0.0,
      "total_pnl": 4723.91,
      "total_return_pct": 0.0472,
      "trade_count": 0.0,
      "win_rate": 0.0
    },
    "old_thin": {
      "expected_value_score": 0.0583,
      "max_drawdown_pct": -0.0016,
      "sharpe_daily": 0.09,
      "survival_rate": 0.0,
      "total_pnl": 2349.25,
      "total_return_pct": 0.0235,
      "trade_count": 0.0,
      "win_rate": 0.0
    }
  },
  "windows_ev_improved": 3,
  "windows_ev_regressed": 0,
  "windows_pnl_improved": 3,
  "windows_pnl_regressed": 0
}
```

## Coverage

```json
{
  "by_surface": {
    "broad_breadth_trend_persistence": {
      "max_score": 1.491207,
      "min_score": 0.512714,
      "total_pnl": 3571.96,
      "trade_count": 5
    },
    "rotation_breakout_leadership": {
      "max_score": 1.956474,
      "min_score": 0.517798,
      "total_pnl": 8037.75,
      "trade_count": 3
    }
  },
  "by_window": {
    "late_strong": {
      "eligible_tickers": [
        "LITE"
      ],
      "eligible_total_pnl": 4536.55,
      "eligible_trade_count": 1
    },
    "mid_weak": {
      "eligible_tickers": [
        "CRDO",
        "GE",
        "GS",
        "MCD"
      ],
      "eligible_total_pnl": 4723.91,
      "eligible_trade_count": 5
    },
    "old_thin": {
      "eligible_tickers": [
        "CRDO",
        "GS"
      ],
      "eligible_total_pnl": 2349.25,
      "eligible_trade_count": 2
    }
  },
  "eligible_fraction": 0.2963,
  "eligible_surfaces": [
    "broad_breadth_trend_persistence",
    "rotation_breakout_leadership"
  ],
  "eligible_total_pnl": 11609.71,
  "eligible_trade_count": 8,
  "event_trade_count": 27,
  "generic_surface_not_eligible": "balanced_state_leadership",
  "rule": "state_feature_available and state_score > 0.5 and state_surface != balanced_state_leadership",
  "score_floor_exclusive": 0.5
}
```

## Decision Rationale

Rejected: non_generic_score_gt_050_2x was the best stricter floor but failed to beat the current score>0 add-on with stable three-window EV improvement and materiality. The current non-generic positive-score paper rule remains the better lead.

No production universe, ranking, sizing, exits, LLM, news, or order path changed.
