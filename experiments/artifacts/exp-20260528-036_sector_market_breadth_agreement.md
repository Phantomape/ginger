# exp-20260528-036 Sector/Market Breadth Agreement

Decision: `rejected_sector_market_breadth_agreement`.

Single variable: route locked sector-breadth breakout paper candidates only when same-day market volume breadth also passed.

## Gate Questions

- alpha_hypothesis: candidate_pool / entry: sector-breadth breakouts should be higher quality when confirmed by broad market volume-breadth participation on the same signal date.
- history_check: exp-20260526-015 and exp-20260528-032 were nearby rejected sector-breadth runs; this changes cross-source confirmation only.
- single_causal_variable: `sector_breadth_market_breadth_agreement_routing_v1`
- acceptance: Same three docs/backtesting.md windows; positive aggregate EV/PnL; 3/3 EV-improved windows; no PnL-regressed window; >=20 paper trades across all 3 windows; drawdown drift <=0.5pp; survival >=5%; concentration inside guardrails.
- reproducibility: `.venv\Scripts\python.exe -B quant\experiments\exp_20260528_036_sector_market_breadth_agreement.py`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw | Confirmed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1088 | -0.0540 | $117,072.92 | $116,643.71 | $-429.21 | +0.0002 | 3 | 17 | 11 |
| mid_weak | 2.1402 | 2.2999 | +0.1597 | $78,110.11 | $81,274.76 | $+3,164.65 | -0.0011 | 13 | 94 | 49 |
| old_thin | 0.5911 | 0.7232 | +0.1321 | $39,667.96 | $44,371.10 | $+4,703.14 | -0.0079 | 20 | 72 | 49 |

## Aggregate

- EV delta vs core: `0.2378` (`0.030124`)
- PnL delta vs core: `$7438.58` (`0.031674`)
- raw sector-breadth EV/PnL delta vs core: `0.1315` / `$7629.93`
- EV delta vs raw sector-breadth control: `0.1063`
- PnL delta vs raw sector-breadth control: `$-191.35`
- target trades: `36` across `3` windows
- max single positive share: `0.352258`
- positive PnL HHI: `0.242741`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "window_ev_regression",
    "window_pnl_regression"
  ],
  "max_drawdown_worse": 0.0002,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.352258,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.242741,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 36,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 2,
  "windows_ev_regressed": 1,
  "windows_pnl_regressed": 1
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
