# exp-20260508-008 Platform RS20 Forward Watch Adapter

## Decision

- decision: accepted_measurement_adapter
- production orders changed: false
- run adapter changed: true

## Source Evidence

- exp-20260508-007 no-gap matched: count=3, pnl=10353.51, win_rate=1.0
- exp-20260508-007 gap-up complement: count=3, pnl=-2381.58, win_rate=0.0

## Adapter

- `quant/platform_rs20_watch.py` records default-off watch rows.
- `quant/run.py` persists the watch after entry execution planning.
- `quant/report_generator.py` renders the watch as observe-only.
- `quant/test_platform_rs20_watch.py` covers classification, dedupe persistence, and report rendering.
