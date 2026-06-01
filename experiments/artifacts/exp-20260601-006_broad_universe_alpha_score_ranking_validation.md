# exp-20260601-006 Broad 1446-Ticker Universe Validation of the alpha_score Ranking Decomposition

Decision: `composite:observed_only_no_robust_quantile_edge | components:observed_only_no_component_edge`.

Read-only `alpha_discovery`. Robustness re-run of `exp-20260531-006`
(composite quintile ladder) and `exp-20260601-003` (component
decomposition) on a **broad heterogeneous universe**, because both prior
experiments ran on the narrow ~52-name curated, momentum-homogeneous
watchlist where "relative_strength dominates and everything else is
collinear" is close to expected by construction.

Universe: the 1,446 `all_windows_full_liquid` tickers from
`data/experiments/exp-20260519-030/warehouse_main.sqlite` (~28x the
curated snapshot; small/mid caps included). 96,833 pooled (day, ticker)
observations across the canonical 3 windows, every 5th trading day.
Forward returns raw close-to-close (no costs). Changes nothing in
production.

## Headline: broadening the universe shrinks the edge

| Metric | narrow 52-name (exp-006/003) | **broad 1446-name (this exp)** |
|---|---|---|
| observations | 3,551 | **96,833** |
| composite quintile 5d spread | +0.56 pp (barely cleared floor) | **+0.21 pp (fails 0.5 pp floor)** |
| composite 10d / 20d | +1.51 / +3.98 pp | +0.51 / +1.53 pp |
| composite ladder monotonic | no | no |
| composite per-window 5d + | 2/3 | **1/3** (late_strong only) |
| relative_strength 5d spread | +0.81 pp | **+0.34 pp** |
| component verdict | momentum_only_edge | **no_component_edge** |

On a broad heterogeneous universe the composite 5d edge collapses from
+0.56 pp to **+0.21 pp**, below the materiality floor, and relative_strength
itself shrinks from +0.81 pp to +0.34 pp — also below floor. **No
component (including RS) clears the floor + within-day + majority-window +
RS-control bar on the broad universe.**

## Broad-universe composite quintile 5d ladder

| Bucket | n | 5d avg | 5d win | 20d avg |
|---|---|---|---|---|
| Q1 | 19,366 | 0.32% | 0.531 | 0.56% |
| Q2 | 19,367 | 0.49% | 0.534 | 1.36% |
| Q3 | 19,366 | 0.30% | 0.523 | 1.29% |
| Q4 | 19,367 | 0.29% | 0.522 | 0.93% |
| Q5 | 19,367 | 0.53% | 0.529 | 2.09% |

Per-window 5d Q5−Q1: late_strong **+0.59 pp**, mid_weak **−0.24 pp**,
old_thin **−0.09 pp** — the entire spread is one window (late_strong, the
strong recent market). A classic single-regime artifact.

## Broad-universe component decomposition

| Component | distinct | within-day share | 5d spread | residual vs RS | windows + |
|---|---|---|---|---|---|
| relative_strength | 8668 | 0.89 | +0.34 pp | — | 2/3 |
| breadth_alignment | 125 | 0.71 | +0.40 pp | +0.33 pp | 2/3 |
| trend | 10 | 0.95 | +0.04 pp | −0.18 pp | 1/3 |
| theme_participation | 12 | 1.00 | −0.78 pp | −0.06 pp | 0/3 |
| expectation_revision | **1** | n/a | constant | — | 0/3 |
| post_earnings_drift | **1** | n/a | constant | — | 0/3 |

`relative_strength` and `breadth_alignment` are the largest but both miss
the 0.5 pp floor; `breadth` is RS-collinear again (residual +0.33 pp).
`expectation_revision` / `post_earnings_drift` are still perfectly
constant (data not populated for non-curated tickers — confirmed, as
predicted).

## Universe-robust conclusion (supersedes the narrow-universe headline)

The prior "alpha_score = repackaged momentum (relative_strength)" headline
from exp-20260601-003 was derived on a curated momentum-homogeneous
universe and **overstated the edge**. The universe-robust finding is
stronger and more deflating:

> On a broad 1,446-name heterogeneous universe, `alpha_score` has **no
> robust 5d cross-sectional forward-return edge** — not even momentum. The
> narrow-watchlist +0.56 pp edge was largely an artifact of the curated
> large-cap momentum universe, and even there it was concentrated in the
> top quantile and one window. The only directional residual is a weak
> momentum tilt that grows with horizon but fails a materiality floor and
> is carried by a single window (late_strong).

This is exactly what the user's instinct to test a broader universe
surfaced: broadening the cross-section *shrank* the edge, the opposite of
what a generalizable alpha would do.

## Gate evaluation

Both reused judges returned non-accept:
- composite: `observed_only_no_robust_quantile_edge` (5d +0.21 pp < 0.5 pp floor).
- components: `observed_only_no_component_edge` (no component clears the bar; breadth RS-collinear; expectation/PEAD constant).

Pre-run prediction (success_probability 0.40) matched: failure modes
`rs_still_only_driver` / `composite_ladder_still_non_monotonic` /
`expectation_pead_theme_still_constant`.

## Caveats

- Warehouse survivorship: `all_windows_full_liquid` = stayed liquid the
  whole period; not delisting-free. If anything this biases toward finding
  an edge (survivors), so the near-null result is conservative.
- Raw close-to-close, no costs, no significance tests / CIs; 0.5 pp floor
  is a materiality heuristic, not a statistical threshold. The point
  estimates are small enough that costs would erase any residual tilt.
- expectation/PEAD/theme remain unpopulated for non-curated tickers — they
  are untested-by-data, not tested-and-weak.

## Next evidence / implications

- **Cross-sectional ranking via `alpha_score` is closed for new alpha**,
  now on robust (broad-universe) evidence, not just the narrow watchlist.
  Do not propose alpha_score reweighting as a live ranking/sizing change.
- Reviving a ranking surface needs genuinely populated, non-OHLCV,
  non-momentum components on the broad universe (a data-population problem)
  AND a per-window / per-regime robustness requirement, since the only
  visible tilt is single-regime (late_strong).
- The parallel default-off alpha_score paper adapters
  (exp-20260531-005/025/029, exp-20260601-001) should be read in this
  light: their historical paper gains likely lean on the same
  late_strong-regime, top-quantile, momentum tilt; forward replacement
  value across regimes is the real test.

## Files

- `quant/experiments/exp_20260601_006_broad_universe_alpha_score_ranking_validation.py` (new)
- `quant/test_exp_20260601_006_broad_universe_ranking_validation.py` (new, 5 tests)
- `data/experiments/exp-20260601-006/broad_universe_alpha_score_ranking_validation.json` (new)
- `experiments/artifacts/exp-20260601-006_broad_universe_alpha_score_ranking_validation.md` (this file)
- `experiments/logs/exp-20260601-006.json`, `experiments/tickets/exp-20260601-006.json`
- Input warehouse `data/experiments/exp-20260519-030/warehouse_main.sqlite` (741 MB, not committed)

No JavaScript was used.
