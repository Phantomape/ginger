# exp-20260603-005 Post-Earnings Characteristic Similarity Peer Transfer

Decision: `rejected_post_earnings_characteristic_similarity_peer_transfer`.

Single variable: same-sector Companyfacts/OHLCV characteristic-similarity peer-transfer candidate source after a confirmed positive EPS-surprise issuer reaction.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Events | Issuer reactions | Characteristic candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1562 | -0.0066 | $117,072.92 | $117,987.34 | $+914.42 | +0.0011 | 18 | 42 | 16 | 26 |
| mid_weak | 2.1402 | 2.6964 | +0.5562 | $78,110.11 | $87,833.33 | $+9,723.22 | -0.0068 | 13 | 42 | 7 | 30 |
| old_thin | 0.5911 | 0.5755 | -0.0156 | $39,667.96 | $39,147.80 | $-520.16 | +0.0046 | 12 | 48 | 12 | 13 |

## Aggregate

- EV delta: `0.534` (`0.067645`)
- PnL delta: `$10117.48` (`0.04308`)
- target trades: `43` across `3` windows
- max single positive share: `0.558212`
- positive PnL HHI: `0.348006`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "window_ev_regression",
    "window_pnl_regression",
    "target_concentration_failed"
  ],
  "max_drawdown_worse": 0.0046,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.558212,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": false,
    "positive_pnl_hhi": 0.348006,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 43,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 1,
  "windows_ev_regressed": 2,
  "windows_pnl_regressed": 1
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
