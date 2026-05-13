# exp-20260513-017 Index ETF Target Width

Decision: `rejected_index_etf_target_width`

## Hypothesis

Broad index ETFs may be target-clipped by the generic target path. If QQQ/SPY/IWM behave more like slow index trend sleeves than single-name breakouts, a separate target-width pool should improve three-window EV without worsening drawdown or tail loss.

## Live QQQ Trigger

- source: `data\trend_signals_20260512.json`
- close/high: `707.24` / `710.18`
- signal target: `650.7` (0.0649)
- triggered rules: `[{'rule': 'SIGNAL_TARGET', 'message': 'daily_high 710.18 >= signal target 650.70 (+6.5%) - full-position target exit', 'trigger_price': 710.18, 'target_price': 650.7}]`

## Gate 4

- passed: `False`
- best variant: `index_etf_target_5_0atr`
- EV delta sum: `-0.1030` (-1.62%)
- PnL delta sum: `$-2,267.28` (-1.21%)
- EV windows improved/regressed: `0` / `1`
- index ETF candidates / changed trades: `3` / `1`
- survival min after: `0.7925`

## Three-Window Deltas

| Window | EV delta | PnL delta | Sharpe delta | DD delta | Tail delta | Trades delta | Candidates | Changed index trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | +0.0000 | +0.00 | +0.0000 | +0.0000 | +0.0000 | +0 | 1 | 0 |
| `mid_weak` | -0.1030 | -2267.28 | -0.0700 | +0.0000 | +0.0006 | +0 | 1 | 1 |
| `old_thin` | +0.0000 | +0.00 | +0.0000 | +0.0000 | +0.0000 | +0 | 1 | 0 |

## Production Parity

No production order path changed. A positive promotion requires moving the target policy into shared `constants.py` / `risk_engine.py`, which is imported by both `run.py` and `backtester.py`, then rerunning this same three-window protocol.

