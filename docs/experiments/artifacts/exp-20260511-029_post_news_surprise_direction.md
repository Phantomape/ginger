# exp-20260511-029 Post-News Surprise-Direction Gate

Decision: `rejected_surprise_direction_gate`

Single variable: `surprise_direction` semantic gate inside the locked exp-20260509-020 post-news continuation pattern.

| Stack | Window | EV | EV delta vs core | EV delta vs raw | PnL delta vs core | PnL delta vs raw | Event trades |
|---|---|---:|---:|---:|---:|---:|---:|
| raw_post_news | late_strong | 4.1818 | -0.0522 | n/a | +737.79 | n/a | 13 |
| raw_post_news | mid_weak | 1.9074 | +0.2385 | n/a | +4414.35 | n/a | 22 |
| raw_post_news | old_thin | 0.4453 | +0.0600 | n/a | +3037.21 | n/a | 20 |
| unknown_only | late_strong | 4.1818 | -0.0522 | +0.0000 | +737.79 | +0.00 | 13 |
| unknown_only | mid_weak | 1.8958 | +0.2269 | -0.0116 | +4241.05 | -173.30 | 19 |
| unknown_only | old_thin | 0.4581 | +0.0728 | +0.0128 | +3490.90 | +453.69 | 19 |
| positive_only | late_strong | 4.2660 | +0.0320 | +0.0842 | +714.15 | -23.64 | 0 |
| positive_only | mid_weak | 1.6243 | -0.0446 | -0.2831 | -749.78 | -5164.13 | 2 |
| positive_only | old_thin | 0.3869 | +0.0016 | -0.0584 | +117.42 | -2919.79 | 2 |
| exclude_directional | late_strong | 4.1818 | -0.0522 | +0.0000 | +737.79 | +0.00 | 13 |
| exclude_directional | mid_weak | 1.8958 | +0.2269 | -0.0116 | +4241.05 | -173.30 | 19 |
| exclude_directional | old_thin | 0.4581 | +0.0728 | +0.0128 | +3490.90 | +453.69 | 19 |

## Best Variant

- Best variant: `unknown_only`
- Aggregate EV delta vs raw post-news: `+0.0012`
- Aggregate PnL delta vs raw post-news: `$+280.39`
- Aggregate EV delta vs core: `+0.2475`
- Aggregate PnL delta vs core: `$+8,469.74`
- Gate 4 passed: `False`

## Direction Attribution

- raw_post_news late_strong: OrderedDict([('unknown', {'trade_count': 13, 'wins': 5, 'win_rate': 0.3846, 'pnl': 23.63})])
- raw_post_news mid_weak: OrderedDict([('negative', {'trade_count': 1, 'wins': 1, 'win_rate': 1.0, 'pnl': 418.44}), ('positive', {'trade_count': 2, 'wins': 1, 'win_rate': 0.5, 'pnl': -1006.86}), ('unknown', {'trade_count': 19, 'wins': 11, 'win_rate': 0.5789, 'pnl': 4914.2})])
- raw_post_news old_thin: OrderedDict([('positive', {'trade_count': 2, 'wins': 1, 'win_rate': 0.5, 'pnl': 117.42}), ('unknown', {'trade_count': 18, 'wins': 12, 'win_rate': 0.6667, 'pnl': 2919.79})])

## Interpretation

The PIT surprise_direction semantic label did not improve the locked post-news continuation surface enough to justify promotion. Explicit positive/negative labels were sparse and did not rescue the raw PEAD-like sleeve from the materiality problem.

## Production Impact

Replay-only alpha search. No shared policy, run adapter, backtester adapter, order path, ranking, sizing, LLM prompt, or live universe changed.
