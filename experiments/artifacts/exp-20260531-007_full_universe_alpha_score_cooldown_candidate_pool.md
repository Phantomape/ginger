# exp-20260531-007 Full-Universe Alpha-Score Cooldown Candidate Pool

Decision: `rejected_full_universe_alpha_score_cooldown_candidate_pool`.

Single variable: keep the exp-20260531-005 full-universe alpha_score top-decile candidate source fixed, but add a 20-trading-day same-ticker admission cooldown before the top-1 daily paper selection.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.5030 | -0.6598 | $117,072.92 | $110,637.45 | $-6,435.47 | +0.0094 | 50 | 287 |
| mid_weak | 2.1402 | 5.5027 | +3.3625 | $78,110.11 | $126,785.91 | $+48,675.80 | -0.0254 | 77 | 503 |
| old_thin | 0.5911 | 1.5755 | +0.9844 | $39,667.96 | $67,907.98 | $+28,240.02 | +0.0342 | 73 | 530 |

## Aggregate

- EV delta: `3.6871` (`0.46707`)
- PnL delta: `$70480.35` (`0.300107`)
- target trades: `200` across `3` windows
- max single positive share: `0.18746`
- positive PnL HHI: `0.103883`

## Versus Raw Top-1

- raw EV delta: `6.6893`; cooldown EV delta: `3.6871`
- raw PnL delta: `$125182.69`; cooldown PnL delta: `$70480.35`
- raw max DD drift: `0.1332`; cooldown max DD drift: `0.0342`
- raw max single positive share: `0.502709`; cooldown: `0.18746`
- raw positive HHI: `0.31675`; cooldown: `0.103883`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "window_ev_regression",
    "window_pnl_regression",
    "drawdown_drift_too_high"
  ],
  "max_drawdown_worse": 0.0342,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.18746,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.103883,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 200,
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

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, exit, LLM, or news behavior changed. A positive replay result is not promoted without a shared default-off adapter and parity tests.

No JavaScript was used.
