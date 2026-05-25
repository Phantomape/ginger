# exp-20260525-003 AI Optical IWM-Confirmed Fixed-Notional Sleeve

Decision: `promising_replay_only_ai_optical_iwm_confirmed_fixed_notional_sleeve`.

Single variable: route the fixed governed AI optical connectivity cohort into an additive fixed-notional default-off paper sleeve only when prior-close IWM 20d momentum leads SPY by at least 30bp.

## Trial Accounting

- trial_family: `governed_ai_optical_iwm_confirmed_fixed_notional_paper_sleeve`
- changed_variable: `ai_optical_iwm_confirmed_fixed_notional_paper_sleeve_routing_v1`
- prior_trial_count: `4`
- multiple_testing_risk_bucket: `high`
- new_evidence_type: `production_visible_iwm_spy_smallcap_confirmation_plus_fixed_notional_sleeve_routing_for_existing_governed_optical_cohort`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target trades | Filtered |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.4546 | +0.2918 | $117,072.92 | $120,405.83 | $+3,332.91 | -0.0007 | 3 | 2 |
| mid_weak | 2.1402 | 2.2837 | +0.1435 | $78,110.11 | $81,557.46 | $+3,447.35 | +0.0007 | 5 | 0 |
| old_thin | 0.5888 | 0.6017 | +0.0129 | $39,517.10 | $40,109.62 | $+592.52 | -0.0004 | 2 | 3 |

## Aggregate

- EV delta: `0.4482` (`0.056793`)
- PnL delta: `$7372.78` (`0.031414`)
- target trades: `10` across `3` windows
- max single positive share: `0.327971`
- positive PnL HHI: `0.2785`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0007,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": true,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.327971,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": true,
    "positive_pnl_hhi": 0.2785,
    "positive_pnl_hhi_guardrail": 0.45
  },
  "target_trade_count": 10,
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
