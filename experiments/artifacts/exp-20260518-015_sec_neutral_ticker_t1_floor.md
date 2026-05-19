# exp-20260518-015 SEC Neutral Ticker T+1 Floor

Decision: `rejected_sec_neutral_ticker_t1_floor`.

## Sweep

| Variant | Gate | dEV | dPnL | EV+ | EV- | Max DD d | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|
| ticker_t1_return_gte_+0.0000 | FAIL | +0.0000 | $+0.00 | 0 | 0 | +0.0000% | 10 |
| ticker_t1_return_gte_+0.0050 | FAIL | +0.0000 | $+0.00 | 0 | 0 | +0.0000% | 10 |
| ticker_t1_return_gte_+0.0100 | FAIL | +0.0000 | $+0.00 | 0 | 0 | +0.0000% | 10 |
| ticker_t1_return_gte_+0.0125 | FAIL | +0.0825 | $+2,196.92 | 1 | 0 | +0.0000% | 9 |
| ticker_t1_return_gte_+0.0150 | FAIL | +0.0383 | $+1,020.84 | 2 | 0 | +0.0000% | 7 |
| ticker_t1_return_gte_+0.0200 | FAIL | -0.1950 | $-2,653.15 | 1 | 2 | +0.0000% | 4 |

## Best Window Deltas

```json
{
  "late_strong": {
    "ev_delta": 0.0,
    "max_drawdown_delta": 0.0,
    "neutral_language_closed_trade_count": 8,
    "neutral_language_pnl_delta": 0.0,
    "pnl_delta": 0.0
  },
  "mid_weak": {
    "ev_delta": 0.0,
    "max_drawdown_delta": 0.0,
    "neutral_language_closed_trade_count": 4,
    "neutral_language_pnl_delta": 0.0,
    "pnl_delta": 0.0
  },
  "old_thin": {
    "ev_delta": 0.082476,
    "max_drawdown_delta": -0.01078,
    "neutral_language_closed_trade_count": 9,
    "neutral_language_pnl_delta": 2196.91,
    "pnl_delta": 2196.92
  }
}
```

## Production Impact

```json
{
  "alters_candidate_ranking": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_sizing": false,
  "backtester_adapter_changed": false,
  "default_off_paper_only": true,
  "parity_test_added": false,
  "replay_only": false,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

No JavaScript was used.
