# exp-20260601-009 Overnight vs Intraday Return Decomposition (broad universe)

Decision: `observed_only_no_robust_overnight_structure`.

Read-only `alpha_discovery`. A deliberate **mechanism switch** after every
cross-sectional OHLCV probe this session reduced to momentum. Tests the
time-of-day structure of returns on the broad 1,446-ticker universe: does the
close-to-close premium accrue mostly **overnight** (prev_close→open) with a
flat/negative **intraday** session (open→close) — the overnight-return
anomaly? This is orthogonal to cross-sectional momentum and relevant to core
entry/exit timing (the system enters at next-day open).

## Result: the textbook overnight anomaly does not robustly hold here

Equal-weight daily cross-sectional means across the canonical 3 windows:

| Component | mean / day | t-stat | significant? |
|---|---|---|---|
| Overnight (prev_close→open) | +0.044% | 1.15 | no |
| Intraday (open→close) | +0.036% | 0.67 | no |
| **Overnight − Intraday** | +0.008% | **0.11** | **no (≈ zero)** |
| Close-to-close | +0.078% | — | — |

- Overnight share of the close-to-close daily return: **55.7%** — only
  slightly more than half, far from the ~100%+ the anomaly literature claims
  (where intraday is typically flat or negative).
- Per-window overnight mean: late_strong +0.019%, mid_weak +0.132%,
  old_thin **−0.016%** → 2/3 windows positive (old_thin negative).
- Overnight and intraday are **statistically indistinguishable**
  (difference t = 0.11); neither component is individually significant.

So on this universe over these three windows, returns split roughly evenly
between the overnight and intraday sessions, and the overnight premium is not
robustly larger than intraday. The textbook overnight-return anomaly is
**absent / not robust** here.

## Why it likely does not appear

- **Survivorship + liquidity filter**: the `all_windows_full_liquid` set is
  liquid large/mid caps; the overnight anomaly is strongest in small / micro
  caps, which are filtered out.
- **Short, bull-leaning sample**: one contiguous 18-month period where the
  intraday session was not punished (unlike the long-run averages in the
  literature).
- **Regime drift**: several recent studies report the overnight anomaly has
  weakened or partially reversed in the last few years.

## Gate evaluation

```json
{
  "all_passed": false,
  "gate4": {
    "name": "robust_overnight_premium_vs_intraday",
    "passed": false,
    "status": "observed_only_no_robust_overnight_structure",
    "overnight_mean_daily": 0.000436,
    "intraday_mean_daily": 0.00036,
    "overnight_share_of_close_to_close": 0.5575,
    "overnight_tstat": 1.1456,
    "overnight_minus_intraday_tstat": 0.1083,
    "overnight_positive_windows": "2/3"
  }
}
```

Pre-run prediction (success_probability 0.45) anticipated this: failure modes
`intraday_not_negative_just_smaller` + `effect_not_robust_across_windows`.

## Implication

- **No overnight-timing edge to exploit on this universe.** The core's
  next-day-open entry is not leaving an obvious overnight premium on the
  table, and shifting entry/exit to capture an overnight-vs-intraday gap is
  not supported here.
- This closes the time-of-day mechanism as a near-term lever on this universe
  without further data (small-cap universe or a longer multi-regime sample
  would be needed to revisit, and even then capturing it requires daily
  open/close turnover whose costs the anomaly literature debates).

## Caveats

Structural decomposition, not a tradeable-edge test (capturing the premium
needs daily close-buy / open-sell with heavy turnover cost + spread);
warehouse `all_windows_full_liquid` survivorship; raw prices, no costs;
gap-open microstructure partly mitigated by a 50% per-component clip; the
three windows are one contiguous 18-month period, not independent regimes.

## Files

- `quant/experiments/exp_20260601_009_overnight_intraday_decomposition.py` (new)
- `quant/test_exp_20260601_009_overnight_intraday.py` (new, 5 tests)
- `data/experiments/exp-20260601-009/overnight_intraday_decomposition.json` (new)
- `experiments/artifacts/exp-20260601-009_overnight_intraday_decomposition.md` (this file)
- `experiments/logs/exp-20260601-009.json`, `experiments/tickets/exp-20260601-009.json`
- Input warehouse `data/experiments/exp-20260519-030/warehouse_main.sqlite` (not committed)

No JavaScript was used.
