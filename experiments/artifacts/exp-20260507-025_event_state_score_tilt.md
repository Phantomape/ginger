# exp-20260507-025 Event State-Score Tilt

Decision: `rejected`

Replay-only alpha search. Tests whether the frozen event bundle should tilt notional toward event trades with positive PIT state-surface score before entry.

## Best Variant Vs Full Bundle

| Window | Full EV | Variant EV | Delta EV | Full PnL | Variant PnL | Delta PnL | Event trades | Event PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.1196 | 4.1007 | -0.0189 | $88,594.32 | $88,566.99 | $-27.33 | 9 | $+5,886.09 |
| mid_weak | 2.0019 | 2.0307 | +0.0288 | $65,850.51 | $66,146.91 | $+296.40 | 11 | $+9,072.68 |
| old_thin | 0.3676 | 0.3807 | +0.0131 | $27,641.23 | $28,201.00 | $+559.77 | 7 | $+1,958.31 |

## Variant Summary

| Variant | EV Sum Vs Full | PnL Delta Vs Full | Windows EV Improved | Windows EV Regressed | Passed |
|---|---:|---:|---:|---:|---|
| state_score_pos_125_075 | +0.0147 | $+414.42 | 2 | 1 | False |
| state_score_pos_150_050 | +0.0230 | $+828.84 | 2 | 1 | False |
| state_score_pos_only | -0.4436 | $-6,657.45 | 0 | 3 | False |

## Coverage

```json
{
  "bucket_counts": {
    "nonpositive_score": 8,
    "positive_score": 18
  },
  "event_trade_count": 27,
  "feature_available_count": 26,
  "feature_available_fraction": 0.963,
  "missing_feature_count": 1,
  "rule": "event ticker's PIT state-surface score > 0 before event entry"
}
```

## Decision Rationale

Rejected: the best state-score variant (state_score_pos_150_050) did not beat the full frozen event bundle with enough stable EV improvement and materiality.

No production universe, ranking, sizing, exits, LLM, news, or order path changed.
