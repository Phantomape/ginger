# exp-20260601-008 Long-Only Short-Formation Continuation — Excess and Incrementality over Core Momentum

Decision: `observed_only_continuation_not_incremental_over_ret20`.

Read-only `alpha_discovery`. Disciplined follow-up to the exp-20260601-007
incidental lead (5d-formation winners continue over a 10d hold). Tests, on
the broad 1,446-ticker universe, whether a **long-only top-quintile of 5d
winners (10d skip-day hold)** earns a real excess over the universe mean AND
whether that excess is **incremental over core 20-day momentum** (the
load-bearing question). Pre-registered single cell f5/h10 (selection
inherited from exp-007, disclosed below).

## Result

| Test | Value | Verdict |
|---|---|---|
| Long-only top-quintile excess over universe mean (gross) | +0.82% / 10d | — |
| ... net of one round trip (0.35%) | **+0.47% / 10d** | positive |
| Excess t-stat | **2.82** | clears 2.0 (and the 6-cell Bonferroni 2.64) |
| Excess per window | late +0.31% / mid +1.11% / old +0.98% | **3/3 positive** |
| **ret20 double-sort residual** (5d top−bottom within ret20 bands) | +0.47% / 10d | above cost... |
| **ret20 residual t-stat** | **1.00** | **NOT significant** |

ret5 quintile 10d forward ladder (Q1 losers → Q5 winners):
`[0.17%, 0.14%, 0.46%, 0.47%, 1.34%]` — monotonically increasing
(continuation), as in exp-007.

## Interpretation

- **The long-only momentum tilt is real.** The top quintile of 5d winners
  beats the universe mean by +0.47%/10d net, in all 3 windows, t = 2.82.
  That t even clears the 6-cell Bonferroni floor (2.64), so the *existence*
  of a long-only excess is not just multiple-testing noise.
- **But it is NOT shown to be incremental over core 20-day momentum.** The
  decisive test — within each ret20 quintile band, the 5d top-minus-bottom
  forward spread — has a positive point estimate (+0.47%) but a t-stat of
  only **1.00**. After controlling for the 20-day momentum the core entry
  already trades, the short-formation-specific component is statistically
  indistinguishable from zero. We cannot claim the 5d signal adds anything
  beyond ret20 momentum.

So the honest conclusion: the continuation is a genuine long-only momentum
tilt, but it is **most plausibly the same momentum the core already
captures**, just at a correlated shorter horizon — not a distinct,
incremental edge. This is consistent with the whole ranking line this
session: the only robust broad-universe cross-sectional signal is momentum,
and short-formation continuation does not demonstrably add to it.

## A judge-overclaim that was caught before finalizing

The first run's judge accepted incrementality on the residual *point
estimate* (+0.47% > 0.35% cost) alone and returned
`accepted_incremental_short_formation_continuation`. That was wrong: the
residual t-stat is 1.00. The judge was corrected to require the ret20
double-sort residual to be **both** above cost **and** significant
(t ≥ 2) before crediting incrementality. With that fix the verdict flips to
`observed_only_continuation_not_incremental_over_ret20`. Recording this
because catching the insignificant-residual overclaim is the point — a
positive point estimate is not evidence of incrementality.

## Gate evaluation

```json
{
  "all_passed": false,
  "gate4": {
    "name": "long_only_excess_and_ret20_incremental",
    "passed": false,
    "status": "observed_only_continuation_not_incremental_over_ret20",
    "long_only_top_quintile_excess_gross": 0.00819,
    "long_only_top_quintile_excess_net": 0.00469,
    "excess_tstat_inherits_007_multiple_testing_debt": 2.8245,
    "excess_per_window": {"late_strong": 0.003107, "mid_weak": 0.011063, "old_thin": 0.009838},
    "excess_positive_windows": "3/3",
    "ret20_double_sort_residual_mean": 0.004711,
    "ret20_double_sort_residual_tstat": 1.003,
    "one_round_trip_cost": 0.0035
  }
}
```

Pre-run prediction (success_probability 0.35) anticipated this: failure mode
`continuation_collapses_after_ret20_control_just_momentum`. Calibrated.

## Next evidence / implications

- **Do not promote the 5d-continuation as a distinct edge.** It is not shown
  incremental over core 20-day momentum; treating it as new alpha would
  double-count what the core already trades.
- The long-only top-quintile momentum tilt itself (t = 2.82, 3/3 windows) is
  real and broad-universe-robust, but it overlaps the core's momentum entry.
  A genuinely useful follow-up would be a direct **replacement-value test
  versus the actual same-day core candidates** (not a ret20 proxy) — does the
  top-quintile name beat the specific core candidate it would displace? That
  needs the core candidate set per day on the broad universe, which this
  experiment did not have.
- True confirmation of any of this needs forward / out-of-sample data: the
  three windows are one contiguous 18-month period, and f5/h10 was selected
  from exp-007's grid.

## Caveats

f5/h10 selection inherited from exp-007 (multiple-testing debt on the excess
t-stat); warehouse `all_windows_full_liquid` survivorship; raw
close-to-close; one flat round-trip cost ignores market impact; ret20 is a
proxy for "core momentum", not the actual core entry rule; windows are not
independent regimes.

## Files

- `quant/experiments/exp_20260601_008_long_only_continuation_incrementality.py` (new)
- `quant/test_exp_20260601_008_continuation_incrementality.py` (new, 5 tests)
- `data/experiments/exp-20260601-008/long_only_continuation_incrementality.json` (new)
- `experiments/artifacts/exp-20260601-008_long_only_continuation_incrementality.md` (this file)
- `experiments/logs/exp-20260601-008.json`, `experiments/tickets/exp-20260601-008.json`
- Input warehouse `data/experiments/exp-20260519-030/warehouse_main.sqlite` (not committed)

No JavaScript was used.
