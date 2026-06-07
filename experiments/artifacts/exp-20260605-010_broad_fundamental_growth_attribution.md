# exp-20260605-010 Broad-Universe Realized Fundamental-Growth Forward-Return Attribution

Decision: `observed_only_no_robust_growth_edge`.

Read-only `alpha_discovery`. First test of the `exp-20260605-007` broad
Companyfacts asset as a cross-sectional signal: does PIT-safe realized
revenue YoY growth predict forward returns on the broad 1,446-ticker
universe, and — the decisive question, mirroring exp-20260601-008 — is it
incremental over ret20 momentum? Independent of the FUNDAMENTAL_GROWTH_RS
paper sleeve (different universe, read-only, no sleeve change).

## Method (read-only, PIT)

For each (signal_day, ticker) the signal is the most recent companyfacts
`revenue` YoY growth row with `asof_date <= signal_day` and
`growth_status == "ok"` (clipped at ±500% to tame tiny-prior-base blowups).
Forward returns are skip-day (enter T+1) close-to-close at 10d/20d on the
warehouse OHLCV. Sampled every 5th trading day across the canonical 3
windows; 71,518 (day, ticker) observations.

## Result: no robust growth edge, raw or momentum-conditional

Growth quintile long-short (top-minus-bottom), daily series:

| Horizon | gross | net of 0.70% cost | t-stat | windows + |
|---|---|---|---|---|
| 10d | +0.20% | −0.50% | 0.53 | 2/3 |
| 20d | +0.52% | −0.18% | **0.92** | 2/3 |

- **Raw long-short is insignificant** (20d t=0.92), net-of-cost negative.
- **Pooled quintile ladder (Q1 low growth → Q5 high growth, 20d):**
  `[+2.57%, −1.53%, +0.79%, +0.88%, +1.76%]` — **not monotonic, U-shaped**:
  the lowest-growth quintile (Q1) actually has the highest forward return,
  while the highest-growth quintile (Q5) is only +1.76%. Plausibly a
  distressed / turnaround / value tilt in Q1, not a clean "growth wins."
- **Not window-robust:** late_strong is strongly negative (−2.58% at 20d)
  while mid_weak/old_thin are positive.
- **ret20 double-sort residual (growth top-minus-bottom within ret20
  bands, proper daily t-stat, n=64 days):** mean +0.30%, **t=0.59** —
  insignificant. Growth carries no clean edge even after controlling for
  momentum.

## A statistical flaw caught and fixed before finalizing

The first run computed the ret20 residual t-stat over only the **5 ret20
band means (n=5)**, which spuriously reported **t=3.29** — a near-useless
significance test on 5 points. It was corrected to t-test the **daily
within-band spread series (n=64 sampled days)**, which gives t=0.59. The
"incidental momentum-conditional growth edge" was an artifact of the n=5
computation; the corrected verdict is no edge.

## Gate evaluation

```json
{
  "all_passed": false,
  "gate4": {
    "name": "incremental_growth_edge_over_ret20",
    "passed": false,
    "status": "observed_only_no_robust_growth_edge",
    "primary_horizon": 20,
    "raw_long_short_ok": false,
    "raw_net_of_cost_ok": false,
    "incremental_over_ret20": false,
    "residual_mean": 0.003014,
    "residual_tstat": 0.5906
  }
}
```

Pre-run prediction (success_probability 0.35) anticipated this: failure
modes `growth_edge_collapses_after_ret20_control` /
`stale_quarterly_growth_low_signal_at_daily_frequency` /
`one_window_carries_it`.

## Interpretation

- Realized revenue YoY growth is **not** a robust daily cross-sectional
  forward-return signal on this broad survivorship-liquid universe over one
  18-month period — raw or momentum-conditional.
- A genuine limitation: realized quarterly growth is **stale at daily
  frequency** (held constant between ~quarterly filings, so a ticker's
  signal updates only ~4×/year). A daily cross-sectional ranking test may
  understate it; the natural test of fundamental growth is at the
  earnings-event frequency (PEAD-style), not daily — but the earnings/PEAD
  direction was itself frozen this session for separate (5d-horizon) reasons.
- Consistent with the session's recurring finding: broad-universe
  cross-sectional signals on this data/period reduce to weak or
  momentum-entangled effects.

## Significance of the asset (separate from this null result)

The null here is a research result, not a knock on the
`exp-20260605-007` Companyfacts asset. That asset is a clean, broad,
free, PIT-safe fundamental surface (79–84% coverage) and remains the right
replacement for the contaminated yfinance `eps_estimate`. The accepted
`FUNDAMENTAL_GROWTH_RS` lead combines growth with RS and position sizing,
which is a different (and so far accepted) construct than this raw
daily-quintile test.

## Next evidence needed

- If revisited, test fundamental growth at **earnings-event frequency**
  (around the filing date) rather than daily, and combine with quality
  (margin/cash-conversion) rather than growth alone.
- A long-only top-quintile-growth framing with a single round-trip cost is
  cheaper to monetize than the long-short tested here, but the raw ladder's
  non-monotonicity (Q1 high) argues against a simple top-quintile rule.

## Files

- `quant/experiments/exp_20260605_010_broad_fundamental_growth_attribution.py` (new)
- `quant/test_exp_20260605_010_fundamental_growth_attribution.py` (new, 8 tests)
- `data/experiments/exp-20260605-010/broad_fundamental_growth_attribution.json` (new)
- `experiments/artifacts/exp-20260605-010_broad_fundamental_growth_attribution.md` (this file)
- `experiments/logs/exp-20260605-010.json`, `experiments/tickets/exp-20260605-010.json`
- Inputs (not re-committed): `data/kova/fundamentals/companyfacts_growth_broad_universe_20260604.jsonl` (LFS),
  `data/experiments/exp-20260519-030/warehouse_main.sqlite` (LFS)

No JavaScript was used.
