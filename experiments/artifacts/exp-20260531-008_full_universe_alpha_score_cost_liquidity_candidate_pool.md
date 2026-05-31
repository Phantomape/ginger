# exp-20260531-008 Full-Universe Alpha-Score Cost/Liquidity Candidate Pool

Decision: `rejected_full_universe_alpha_score_cost_liquidity_candidate_pool`.

Single variable: keep the exp-20260531-005 full-universe alpha_score top-decile source fixed, but admit only candidates with 20-day average dollar volume >= $200m and signal-day range/close <= 10%.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 6.0013 | +0.8385 | $117,072.92 | $130,176.80 | $+13,103.88 | +0.0091 | 100 | 285 |
| mid_weak | 2.1402 | 4.9044 | +2.7642 | $78,110.11 | $120,498.39 | $+42,388.28 | -0.0190 | 109 | 479 |
| old_thin | 0.5911 | 3.0287 | +2.4376 | $39,667.96 | $100,617.70 | $+60,949.74 | +0.1126 | 121 | 485 |

## Aggregate

- EV delta: `6.0403` (`0.765166`)
- PnL delta: `$116441.9` (`0.495812`)
- target trades: `330` across `3` windows
- max single positive share: `0.515024`
- positive PnL HHI: `0.323382`

## Prior Comparison

```json
{
  "cooldown": {
    "decision": "rejected_full_universe_alpha_score_cooldown_candidate_pool",
    "ev_delta_sum": 3.6871,
    "experiment_id": "exp-20260531-007",
    "max_drawdown_delta_max": 0.0342,
    "max_single_positive_share": 0.18746,
    "pnl_delta_sum": 70480.35,
    "positive_hhi": 0.103883,
    "target_trades": 200
  },
  "current_cost_liquidity": {
    "ev_delta_sum": 6.0403,
    "max_drawdown_delta_max": 0.1126,
    "max_single_positive_share": 0.515024,
    "pnl_delta_sum": 116441.9,
    "positive_hhi": 0.323382,
    "target_trades": 330
  },
  "raw_top1": {
    "decision": "rejected_full_universe_alpha_score_top1_20d_candidate_pool",
    "ev_delta_sum": 6.6893,
    "experiment_id": "exp-20260531-005",
    "max_drawdown_delta_max": 0.1332,
    "max_single_positive_share": 0.502709,
    "pnl_delta_sum": 125182.69,
    "positive_hhi": 0.31675,
    "target_trades": 330
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "drawdown_drift_too_high",
    "target_concentration_failed"
  ],
  "max_drawdown_worse": 0.1126,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.515024,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.323382,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 330,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 3,
  "windows_ev_regressed": 0,
  "windows_pnl_regressed": 0
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, exit, LLM, or news behavior changed. A positive replay result is not promoted without a shared default-off adapter and parity tests.

No JavaScript was used.
