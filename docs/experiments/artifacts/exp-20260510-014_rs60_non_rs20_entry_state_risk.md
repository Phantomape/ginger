# exp-20260510-014 RS60 Non-RS20 Entry-State Risk

Decision: `rejected`

## Hypothesis

Already-entered A/B trades with positive 60-day ticker-vs-SPY relative return, excluding trades that already received the RS20 entry-state top-up, may deserve a modest cap-aware 1.10x post-sizing top-up because medium-term leadership can persist even when the 20-day burst is absent.

## Aggregate

| EV before | EV after | EV delta | PnL delta | EV windows +/- | Eligible | Changed | DD drift | Single ticker share |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 9.0761 | 9.0724 | -0.0037 | 5.32 | 2/1 | 36 | 12 | 0.0068 | 0.4105 |

## Windows

| Window | EV before | EV after | EV delta | PnL delta | Sharpe delta | DD delta | Changed |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.528 | 5.5333 | 0.0053 | 207.02 | -0.01 | 0.0002 | 4 |
| mid_weak | 2.8592 | 2.8877 | 0.0285 | 395.06 | 0.02 | 0.0 | 3 |
| old_thin | 0.6889 | 0.6514 | -0.0375 | -596.76 | -0.08 | 0.0068 | 5 |

## Production Impact

Replay only. No shared policy, run adapter, backtester adapter, live/default orders, ranking, exits, add-ons, LLM/news, or universe behavior changed.
