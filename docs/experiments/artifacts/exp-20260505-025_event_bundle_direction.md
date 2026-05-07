# exp-20260505-025 Event Bundle Direction

This run did not promote a new core A/B rule. The alpha search conclusion is that the strongest current direction is the default-off external event overlay bundle: Form 4 meaningful purchase, SEC negative reaction, and SEC governance/procedural events.

## Why This Direction

- LLM soft-ranking still lacks enough production-aligned outcome joins.
- Options and short/borrow overlays still have no PIT-safe local rows.
- Consumer digital platform expansion regressed two of three windows.
- The first add-on haircut idea was already rejected as too sparse in `exp-20260430-030`.
- The event overlay bundle is the recent family with positive EV and PnL in all three canonical windows.

## Canonical Three-Window Metrics

| Window | Core EV | Bundle EV | EV Delta | Core PnL | Bundle PnL | PnL Delta |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 4.0085 | 0.5894 | 78600.33 | 86951.61 | 8351.28 |
| mid_weak | 1.4415 | 2.0246 | 0.5831 | 55015.08 | 65309.93 | 10294.85 |
| old_thin | 0.3179 | 0.3516 | 0.0337 | 24642.07 | 26046.73 | 1404.66 |

Aggregate EV delta: `+1.2062` (`+23.2925%`).

Aggregate PnL delta: `+20050.79` (`+12.6697%`).

## Decision

Keep the event bundle default-off and production-visible through paper attribution. Do not start another core threshold, ranking, add-on, or noisy universe expansion until the bundle has closed forward paper outcomes, the forward gate can be evaluated, or a materially new alpha source appears.

Relevant validation: `.\\.venv\\Scripts\\python.exe -m pytest quant\\test_event_sleeve_bundle.py quant\\test_form4_event_sleeve.py quant\\test_sec_negative_event_sleeve.py quant\\test_sec_event_sleeve.py` -> `16 passed`.
