# exp-20260507-016 State Surface Satellite Replay

Replay-only alpha search. Core A/B entries, ranking, sizing, exits, LLM, news, and production orders are unchanged.

## Three-window result

| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL | Sleeve trades | Sleeve PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.7435 | 3.7786 | 0.0351 | $83,562.53 | $88,492.45 | $4,929.92 | 15 | $4,273.99 |
| mid_weak | 1.5478 | 2.2951 | 0.7473 | $57,542.74 | $71,056.95 | $13,514.21 | 21 | $11,131.67 |
| old_thin | 0.3359 | 0.8164 | 0.4805 | $26,242.68 | $43,891.34 | $17,648.66 | 21 | $17,223.56 |

## Decision

Promising replay-only: the state-aware surface satellite improved the majority of canonical windows without EV regression. It remains replay-only; production use requires a shared run.py/backtester.py adapter and parity tests.

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
