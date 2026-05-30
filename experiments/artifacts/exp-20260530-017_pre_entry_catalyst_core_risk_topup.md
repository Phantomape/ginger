# exp-20260530-017 Pre-Entry Catalyst Core Risk Top-Up

Decision: `rejected_pre_entry_catalyst_core_risk_topup`.

Single variable: small risk-budget scalar for already-selected core trend/breakout candidates with a PIT high-confidence pre-entry catalyst.

## Best Variant

- Variant: `scalar_1p15`
- Scalar: `1.15`
- Gate 4 passed: `False`
- Aggregate EV delta: `0.0057`
- Aggregate PnL delta: `$2334.25`
- Adjusted trades: `2`

| Window | EV before | EV after | dEV | PnL delta | Max DD delta | Trades delta | Survival delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | 5.1628 | 5.1628 | +0.0000 | $+0.00 | +0.0000 | 0.0 | +0.0000 |
| mid_weak | 2.1402 | 2.1435 | +0.0033 | $+2,174.46 | +0.0102 | 0.0 | +0.0000 |
| old_thin | 0.5911 | 0.5935 | +0.0024 | $+159.79 | +0.0001 | 0.0 | +0.0000 |

## Gate 4

```json
{
  "aggregate_ev_delta": 0.0057,
  "aggregate_pnl_delta": 2334.25,
  "concentration": {
    "max_single_positive_pnl_share": 0.910158,
    "passed": false,
    "positive_incremental_pnl": 1795.37,
    "positive_pnl_hhi": 0.836459,
    "top_positive_ticker": "COIN"
  },
  "failed_reasons": [
    "max_drawdown_drift_above_guardrail",
    "target_trade_count_below_10",
    "target_concentration_failed"
  ],
  "max_drawdown_worse": 0.0102,
  "passed": false,
  "rule": "Pass if aggregate EV/PnL improve, no canonical window regresses on EV or PnL, min survival stays >=5%, max drawdown drift <=0.5pp, >=10 adjusted trades across >=2 windows, and positive incremental PnL concentration stays below 40% single ticker / 0.30 HHI.",
  "target_trade_count": 2,
  "target_windows": [
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_regressed": [],
  "windows_pnl_regressed": []
}
```

## Production Impact

Replay-only scout. No shared policy, production adapter, backtester adapter, watchlist, order path, ranking, exits, LLM path, or live/default order behavior changed.

No JavaScript was used.
