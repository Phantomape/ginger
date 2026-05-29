# exp-20260529-020 Space High-Close Intraday-Thrust Sleeve

Decision: `accepted_default_off_space_trend_high_close_intraday_thrust_sleeve`.

Single variable: route the governed full-history Space observation pool into an additive fixed-notional default-off paper sleeve only when the existing signal engine labels the discovery `trend_long`, signal-day close-location is `>= 0.84`, and signal-day open-to-close return is `>= 4%`.

## Gate Questions

- alpha_hypothesis: entry/candidate_pool/risk allocation: accepted governed Space high-close trend candidates may have stronger replacement value when the signal-day open-to-close gain is at least 4%.
- single_causal_variable: `space_governed_trend_high_close_intraday_thrust_fixed_notional_paper_sleeve_routing_v1`
- reproducibility: `.venv\Scripts\python.exe quant\experiments\exp_20260529_020_space_trend_high_close_orderly_range_fixed_notional_sleeve.py`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target trades | Filtered |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.5755 | 4.7332 | +0.1577 | $109,198.53 | $111,371.18 | $+2,172.65 | +0.0000 | 1 | 8 |
| mid_weak | 2.6219 | 3.2429 | +0.6210 | $88,276.19 | $99,171.46 | $+10,895.27 | -0.0021 | 4 | 3 |
| old_thin | 0.3787 | 0.3787 | +0.0000 | $28,472.77 | $28,472.77 | $+0.00 | +0.0000 | 0 | 4 |

## Aggregate Versus Core

- EV delta: `0.7787` (`0.102784`)
- PnL delta: `$13067.92` (`0.057836`)
- target trades: `5` across `2` windows
- max single positive share: `0.353561`

## Incremental Versus Accepted High-Close

- baseline: `exp-20260528-026`
- EV delta: `0.0282`
- PnL delta: `$559.06`
- EV-regressed windows: `0`
- PnL-regressed windows: `0`

## Gate 4

```json
{
  "acceptance_rule": "positive aggregate EV/PnL versus core; zero EV/PnL-regressed windows versus core; aggregate EV/PnL improvement versus accepted exp-20260528-026 high-close baseline; >=5 target trades across >=2 windows; drawdown drift <=0.5pp; survival >=5%; concentration guard passes",
  "accepted_high_close_baseline_improved": true,
  "aggregate_ev_delta_positive": true,
  "aggregate_expected_value_score_delta": 0.7787,
  "aggregate_pnl_delta_positive": true,
  "aggregate_total_pnl_delta": 13067.92,
  "base_gate4_passed": true,
  "max_drawdown_worse": 0.0,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": true,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.353561,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": true,
    "positive_pnl_hhi": 0.27265,
    "positive_pnl_hhi_guardrail": 0.45
  },
  "target_trade_count": 5,
  "target_trade_count_min": 5,
  "target_window_count_min": 2,
  "target_windows": [
    "late_strong",
    "mid_weak"
  ],
  "windows_ev_improved": 2,
  "windows_ev_regressed": 0,
  "windows_pnl_regressed": 0
}
```

## Production Impact

Gate-passing metadata is surfaced through the shared feature layer and default-off Space observation slot. Live Space slots remain zero, and no production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
