# exp-20260720-003: FINRA venue/short-crowding entry admission

- Decision: `rejected`
- Accepted alpha: `false`
- Live ready: `false`
- Locked source hash: `2d0771e246f724db62ad7c412153634690f73f3ec595e6cb341e6bd3282dcd05`
- Price replay count: one completed three-window before/after run; this report was reclassified from those persisted results without replaying prices.

## Gate summary

- Gate 1 exact baseline: `true`
- Gate 2 source/PIT/revision/admission: `true`
- Gate 3 survival: `true`
- Candidate-touch floor: `true`
- Gate 4 canonical alpha: `false`

## Results

| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Denied | Baseline entered touches |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.1067 | 3.8249 | -0.2818 | $70,075.18 | $68,179.73 | 3 | 1 |
| mid_weak | 1.9908 | 1.9908 | 0.0000 | $51,976.41 | $51,976.41 | 1 | 0 |
| old_thin | 0.1082 | 0.0328 | -0.0754 | $8,940.77 | $4,833.81 | 7 | 4 |

Aggregate EV changed from `6.2057` to `5.8485` (`-0.3572`). Aggregate PnL changed from `$130,992.36` to `$124,989.95` (`-6,002.41`).

## Revision-safe source contract

- Raw CSV files hash-bound: `46`
- Normalized rows raw-matched: `46511`
- Revised rows failed closed: `152`
- Frozen-universe revised rows by window: `{"late_strong": 11, "mid_weak": 3, "old_thin": 4}`

## Admission attribution

The full-base fail-open audit resolver is identical in both arms. The before arm has no admission policy; the after arm installs the default-off FINRA policy after qualification and actual fill discovery. Every baseline executable exclusion was denied, and every denial was an excluded survived candidate in the after arm's full-base candidate surface. Additional denials are recorded as cash/slot path dependence. Delayed fills are explicitly admitted as `admitted_not_strict_next_session`; add-ons never pass through the hook.

Gate 4 rejects the hypothesis because aggregate EV and PnL regressed. No live/default order path changed.

## Reproduction

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260720_003_finra_venue_short_crowding_entry_exclusion.py
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260720_003_finra_venue_short_crowding_entry_exclusion.py --reclassify-existing
```
