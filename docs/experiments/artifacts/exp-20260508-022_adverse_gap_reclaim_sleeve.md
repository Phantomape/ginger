# exp-20260508-022 - Adverse-gap reclaim delayed-entry sleeve

## Decision

rejected.

## Hypothesis

Keep the accepted 2% adverse-gap cancel intact, but treat a later same-day reclaim of the original signal entry as a default-off delayed-entry satellite candidate.

## Results

| Variant | Gate 4 | Aggregate EV delta | Aggregate PnL delta | Satellite trades | EV +/- windows |
| --- | --- | ---: | ---: | ---: | --- |
| intraday_reclaim_next_open | fail | -0.0411 | $153.08 | 2 | 1/1 |
| close_reclaim_next_open | fail | -0.0829 | $-739.25 | 1 | 0/1 |

## Mechanism Read

The reclaim idea is distinct from raw gap-cancel bypasses, but the tested daily reclaim signals do not deliver enough stable marginal EV. The accepted adverse-gap cancel should remain unchanged; a valid retry needs richer intraday structure, fresh event/news context, or forward paper evidence.

## Production Impact

Replay-only. No production order path, shared policy, sizing, entry filter, exit, LLM, news, universe, or add-on behavior was changed.
