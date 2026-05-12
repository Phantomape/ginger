# exp-20260511-104 Post-News Pre-Event RS20 Context

Decision: `rejected_pre_event_rs20_context_gate`

Single variable: pre-event 20-trading-day ticker return minus SPY return inside the locked PEAD-like post-news continuation surface.

| Stack | Window | EV | EV delta vs core | EV delta vs raw | PnL delta vs core | PnL delta vs raw | Event trades |
|---|---:|---:|---:|---:|---:|---:|---:|
| raw_post_news | late_strong | 4.1818 | -0.0522 | n/a | +737.79 | n/a | 13 |
| raw_post_news | mid_weak | 1.9074 | +0.2385 | n/a | +4414.35 | n/a | 22 |
| raw_post_news | old_thin | 0.4453 | +0.0600 | n/a | +3037.21 | n/a | 20 |
| exclude_rs20_laggard_5pp | late_strong | 4.2997 | +0.0657 | +0.1179 | +1675.01 | +937.22 | 8 |
| exclude_rs20_laggard_5pp | mid_weak | 1.9207 | +0.2518 | +0.0133 | +4645.12 | +230.77 | 16 |
| exclude_rs20_laggard_5pp | old_thin | 0.4723 | +0.0870 | +0.0270 | +3806.98 | +769.77 | 15 |
| rs20_positive_only | late_strong | 4.3096 | +0.0756 | +0.1278 | +1468.84 | +731.05 | 4 |
| rs20_positive_only | mid_weak | 1.9218 | +0.2529 | +0.0144 | +4683.23 | +268.88 | 14 |
| rs20_positive_only | old_thin | 0.5074 | +0.1221 | +0.0621 | +5057.97 | +2020.76 | 14 |
| rs20_leader_5pp_only | late_strong | 4.2201 | -0.0139 | +0.0383 | +534.91 | -202.88 | 1 |
| rs20_leader_5pp_only | mid_weak | 1.9183 | +0.2494 | +0.0109 | +4564.99 | +150.64 | 9 |
| rs20_leader_5pp_only | old_thin | 0.4793 | +0.0940 | +0.0340 | +3840.66 | +803.45 | 9 |

## Best Variant

- Best variant: `rs20_positive_only`
- Aggregate EV delta vs raw post-news: `+0.2043`
- Aggregate PnL delta vs raw post-news: `$+3,020.69`
- Aggregate EV delta vs core: `+0.4506`
- Aggregate PnL delta vs core: `$+11,210.04`
- Gate 4 passed: `False`

## Interpretation

Pre-event RS20 context did not improve the locked post-news continuation surface enough to justify promotion. This rejects RS20 sign/5pp gates as the next same-sample post-news discriminator.

## Production Impact

Replay-only alpha search. No shared policy, run adapter, backtester adapter, order path, ranking, sizing, LLM prompt, or live universe changed.
