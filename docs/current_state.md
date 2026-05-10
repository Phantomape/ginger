# Current State

Last updated: 2026-05-10.

The current accepted core stack includes the 2026-05-10 TRIP sector taxonomy
completion from `exp-20260510-015`, layered on top of the RS20 entry-state
shared sizing promotion from `exp-20260510-012`. Both are documented in
`docs/backtesting.md` and `docs/alpha-optimization-playbook.md`. Canonical
fixed-window core metrics are:

| Window | EV | Return | Sharpe daily | Max DD | Trades | Survival |
|---|---:|---:|---:|---:|---:|---:|
| `late_strong` | 4.2340 | 94.09% | 4.50 | 5.48% | 19 | 80.39% |
| `mid_weak` | 1.6689 | 61.81% | 2.70 | 9.41% | 21 | 79.25% |
| `old_thin` | 0.3853 | 28.54% | 1.35 | 8.15% | 22 | 91.67% |

Latest accepted alpha result: `exp-20260510-015` maps TRIP to Consumer
Discretionary in shared `risk_engine.SECTOR_MAP` instead of leaving it in the
`Unknown` sector path. Aggregate EV improved `+0.0171` (`+0.27%`) and aggregate
PnL improved `+$403.46` (`+0.22%`) across the three canonical windows, with
unchanged trade count and survival. The effect flows through shared sector
enrichment / sector-dispersion allocation, so this is production-visible and
not a replay-only branch.

Latest alpha-search scout: `exp-20260510-018` rejected effective core slot
accounting from observed-only slot-missed replacement value. All blocked rows
were positive in aggregate (`25` rows, `+$8,330.63`), but failed the gate because
win rate was only `40%` and only `1/3` windows was positive. Pure one-extra-slot
rows were positive but too concentrated in PLTR; breakout rows need
`available_slots > 1` because the accepted scarce-slot breakout deferral is
still active.

Current priority: do not retune local add-on trigger, cap, heat, reserve,
strategy-cohort variants, ETF overlay parameters, nearby RS20 risk scalars,
single-ticker sector taxonomy, global `MAX_POSITIONS`, or scarce-slot breakout
thresholds on the same frozen samples. Future slot work needs a shared
exposure/risk-based effective-slot accounting design with full portfolio replay
and production visibility, not another global slot-count sweep.
