# exp-20260530-022 Cross-Sectional Composite alpha_score Rank Predictive-Power Attribution

Decision: `observed_only_rank_degenerate_requires_full_universe`.

Read-only `alpha_discovery`. Executes the never-completed "Ranking Score
Replacement Test" (alpha-direction memo section 9) for the *composite*
cross-sectional `alpha_score`, rebuilt point-in-time as of the day before
each filled core entry by `quant/entry_day_ranking_attribution.py`, across
the canonical three windows. `exp-20260528-007` only tested whether
*adding* the expectation increment improved ranking (it did not); this
tests the composite score itself.

Headline: the composite `alpha_score` rank **cannot be validated for
monotonic predictive power on filled core trades** — the core entry rule
already selects top-ranked names, so 56/61 trades land in `top_decile`
and 0/61 fall below `top_quartile`. There is no bottom-rank comparison
group. Where individual components do vary, two of three invert. This
changes no entries, exits, ranking, sizing, LLM/news inputs, paper
sleeves, or live orders.

## Inputs (canonical three windows, PIT coverage 1.0)

| Window | Period | Trades | EV (parity) |
|---|---|---|---|
| late_strong | 2025-10-23 → 2026-04-21 | 18 | 5.1628 |
| mid_weak | 2025-04-23 → 2025-10-22 | 21 | 2.1402 |
| old_thin | 2024-10-02 → 2025-04-22 | 22 | 0.5911 |
| **aggregate** | — | **61** | **7.8941** |

All 61 trades carry a PIT `alpha_score` (overall PIT coverage = 1.0,
`policy_research_ready = True` in every window). The backtest EVs match
the canonical accepted stack exactly, so the trade sample is the real
core book, not a degraded replay.

## Finding 1: composite rank is degenerate on filled trades

| Rank bucket | Trades | avg_pnl | avg_r | win_rate |
|---|---|---|---|---|
| `top_decile` | 56 | $3,474 | 1.30 | 0.554 |
| `top_quartile` | 5 | $8,056 | 2.32 | 0.800 |
| `upper_mid` … `bottom_quartile` | **0** | — | — | — |

The entry rule concentrates fills into the top of the daily alpha_score
cross-section, so the monotonicity question (top > bottom) cannot be
asked: there is no below-`top_quartile` group. The 5 trades that did land
one bucket lower (`top_quartile`) actually out-earned the 56 `top_decile`
trades on every metric — the opposite of the hypothesis — but with a
56-vs-5 split this is not interpretable, only a flag that "highest rank =
best" does not hold among fills.

## Finding 2: half the components carry zero discriminating information

Rebuilt PIT, three of six components are **perfectly constant** across all
61 filled trades:

- `trend` → all `high`
- `expectation_revision` → all `mid`
- `post_earnings_drift` → all `mid`

`trend` constant-high is expected (the entry requires trend). But
`expectation_revision` and `post_earnings_drift` being constant means the
two components the frozen expectation direction is built on add **no
ranking dispersion at all** among the names the core actually buys — an
independent confirmation of the 2026-05-29 expectation 5d freeze from the
ranking side.

## Finding 3: the components that do vary mostly invert

For the three dispersed components (both buckets ≥ 8 trades, so the
comparison is not a tiny-sample artifact):

| Component | high avg_r | mid avg_r | high−mid margin | verdict |
|---|---|---|---|---|
| `relative_strength` | 0.72 (n=10) | 1.51 (n=51) | **−0.79** | inverted |
| `breadth_alignment` | 1.04 (n=29) | 1.69 (n=32) | **−0.66** | inverted |
| `theme_participation` | 1.37 (n=52, mid) | 1.45 (n=9, low) | −0.08 | flat |

Higher relative-strength and higher breadth-alignment scores are
associated with **lower** risk-adjusted return among filled trades.
`relative_strength` even shows higher raw avg_pnl in its high bucket
($5,062 vs $3,612) but a much lower `avg_r` (0.72 vs 1.51), i.e. the
high-RS edge is jackpot/notional-driven, not risk-adjusted — exactly the
"not via a single jackpot trade" failure mode the hypothesis was meant to
exclude.

## Gate evaluation

```json
{
  "all_passed": false,
  "gate1": {"name": "canonical_three_window_trades_available", "passed": true, "total_trades": 61},
  "gate2": {"name": "pit_alpha_score_coverage", "passed": true, "overall_pit_coverage": 1.0, "floor": 0.95},
  "gate3": {"name": "survival_rate_not_affected_read_only_attribution", "passed": true},
  "gate4": {
    "name": "composite_alpha_score_rank_monotonicity",
    "passed": false,
    "status": "observed_only_rank_degenerate_requires_full_universe",
    "rank_degenerate_no_bottom_group": true,
    "constant_components_zero_info": ["expectation_revision", "post_earnings_drift", "trend"],
    "dispersed_components": ["breadth_alignment", "relative_strength", "theme_participation"]
  }
}
```

## Why observed_only (not accepted/rejected)

The honest scientific call: filled core trades are a *selected* sample
incapable of testing rank monotonicity (no bottom group). The dispersed
components invert, which argues against the ranking hypothesis, but the
decisive test requires scoring the **full daily candidate universe**
(filled + unfilled) and comparing forward outcomes across rank buckets —
which this filled-trade attribution structurally cannot do.

## Methodological next step (for the next agent)

To actually validate or reject the composite ranking surface:

1. Persist the daily `cross_sectional_ranking_surface` alpha_score for the
   **entire candidate universe each day** (not just filled entries), with
   the forward 5/10/20-day outcome of each ranked name.
2. Then bucket *all ranked candidates* by alpha_score decile and compare
   forward returns top-vs-bottom. Only that design has a bottom group.
3. Do not attempt to promote the composite alpha_score to live sizing or
   ranking from filled-trade attribution; it is structurally blind to the
   names the core never bought.

Separately, the constant-component finding says `expectation_revision`
and `post_earnings_drift` add zero ranking dispersion among core fills —
consistent with the expectation 5d freeze; do not reintroduce them as
ranking weights without the full-universe test above.

## Files

- `quant/experiments/exp_20260530_022_cross_sectional_ranking_predictive_power_attribution.py` (new)
- `quant/test_exp_20260530_022_cross_sectional_ranking_attribution.py` (new, 6 tests)
- `data/experiments/exp-20260530-022/result_{late_strong,mid_weak,old_thin}.json` (canonical 3-window backtests)
- `data/experiments/exp-20260530-022/ranking_attr_{late_strong,mid_weak,old_thin}.json` (per-window PIT attribution)
- `data/experiments/exp-20260530-022/cross_sectional_ranking_predictive_power_attribution.json` (aggregate + judgment)
- `experiments/artifacts/exp-20260530-022_cross_sectional_ranking_predictive_power_attribution.md` (this file)
- `experiments/logs/exp-20260530-022.json`, `experiments/tickets/exp-20260530-022.json`

No JavaScript was used.
