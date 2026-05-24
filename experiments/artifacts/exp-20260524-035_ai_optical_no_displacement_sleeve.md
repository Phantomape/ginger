# exp-20260524-035 AI Optical No-Displacement Paper Sleeve

Decision: `rejected_ai_optical_no_displacement_sleeve`.

Single variable: route the fixed governed AI optical connectivity cohort into an additive default-off paper sleeve instead of core slot competition.

## Trial Accounting

- trial_family: `governed_ai_optical_no_displacement_paper_sleeve`
- changed_variable: `ai_optical_no_displacement_paper_sleeve_routing`
- prior_trial_count: `2`
- multiple_testing_risk_bucket: `high`
- new_evidence_type: `candidate_pool_capital_routing_no_displacement_test`
- snapshot_note: The docs/backtesting.md canonical core snapshots preserve the standard date windows but do not contain the governed optical target tickers, so target-trade discovery uses the existing exp-20260519-029 observation-universe snapshots. Promotion still requires a shared/default-off adapter and parity validation.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.6399 | +0.4771 | $117,072.92 | $129,056.50 | $+11,983.58 | -0.0017 | 5 |
| mid_weak | 2.1402 | 3.0006 | +0.8604 | $78,110.11 | $99,034.90 | $+20,924.79 | +0.0001 | 5 |
| old_thin | 0.5888 | 0.5917 | +0.0029 | $39,517.10 | $39,712.39 | $+195.29 | -0.0002 | 5 |

## Aggregate

- EV delta: `1.3404` (`0.169847`)
- PnL delta: `$33103.66` (`0.141047`)
- target trades: `15` across `3` windows
- max single positive share: `0.525319`
- positive PnL HHI: `0.383406`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0001,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.525319,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": false,
    "positive_pnl_hhi": 0.383406,
    "positive_pnl_hhi_guardrail": 0.45
  },
  "target_trade_count": 15,
  "target_trade_count_min": 10,
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

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
