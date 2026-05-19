# exp-20260509-011 State-Surface Core-Overlap Filter

Decision: `rejected_core_overlap_filter`

Alpha search, replay-only. Tests whether the state-surface sleeve should avoid tickers already traded by core A/B in the same canonical window.

## Three-Window Result Versus Full State-Surface Sleeve

| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL | Before sleeve trades | After sleeve trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.1266 | 2.9800 | -1.1466 | $95,744.88 | $79,466.01 | $-16,278.87 | 15 | 12 |
| mid_weak | 2.3817 | 2.5844 | +0.2027 | $73,056.94 | $77,609.04 | $+4,552.10 | 21 | 18 |
| old_thin | 0.8504 | 0.3572 | -0.4932 | $44,996.08 | $27,902.35 | $-17,093.73 | 21 | 21 |

## Aggregate Gate

- EV sum: 7.3587 -> 5.9216 (-1.4371, -19.53%)
- PnL sum: $213,797.90 -> $184,977.40 (-28,820.50, -13.48%)
- EV windows improved/regressed: 1/2

## Decision Rationale

Rejected: excluding same-window core A/B tickers did not improve the full state-surface sleeve with enough three-window stability and materiality. The current result says duplicate core ticker exposure is not the main state-surface weakness.

## Dropped Candidate Summary

