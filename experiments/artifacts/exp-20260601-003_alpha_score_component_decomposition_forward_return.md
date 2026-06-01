# exp-20260601-003 alpha_score Component-Decomposition Forward-Return Attribution

Decision: `observed_only_momentum_only_edge`.

Read-only `alpha_discovery`. Answers the open question from
`exp-20260531-006`: is the composite `alpha_score`'s top-quantile
forward-return edge driven by the momentum components the core entry rule
already trades on, or do the other components carry **independent**
cross-sectional signal? Decomposes the same 3,551 full-universe
(day, ticker) observations by each of the six components.

**Result: the edge is entirely momentum.** `relative_strength` is the
only component with a clean, robust, cross-sectional forward-return
spread. After controlling for `relative_strength` (double-sort), no other
component carries an incremental edge. Two components are perfectly
constant. Therefore `alpha_score` adds no new cross-sectional alpha over
the core momentum logic. Changes nothing in production.

## Per-component decomposition (pooled, 3,551 obs)

| Component | weight | distinct | within-day var share | 5d spread | windows + | residual 5d vs RS | verdict |
|---|---|---|---|---|---|---|---|
| **relative_strength** | 0.25 | 2460 | 0.87 | **+0.81 pp** | **3/3** | — (control axis) | **real momentum edge** |
| breadth_alignment | 0.05 | 69 | 0.66 | +0.88 pp | 2/3 | **+0.34 pp** (< floor) | RS-collinear, not incremental |
| trend | 0.30 | 10 | 0.93 | −0.13 pp | 1/3 | −0.05 pp | no edge / not robust |
| theme_participation | 0.10 | 8 | 0.98 | −0.67 pp | 0/3 | −0.05 pp | no edge |
| **expectation_revision** | 0.20 | **1** | n/a | n/a | 0/3 | +0.20 pp | **CONSTANT (0.5), inert** |
| **post_earnings_drift** | 0.10 | **1** | n/a | n/a | 0/3 | +0.20 pp | **CONSTANT (0.5), inert** |

Three discriminators were applied, each tightening the verdict:

1. **Univariate quintile spread** flagged `relative_strength` (+0.81 pp)
   and `breadth_alignment` (+0.88 pp).
2. **Within-day vs across-day variance** confirmed both vary
   cross-sectionally (within-day share 0.87 / 0.66), not as pure
   market-timing confounds — so the first-cut "accept" on breadth held.
3. **RS double-sort control** (the decisive test): within each
   `relative_strength` quintile band, `breadth_alignment`'s top-vs-bottom
   5d spread collapses from +0.88 pp to **+0.34 pp** (below the 0.5 pp
   floor). breadth_alignment is collinear with momentum by construction —
   its cross-sectional variation comes from the same per-stock
   `momentum_20d > 0` and `breakout_20d` gates that `relative_strength`
   and `trend` use. It is not independent alpha.

## Two findings worth acting on

1. **30% of the composite weight is inert.** `expectation_revision`
   (weight 0.20) and `post_earnings_drift` (weight 0.10) are perfectly
   constant at 0.5 across all 3,551 observations — they carry zero
   ordering information. The `build_component_scores` defaults
   (`expectation_revision = 0.5` unless an avg-surprise row matches;
   `post_earnings_drift = 0.5` unless avg_surprise and momentum agree)
   leave them at the default for the entire universe. The composite score
   is effectively `0.30*trend + 0.25*RS + 0.10*theme + 0.05*breadth`
   re-scaled, with 0.30 of weight doing nothing. This is consistent with
   the 2026-05-29 freeze of the expectation direction: the expectation
   inputs are not populated in this universe.

2. **`alpha_score` is repackaged momentum.** The only robust
   cross-sectional driver is `relative_strength`, which is exactly what
   the core entry rule already selects on. The full-universe top-quantile
   edge from exp-20260531-006 is a momentum edge, not new alpha.

## Gate evaluation

```json
{
  "all_passed": false,
  "gate4": {
    "name": "incremental_non_momentum_component_edge",
    "passed": false,
    "status": "observed_only_momentum_only_edge",
    "momentum_components_with_edge": ["relative_strength"],
    "non_momentum_univariate_edges": ["breadth_alignment"],
    "momentum_collinear_components": ["breadth_alignment"],
    "non_momentum_components_with_edge": [],
    "near_constant_components": ["expectation_revision", "post_earnings_drift"]
  }
}
```

Pre-run prediction (success_probability 0.30) anticipated exactly this:
main failure mode `only_trend_rs_carry_signal_no_incremental`. Calibrated.

## Caveat

Univariate-plus-RS-control is not a full multivariate regression;
remaining components are not jointly orthogonalized. But the decisive
question — does anything beat momentum — is answered: the only robust
driver is RS, and the one challenger (breadth) is RS-collinear.

## Next evidence needed / implications

- **Close the cross-sectional ranking direction for new alpha.**
  `alpha_score` = momentum; it does not beat the core momentum entry. Do
  not propose `alpha_score` (or any current reweighting of it) as a live
  ranking/sizing change — there is no incremental edge to capture.
- **If the ranking surface is to be revived,** it needs genuinely new,
  populated, non-momentum components (the current expectation/PEAD inputs
  are constant). That is a data-population problem (same blocker as the
  frozen expectation direction), not a weighting problem.
- The parallel default-off `alpha_score` paper adapters
  (exp-20260531-005/025/029, exp-20260601-001 cross-source consensus) are
  observing top-decile/consensus selection forward; this decomposition
  explains *why* a raw monotonic alpha_score ranking failed promotion —
  the middle ranks carry only momentum-collinear noise.

## Files

- `quant/experiments/exp_20260601_003_alpha_score_component_decomposition_forward_return.py` (new)
- `quant/test_exp_20260601_003_alpha_score_component_decomposition.py` (new, 8 tests)
- `data/experiments/exp-20260601-003/alpha_score_component_decomposition_forward_return.json` (new)
- `experiments/artifacts/exp-20260601-003_alpha_score_component_decomposition_forward_return.md` (this file)
- `experiments/logs/exp-20260601-003.json`, `experiments/tickets/exp-20260601-003.json`

No JavaScript was used.
