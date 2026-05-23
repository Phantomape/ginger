# exp-20260523-011 Core-Misfit Trend Long No-Entry Shadow

Decision: `rejected_core_misfit_trend_long_no_entry`.

Single variable: post-sizing shares become zero only for `trend_long` signals in the current CORE_MISFIT_PAPER ticker set.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before target trades | After target trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1628 | +0.0000 | $117,072.92 | $117,072.92 | $+0.00 | 0 | 0 |
| mid_weak | 2.1402 | 2.1405 | +0.0003 | $78,110.11 | $78,119.38 | $+9.27 | 1 | 0 |
| old_thin | 0.5911 | 0.5156 | -0.0755 | $39,667.96 | $36,828.59 | $-2,839.37 | 6 | 0 |

## Gate 4

```json
{
  "after_target_candidate_event_summary": {
    "by_decision": {
      "no_shares": 10
    },
    "by_ticker_decision": {
      "DDOG": {
        "no_shares": 2
      },
      "ISRG": {
        "no_shares": 2
      },
      "TSM": {
        "no_shares": 4
      },
      "V": {
        "no_shares": 2
      }
    },
    "candidate_event_count": 10,
    "windows_with_target_candidates": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ]
  },
  "after_target_trade_summary": {
    "by_ticker_count": {},
    "by_ticker_pnl": {},
    "total_pnl": 0,
    "trade_count": 0,
    "windows_with_trades": []
  },
  "aggregate_ev_delta_positive": false,
  "aggregate_pnl_delta_positive": false,
  "before_target_trade_summary": {
    "by_ticker_count": {
      "DDOG": 1,
      "ISRG": 1,
      "TSM": 3,
      "V": 2
    },
    "by_ticker_pnl": {
      "DDOG": -9.86,
      "ISRG": -440.94,
      "TSM": -133.35,
      "V": -3684.85
    },
    "total_pnl": -4269.0,
    "trade_count": 7,
    "windows_with_trades": [
      "mid_weak",
      "old_thin"
    ]
  },
  "improved_windows": [
    "mid_weak"
  ],
  "max_drawdown_worse": 0.0,
  "max_drawdown_worse_guardrail": 0.005,
  "no_share_count": 10,
  "passed": false,
  "regressed_windows": [
    "old_thin"
  ],
  "survival_guard_passed": true
}
```

## Production Impact

No shared production policy, run adapter, backtester adapter, watchlist, or order path changed. Promotion would require a shared rule plus parity coverage.

No JavaScript was used.
