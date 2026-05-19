# exp-20260516-042 ISRG Core Adaptation

Decision: `accepted_promoted_shared_policy`.

Single variable: `ISRG_CORE_RISK_MULTIPLIER = 0.25` applied post-sizing to existing ISRG `trend_long` / `breakout_long` signals only.

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1361 | 5.1361 | +0.0000 | $116,727.26 | $116,727.26 | +$0.00 |
| mid_weak | 2.1065 | 2.1084 | +0.0019 | $76,595.08 | $76,665.80 | +$70.72 |
| old_thin | 0.5410 | 0.5903 | +0.0493 | $37,827.90 | $39,615.16 | +$1,787.26 |

Aggregate EV improved `+0.0512`; aggregate PnL improved `+$1,857.98`. The `0.0x` variant failed by regressing `old_thin`, so this is a 0.25x residual-risk exception, not a full quarantine or Healthcare rule.

Production impact: promoted through shared `constants.py` / `portfolio_engine.py`; `backtester.py` captures `isrg_core_risk_multiplier_applied`; focused sizing tests cover the shared path.
