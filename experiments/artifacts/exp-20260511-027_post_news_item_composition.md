# exp-20260511-027 Post-News Item Composition

Decision: `rejected_item_composition_gate`

Single variable: 8-K item-composition gate inside the locked exp-20260509-020 post-news continuation pattern.

| Stack | Window | EV | EV Δ vs core | EV Δ vs raw | PnL Δ vs core | PnL Δ vs raw | Event trades |
|---|---|---:|---:|---:|---:|---:|---:|
| raw_post_news | late_strong | 4.1818 | -0.0522 | n/a | +737.79 | n/a | 13 |
| raw_post_news | mid_weak | 1.9074 | +0.2385 | n/a | +4414.35 | n/a | 22 |
| raw_post_news | old_thin | 0.4453 | +0.0600 | n/a | +3037.21 | n/a | 20 |
| exclude_auxiliary_items | late_strong | 4.4542 | +0.2202 | +0.2724 | +3380.24 | +2642.45 | 10 |
| exclude_auxiliary_items | mid_weak | 1.8740 | +0.2051 | -0.0334 | +3711.53 | -702.82 | 17 |
| exclude_auxiliary_items | old_thin | 0.4091 | +0.0238 | -0.0362 | +1315.53 | -1721.68 | 15 |
| pure_item_2_02_only | late_strong | 4.4542 | +0.2202 | +0.2724 | +3380.24 | +2642.45 | 10 |
| pure_item_2_02_only | mid_weak | 1.8740 | +0.2051 | -0.0334 | +3711.53 | -702.82 | 17 |
| pure_item_2_02_only | old_thin | 0.4091 | +0.0238 | -0.0362 | +1315.53 | -1721.68 | 15 |

## Best Variant

- Best variant: `exclude_auxiliary_items`
- Aggregate EV delta vs raw post-news: `+0.2028`
- Aggregate PnL delta vs raw post-news: `$+217.95`
- Aggregate EV delta vs core: `+0.4491`
- Aggregate PnL delta vs core: `$+8,407.30`
- Gate 4 passed: `False`

## Interpretation

The clean Item 2.02 / auxiliary-item discriminator did not improve the raw post-news continuation surface enough to justify promotion. This rejects nearby item-composition gating on the frozen sample.

## Production Impact

Replay-only alpha search. No shared policy, run adapter, backtester adapter, order path, ranking, sizing, LLM prompt, or live universe changed.
