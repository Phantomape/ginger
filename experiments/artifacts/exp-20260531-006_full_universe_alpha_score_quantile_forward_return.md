# exp-20260531-006 Full-Universe Composite alpha_score Quantile Forward-Return Attribution

Decision: `observed_only_top_bottom_edge_without_clean_ladder`.

Read-only `alpha_discovery`. The methodological follow-on to
`exp-20260530-022`, which found the composite cross-sectional alpha_score
cannot be validated on *filled* core trades (the entry rule concentrates
fills into the top rank bucket, leaving no bottom comparison group). This
experiment scores the **full daily candidate universe** (filled and
unfilled) on sampled trading days across the canonical three windows,
computes 5/10/20-day close-to-close forward returns per ranked ticker,
and buckets all (day, ticker) observations by alpha_score quintile and
decile — the design that actually has a bottom comparison group.

Pre-run prediction (recorded in the ticket): success_probability 0.30;
main failure modes flat / inverted / top-quantile-only / one-window-
negative. The result landed close to that prediction: a real but
**top-quantile-concentrated, non-monotonic** edge.

This changes no entries, exits, ranking, sizing, LLM/news inputs, paper
sleeves, or live orders. Forward returns are raw close-to-close (no
costs): it is an attribution of cross-sectional predictive power, not a
tradeable PnL.

## Method

- Sample every 5th trading day across each window interior (forward
  buffer of 20 sessions so 20d outcomes are observable).
- For each sampled day, reuse `entry_day_ranking_attribution._context_for_asof`
  to score the full universe PIT and read each ticker's `alpha_score`.
- Pool all (day, ticker) observations: **3,551** total
  (late_strong 1,159 / mid_weak 1,144 / old_thin 1,248).

## Pooled quintile ladder (Q1 = lowest alpha_score → Q5 = highest)

| Bucket | n | alpha_score | 5d avg | 5d win | 10d avg | 20d avg | top5 pos. share |
|---|---|---|---|---|---|---|---|
| Q1 | 710 | 0.175–0.332 | 0.63% | 0.556 | 0.72% | 0.40% | 0.098 |
| Q2 | 710 | 0.332–0.438 | 0.57% | 0.528 | 1.05% | 1.94% | 0.100 |
| Q3 | 710 | 0.438–0.479 | 0.32% | 0.527 | 0.67% | 1.65% | 0.120 |
| Q4 | 710 | 0.479–0.516 | 0.42% | 0.537 | 0.92% | 2.17% | 0.092 |
| **Q5** | 711 | 0.516–0.761 | **1.19%** | 0.575 | **2.23%** | **4.38%** | 0.088 |

Pooled top-minus-bottom (Q5−Q1) spread: **5d +0.56 pp, 10d +1.51 pp,
20d +3.98 pp** — the spread grows with horizon. Decile 20d ladder:
`[0.52, 0.28, 2.72, 1.15, 1.67, 1.62, 1.94, 2.40, 3.76, 5.00]` — the top
two deciles (3.76, 5.00) are clearly best.

## What is real, and what is not

Real:
- **A top-quantile effect.** Q5 (and especially the top 1–2 deciles)
  clearly out-returns, and the edge **grows with horizon** (5d → 20d).
- **Not jackpot-driven.** Each quintile's top-5 single-observation share
  of positive return mass is only ~0.09–0.12; the Q5 edge is broad, not
  one or two names.

Not clean:
- **The ladder is not monotonic** at any horizon. Q1 (lowest score)
  actually beats Q2/Q3 at 5d; the bottom-to-middle quintiles carry almost
  no ordering information. The signal is concentrated in the top quantile,
  not spread across the rank.
- **Not robust across all windows.** mid_weak's 5d Q5−Q1 spread is
  **−0.46 pp** (negative); only 2 of 3 windows are positive
  (late_strong +1.32 pp, old_thin +0.39 pp).

## Gate evaluation

```json
{
  "all_passed": false,
  "gate1": {"name": "full_universe_observations_collected", "passed": true, "total_observations": 3551},
  "gate2": {"name": "quantile_buckets_meet_obs_floor", "passed": true, "min_pooled_quintile_obs": 710, "floor": 30},
  "gate3": {"name": "survival_rate_not_affected_read_only_attribution", "passed": true},
  "gate4": {
    "name": "full_universe_quantile_forward_return_edge",
    "passed": false,
    "status": "observed_only_top_bottom_edge_without_clean_ladder",
    "pooled_quintile_top_minus_bottom_5d": 0.005557,
    "pooled_quintile_monotonic_ladder_5d": false,
    "per_window_5d_spread": {"late_strong": 0.013194, "mid_weak": -0.00456, "old_thin": 0.003919},
    "positive_windows": 2,
    "measured_windows": 3
  }
}
```

The accept bar required a monotonic ladder AND majority-positive windows
AND >= 0.5 pp 5d spread. The 5d spread (+0.56 pp) and majority windows
(2/3) pass, but the ladder is not monotonic, so the honest verdict is
`observed_only_top_bottom_edge_without_clean_ladder` — a downgrade from a
clean accept.

## Significance

This is the **first positive cross-sectional signal of the session**
after the expectation-direction main line was frozen (residual /
PEAD-window / revision-magnitude all rejected at 5d in
exp-20260528-027/028 and exp-20260529-007) and after exp-20260530-022
showed the composite score degenerate/inverted on filled trades. The
full-universe view recovers a genuine, non-jackpot, horizon-growing
top-quantile effect that the filled-trade view structurally could not see.

## Next evidence needed

1. **Top-quantile selection, not monotonic sizing.** The right use of
   alpha_score is a top-decile / top-quintile *selection* signal (e.g. a
   default-off paper sleeve that observes the top-decile names each day),
   not a full-universe monotonic sizing weight — the middle/bottom ranks
   carry no ordering information.
2. **A 4th+ window for robustness.** mid_weak is negative; the edge needs
   confirmation on at least one more non-overlapping window before any
   promotion beyond observation.
3. **Decompose the Q5 edge by component.** Determine whether the top-
   quintile effect is driven by the trend / relative_strength weight
   (the components the core already trades on) or by something
   incremental; if it is just trend/RS, it is not new alpha over the
   existing entry rule.

## Files

- `quant/experiments/exp_20260531_006_full_universe_alpha_score_quantile_forward_return.py` (new)
- `quant/test_exp_20260531_006_full_universe_quantile_forward_return.py` (new, 9 tests)
- `data/experiments/exp-20260531-006/full_universe_alpha_score_quantile_forward_return.json` (new)
- `experiments/artifacts/exp-20260531-006_full_universe_alpha_score_quantile_forward_return.md` (this file)
- `experiments/logs/exp-20260531-006.json`, `experiments/tickets/exp-20260531-006.json`

No JavaScript was used.
