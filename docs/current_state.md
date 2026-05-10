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

Latest alpha-search result: `exp-20260510-015` maps TRIP to Consumer
Discretionary in shared `risk_engine.SECTOR_MAP` instead of leaving it in the
`Unknown` sector path. Aggregate EV improved `+0.0171` (`+0.27%`) and aggregate
PnL improved `+$403.46` (`+0.22%`) across the three canonical windows, with
unchanged trade count and survival. The effect flows through shared sector
enrichment / sector-dispersion allocation, so this is production-visible and
not a replay-only branch.

Current priority: do not retune local add-on trigger, cap, heat, reserve,
strategy-cohort variants, ETF overlay parameters, nearby RS20 risk scalars, or
single-ticker sector taxonomy on the same frozen samples. Future taxonomy work
needs a real production universe classification gap plus three-window
no-regression evidence; future RS20 work needs forward attribution or a new
discriminator, not local scalar tuning.
