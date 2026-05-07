# exp-20260507-024 Event Price Structure

Decision: `rejected`

Replay-only alpha search. Tests whether the frozen event bundle should tilt notional toward event trades with confirmed PIT-safe SMA20/SMA50 price structure before entry.

## Best Variant Vs Full Bundle

| Window | Full EV | Variant EV | Delta EV | Full PnL | Variant PnL | Delta PnL | Event trades | Event PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.1196 | 3.0169 | -1.1027 | $88,594.32 | $83,339.70 | $-5,254.62 | 9 | $+5,676.30 |
| mid_weak | 2.0019 | 3.6578 | +1.6559 | $65,850.51 | $91,216.91 | $+25,366.40 | 11 | $+9,072.68 |
| old_thin | 0.3676 | 1.1244 | +0.7568 | $27,641.23 | $53,288.50 | $+25,647.27 | 7 | $+1,958.31 |

## Variant Summary

| Variant | EV Sum Vs Full | PnL Delta Vs Full | Windows EV Improved | Windows EV Regressed | Passed |
|---|---:|---:|---:|---:|---|
| price_structure_125_075 | +0.7513 | $+22,879.53 | 2 | 1 | False |
| price_structure_150_050 | +1.3100 | $+45,759.05 | 2 | 1 | False |
| price_structure_only | -0.4882 | $-7,077.03 | 0 | 3 | False |

## Coverage

```json
{
  "bucket_counts": {
    "confirmed": 18,
    "unconfirmed": 9
  },
  "event_trade_count": 27,
  "feature_available_count": 27,
  "feature_available_fraction": 1.0,
  "missing_feature_count": 0,
  "rule": "pre-entry close > SMA50 and SMA20 > SMA50, using only closes before event entry date"
}
```

## Decision Rationale

Rejected: the best price-structure variant (price_structure_150_050) did not beat the full frozen event bundle with enough stable EV improvement and materiality.

No production universe, ranking, sizing, exits, LLM, news, or order path changed.
