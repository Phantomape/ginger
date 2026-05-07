# exp-20260507-017 State Surface Conviction Prune

Replay-only alpha search. Core A/B entries, ranking, sizing, exits, LLM, news, and production orders are unchanged.

## Tested Variable

Exclude `balanced_state_leadership`; keep `broad_breadth_trend_persistence` and `rotation_breakout_leadership` unchanged.

## Three-window result

| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL | Sleeve trades | Sleeve PnL | Max DD after |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.7435 | 3.2663 | -0.4772 | $83,562.53 | $82,482.30 | $-1,080.23 | 12 | $-1,736.14 | 5.80% |
| mid_weak | 1.5478 | 1.6961 | 0.1483 | $57,542.74 | $62,129.88 | $4,587.14 | 18 | $7,021.65 | 8.51% |
| old_thin | 0.3359 | 0.9503 | 0.6144 | $26,242.68 | $47,513.25 | $21,270.57 | 15 | $21,270.57 | 12.17% |

## Decision

Rejected: excluding balanced_state_leadership did not clear the three-window Gate 4 standard with material improvement, no EV regression, and concentration controls.

## Incremental Comparison Versus exp-20260507-016

```json
{
  "aggregate": {
    "full_replay_ev_delta": 1.2629,
    "full_replay_pnl_delta": 36092.79,
    "incremental_ev_delta_vs_full": -0.9774,
    "incremental_pnl_delta_vs_full": -11315.31,
    "pruned_replay_ev_delta": 0.2855,
    "pruned_replay_pnl_delta": 24777.48
  },
  "late_strong": {
    "expected_value_score": -0.5123,
    "max_drawdown_pct": 0.0014,
    "total_pnl": -6010.15,
    "trade_count": -3,
    "win_rate": -0.0959
  },
  "mid_weak": {
    "expected_value_score": -0.599,
    "max_drawdown_pct": 0.0103,
    "total_pnl": -8927.07,
    "trade_count": -3,
    "win_rate": 0.0165
  },
  "old_thin": {
    "expected_value_score": 0.1339,
    "max_drawdown_pct": -0.0288,
    "total_pnl": 3621.91,
    "trade_count": -6,
    "win_rate": -0.0251
  }
}
```

## Surface Contribution

```json
{
  "late_strong": {
    "broad_breadth_trend_persistence": {
      "total_pnl": -2924.85,
      "trade_count": 6,
      "win_rate": 0.1667,
      "wins": 1
    },
    "rotation_breakout_leadership": {
      "total_pnl": 1188.71,
      "trade_count": 6,
      "win_rate": 0.3333,
      "wins": 2
    }
  },
  "mid_weak": {
    "broad_breadth_trend_persistence": {
      "total_pnl": 8558.65,
      "trade_count": 14,
      "win_rate": 0.7143,
      "wins": 10
    },
    "rotation_breakout_leadership": {
      "total_pnl": -1537.0,
      "trade_count": 4,
      "win_rate": 0.25,
      "wins": 1
    }
  },
  "old_thin": {
    "broad_breadth_trend_persistence": {
      "total_pnl": 18935.37,
      "trade_count": 12,
      "win_rate": 0.5,
      "wins": 6
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
