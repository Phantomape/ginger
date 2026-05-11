# exp-20260510-028 SPACE_CATALYST_SHADOW OHLCV Replay

Status: observed only.

This fills the immediate data gap for the space catalyst sleeve. The canonical
three-window snapshots were copied into experiment-local augmented snapshots and
13 available space tickers were appended from Yahoo Finance adjusted OHLC. The
canonical snapshots were not modified. `HAWK` returned Yahoo chart API 400 and
was left missing rather than represented with empty data.

## Outputs

- Manifest: `data/experiments/exp-20260510-028/space_catalyst_ohlcv_snapshot_build.json`
- Shadow replay: `data/experiments/exp-20260510-028/space_catalyst_shadow_basket_replay.json`
- `late_strong`: `data/experiments/exp-20260510-028/ohlcv/exp-20260510-028_late_strong_with_space_catalyst.json`
- `mid_weak`: `data/experiments/exp-20260510-028/ohlcv/exp-20260510-028_mid_weak_with_space_catalyst.json`
- `old_thin`: `data/experiments/exp-20260510-028/ohlcv/exp-20260510-028_old_thin_with_space_catalyst.json`

## Core No-Drift

Running the normal backtester with `--include-pilot-sleeve` on the augmented
snapshot copies reproduced the accepted core metrics and produced zero pilot
entries in all three windows:

| Window | EV | PnL | Sharpe | Max DD | Trades | Survival | Pilot entries |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | 4.2340 | $94,086.91 | 4.50 | 5.48% | 19 | 80.39% | 0 |
| `mid_weak` | 1.6689 | $61,813.40 | 2.70 | 9.41% | 21 | 79.25% | 0 |
| `old_thin` | 0.3853 | $28,544.11 | 1.35 | 8.15% | 22 | 91.67% | 0 |

## Shadow Basket Diagnostic

The current 2026-05-10 space basket is replayed on older windows, so this is a
theme-risk diagnostic with look-ahead selection. It is not acceptance evidence
for live trading.

Equal-weight space equities excluding `SPCE`:

| Window | Return | PnL proxy | Sharpe | Max DD | Max positive contribution share |
| --- | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | 83.02% | $83,024.15 | 2.15 | 24.28% | 23.33% |
| `mid_weak` | 159.19% | $159,188.76 | 3.87 | 17.71% | 19.13% |
| `old_thin` | 13.44% | $13,439.19 | 0.67 | 49.68% | 44.42% |

Top-3 RS20 monthly rotation, no transaction cost:

| Window | Return | PnL proxy | Sharpe | Max DD |
| --- | ---: | ---: | ---: | ---: |
| `late_strong` | 66.98% | $66,981.75 | 1.81 | 33.26% |
| `mid_weak` | 156.29% | $156,291.51 | 2.91 | 26.24% |
| `old_thin` | 88.08% | $88,075.20 | 1.83 | 46.98% |

`SPCE` stays quarantine: it lost 26.45% in `late_strong`, lost 57.55% in
`old_thin`, and had maximum drawdowns above 52% / 69% in those windows.

## Decision

Keep `SPACE_CATALYST_SHADOW` observe-only. The data coverage is now good enough
for shadow replay, but the static basket result is not a live promotion signal:
it uses a current basket on older windows and carries very large drawdown. The
valid next step is event-dated shadow decisions with direct, cash-relative,
core-replacement, and same-theme replacement value.
