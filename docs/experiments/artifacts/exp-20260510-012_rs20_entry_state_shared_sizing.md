# exp-20260510-012 RS20 Entry-State Shared Sizing

Decision: `accepted`

## Hypothesis

Already-entered A/B trades whose signal-date 20-day return beats SPY by at least 5 percentage points deserve a small cap-aware post-sizing top-up because broad relative-strength leadership identifies continuation without adding noisy tickers.

## Protocol

Three fixed windows from `docs/backtesting.md` using the canonical OHLCV snapshots and the shared production/backtest sizing path.

## Three-window deltas

| Window | EV delta | PnL delta | SharpeD delta | DD delta | Survival delta | Trades delta |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | +0.1666 | +3298.03 | +0.02 | +0.0009 | 0.0000 | 0 |
| mid_weak | +0.0483 | +2228.32 | -0.02 | +0.0062 | 0.0000 | 0 |
| old_thin | +0.0110 | +837.68 | +0.00 | +0.0012 | 0.0000 | 0 |

## Aggregate

- EV before sum: `6.0452`
- EV after sum: `6.2711`
- EV delta sum: `+0.2259` (+0.037368)
- PnL before sum: `$177676.93`
- PnL after sum: `$184040.96`
- PnL delta sum: `$6364.03` (+0.035818)
- EV/PnL improved windows: `3/3` and `3/3`
- Max drawdown worsening max: `+0.0062`

## Trial variants

| Variant | Decision | EV delta | PnL delta | Max DD worsening | Reason |
|---|---|---:|---:|---:|---|
| 1.50x | rejected | +0.3653 | +19924.00 | +0.0301 | mid_weak drawdown rose to 11.80% |
| 1.25x | rejected | +0.3690 | +13088.96 | +0.0161 | mid_weak drawdown rose to 10.40% |
| 1.10x | accepted | +0.2259 | +6364.03 | +0.0062 | cleanest EV/risk tradeoff |

## Production impact

```text
production_impact:
  shared_policy_changed: True
  backtester_adapter_changed: True
  run_adapter_changed: True
  replay_only: False
  parity_test_added: True
```

## Decision rationale

Accept the 1.10x shared policy as a small but stable alpha improvement: EV and PnL improved in all three canonical windows, trade count and survival stayed unchanged, and drawdown drift stayed under +0.62 pp. Do not retry nearby RS20 scalars on the same frozen windows without forward evidence.
