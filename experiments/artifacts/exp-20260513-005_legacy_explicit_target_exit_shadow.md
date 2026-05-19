# exp-20260513-005 Legacy Explicit Target Exit Shadow

Decision: `observed_only_measurement_gap_confirmed`

Single variable: whether `legacy_basis` suppresses an explicit recorded `target_price`.

## Summary

- Signal files scanned: 36
- Position context rows: 326
- Explicit target reached rows: 87
- Baseline SIGNAL_TARGET rows: 36
- Suppressed by legacy_basis rows: 34
- Suppressed tickers: AMD, NVDA, SNXX, TSLA

## Suppressed Rows

| Date | Ticker | Intent | Price | High | Target | Current Rules | Shadow Action |
|---|---|---|---:|---:|---:|---|---|
| 2026-04-15 | AMD | swing | 258.12 | None | 61.23 | none | EXIT_FULL |
| 2026-04-16 | AMD | swing | 278.26 | None | 61.23 | none | EXIT_FULL |
| 2026-04-17 | AMD | swing | 278.39 | None | 61.23 | none | EXIT_FULL |
| 2026-04-20 | AMD | swing | 274.95 | None | 61.23 | none | EXIT_FULL |
| 2026-04-21 | NVDA | core_hold | 199.88 | None | 120.95 | none | REDUCE_AND_RAISE_STOP |
| 2026-04-21 | AMD | swing | 284.49 | None | 61.23 | none | EXIT_FULL |
| 2026-04-22 | NVDA | core_hold | 202.5 | None | 120.95 | none | REDUCE_AND_RAISE_STOP |
| 2026-04-22 | AMD | swing | 303.46 | None | 61.23 | none | EXIT_FULL |
| 2026-04-23 | NVDA | core_hold | 199.64 | None | 120.95 | none | REDUCE_AND_RAISE_STOP |
| 2026-04-23 | AMD | swing | 305.33 | None | 61.23 | none | EXIT_FULL |
| 2026-04-24 | NVDA | core_hold | 208.27 | None | 120.95 | none | REDUCE_AND_RAISE_STOP |
| 2026-04-24 | AMD | swing | 347.81 | None | 61.23 | none | EXIT_FULL |
| 2026-04-27 | NVDA | core_hold | 216.61 | None | 120.95 | none | REDUCE_AND_RAISE_STOP |
| 2026-04-27 | AMD | swing | 334.63 | None | 61.23 | none | EXIT_FULL |
| 2026-04-28 | NVDA | core_hold | 213.17 | None | 120.95 | none | REDUCE_AND_RAISE_STOP |
| 2026-04-28 | AMD | swing | 323.21 | None | 61.23 | TRAILING_STOP | EXIT_FULL |
| 2026-04-28 | TSLA | swing | 376.02 | None | 321.39 | TRAILING_STOP | EXIT_FULL |
| 2026-04-29 | NVDA | core_hold | 209.25 | None | 120.95 | none | REDUCE_AND_RAISE_STOP |
| 2026-04-29 | AMD | swing | 337.11 | None | 61.23 | none | EXIT_FULL |
| 2026-04-29 | TSLA | swing | 372.8 | None | 321.39 | TRAILING_STOP | EXIT_FULL |
| 2026-05-06 | SNXX | tactical_fomo | 162.6 | 170.37 | 136.07 | none | EXIT_FULL |
| 2026-05-06 | AMD | swing | 421.39 | 430.6 | 410.38 | none | EXIT_FULL |
| 2026-05-07 | SNXX | tactical_fomo | 146.16 | 160.54 | 136.07 | none | EXIT_FULL |
| 2026-05-07 | AMD | swing | 408.46 | 421.71 | 410.38 | none | EXIT_FULL |
| 2026-05-08 | SNXX | tactical_fomo | 195.89 | 195.89 | 136.07 | none | EXIT_FULL |
| 2026-05-08 | AMD | swing | 455.19 | 456.29 | 410.38 | none | EXIT_FULL |
| 2026-05-09 | SNXX | tactical_fomo | 195.89 | 195.89 | 136.07 | none | EXIT_FULL |
| 2026-05-09 | AMD | swing | 455.19 | 456.29 | 410.38 | none | EXIT_FULL |
| 2026-05-10 | SNXX | tactical_fomo | 195.89 | 195.89 | 136.07 | none | EXIT_FULL |
| 2026-05-10 | AMD | swing | 455.19 | 456.29 | 410.38 | none | EXIT_FULL |
| 2026-05-11 | SNXX | tactical_fomo | 191.5 | 204.56 | 136.07 | none | EXIT_FULL |
| 2026-05-11 | NVDA | core_hold | 219.44 | 222.3 | 221.65 | none | REDUCE_AND_RAISE_STOP |
| 2026-05-11 | AMD | swing | 458.79 | 469.22 | 410.38 | none | EXIT_FULL |
| 2026-05-11 | TSLA | swing | 445.0 | 449.16 | 431.57 | none | EXIT_FULL |

## Guardrail

This is not the rejected `exp-20260429-032` target partial-reduce replay. No production policy, canonical backtest exit, entry, sizing, LLM, or news behavior changed.
