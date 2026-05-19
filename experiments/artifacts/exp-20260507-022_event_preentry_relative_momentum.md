# exp-20260507-022 Event Pre-Entry Relative Momentum

Decision: `rejected`

Replay-only alpha search. Tests whether the frozen event bundle should tilt notional toward event trades with stronger PIT-safe pre-entry relative momentum.

## Best Variant Vs Full Bundle

| Window | Full EV | Variant EV | Delta EV | Full PnL | Variant PnL | Delta PnL | Event trades | Event PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.1196 | 4.3625 | +0.2429 | $88,594.32 | $91,648.20 | $+3,053.88 | 9 | $+8,967.30 |
| mid_weak | 2.0019 | 1.9963 | -0.0056 | $65,850.51 | $65,668.70 | $-181.81 | 11 | $+8,130.41 |
| old_thin | 0.3676 | 0.3992 | +0.0316 | $27,641.23 | $28,924.55 | $+1,283.32 | 7 | $+2,681.86 |

## Variant Summary

| Variant | EV Sum Vs Full | PnL Delta Vs Full | Windows EV Improved | Windows EV Regressed | Passed |
|---|---:|---:|---:|---:|---|
| preentry_rs_positive_125_075 | +0.1230 | $+2,204.50 | 3 | 0 | False |
| preentry_rs_positive_150_050 | +0.2472 | $+4,409.01 | 3 | 0 | False |
| preentry_rs_2pct_150_050 | +0.2689 | $+4,155.39 | 2 | 1 | False |

## Coverage

```json
{
  "event_trade_count": 27,
  "feature_available_count": 27,
  "feature_available_fraction": 1.0,
  "lookback_days": 5,
  "missing_feature_count": 0,
  "preentry_bucket_counts": {
    "confirmed": 19,
    "unconfirmed": 8
  }
}
```

## Decision Rationale

Rejected: the best pre-entry momentum tilt (preentry_rs_2pct_150_050) did not beat the full frozen event bundle with enough stable EV improvement and materiality.

No production universe, ranking, sizing, exits, LLM, news, or order path changed.
