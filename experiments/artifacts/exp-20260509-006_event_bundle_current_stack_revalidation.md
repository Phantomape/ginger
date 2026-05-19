# exp-20260509-006 Event Bundle Current-Stack Revalidation

Decision: `accepted_direction_paper_only`

## Hypothesis

The highest-value alpha direction now is candidate-pool extension via the frozen default-off event bundle, because it adds independent event-driven satellite returns without consuming core A/B slots.

## Three-Window Result

| Window | Core EV | Core+Event EV | Delta EV | Core PnL | Core+Event PnL | Delta PnL | Event trades | Event PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.0674 | 4.5771 | 0.5097 | $90,788.88 | $97,384.30 | $6,595.42 | 9 | $5,913.43 |
| mid_weak | 1.6195 | 2.0830 | 0.4635 | $59,540.63 | $67,850.50 | $8,309.87 | 11 | $8,544.25 |
| old_thin | 0.3583 | 0.3938 | 0.0355 | $27,347.42 | $28,745.97 | $1,398.55 | 7 | $1,398.55 |

## Aggregate Gate

- EV sum: 6.0452 -> 7.0539 (+1.0087, +16.69%)
- PnL sum: $177,676.93 -> $193,980.77 (+16,303.84, +9.18%)
- EV windows improved/regressed: 3/0

## Decision Rationale

Accepted as the current strongest alpha direction for forward paper optimization: the frozen event bundle improves EV in all three canonical windows and clears aggregate materiality versus the current core stack. It is not promoted to live/default orders because replay-only event queues still need shared adapter parity and forward replacement-value evidence.

## Production Impact

Replay only. Production and default backtest order paths are unchanged. A positive live-capital version still needs a shared trade-enabled event adapter, run/backtester parity tests, and forward paper replacement-value evidence.

## Source Contribution

```json
{
  "late_strong": {
    "sec_governance_procedural": {
      "total_pnl": 1450.84,
      "trade_count": 4,
      "win_rate": 0.25,
      "wins": 1
    },
    "sec_negative_reaction": {
      "total_pnl": 4462.59,
      "trade_count": 5,
      "win_rate": 0.8,
      "wins": 4
    }
  },
  "mid_weak": {
    "sec_governance_procedural": {
      "total_pnl": 4513.51,
      "trade_count": 5,
      "win_rate": 0.8,
      "wins": 4
    },
    "sec_negative_reaction": {
      "total_pnl": 4030.74,
      "trade_count": 6,
      "win_rate": 1.0,
      "wins": 6
    }
  },
  "old_thin": {
    "sec_governance_procedural": {
      "total_pnl": 1368.67,
      "trade_count": 4,
      "win_rate": 0.75,
      "wins": 3
    },
    "sec_negative_reaction": {
      "total_pnl": 29.88,
      "trade_count": 3,
      "win_rate": 0.6667,
      "wins": 2
    }
  }
}
```
