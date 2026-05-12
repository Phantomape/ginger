# exp-20260511-113 Space one-slot cap

- Decision: `rejected_space_one_slot_cap`
- Single variable: official Space concurrent position cap.
- Best variant: `space_one_slot_cap`
- Aggregate EV delta vs accepted: `+0.0000`
- Aggregate PnL delta vs accepted: `$+0.00`

## Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.9509 | 4.9509 | +0.0000 | 104,454.52 | 104,454.52 | +0.00 | 23 | 0.0629 | 0.8070 |
| mid_weak | 4.2199 | 4.2199 | +0.0000 | 101,437.88 | 101,437.88 | +0.00 | 26 | 0.0471 | 0.8169 |
| old_thin | 0.7694 | 0.7694 | +0.0000 | 48,093.28 | 48,093.28 | +0.00 | 24 | 0.1012 | 0.8919 |

## Interpretation

The one-slot Space cap did not beat the accepted exp-105 stack. Space sleeve optimization should not solve overlap by reducing capacity alone; the next valid direction needs forward catalyst quality or replacement-value evidence.

## Production Impact

Default-off Space metadata experiment. Live Space slots remain zero; positive promotion would need the shared Space forward hypothesis and production observe-only slot metadata to stay aligned.
