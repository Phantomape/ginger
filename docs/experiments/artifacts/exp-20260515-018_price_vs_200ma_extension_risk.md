# exp-20260515-018 Price-vs-200MA Extension Risk

Decision: `accepted_for_shared_policy_implementation`.

Single variable: cap-aware post-sizing risk top-up for `trend_long` and `breakout_long` stock signals whose `price_vs_200ma_pct` is in the same-day top quartile of feature-complete non-ETF/non-commodity stocks. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.025 | PASS | +0.0208 | $+882.67 | late_strong, mid_weak, old_thin | - | 15 | +0.0010 |
| 1.050 | FAIL | +0.0316 | $+1,801.21 | mid_weak, old_thin | late_strong | 22 | +0.0020 |
| 1.100 | FAIL | +0.0448 | $+3,666.03 | mid_weak, old_thin | late_strong | 26 | +0.0039 |
| 1.150 | FAIL | +0.0697 | $+5,319.43 | mid_weak, old_thin | late_strong | 28 | +0.0059 |

Selected multiplier: `1.025`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.0322 | 5.0334 | +0.0012 | $114,886.19 | $115,183.05 | $+296.86 | 0.8039 | 4 |
| mid_weak | 1.9947 | 2.0103 | +0.0156 | $72,796.75 | $73,104.97 | $+308.22 | 0.7925 | 6 |
| old_thin | 0.5059 | 0.5099 | +0.0040 | $35,379.65 | $35,657.24 | $+277.59 | 0.9167 | 5 |

## Promotion Closeout

Production impact:

```text
shared_policy_changed: true
backtester_adapter_changed: true
run_adapter_changed: true
replay_only: false
parity_test_added: true
```

The accepted state now lives in shared `risk_engine.py` and `portfolio_engine.py`;
`run.py` and `backtester.py` both consume that path. Backtester attribution tracks
`price_vs_200ma_extension_risk_multiplier_applied`.
