# exp-20260506-011 time-stop days sweep

## Decision

Rejected/no-op. `TIME_STOP_DAYS` values 30, 45, and 60 produced identical
three-window metrics, and no accepted trade exited via `time_stop`.

## Alpha hypothesis

Shorter or longer time stops might improve exit lifecycle by freeing slots
or avoiding stale drift after accepted signals fail to hit target or stop.

## Three-window result

| TIME_STOP_DAYS | late EV | mid EV | old EV | agg EV delta | agg PnL delta | time_stop exits | decision |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 30 | 3.4191 | 1.4415 | 0.3179 | 0.0000 | $0.00 | 0 | rejected |
| 45 | 3.4191 | 1.4415 | 0.3179 | 0.0000 | $0.00 | 0 | baseline |
| 60 | 3.4191 | 1.4415 | 0.3179 | 0.0000 | $0.00 | 0 | rejected |

## Mechanism insight

The accepted stack exits before the time-stop surface is reached in the
canonical windows. Nearby time-stop values should not be retried without a
trade-duration cohort showing that the rule would actually fire.

## Production parity

No shared policy, run adapter, order path, sizing path, signal path, or
backtester adapter was changed. There is no production/backtest mismatch to
promote because the experiment was rejected.
