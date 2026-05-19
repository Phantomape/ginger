# exp-20260509-010 State-Surface Current-Stack Revalidation

Decision: `promising_replay_only_current_stack`

Alpha search, replay-only. Revalidates the frozen state-surface satellite sleeve on the refreshed accepted stack.

## Three-Window Result

| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL | Sleeve trades | Sleeve PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.0674 | 4.1266 | +0.0592 | $90,788.88 | $95,744.88 | $+4,956.00 | 15 | $+4,273.99 |
| mid_weak | 1.6195 | 2.3817 | +0.7622 | $59,540.63 | $73,056.94 | $+13,516.31 | 21 | $+11,131.67 |
| old_thin | 0.3583 | 0.8504 | +0.4921 | $27,347.42 | $44,996.08 | $+17,648.66 | 21 | $+17,223.56 |

## Aggregate Gate

- EV sum: 6.0452 -> 7.3587 (+1.3135, +21.73%)
- PnL sum: $177,676.93 -> $213,797.90 (+36,120.97, +20.33%)
- EV windows improved/regressed: 3/0
- Single-ticker positive share: 0.3134

## Decision Rationale

Promising replay-only on the current stack: the frozen state-surface satellite improved the majority of canonical windows under the existing Gate 4/concentration guard. It remains paper-only because live/default orders require a shared adapter, parity tests, and closed forward replacement-value evidence.

## Surface Contribution

```json
{
  "late_strong": {
    "balanced_state_leadership": {
      "total_pnl": -2572.25,
      "trade_count": 6,
      "win_rate": 0.5,
      "wins": 3
    },
    "broad_breadth_trend_persistence": {
      "total_pnl": -3113.4,
      "trade_count": 3,
      "win_rate": 0.0,
      "wins": 0
    },
    "rotation_breakout_leadership": {
      "total_pnl": 9959.64,
      "trade_count": 6,
      "win_rate": 0.8333,
      "wins": 5
    }
  },
  "mid_weak": {
    "balanced_state_leadership": {
      "total_pnl": -465.49,
      "trade_count": 6,
      "win_rate": 0.3333,
      "wins": 2
    },
    "broad_breadth_trend_persistence": {
      "total_pnl": 1471.85,
      "trade_count": 12,
      "win_rate": 0.5833,
      "wins": 7
    },
    "rotation_breakout_leadership": {
      "total_pnl": 10125.31,
      "trade_count": 3,
      "win_rate": 1.0,
      "wins": 3
    }
  },
  "old_thin": {
    "balanced_state_leadership": {
      "total_pnl": -6896.5,
      "trade_count": 12,
      "win_rate": 0.4167,
      "wins": 5
    },
    "broad_breadth_trend_persistence": {
      "total_pnl": 21784.86,
      "trade_count": 6,
      "win_rate": 0.8333,
      "wins": 5
    },
    "rotation_breakout_leadership": {
      "total_pnl": 2335.2,
      "trade_count": 3,
      "win_rate": 1.0,
      "wins": 3
    }
  }
}
```

## Production Impact

No live/default orders, core A/B behavior, LLM, news, or production adapter changed. Any positive trade-enabled version must be implemented through a shared run/backtester adapter with parity tests and forward replacement-value evidence.
