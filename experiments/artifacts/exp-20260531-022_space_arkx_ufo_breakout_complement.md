# exp-20260531-022 Space ARKX/UFO Breakout Complement

Decision: `accepted_default_off_space_arkx_ufo_breakout_complement`.

Single variable: keep the accepted Space trend high-close intraday-thrust branch fixed, and add a breakout_long high-close/thrust complement only when ARKX 20d return is greater than UFO 20d return.

## Gate Questions

- alpha_hypothesis: candidate_pool/risk allocation: keep the accepted Space trend high-close intraday-thrust route fixed and add only a breakout_long complement when ARKX 20d return exceeds UFO 20d return.
- single_causal_variable: `space_high_close_thrust_plus_arkx_ufo_breakout_branch_v1`
- reproducibility: `.venv\Scripts\python.exe quant\experiments\exp_20260531_022_space_arkx_ufo_breakout_complement.py`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target trades | Filtered |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.5755 | 4.7332 | +0.1577 | $109,198.53 | $111,371.18 | $+2,172.65 | +0.0000 | 1 | 8 |
| mid_weak | 2.6219 | 3.2429 | +0.6210 | $88,276.19 | $99,171.46 | $+10,895.27 | -0.0021 | 4 | 3 |
| old_thin | 0.3787 | 0.4540 | +0.0753 | $28,472.77 | $31,526.05 | $+3,053.28 | -0.0023 | 1 | 3 |

## Aggregate Versus Core

- EV delta: `0.854` (`0.112723`)
- PnL delta: `$16121.2` (`0.071349`)
- target trades: `6` across `3` windows
- max single positive share: `0.286598`

## Incremental Versus Accepted Space Route

- baseline: `exp-20260529-020`
- EV delta: `0.0753`
- PnL delta: `$3053.28`
- EV-regressed windows: `0`
- PnL-regressed windows: `0`
- breakout complement trades: `1`
- breakout complement PnL: `$3053.28`

## Gate 4

```json
{
  "acceptance_rule": "positive aggregate EV/PnL versus core; zero EV/PnL-regressed windows versus core; aggregate EV/PnL improvement versus accepted exp-20260529-020; >=6 target trades across 3 windows; drawdown drift <=0.5pp; survival >=5%; concentration guard passes",
  "accepted_baseline_improved": true,
  "aggregate_ev_delta_positive": true,
  "aggregate_expected_value_score_delta": 0.854,
  "aggregate_pnl_delta_positive": true,
  "aggregate_total_pnl_delta": 16121.2,
  "base_gate4_passed": true,
  "incremental_branch_observed": true,
  "max_drawdown_worse": 0.0,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": true,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.286598,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": true,
    "positive_pnl_hhi": 0.215023,
    "positive_pnl_hhi_guardrail": 0.45
  },
  "target_trade_count": 6,
  "target_trade_count_min": 6,
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

If retained, metadata is surfaced through the shared default-off Space observation slot. Live Space slots remain zero, and no production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
