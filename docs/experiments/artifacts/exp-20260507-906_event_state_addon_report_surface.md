# exp-20260507-906: Event State Add-On Report Surface

## Hypothesis

`exp-20260507-026` found the strongest current positive alpha lead: non-generic positive state-surface confirmation improved event-sleeve capital allocation across all three canonical windows. The blocker is not backtest mechanics; it is that the default-off paper add-on needs production-visible attribution before live promotion.

## Change

Added production report rendering for the event bundle `state_surface_addon` summary:

- eligible candidate count
- total event candidate count
- incremental paper notional
- eligible non-generic state surfaces

This is a default-off attribution surface only. It does not change live orders, sizing, ranking, entry, exit, or backtester strategy logic.

## Three-Window Check

| Window | EV | Sharpe Daily | Max DD | PnL | Win Rate | Trades | Survival |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong 2025-10-23 -> 2026-04-21 | 3.6257 | 4.42 | 5.39% | $82,030.12 | 75.00% | 20 | 80.39% |
| mid_weak 2025-04-23 -> 2025-10-22 | 1.5478 | 2.69 | 8.79% | $57,542.74 | 52.38% | 21 | 79.25% |
| old_thin 2024-10-02 -> 2025-04-22 | 0.3359 | 1.28 | 9.05% | $26,242.68 | 40.91% | 22 | 91.67% |

All three windows remained `CONVERGED`. Metrics are unchanged by design because this iteration exposes attribution for an already shared default-off paper policy.

## Validation

- `.\\.venv\\Scripts\\python.exe -m pytest quant\\test_event_sleeve_bundle.py -q`
- `.\\.venv\\Scripts\\python.exe quant\\backtester.py --start 2025-10-23 --end 2026-04-21 --ohlcv-snapshot data\\ohlcv_snapshot_20251023_20260421.json --no-secondary`
- `.\\.venv\\Scripts\\python.exe quant\\backtester.py --start 2025-04-23 --end 2025-10-22 --ohlcv-snapshot data\\ohlcv_snapshot_20250423_20251022.json --no-secondary`
- `.\\.venv\\Scripts\\python.exe quant\\backtester.py --start 2024-10-02 --end 2025-04-22 --ohlcv-snapshot data\\ohlcv_snapshot_20241002_20250422.json --no-secondary`

## Decision

Accepted as a production attribution bridge for the positive `exp-20260507-026` alpha lead. The next required evidence is closed forward paper replacement-value outcomes for add-on-eligible candidates versus base event notional.
