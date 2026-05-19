# exp-20260510-010 RS20 Entry-State Risk Replay

Decision: `promising_replay_only_not_promoted`
Best variant: `rs20_1_50x_cap_aware`

## Hypothesis

Accepted A/B trades whose signal-date entry-state oracle tags them as `rs20_leader` may deserve cap-aware extra risk because a 20-day ticker-vs-SPY excess return of at least 5pp identifies broad continuation leadership without adding noisy tickers or LLM input.

## Baseline

| EV sum | PnL sum | Trades |
|---:|---:|---:|
| 6.0452 | 177676.93 | 62 |

## Aggregate Replay

| Variant | EV delta | EV delta % | PnL delta | PnL delta % | Windows EV +/- | Touched | Changed | DD worsening | Single ticker share | Strong gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| rs20_1_10x_cap_aware | 0.2287 | 0.026242 | 3735.27 | 0.021023 | 3/0 | 51 | 25 | 0.0018 | 0.2225 | FAIL |
| rs20_1_25x_cap_aware | 0.4172 | 0.047871 | 7433.3 | 0.041836 | 3/0 | 51 | 30 | 0.0028 | 0.2853 | FAIL |
| rs20_1_50x_cap_aware | 0.5547 | 0.063649 | 10898.7 | 0.06134 | 3/0 | 51 | 32 | 0.0049 | 0.3835 | FAIL |

## Window Deltas

| Variant | Window | EV delta | PnL delta | SharpeD delta | DD delta |
|---|---|---:|---:|---:|---:|
| rs20_1_10x_cap_aware | late_strong | 0.1515 | 1809.3 | 0.05 | 0.0006 |
| rs20_1_10x_cap_aware | mid_weak | 0.0614 | 1248.82 | 0.0 | 0.0 |
| rs20_1_10x_cap_aware | old_thin | 0.0158 | 677.15 | 0.0 | 0.0018 |
| rs20_1_25x_cap_aware | late_strong | 0.2739 | 3457.49 | 0.08 | 0.0021 |
| rs20_1_25x_cap_aware | mid_weak | 0.0948 | 2113.95 | -0.01 | 0.0 |
| rs20_1_25x_cap_aware | old_thin | 0.0485 | 1861.86 | 0.01 | 0.0028 |
| rs20_1_50x_cap_aware | late_strong | 0.3676 | 5240.56 | 0.07 | 0.0047 |
| rs20_1_50x_cap_aware | mid_weak | 0.1024 | 2337.85 | -0.01 | 0.0 |
| rs20_1_50x_cap_aware | old_thin | 0.0847 | 3320.29 | 0.01 | 0.0049 |

## Decision Rationale

Promising replay-only: EV improved in all three canonical windows, aggregate PnL cleared +5%, drawdown and concentration stayed inside guards, but the EV delta missed the >10% strong gate. Do not promote to production without a shared policy and additional evidence.

## Best Variant Summary

- EV delta: `0.5547` (`0.063649` proxy basis)
- PnL delta: `$10898.7` (`0.06134`)
- Touched / changed trades: `51` / `32`
- Single ticker positive share: `0.3835`

## Production Impact

Replay-only diagnostic. No production orders, shared policy, default backtest strategy, LLM/news boundary, or universe changed. Any promotion must implement the risk rule in shared production/backtest policy with parity tests.
