# exp-20260605-005: SEC 8-K Results Gap/Hold Candidate Pool

- decision: `rejected_preflight_sample_too_thin`
- event source: `data/non_ohlcv/sec_filing_events_20241002_20260421.jsonl`
- event keys: `306`
- event tickers: `48`
- raw candidates across canonical windows: `11`
- production impact: replay/preflight only; no production or backtest adapter changed

## Preflight Result

| window | raw candidates | raw candidate days |
|---|---:|---:|
| late_strong | 1 | 1 |
| mid_weak | 2 | 2 |
| old_thin | 8 | 7 |

## Conclusion

The strict SEC 8-K item 2.02 plus gap/hold/high-close candidate definition is too thin for Gate 4. A full strategy replay would not have statistical meaning, so no runner or production-visible adapter was retained.

Next valid SEC results work needs a less sparse pre-registered filing-quality field, XBRL financial-quality context, or forward event rows. Do not retry this exact strict 8-K 2.02 gap/hold/high-close branch on the frozen windows.
