# exp-20260526-012 AI Optical Dual Market Confirmation

Decision: `rejected_ai_optical_dual_market_confirmation_candidate_expansion`.

Single variable: expand the accepted AI optical IWM-only default-off paper route to admit candidates when either IWM/SPY or QQQ/SPY market confirmation passes.

## Trial Accounting

- trial_family: `governed_ai_optical_dual_market_confirmation_candidate_expansion`
- changed_variable: `ai_optical_iwm_or_qqq_market_confirmation_candidate_expansion_v1`
- prior_trial_count: `2`
- multiple_testing_risk_bucket: `moderate`
- new_evidence_type: `new_production_visible_free_qqq_growth_tape_confirmation`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Before trades | After trades | Added |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.4546 | 5.5315 | +0.0769 | $120,405.83 | $121,841.95 | $+1,436.12 | +0.0003 | 3 | 5 | 2 |
| mid_weak | 2.2837 | 2.2837 | +0.0000 | $81,557.46 | $81,557.46 | $+0.00 | +0.0000 | 5 | 5 | 0 |
| old_thin | 0.6017 | 0.5915 | -0.0102 | $40,109.62 | $39,695.64 | $-413.98 | +0.0002 | 2 | 3 | 1 |

## Aggregate

- EV delta vs accepted IWM-only: `0.0667` (`0.007998`)
- PnL delta vs accepted IWM-only: `$1022.14` (`0.004222`)
- added trades: `3` / `$1022.14`
- after max single positive share: `0.31823`
- after positive PnL HHI: `0.245384`

## Gate 4

```json
{
  "added_trade_count": 3,
  "added_trade_count_min": 2,
  "after_target_trade_count": 13,
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "before_target_trade_count": 10,
  "max_drawdown_worse": 0.0003,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.31823,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": true,
    "positive_pnl_hhi": 0.245384,
    "positive_pnl_hhi_guardrail": 0.45
  },
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 1,
  "windows_ev_regressed": 1,
  "windows_pnl_regressed": 1
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
