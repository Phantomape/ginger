# exp-20260507-023 state_surface_collision_rank

## Hypothesis

When core A/B entry candidates exceed available slots, ranking the collision set by a point-in-time state-surface score improves allocation quality without adding ticker noise.

## Non-repeat check

This is not an event-bundle threshold/source/notional retune, not an LLM/earnings/options experiment, and not a raw watchlist expansion. It uses the already validated state-surface mechanism only as a scarce-slot ordering signal.

## Three-window results

| Window | EV before | EV after | PnL before | PnL after | SharpeD before | SharpeD after | Gate4 |
|---|---:|---:|---:|---:|---:|---:|---|
| late_strong | 3.6257 | 3.478 | 82030.12 | 80509.12 | 4.42 | 4.32 | FAIL |
| mid_weak | 1.5478 | 1.48 | 57542.74 | 56062.37 | 2.69 | 2.64 | FAIL |
| old_thin | 0.3359 | 0.1306 | 26242.68 | 14199.86 | 1.28 | 0.92 | FAIL |

## Decision

`rejected` - insufficient stable three-window improvement versus current accepted stack

## Production impact

`replay_only`: no shared policy, run adapter, sizing, exits, LLM/news, event sleeve, or universe membership changed. If this had passed, the next step would have been a shared production parity policy rather than leaving ranking in the backtester.

## Files

- `data/experiments/exp-20260507-023/state_surface_collision_rank.json`
- `experiments/logs/exp-20260507-023.json`
- `experiments/tickets/exp-20260507-023.json`
