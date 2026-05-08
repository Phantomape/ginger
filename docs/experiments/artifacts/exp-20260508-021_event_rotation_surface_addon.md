# exp-20260508-021 Event Rotation Surface Add-On

Decision: `rejected`
Best variant: `rotation_surface_3_0x`

## Hypothesis

Within the current default-off non-generic positive state-surface event add-on, rotation_breakout_leadership may be the highest-quality surface and may deserve more event satellite notional than the broad 2.0x scalar.

## Best Variant Vs Current Event Add-On

| Window | Current EV | Variant EV | Delta EV | Current PnL | Variant PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 4.5775 | 4.8916 | +0.3141 | $94,576.35 | $99,020.84 | $+4,444.49 |
| mid_weak | 2.2741 | 2.4913 | +0.2172 | $70,187.00 | $73,490.21 | $+3,303.21 |
| old_thin | 0.3959 | 0.4021 | +0.0062 | $28,900.28 | $29,140.48 | $+240.20 |

## Variant Summary Vs Current

| Variant | EV Delta | PnL Delta | Windows EV +/- | Gate | Touched | Single ticker share |
|---|---:|---:|---:|---|---:|---:|
| rotation_surface_2_5x | +0.2644 | $+3,993.95 | 3/0 | False | 7 | 0.5367 |
| rotation_surface_3_0x | +0.5375 | $+7,987.90 | 3/0 | True | 7 | 0.5367 |

## Coverage

```json
{
  "by_surface": {
    "broad_breadth_trend_persistence": {
      "tickers": [
        "CRDO",
        "GS",
        "MCD",
        "NOW"
      ],
      "total_pnl": 1998.0,
      "trade_count": 8
    },
    "mid_dispersion_selective_leadership": {
      "tickers": [
        "RTX"
      ],
      "total_pnl": 54.13,
      "trade_count": 1
    },
    "rotation_breakout_leadership": {
      "tickers": [
        "CRDO",
        "GE",
        "GS",
        "JPM",
        "LITE"
      ],
      "total_pnl": 8451.95,
      "trade_count": 7
    }
  },
  "event_trade_count": 27,
  "non_generic_positive_trade_count": 16,
  "rotation_surface_tickers": [
    "GS",
    "LITE",
    "GE",
    "CRDO",
    "JPM",
    "GS",
    "GS"
  ],
  "rotation_surface_total_pnl_before_scalar": 8451.95,
  "rotation_surface_trade_count": 7,
  "rule": "positive PIT state score and state_surface != balanced_state_leadership; treatment surface is rotation_breakout_leadership"
}
```

## Decision Rationale

Rejected for production: the rotation surface is directionally strong, but this replay is too sample-thin and concentrated to justify more same-sample event notional.

## Production Impact

Replay only. No production policy, backtester adapter, run adapter, candidate universe, ranking, sizing, stop, LLM, or news behavior changed.
