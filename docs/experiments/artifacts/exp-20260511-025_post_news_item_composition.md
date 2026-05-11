# exp-20260511-025 Post-News Item Composition

Decision: `rejected_semantic_filter_underpowered`

Alpha search. Tests one causal variable inside the PEAD-like post-news continuation sleeve: the semantic composition of the 8-K filing items.

## Three-Window Result

| Variant | Window | Variant EV | EV Delta Vs Core | Variant PnL | PnL Delta Vs Core | SharpeD | Max DD | Event Trades | Event PnL |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| raw_post_news_original | late_strong | 4.1818 | -0.0522 | $94,824.70 | $+737.79 | 4.41 | 4.95% | 13 | $+23.63 |
| raw_post_news_original | mid_weak | 1.9074 | +0.2385 | $66,227.75 | $+4,414.35 | 2.88 | 9.06% | 22 | $+4,325.78 |
| raw_post_news_original | old_thin | 0.4453 | +0.0600 | $31,581.32 | $+3,037.21 | 1.41 | 12.11% | 20 | $+3,037.21 |
| exclude_reg_fd_7_01 | late_strong | 4.3171 | +0.0831 | $96,148.55 | $+2,061.64 | 4.49 | 4.95% | 12 | $+1,347.48 |
| exclude_reg_fd_7_01 | mid_weak | 1.8897 | +0.2208 | $65,841.81 | $+4,028.41 | 2.87 | 9.10% | 19 | $+3,939.84 |
| exclude_reg_fd_7_01 | old_thin | 0.4255 | +0.0402 | $30,609.83 | $+2,065.72 | 1.39 | 11.43% | 18 | $+2,065.72 |
| pure_item_2_02_only | late_strong | 4.4542 | +0.2202 | $97,467.15 | $+3,380.24 | 4.57 | 4.91% | 10 | $+2,666.09 |
| pure_item_2_02_only | mid_weak | 1.8740 | +0.2051 | $65,524.93 | $+3,711.53 | 2.86 | 9.13% | 17 | $+3,622.96 |
| pure_item_2_02_only | old_thin | 0.4091 | +0.0238 | $29,859.64 | $+1,315.53 | 1.37 | 11.29% | 15 | $+1,315.53 |

## Best Variant

- Best variant: `pure_item_2_02_only`
- Aggregate EV delta vs core: `+0.4491`
- Aggregate PnL delta vs core: `$+8,407.30`
- EV windows improved/regressed: `3` / `0`
- Gate passed: `False`

## Decision Rationale

Rejected for promotion. The item-composition gate did not clear the pre-registered Gate 4 rule against the current core: it required no EV-regressing canonical window, non-negative late_strong EV, positive aggregate EV/PnL, and aggregate EV >10% or PnL >5%.

## Production Impact

Replay only. No production orders, shared core policy, sizing, ranking, exits, LLM/news prompt, or live universe changed. A positive future version would need a shared default-off post-news sleeve adapter and parity tests before any live/default promotion.
