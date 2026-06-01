# exp-20260601-007 Short-Horizon Cross-Sectional Reversal Attribution (broad universe)

Decision: `observed_only_no_robust_net_reversal_edge`.
**Registered hypothesis (reversal) is rejected. Incidental finding: short-formation
continuation, reported as a pre-registration-worthy lead, NOT a claim.**

Read-only `alpha_discovery`. New direction after the momentum / expectation /
ranking lines closed. Tests cross-sectional **short-horizon reversal** (recent
losers bounce) on the broad 1,446-ticker all-windows-full-liquid warehouse
universe — OHLCV-only (broadly populated), orthogonal to the closed lines.

Rigor built in from the start (this session's lessons):
- broad 1,446-ticker universe;
- **skip-a-day**: formation return ends day T, holding return measured T+1→T+1+H,
  removing the bid-ask-bounce artifact that inflates naive reversal;
- **t-stat** of the daily long-short series (not an arbitrary spread floor);
- **cost adjustment**: net = gross − 2·ROUND_TRIP_COST_PCT (0.70 pct per rebalance);
- **horizon grid** formation {1,3,5} × hold {5,10} (no cherry-picking);
- **non-overlapping** sampling (cadence = hold) for a clean t-stat;
- per-window robustness.

## Result: no reversal — the sign is continuation

Long-short = losers-minus-winners skip-day forward return (reversal ⇒ positive):

| Cell | gross L−W | net L−W | t-stat | monotonic-reversal | windows + (reversal) |
|---|---|---|---|---|---|
| f1_h5 | −0.10% | −0.80% | −0.37 | no | 0/3 |
| f1_h10 | −0.37% | −1.07% | −0.71 | no | 0/3 |
| f3_h5 | −0.28% | −0.98% | −1.02 | no | 0/3 |
| f3_h10 | −0.97% | −1.67% | −1.81 | no | 0/3 |
| f5_h5 | −0.21% | −0.91% | −0.81 | no | 0/3 |
| f5_h10 | **−1.16%** | −1.86% | **−2.15** | no | 0/3 |

Every cell's losers-minus-winners is **negative** → recent winners out-return
recent losers = **short-horizon continuation, not reversal**. The reversal
hypothesis is cleanly rejected on this universe.

## Incidental finding (pre-registration-worthy lead, not a claim)

Sign-flipped (winners-minus-losers = continuation), the 10-day-hold cells are
the interesting ones:

**f5_h10 quintile ladder (Q1 losers → Q5 winners, 10d forward):**
`[0.18%, 0.14%, 0.46%, 0.47%, 1.34%]` — monotonically increasing. Recent 5-day
winners (top quintile) earn **+1.34% / 10d** vs +0.18% for losers.
- winners-minus-losers gross **+1.16 pp**, all 3 windows positive
  (late_strong +1.32, mid_weak +0.92, old_thin +1.25), t = 2.15.

**f3_h10:** ladder `[0.26, 0.24, 0.36, 0.49, 1.24]`; winners-minus-losers
+0.97 pp; all 3 windows positive; t = 1.81.

This is more window-robust than the alpha_score finding (3/3 vs 1–2/3). But it
is **explicitly not promoted**, for four reasons:

1. **Multiple testing.** 6 cells were run; only the two 10d-hold cells reach
   |t| ≈ 1.8–2.1. A Bonferroni floor for 6 tests is |t| ≥ 2.64 — neither clears
   it. The t = 2.15 is marginal.
2. **Thin net of cost.** winners-minus-losers net (after 0.70 pct round-trip) is
   ~+0.46 pp / 10d at f5_h10, and a real 1,446-name long-short also pays
   short-borrow + market impact. Not tradeable as a pure long-short.
3. **It is a momentum variant.** Short-formation (5d) continuation may be
   collinear with what the core entry rule (momentum / breakout) already trades.
   Incremental value over core is **untested**.
4. **Only 10d hold works; 5d holds are weak** (|t| < 1.0). The effect is
   horizon-specific.

The more plausibly usable form is the **long-only top quintile** (recent 5d
winners, +1.34% / 10d gross; ≈ +1.0% net of one round trip), not the long-short.

## Gate evaluation

```json
{
  "all_passed": false,
  "gate4": {
    "name": "net_cost_adjusted_significant_reversal",
    "passed": false,
    "status": "observed_only_no_robust_net_reversal_edge",
    "tstat_floor": 2.0,
    "round_trip_long_short_cost": 0.007,
    "primary_sign": "continuation_or_flat",
    "qualifying_cells": []
  }
}
```

Pre-run prediction (success_probability 0.30) anticipated this: failure mode
`no_reversal_only_continuation` (plus `reversal_gross_positive_but_erased_by_costs`
for the weak cells). Calibrated.

## Next evidence / implications

- **Reversal is not a usable edge on this universe** — rejected. Do not pursue
  short-horizon mean-reversion here.
- The incidental **short-formation (5d) continuation at 10d hold** is the only
  positive lead. A clean follow-up would be a SEPARATE pre-registered experiment:
  (a) long-only top-quintile of 5d-formation winners, 10d hold, broad universe;
  (b) a hard test of whether it is INCREMENTAL over the core's existing
  momentum / breakout entry (double-sort vs the core signal); (c) a real cost
  model (one round trip for long-only, not long-short); (d) more windows /
  out-of-sample, since t = 2.15 fails a multiple-testing floor.
- Note the consistency with exp-20260601-006: alpha_score's RS component
  (20–60d formation) was weak, but **shorter 5d formation + 10d hold** is more
  window-robust here. The momentum horizon, not the existence of momentum, may
  be the lever — but only as a pre-registered, cost-and-multiple-testing-aware
  follow-up.

## Caveats

Warehouse `all_windows_full_liquid` survivorship; raw close-to-close; flat
2× round-trip cost ignores short-borrow / impact / financing; t-stat assumes
independent sampled days (cadence = hold so forward windows do not overlap, but
the three windows are one contiguous 18-month period, not independent regimes).

## Files

- `quant/experiments/exp_20260601_007_short_horizon_reversal_attribution.py` (new)
- `quant/test_exp_20260601_007_short_horizon_reversal.py` (new, 9 tests)
- `data/experiments/exp-20260601-007/short_horizon_reversal_attribution.json` (new)
- `experiments/artifacts/exp-20260601-007_short_horizon_reversal_attribution.md` (this file)
- `experiments/logs/exp-20260601-007.json`, `experiments/tickets/exp-20260601-007.json`
- Input warehouse `data/experiments/exp-20260519-030/warehouse_main.sqlite` (not committed)

No JavaScript was used.
