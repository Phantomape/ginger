# exp-20260603-003: Companyfacts Gross-Margin Source Support

- decision: `rejected_companyfacts_gross_margin_source_support`
- aggregate EV: `16.1444` -> `16.3479` (+0.2035)
- aggregate PnL: `$359,253.44` -> `$362,282.63` (+3,029.19)
- incremental target trades: `99`
- max single positive share: `0.887952`
- positive PnL HHI: `0.796841`
- failed gates: `concentration_guard_passed`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | adjusted trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 7.2995 | 7.3229 | +0.0234 | $+175.64 | 19 |
| mid_weak | 5.9392 | 5.9873 | +0.0481 | $+769.66 | 20 |
| old_thin | 2.9057 | 3.0377 | +0.1320 | $+2,083.89 | 60 |

## Source Coverage

```json
{
  "late_strong": {
    "cost_of_revenue_fallback": 19,
    "direct_gross_profit": 51
  },
  "mid_weak": {
    "cost_of_revenue_fallback": 20,
    "direct_gross_profit": 70
  },
  "old_thin": {
    "cost_of_revenue_fallback": 60,
    "direct_gross_profit": 45
  }
}
```

## Production Parity

Replay-only and default-off paper only. The test uses fields already emitted by the accepted Companyfacts paper route from SEC facts with `filed <= signal_date`. No live orders, shared production adapter, core ranking, sizing, exits, LLM, or news behavior changed.

## Conclusion

Cost-of-revenue fallback source support failed Gate 4; no production, shared adapter, or strategy behavior is retained.

## Top Positive Incremental Contributors

| ticker | trades | incremental PnL | positive PnL share |
|---|---:|---:|---:|
| APP | 73 | $3,035.69 | 0.887952 |
| GOOG | 14 | $161.84 | 0.088464 |
| NFLX | 9 | $-5.78 | 0.023583 |
| META | 3 | $-162.56 | 0.0 |
