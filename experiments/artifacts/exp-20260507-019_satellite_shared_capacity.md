# exp-20260507-019 Satellite Shared-Capacity Allocation

Decision: `rejected`

Replay-only alpha search. Event-bundle trades keep priority; state-surface trades may use only idle slots inside the same max-3 active satellite budget.

## Event Baseline To Shared Stack

| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL | State-in-shared | Shared trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2452 | 3.9226 | -0.3226 | $90,131.87 | $90,173.91 | $42.04 | 13 | 16 |
| mid_weak | 2.0019 | 2.2951 | 0.2932 | $65,850.51 | $71,056.95 | $5,206.44 | 21 | 21 |
| old_thin | 0.3676 | 0.8164 | 0.4488 | $27,641.23 | $43,891.34 | $16,250.11 | 21 | 21 |

## Shared Vs Core

```json
{
  "after_ev_sum": 7.0341,
  "after_pnl_sum": 205122.2,
  "aggregate_ev_delta": 1.4069,
  "aggregate_ev_delta_pct": 0.250018,
  "aggregate_pnl_delta": 37774.25,
  "aggregate_pnl_delta_pct": 0.225723,
  "baseline_ev_sum": 5.6272,
  "baseline_pnl_sum": 167347.95,
  "by_window": {
    "late_strong": {
      "expected_value_score": 0.1791,
      "max_drawdown_pct": 0.002,
      "sharpe_daily": -0.13,
      "survival_rate": 0.0,
      "total_pnl": 6611.38,
      "total_return_pct": 0.0661,
      "trade_count": 16.0,
      "win_rate": -0.0752
    },
    "mid_weak": {
      "expected_value_score": 0.7473,
      "max_drawdown_pct": -0.0131,
      "sharpe_daily": 0.54,
      "survival_rate": 0.0,
      "total_pnl": 13514.21,
      "total_return_pct": 0.1352,
      "trade_count": 21.0,
      "win_rate": 0.0238
    },
    "old_thin": {
      "expected_value_score": 0.4805,
      "max_drawdown_pct": 0.06,
      "sharpe_daily": 0.58,
      "survival_rate": 0.0,
      "total_pnl": 17648.66,
      "total_return_pct": 0.1765,
      "trade_count": 21.0,
      "win_rate": 0.1025
    }
  },
  "windows_ev_improved": 3,
  "windows_ev_regressed": 0,
  "windows_pnl_improved": 3,
  "windows_pnl_regressed": 0
}
```

## Shared Source Summary

```json
{
  "late_strong": {
    "sec_governance_procedural": {
      "total_pnl": -732.95,
      "trade_count": 1,
      "win_rate": 0.0,
      "wins": 0
    },
    "sec_negative_reaction": {
      "total_pnl": 498.4,
      "trade_count": 2,
      "win_rate": 1.0,
      "wins": 2
    },
    "state_surface_satellite": {
      "total_pnl": 6189.99,
      "trade_count": 13,
      "win_rate": 0.6154,
      "wins": 8
    }
  },
  "mid_weak": {
    "state_surface_satellite": {
      "total_pnl": 11131.67,
      "trade_count": 21,
      "win_rate": 0.5714,
      "wins": 12
    }
  },
  "old_thin": {
    "state_surface_satellite": {
      "total_pnl": 17223.56,
      "trade_count": 21,
      "win_rate": 0.619,
      "wins": 13
    }
  }
}
```

## Decision Rationale

Rejected: the shared-capacity satellite stack did not clear the pre-registered event-only incremental Gate 4 plus concentration controls. Keep event and state-surface sleeves in forward paper observation rather than combining them.