```json
{
  "late_strong": {
    "dropped_candidate_count": 276,
    "price_ready_dropped_count": 232,
    "reason_counts": {
      "same_window_core_ticker": 276
    },
    "sample": [
      {
        "date": "2025-10-23",
        "rank": 1,
        "score": 2.244149,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "MU"
      },
      {
        "date": "2025-10-23",
        "rank": 2,
        "score": 1.630877,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "AMD"
      },
      {
        "date": "2025-10-24",
        "rank": 1,
        "score": 2.274844,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "MU"
      },
      {
        "date": "2025-10-24",
        "rank": 2,
        "score": 1.586264,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "AMD"
      },
      {
        "date": "2025-10-27",
        "rank": 1,
        "score": 2.202839,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "MU"
      },
      {
        "date": "2025-10-27",
        "rank": 2,
        "score": 1.708197,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "AMD"
      },
      {
        "date": "2025-10-28",
        "rank": 1,
        "score": 2.08073,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "MU"
      },
      {
        "date": "2025-10-28",
        "rank": 2,
        "score": 1.591372,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "AMD"
      },
      {
        "date": "2025-10-29",
        "rank": 1,
        "score": 1.72583,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "MU"
      },
      {
        "date": "2025-10-29",
        "rank": 2,
        "score": 1.530391,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "AMD"
      },
      {
        "date": "2025-10-29",
        "rank": 3,
        "score": 0.569993,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "GOOG"
      },
      {
        "date": "2025-10-30",
        "rank": 1,
        "score": 1.849619,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "MU"
      },
      {
        "date": "2025-10-30",
        "rank": 2,
        "score": 1.590827,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "AMD"
      },
      {
        "date": "2025-10-31",
        "rank": 1,
        "score": 2.004109,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "MU"
      },
      {
        "date": "2025-10-31",
        "rank": 2,
        "score": 1.845566,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "AMD"
      },
      {
        "date": "2025-11-03",
        "rank": 1,
        "score": 2.098102,
        "status": "price_ready",
        "surface": "balanced_state_leadership",
        "ticker": "MU"
      },
      {
        "date": "2025-11-03",
        "rank": 2,
        "score": 1.629857,
        "status": "price_ready",
        "surface": "balanced_state_leadership",
        "ticker": "AMD"
      },
      {
        "date": "2025-11-04",
        "rank": 1,
        "score": 1.840146,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "MU"
      },
      {
        "date": "2025-11-04",
        "rank": 2,
        "score": 1.191764,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "AMD"
      },
      {
        "date": "2025-11-05",
        "rank": 1,
        "score": 2.073149,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "MU"
      },
      {
        "date": "2025-11-05",
        "rank": 2,
        "score": 1.071025,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "GOOG"
      },
      {
        "date": "2025-11-06",
        "rank": 1,
        "score": 2.219401,
        "status": "price_ready",
        "surface": "balanced_state_leadership",
        "ticker": "MU"
      },
      {
        "date": "2025-11-06",
        "rank": 2,
        "score": 1.331625,
        "status": "price_ready",
        "surface": "balanced_state_leadership",
        "ticker": "GOOG"
      },
      {
        "date": "2025-11-07",
        "rank": 1,
        "score": 2.277373,
        "status": "price_ready",
        "surface": "balanced_state_leadership",
        "ticker": "MU"
      },
      {
        "date": "2025-11-07",
        "rank": 3,
        "score": 1.098089,
        "status": "price_ready",
        "surface": "balanced_state_leadership",
        "ticker": "GOOG"
      }
    ]
  },
  "mid_weak": {
    "dropped_candidate_count": 158,
    "price_ready_dropped_count": 158,
    "reason_counts": {
      "same_window_core_ticker": 158
    },
    "sample": [
      {
        "date": "2025-04-23",
        "rank": 1,
        "score": 1.711649,
        "status": "price_ready",
        "surface": "balanced_state_leadership",
        "ticker": "GLD"
      },
      {
        "date": "2025-04-23",
        "rank": 3,
        "score": 1.560639,
        "status": "price_ready",
        "surface": "balanced_state_leadership",
        "ticker": "PLTR"
      },
      {
        "date": "2025-04-24",
        "rank": 1,
        "score": 1.711972,
        "status": "price_ready",
        "surface": "balanced_state_leadership",
        "ticker": "PLTR"
      },
      {
        "date": "2025-04-24",
        "rank": 3,
        "score": 1.633344,
        "status": "price_ready",
        "surface": "balanced_state_leadership",
        "ticker": "GLD"
      },
      {
        "date": "2025-04-25",
        "rank": 1,
        "score": 2.062641,
        "status": "price_ready",
        "surface": "balanced_state_leadership",
        "ticker": "PLTR"
      },
      {
        "date": "2025-04-25",
        "rank": 3,
        "score": 1.35217,
        "status": "price_ready",
        "surface": "balanced_state_leadership",
        "ticker": "GLD"
      },
      {
        "date": "2025-04-28",
        "rank": 1,
        "score": 2.204882,
        "status": "price_ready",
        "surface": "balanced_state_leadership",
        "ticker": "PLTR"
      },
      {
        "date": "2025-04-28",
        "rank": 3,
        "score": 1.281793,
        "status": "price_ready",
        "surface": "balanced_state_leadership",
        "ticker": "GLD"
      },
      {
        "date": "2025-04-29",
        "rank": 1,
        "score": 2.199338,
        "status": "price_ready",
        "surface": "balanced_state_leadership",
        "ticker": "PLTR"
      },
      {
        "date": "2025-04-30",
        "rank": 1,
        "score": 2.213068,
        "status": "price_ready",
        "surface": "balanced_state_leadership",
        "ticker": "PLTR"
      },
      {
        "date": "2025-05-01",
        "rank": 1,
        "score": 1.691171,
        "status": "price_ready",
        "surface": "balanced_state_leadership",
        "ticker": "PLTR"
      },
      {
        "date": "2025-05-02",
        "rank": 1,
        "score": 1.548509,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "PLTR"
      },
      {
        "date": "2025-05-05",
        "rank": 1,
        "score": 1.410689,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "PLTR"
      },
      {
        "date": "2025-05-06",
        "rank": 2,
        "score": 1.119877,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "GLD"
      },
      {
        "date": "2025-05-07",
        "rank": 3,
        "score": 1.007953,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "GLD"
      },
      {
        "date": "2025-05-08",
        "rank": 2,
        "score": 1.220736,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "PLTR"
      },
      {
        "date": "2025-05-12",
        "rank": 1,
        "score": 0.961235,
        "status": "price_ready",
        "surface": "rotation_breakout_leadership",
        "ticker": "DIS"
      },
      {
        "date": "2025-05-13",
        "rank": 1,
        "score": 1.46046,
        "status": "price_ready",
        "surface": "rotation_breakout_leadership",
        "ticker": "COIN"
      },
      {
        "date": "2025-05-13",
        "rank": 2,
        "score": 0.852274,
        "status": "price_ready",
        "surface": "rotation_breakout_leadership",
        "ticker": "PLTR"
      },
      {
        "date": "2025-05-15",
        "rank": 1,
        "score": 0.94747,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "PLTR"
      },
      {
        "date": "2025-05-16",
        "rank": 1,
        "score": 1.074954,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "PLTR"
      },
      {
        "date": "2025-05-19",
        "rank": 1,
        "score": 1.008796,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "PLTR"
      },
      {
        "date": "2025-05-20",
        "rank": 1,
        "score": 1.480026,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "PLTR"
      },
      {
        "date": "2025-05-20",
        "rank": 3,
        "score": 0.823461,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "COIN"
      },
      {
        "date": "2025-05-21",
        "rank": 1,
        "score": 1.112277,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "COIN"
      }
    ]
  },
  "old_thin": {
    "dropped_candidate_count": 113,
    "price_ready_dropped_count": 113,
    "reason_counts": {
      "same_window_core_ticker": 113
    },
    "sample": [
      {
        "date": "2024-10-02",
        "rank": 1,
        "score": 2.692379,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "APP"
      },
      {
        "date": "2024-10-02",
        "rank": 3,
        "score": 0.711175,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "MCD"
      },
      {
        "date": "2024-10-03",
        "rank": 1,
        "score": 2.382468,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "APP"
      },
      {
        "date": "2024-10-04",
        "rank": 1,
        "score": 2.190256,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "APP"
      },
      {
        "date": "2024-10-07",
        "rank": 1,
        "score": 2.288661,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "APP"
      },
      {
        "date": "2024-10-08",
        "rank": 1,
        "score": 2.343999,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "APP"
      },
      {
        "date": "2024-10-09",
        "rank": 1,
        "score": 2.214726,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "APP"
      },
      {
        "date": "2024-10-10",
        "rank": 1,
        "score": 2.249175,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "APP"
      },
      {
        "date": "2024-10-11",
        "rank": 1,
        "score": 2.259952,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "APP"
      },
      {
        "date": "2024-10-14",
        "rank": 1,
        "score": 2.134793,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "APP"
      },
      {
        "date": "2024-10-15",
        "rank": 1,
        "score": 2.123303,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "APP"
      },
      {
        "date": "2024-10-16",
        "rank": 1,
        "score": 2.144756,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "APP"
      },
      {
        "date": "2024-10-17",
        "rank": 1,
        "score": 2.092976,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "APP"
      },
      {
        "date": "2024-10-18",
        "rank": 1,
        "score": 2.1898,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "APP"
      },
      {
        "date": "2024-10-22",
        "rank": 1,
        "score": 1.976386,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "APP"
      },
      {
        "date": "2024-10-23",
        "rank": 1,
        "score": 1.861146,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "APP"
      },
      {
        "date": "2024-10-24",
        "rank": 1,
        "score": 2.18893,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "APP"
      },
      {
        "date": "2024-10-25",
        "rank": 1,
        "score": 2.280395,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "APP"
      },
      {
        "date": "2024-10-28",
        "rank": 1,
        "score": 2.682328,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "APP"
      },
      {
        "date": "2024-10-29",
        "rank": 1,
        "score": 2.395158,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "APP"
      },
      {
        "date": "2024-10-30",
        "rank": 1,
        "score": 2.650676,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "APP"
      },
      {
        "date": "2024-10-31",
        "rank": 1,
        "score": 2.827025,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "APP"
      },
      {
        "date": "2024-11-01",
        "rank": 1,
        "score": 2.702274,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "APP"
      },
      {
        "date": "2024-11-04",
        "rank": 1,
        "score": 2.23193,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "APP"
      },
      {
        "date": "2024-11-04",
        "rank": 3,
        "score": 0.729177,
        "status": "price_ready",
        "surface": "broad_breadth_trend_persistence",
        "ticker": "BKNG"
      }
    ]
  }
}
```

## Production Impact

No live/default orders, core A/B behavior, LLM, news, default backtest strategy, or production adapter changed. Any positive trade-enabled version must be implemented through shared run/backtester policy with parity tests.
