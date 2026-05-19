# exp-20260509-016 State-Surface Benchmark Gate Adapter

Decision: `accepted_production_alignment_default_off`.

The strongest current alpha lead remains the state-surface benchmark momentum
gate from `exp-20260509-014`: allow state-surface participation only when
`max(SPY_20d_return, QQQ_20d_return) > 0`. This run did not retune that alpha.
It removed the production-parity blocker by adding the exact gate to the shared
default-off state-surface paper queue and snapshot.

The change is intentionally default-off for trading:

- No live orders.
- No core A/B ranking change.
- No sizing change.
- No exit change.
- Production now emits the same benchmark-momentum allow/block reason that the
  replay gate uses.

Three-window backtests stayed unchanged, as expected for a paper-only adapter:

| Window | EV | Sharpe daily | Return | Max DD | Win rate | Trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | 4.0674 | 4.48 | 90.79% | 5.39% | 78.95% | 19 |
| mid_weak | 1.6195 | 2.72 | 59.54% | 8.79% | 52.38% | 21 |
| old_thin | 0.3583 | 1.31 | 27.35% | 9.03% | 40.91% | 22 |

Tests:

- `.\\.venv\\Scripts\\python.exe -m pytest quant\\test_state_surface_sleeve.py`
- `.\\.venv\\Scripts\\python.exe -m pytest quant\\test_event_sleeve_bundle.py quant\\test_state_surface_sleeve.py`

Next action: keep live orders disabled and collect forward paper outcomes with
gate allow/block attribution. A trade-enabled version still needs an explicit
shared backtester adapter and fresh three-window acceptance.
