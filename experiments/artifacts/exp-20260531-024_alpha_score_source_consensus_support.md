# exp-20260531-024 Alpha-Score Source-Consensus Support

Decision: `positive_replay_lead_not_promoted_requires_shared_source_consensus_adapter`.

Single variable: apply `1.25x` paper notional only to accepted alpha_score market-regime candidates that overlap accepted FINRA/IWM or VBB paper sources on the same signal date.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Consensus trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.7556 | +0.5928 | $117,072.92 | $124,854.08 | $+7,781.16 | +0.0000 | 52 | 5 |
| mid_weak | 2.1402 | 2.8788 | +0.7386 | $78,110.11 | $91,103.22 | $+12,993.11 | -0.0029 | 62 | 9 |
| old_thin | 0.5911 | 1.0206 | +0.4295 | $39,667.96 | $54,004.65 | $+14,336.69 | -0.0074 | 37 | 10 |

## Aggregate

- EV delta vs core: `1.7609` (`0.223065`)
- PnL delta vs core: `$35110.96` (`0.149503`)
- supported trades: `24` across `3` windows
- incremental support PnL: `$2340.43`
- max single positive share: `0.276114`
- positive PnL HHI: `0.187684`

## Comparison Versus Accepted exp-20260531-021

```json
{
  "aggregate_expected_value_score_delta_vs_exp021": 0.117,
  "aggregate_total_pnl_delta_vs_exp021": 2340.44,
  "available": true,
  "baseline_after_aggregate": {
    "expected_value_score_sum": 9.538,
    "max_drawdown_delta_max": 0.0,
    "total_pnl_sum": 267621.51
  },
  "baseline_artifact": "data/experiments/exp-20260531-021/exp_20260531_021_full_universe_alpha_score_market_regime_safe_notional.json",
  "baseline_experiment_id": "exp-20260531-021",
  "current_after_aggregate": {
    "expected_value_score_sum": 9.655,
    "max_drawdown_delta_max": 0.0,
    "total_pnl_sum": 269961.95
  },
  "incremental_vs_exp021": {
    "late_strong": {
      "expected_value_score_delta": 0.0465,
      "max_drawdown_delta": 0.0,
      "total_pnl_delta": 745.9
    },
    "mid_weak": {
      "expected_value_score_delta": 0.034,
      "max_drawdown_delta": -0.0005,
      "total_pnl_delta": 500.13
    },
    "old_thin": {
      "expected_value_score_delta": 0.0365,
      "max_drawdown_delta": -0.0012,
      "total_pnl_delta": 1094.41
    }
  },
  "windows_ev_regressed_vs_exp021": 0,
  "windows_pnl_regressed_vs_exp021": 0
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [],
  "max_drawdown_worse": 0.0,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": true,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.276114,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.187684,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 151,
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

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, exit, LLM, or news behavior changed.

No JavaScript was used.
