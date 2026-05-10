# exp-20260510-007 Low-deployment Dynamic ETF Overlay

Decision: `promising_replay_only_low_deployment_dynamic_etf_overlay`

## Hypothesis

When the accepted A/B core is materially under-deployed, a small liquid ETF selector using only prior-close momentum/trend state may capture replacement value without displacing scarce stock slots.

## Three-window Deltas

| Window | EV delta | PnL delta | Return delta | SharpeD delta | DD delta | Overlay days | Ticker days |
|---|---:|---:|---:|---:|---:|---:|---|
| late_strong | +0.0539 | $+3,518.56 | +0.0352 | -0.11 | -0.0022 | 46 | GLD:7, IWM:7, QQQ:5, SLV:25, SPY:2 |
| mid_weak | +0.1368 | $+2,300.74 | +0.0230 | +0.12 | -0.0036 | 39 | GLD:13, IWM:2, QQQ:14, SLV:9, SPY:1 |
| old_thin | +0.1234 | $+4,557.52 | +0.0455 | +0.20 | +0.0037 | 47 | GLD:25, QQQ:8, SLV:14 |

## Aggregate

- EV delta: `0.3141` (`0.051959`)
- PnL delta: `$10376.82` (`0.058403`)
- EV windows improved/regressed: `3` / `0`
- Overlay days: `132` selected from `152` low-deployment days

## Gate 4

```json
{
  "basis": "Three canonical backtesting.md windows using the same snapshots.",
  "concentration_ok": true,
  "passed_directionally": true,
  "rule": "Require 3/3 EV improvement, no PnL regression, positive aggregate EV/PnL, max drawdown worsening <= 1pp, min 4 overlay days per window, and single ETF positive contribution share <= 75%.",
  "single_ticker_positive_share": 0.5024,
  "strong_materiality_passed": true
}
```

## Decision Rationale

Promising replay-only: the low-deployment dynamic ETF overlay cleared the three-window EV/PnL materiality gate without breaching drawdown or concentration guards. It remains non-production because actual cash/risk budget semantics and shared run/backtester adapters are not implemented.

## Production Impact

Replay-only. No live/default orders, core A/B signal generation, ranking, sizing, exits, add-ons, LLM/news behavior, or production adapters changed. Any positive follow-up needs shared run.py/backtester.py cash/risk-budget semantics and parity tests.

