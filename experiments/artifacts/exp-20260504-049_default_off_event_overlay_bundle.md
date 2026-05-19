# exp-20260504-049 Default-Off Event Overlay Bundle

Replay-only alpha search. Core A/B entries, ranking, sizing, exits, LLM, news, and production orders are unchanged.

## Three-window result

| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL | Event trades | Event PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 4.0085 | 0.5894 | $78,600.33 | $86,951.61 | $8,351.28 | 12 | $7,713.06 |
| mid_weak | 1.4415 | 2.0246 | 0.5831 | $55,015.08 | $65,309.93 | $10,294.85 | 15 | $10,535.55 |
| old_thin | 0.3179 | 0.3516 | 0.0337 | $24,642.07 | $26,046.73 | $1,404.66 | 8 | $1,404.66 |

## Decision

Promising replay-only: the frozen event overlay bundle improved the majority of windows without EV regression. It is not promoted to production orders here; a shared trade-enabled adapter and forward paper outcomes are required before live capital.

## Source contribution

```json
{
  "late_strong": {
    "form4_meaningful_purchase": {
      "total_pnl": 1799.63,
      "trade_count": 3,
      "win_rate": 1.0,
      "wins": 3
    },
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
    "form4_meaningful_purchase": {
      "total_pnl": 1991.3,
      "trade_count": 4,
      "win_rate": 0.5,
      "wins": 2
    },
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
    "form4_meaningful_purchase": {
      "total_pnl": 6.11,
      "trade_count": 1,
      "win_rate": 1.0,
      "wins": 1
    },
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
