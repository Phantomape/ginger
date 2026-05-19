# exp-20260505-009 Historical Watchlist Fresh OHLCV

Decision: `rejected_for_core_promotion`

## Hypothesis

The user's historical attention list may contain recurring momentum, event, AI-infrastructure, crypto-beta, and high-volatility candidates that the existing A/B/C signal stack can monetize when they are added to the candidate universe using fresh OHLCV.

## Universe

- Requested tickers: `81`
- Tradeable requested tickers: `80`
- Newly added vs current core universe: `56`
- Already present in core universe: `24`
- Skipped non-tradeable requests: `{".RUT": "cash index; use IWM/VTWO for tradeable Russell exposure"}`

## Three-window deltas

| Window | EV delta | PnL delta | SharpeD delta | DD delta | WR delta | Trades delta | Added-name trades | Added-name PnL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | -1.0498 | -7073.04 | -1.06 | +0.0198 | -0.2750 | +20 | 22 | +7592.57 |
| `mid_weak` | -1.0987 | -25965.84 | -1.44 | +0.0717 | -0.1750 | +22 | 25 | -7086.42 |
| `old_thin` | -0.2869 | -18047.30 | -0.82 | +0.0723 | -0.1459 | +16 | 18 | -8285.42 |

## Aggregate

- EV delta sum: `-2.4354` (-47.81%)
- PnL delta sum: `$-51,086.18` (-32.54%)
- Max Sharpe daily delta: `-0.82`
- Trade-count delta sum: `+58`

## Data Notes

- Fresh yfinance OHLCV snapshots were saved under `data/experiments/exp-20260505-009/ohlcv/`.
- Baseline and expanded variants used the same fresh snapshot inside each window.
- `.RUT` was skipped because it is a cash index, not a directly tradeable instrument.
- `ALB.PRA` was downloaded as Yahoo symbol `ALB-PA`.

## Parity

No production code or core watchlist was changed. If accepted, promotion must go through universe governance / pilot handling rather than direct `filter.py` expansion.
