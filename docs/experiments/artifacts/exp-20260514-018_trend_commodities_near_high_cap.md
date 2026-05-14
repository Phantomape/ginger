# exp-20260514-018 Trend Commodities Near-High Cap

Decision: `accepted_shared_policy_promoted`.

Single variable: max position cap for the already-accepted `trend_long + Commodities + pct_from_52w_high >= -3%` sleeve. Entries, exits, ranking, universe, LLM/news logic, raw commodity risk multiplier, heat, and slot limits were unchanged.

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.3768 | 4.4313 | +0.0545 | $99,695.99 | $101,873.18 | $+2,177.19 | -0.0004 | 0.8039 | 4 |
| mid_weak | 1.6788 | 1.7334 | +0.0546 | $62,644.67 | $65,410.59 | $+2,765.92 | +0.0042 | 0.7925 | 4 |
| old_thin | 0.4292 | 0.4520 | +0.0228 | $31,563.29 | $32,522.26 | $+958.97 | +0.0012 | 0.9167 | 1 |

## Sweep

| Cap | Gate 4 | Aggregate dEV | Aggregate dPnL | Max DD worse | Adjusted signals |
|---:|---|---:|---:|---:|---:|
| 0.45 | PASS | +0.0955 | $+3,410.74 | +0.0021 | 9 |
| 0.50 | PASS | +0.1319 | $+5,902.08 | +0.0042 | 9 |

Production impact: promoted into shared `constants.py` / `portfolio_engine.py`; production `run.py` and `backtester.py` both use the same `size_signals` path. Focused production-parity tests passed, and `data/experiments/exp-20260514-018/post_promotion_standard.json` reproduced the selected three-window metrics after promotion.
