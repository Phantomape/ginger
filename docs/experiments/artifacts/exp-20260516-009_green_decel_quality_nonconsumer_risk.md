# exp-20260516-009 Green Deceleration Quality Non-Consumer Risk

Decision: `accepted_and_promoted_shared_policy`.

Single variable: cap-aware post-sizing top-up for existing `trend_long` / `breakout_long` signals with own signal-day green confirmation, positive but decelerating 10d-vs-20d momentum, `trade_quality_score >= 0.95`, and sector outside Consumer Discretionary / Communication Services. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, and slots were unchanged.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.0125 | FAIL | +0.0160 | $+330.11 | late_strong | mid_weak | 6 | +0.0008 |
| 1.0250 | PASS | +0.0309 | $+754.19 | late_strong, mid_weak | - | 7 | +0.0020 |
| 1.0500 | FAIL | +0.0649 | $+1,542.47 | late_strong, mid_weak | old_thin | 10 | +0.0036 |
| 1.0750 | FAIL | +0.0858 | $+2,532.95 | late_strong, mid_weak | old_thin | 10 | +0.0056 |

Selected multiplier: `1.025`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1064 | 5.1344 | +0.0280 | $116,319.10 | $116,686.40 | $+367.30 | +0.0000 | 0.8039 | 3 |
| mid_weak | 2.0987 | 2.1016 | +0.0029 | $76,035.04 | $76,421.93 | $+386.89 | +0.0020 | 0.7925 | 2 |
| old_thin | 0.5294 | 0.5294 | +0.0000 | $37,282.59 | $37,282.59 | $+0.00 | +0.0000 | 0.8667 | 2 |

Production impact: promoted into shared policy. The state is tagged in shared `risk_engine.py`; the 1.025x cap-aware top-up is applied in shared `portfolio_engine.py`; `run.py` and `backtester.py` both use the same shared policy. `backtester.py` only adds sizing-attribution output for the new multiplier. Focused production-parity tests cover both the state tag and the shared sizing helper.

## Shared-Policy Promotion Validation

Canonical shared-policy rerun matched the selected three-window result:

| Window | EV | PnL | Max DD | Trades | Survival |
|---|---:|---:|---:|---:|---:|
| late_strong | 5.1344 | $116,686.40 | 6.65% | 19 | 80.39% |
| mid_weak | 2.1016 | $76,421.93 | 10.83% | 21 | 79.25% |
| old_thin | 0.5294 | $37,282.59 | 10.01% | 22 | 86.67% |

Aggregate promoted-stack EV is `7.7654`; aggregate PnL is `$230,390.92`. Trade count and survival are unchanged from `exp-20260515-028`; worst-window max drawdown drift is `+0.20 pp`, inside Gate 4.
