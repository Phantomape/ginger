# Current State

Last updated: 2026-05-18.

The current accepted core stack includes the 2026-05-17 stock-only ample-slot
rank-1 post-sizing top-up from `exp-20260517-009`, layered on top of the
2026-05-17 scarce-slot rank-1 post-sizing top-up from `exp-20260517-004`,
layered on top of the 2026-05-16 ISRG core long risk promotion from
`exp-20260516-042`, layered on top of the
2026-05-16 TSM core
long risk promotion from `exp-20260516-039`, layered on top of the 2026-05-16
Technology trend DTE residual risk promotion from `exp-20260516-020`, layered on top of the
2026-05-16 green-deceleration quality non-consumer core sizing promotion from
`exp-20260516-009`, layered on
top of the 2026-05-15 confirmed-quality core sizing promotion from
`exp-20260515-028`, layered on top of the 2026-05-15
trend-only price-vs-200MA extension sizing promotion from `exp-20260515-026`,
layered on top of the 2026-05-15 broad price-vs-200MA extension sizing promotion from
`exp-20260515-018`, layered on top of the
2026-05-15 clean-SPY cap-only RS20 leader cap promotion from
`exp-20260515-013`,
the 2026-05-15 clean-SPY cap-only leader cap promotion from
`exp-20260515-008`,
the 2026-05-14 Gold trend near-high cap promotion from core
`exp-20260514-050`, the 2026-05-14 Commodity breakout cap promotion from core
`exp-20260514-049`, the 2026-05-14 Financials mid-dispersion sector-leader
cap promotion from core `exp-20260514-030`, the 2026-05-14 clean SPY-relative
leader signal-day cap promotion from `exp-20260514-027`, the 2026-05-14
Financials sector-leader trend cap promotion from `exp-20260514-023`, the
2026-05-14 commodity near-high trend cap promotion from `exp-20260514-018`,
the 2026-05-13 clean SPY-relative leader signal-day sizing promotion from `exp-20260513-036`,
the RS60 top-quintile stock sizing promotion from `exp-20260513-030`, the
signal-day own-green candle sizing promotion from `exp-20260513-007`, the
2026-05-10 TRIP sector taxonomy completion from `exp-20260510-015`, and the
RS20 entry-state shared sizing promotion from `exp-20260510-012`. These are
documented in `docs/backtesting.md` and
`docs/alpha-optimization-playbook.md`. Canonical fixed-window core metrics are:

| Window | EV | Return | Sharpe daily | Max DD | Trades | Survival |
|---|---:|---:|---:|---:|---:|---:|
| `late_strong` | 5.1628 | 117.07% | 4.41 | 6.65% | 18 | 80.39% |
| `mid_weak` | 2.1402 | 78.11% | 2.74 | 11.19% | 21 | 79.25% |
| `old_thin` | 0.5911 | 39.67% | 1.49 | 10.01% | 22 | 86.67% |

Latest accepted three-window artifact:
`data/experiments/exp-20260517-009/`.
Aggregate core EV is now `7.8941`; aggregate PnL is `$234,850.99`.
Latest saved single-window backtest artifacts can reflect only the most recent
command; canonical acceptance evidence is the three-window artifact above.

Latest core-misfit replay-only paper-sleeve result: `exp-20260516-043` accepted a
default-off core-misfit paper attribution surface for `TSM`, `ISRG`, `V`, and
`DDOG` without changing core metrics. Identity control passed with zero metric
delta versus the accepted `exp-20260516-042` core stack. Across the 9 primary
misfit core trades, actual core PnL was `-$6,469.57`, so the no-trade avoided
value was `+$6,469.57`; inverse paper held to the actual long exit was
`+$4,385.29`. The 1/3/5/10-day fast-long surfaces were all negative, while
inverse paper horizons were positive. This supports treating the cohort as
negative-for-core and tracking it in a default-off paper sleeve, not live
shorting or immediate full core exclusion. Live short/exclusion promotion
requires closed forward paper outcomes and a separate Gate 1-4 experiment.

Latest production-visible paper adapter: `exp-20260517-002` implements the
`CORE_MISFIT_PAPER` sleeve as a daily default-off ledger and report block. It
copies only selected or slot-sliced `TSM` / `ISRG` / `V` / `DDOG` core long
signals into no-trade, fast-long, and inverse-short paper outcomes at 1/3/5/10
trading-day horizons. It does not change core entries, exits, ranking, sizing,
slots, heat, LLM/news, or orders, and it does not enable live shorts. The
forward gate requires at least 20 closed 10-day paper outcomes plus positive
no-trade and inverse evidence before any separate live exclusion/short
experiment is allowed.

Latest rejected short-shadow scout: `exp-20260517-003` tested whether the same
`TSM` / `ISRG` / `V` / `DDOG` core-misfit signals are true short alpha rather
than only no-trade alpha. The best replay-only policy was a simple 10-trading-
day short hold, with 9 trades, PnL `+$6,079.66`, win rate `66.67%`, worst trade
`-4.53%`, and max drawdown `0.73%`. Gate 4 still rejected live/paper promotion
because only `old_thin` was positive (`+$6,855.82`) while `mid_weak` was
negative (`-$776.16`), and the sample still lacks borrow/locate costs plus the
20 closed forward outcomes required by `CORE_MISFIT_PAPER`. Interpretation:
there is a real inverse clue, but not a live short rule.

Latest accepted alpha result: core `exp-20260517-009` keeps entries, exits,
filters, universe, targets, heat, LLM, news, and pre-slot ranking unchanged,
but applies a shared cap-aware `1.05x` post-sizing top-up to the already
selected rank-1 stock signal only when entry planning has at least four
available slots. ETF and Commodity sectors are excluded; this preserves the
positive `late_strong` / `mid_weak` allocation clue from rejected broad
ample-slot scout `exp-20260517-008` while avoiding its `old_thin` Commodity
regression. The top-up lives in `production_parity.py`, so `backtester.py` and
`run.py` use the same planner. Aggregate EV improved `+0.0356` and aggregate
PnL improved `+$1,232.90`; `late_strong` improved EV `+0.0267` / PnL
`+$345.66`, `mid_weak` improved EV `+0.0089` / PnL `+$887.24`, and `old_thin`
was unchanged. Trade count, survival, worst trade, and loss streak did not
worsen; `mid_weak` max drawdown rose from `10.83%` to `11.19%`, inside the
Gate 4 guardrail. This is not a slot-priority rule: it does not rescue sliced
candidates or change ranking.

Previous accepted default-off paper alpha result: `exp-20260517-014` tested a
rotation-only state-surface satellite candidate pool. It restricts the
default-off `STATE_SURFACE_SATELLITE` paper candidates to
`rotation_breakout_leadership` while retaining full scored-candidate audit and
leaving live/default orders disabled. Three-window replay improved every
window: aggregate EV `+1.0486`, aggregate PnL `+$26,129.58`, selected sleeve
trades `22`, and single-ticker positive contribution share `31.17%`. The
shared policy lives in `state_surface_sleeve.py`; `run.py` continues to use
that shared default-off paper path, and core backtests / live orders are not
changed.

Previous accepted state-surface paper refinement: `exp-20260517-016` keeps the
rotation-only paper sleeve from `exp-20260517-014`, but requires
`features.ret20_excess_spy >= 0.0` before a candidate can enter the
default-off paper queue. The three-window sweep accepted the least restrictive
passing floor: aggregate EV `+0.2234`, aggregate PnL `+$2,449.90`, selected
sleeve trades stayed `22`, and single-ticker positive contribution share fell
from `31.17%` to `29.72%`. `late_strong` improved EV `+0.1739` / PnL
`+$1,733.03`, `mid_weak` improved EV `+0.0495` / PnL `+$716.87`, and
`old_thin` was unchanged. The shared policy and test live in
`state_surface_sleeve.py` / `test_state_surface_sleeve.py`; live/default
orders remain disabled.

Latest accepted state-surface paper refinement: `exp-20260517-025` keeps the
rotation-only sleeve and `ret20_excess_spy >= 0.0` gate from
`exp-20260517-016`, but expands the shared default-off daily paper queue from
top 3 to top 5 ranked candidates. The 3-window replay improved aggregate EV by
`+0.3995` and aggregate PnL by `+$5,321.49`: `late_strong` improved EV
`+0.2004` / PnL `+$1,979.75`, `mid_weak` improved EV `+0.1991` / PnL
`+$3,341.74`, and `old_thin` was unchanged. Selected state-surface paper
trades rose from `22` to `24`, single-ticker positive share stayed controlled
at `34.04%`, and live/default orders remain disabled. The accepted production
path is the shared default-off `state_surface_sleeve.py` queue with parity
coverage in `test_state_surface_sleeve.py`.

Latest accepted state-surface paper allocation refinement:
`exp-20260518-002` keeps the accepted rotation-only sleeve, `ret20_excess_spy
>= 0.0` gate, top-five daily queue, active cap, and 20-day hold unchanged, but
changes default-off paper notional by queue rank to `[1.5, 1.25, 1.0, 0.75,
0.5]` times the $10,000 base. Versus the flat-notional top-five baseline,
three-window EV improved `+0.4905` and PnL improved `+$10,118.13`: `late_strong`
improved EV `+0.1324` / PnL `+$2,370.46`, `mid_weak` improved EV `+0.2653` /
PnL `+$4,534.04`, and `old_thin` improved EV `+0.0928` / PnL `+$3,213.63`.
Selected paper trades stayed `24`, single-ticker positive share fell to
`32.22%`, and live/default orders remain disabled. The accepted profile lives
in shared `state_surface_sleeve.py` with focused parity coverage in
`test_state_surface_sleeve.py`.

Recent observed-only state-surface diagnostics: `exp-20260518-004` captured
canonical three-window core controls plus tail-aware sidecar diagnostics for
the flat top-five, accepted rank-notional, and rejected hold-days variants.
Core control passed exactly against the accepted fixed-window metrics. The
accepted rank-notional profile still improved EV by `+0.4905` and PnL by
`+$10,118.13` versus flat notional, but the PnL top-five contribution worsened
from `57.52%` to `60.16%`; old_thin rank-notional evidence remained only three
paper trades. The closeout decision is
`observed_only_no_new_strategy_variable`: keep the accepted default-off
rank-notional policy, do not revive the 25-day hold, and require forward
replacement-value evidence or a genuinely new production-visible
heat/regime/rank-quality field before another allocation test.

Previous accepted state-surface paper regime refinement: `exp-20260518-005`
uses the production-visible shared market-regime classifier as that new
discriminator. It keeps the accepted rotation-only sleeve, `ret20_excess_spy
>= 0.0` gate, top-five queue, active cap, 20-day hold, and all-regime
rank-notional profile unchanged, but applies a `chop` override of `[1.625, 1.3,
1.0, 0.7, 0.375]` times the $10,000 base. Versus the accepted all-regime
rank-notional baseline, three-window EV improved `+0.1199` and PnL improved
`+$2,111.20`: `late_strong` improved EV `+0.0390` / PnL `+$576.22`,
`mid_weak` improved EV `+0.0570` / PnL `+$806.91`, and `old_thin` improved EV
`+0.0239` / PnL `+$728.07`. Selected paper trades stayed `24`, max drawdown
worsened by only `0.08pp`, and single-ticker positive share stayed controlled
at `31.69%`. The accepted rule lives in shared `state_surface_sleeve.py` with
focused parity coverage in `test_state_surface_sleeve.py`; live/default orders
remain disabled.

Recent state-surface measurement repair: `exp-20260518-006` adds a read-only
tail-concentration diagnostic to the shared default-off state-surface forward
paper gate and daily report. It does not change candidates, ranking, notional,
hold days, core metrics, or live/default orders. Replaying the accepted
`exp-20260518-005` paper outcomes as a matured closed sample showed the old
forward gate would pass on 24 closed paper trades, `0.7917` win rate, and
`$48,529.40` realized paper PnL, but the tail-aware gate correctly blocks
promotion readiness because PnL top-five contribution is `61.04%`
(`pnl_top5_concentration`) with HHI `0.0949`. Treat this as a forward promotion
guardrail: keep collecting closed state-surface paper outcomes, and do not
promote or retune nearby profiles until concentration improves or a genuinely
new production-visible discriminator appears.

Latest accepted state-surface paper candidate-breadth refinement:
`exp-20260518-008` uses that new production-visible discriminator while keeping
the rotation-only sleeve, `ret20_excess_spy >= 0.0` gate, top-five queue,
active cap, 20-day hold, and the accepted regime-aware rank-notional profile
otherwise unchanged. When the qualified same-day paper queue has at least four
candidates, the shared default-off paper path uses `[1.6625, 1.315, 1.0,
0.675, 0.35]` times the $10,000 base. Versus the accepted `exp-20260518-005`
baseline, three-window EV improved `+0.0400` and PnL improved `+$926.94`:
`late_strong +0.0078` EV / `+$172.87`, `mid_weak +0.0282` EV / `+$535.65`,
and `old_thin +0.0040` EV / `+$218.42`. Selected paper trades stayed `24`,
max drawdown worsened by only `0.03pp`, and single-ticker positive share stayed
controlled at `31.37%`. The accepted rule lives in shared
`state_surface_sleeve.py` with focused parity coverage in
`test_state_surface_sleeve.py`; live/default orders remain disabled.

Previous accepted state-surface paper score-dispersion refinement:
`exp-20260518-013` keeps the accepted `exp-20260518-008` candidate-breadth
profile fixed, but adds a production-visible top-three queue score-compression
override. When the same-day qualified paper queue has at least three candidates
and `score_top3_spread <= 0.40`, the shared default-off paper path uses
`[1.35, 1.45, 1.05, 0.675, 0.35]` times the $10,000 base. Versus the accepted
candidate-breadth baseline, three-window EV improved `+0.0422` and PnL
improved `+$451.81`: `late_strong +0.0287` EV / `+$347.24`, `mid_weak
+0.0135` EV / `+$104.57`, and `old_thin` unchanged. Six paper trades were
adjusted across two windows, max drawdown did not worsen, and single-ticker
positive share stayed controlled at `31.28%`. The accepted rule lives in
shared `state_surface_sleeve.py` with focused parity coverage in
`test_state_surface_sleeve.py`; live/default orders remain disabled.

Latest accepted state-surface paper rank-quality refinement:
`exp-20260518-018` keeps the accepted `exp-20260518-013` score-compression
stack fixed, but adds one production-visible field: rank-2 candidate
`ret20_excess_spy` leadership over rank 1. When rank 2 leads rank 1 by at
least `0.005`, the shared default-off paper path uses
`[1.3, 1.55, 1.1, 0.675, 0.35]` times the $10,000 base. Versus the accepted
score-compression baseline, three-window EV improved `+0.0260` and PnL
improved `+$544.72`: `late_strong +0.0041` EV / `+$90.93`, `mid_weak +0.0178`
EV / `+$228.52`, and `old_thin +0.0041` EV / `+$225.27`. Nine paper trades
were adjusted across all three windows, max drawdown did not worsen, and
single-ticker positive share stayed controlled at `33.63%`. The accepted rule
lives in shared `state_surface_sleeve.py` with focused parity coverage in
`test_state_surface_sleeve.py`; live/default orders remain disabled.

Latest rejected default-off paper alpha result: `exp-20260517-015` tested
whether the rotation-only state-surface sleeve should require a stronger
`max(SPY, QQQ)` 20-day benchmark return before admitting paper candidates. The
current shared `0.0` threshold remains best. The `0.5%` non-control threshold
was identical to the current policy (`0.0000` EV / `$0.00` PnL delta), while
`1.0%+` thresholds regressed aggregate EV/PnL by removing useful old-window
paper trades. No shared policy changed; do not retune this benchmark gate again
on the frozen windows without forward paper outcomes or a new production-visible
state field.

Latest rejected alpha result: core `exp-20260517-008` tested the opposite slot
regime after the accepted one-slot rank-1 top-up: a replay-only cap-aware
top-up to the already selected rank-1 signal only when entry planning had at
least four available slots. The best non-control scalar was `1.05x`, with
aggregate EV `+0.0919` and aggregate PnL `+$2,205.88`, but Gate 4 rejected
promotion because `old_thin` regressed (`0.5911 -> 0.5902` EV / `-$55.19`)
while `late_strong` and `mid_weak` improved. No shared production policy
changed. This means the accepted scarce-slot top-up remains scoped to exactly
one remaining slot; do not generalize slot-availability top-ups without a new
production-visible discriminator.

Latest rejected sample-thin alpha result: core `exp-20260517-007` tested a
replay-only haircut of the existing `breakout_long` Financials 8-14 DTE risk
pocket. The best non-control scalar was `0.125x`, improving aggregate EV
`+0.0274` and aggregate PnL `+$566.73` with no regressed window, but only two
signals were affected across the three canonical windows, below the Gate 4
sample guard. No shared production policy changed. Treat it as a clue that the
current Financials breakout DTE pocket deserves forward attribution, not as a
reason to keep sweeping nearby DTE scalars on the frozen sample.

Previous rejected scarce-slot scout: core `exp-20260517-006` tested the
adjacent scarce-slot generalization after `exp-20260517-005`: a replay-only
cap-aware top-up to the already selected rank-2 core signal when entry planning
had exactly two remaining slots. The best non-control scalar was `1.025x`, but
Gate 4 rejected promotion: aggregate EV moved only `+0.0019`, aggregate PnL
fell `-$0.55`, only `late_strong` improved, `old_thin` regressed, `mid_weak`
was unchanged, and only 2 signals were adjusted across two windows. No shared
production policy changed.

Previous accepted alpha result: core `exp-20260516-042` keeps entries, exits,
ranking, universe, filters, targets, slots, heat, LLM, and news logic
unchanged, but applies a ticker-specific `0.25x` post-sizing scalar to existing
`ISRG` core long signals. Aggregate EV improved `+0.0512` and aggregate PnL
improved `+$1,857.98` across the three canonical windows after the TSM
promotion. `late_strong` was unchanged; `mid_weak` and `old_thin` improved.
The lifecycle diagnostic found no fast-target rescue support, and the `0.0x`
variant failed by regressing `old_thin`. The rule lives in the shared
`portfolio_engine.py` constant path used by both `quant/backtester.py` and
`quant/run.py`; focused sizing tests cover ISRG and non-ISRG Healthcare
behavior. This is a ticker-specific exception, not a Healthcare rule.

Previous accepted alpha result: core `exp-20260516-039` keeps entries, exits,
ranking, universe, filters, targets, slots, heat, LLM, and news logic
unchanged, but applies a ticker-specific `0.25x` post-sizing scalar to existing
`TSM` core long signals. Aggregate EV improved `+0.0143` and aggregate PnL
improved `+$607.71` across the three canonical windows. The lifecycle
diagnostic found no fast-target rescue support: all 1/3/5-day net windows were
negative and no TSM trade had close-to-close profit available before stop. The
rule lives in the shared `portfolio_engine.py` constant path used by both
`quant/backtester.py` and `quant/run.py`; focused sizing tests cover TSM and
non-TSM Technology behavior. The `0.0x` variant failed by regressing
`old_thin`, so do not generalize this into a semiconductor rule or retry nearby
TSM scalar/target changes without new evidence.

Latest rejected core risk-allocation scout: `exp-20260516-011` tested whether
the existing `trend_long` / Industrials zero-risk rule was over-killing
qualified candidates. The replay-only sweep changed only
`TREND_INDUSTRIALS_RISK_MULTIPLIER` (`0.10x`, `0.25x`, `0.50x`) and left
entries, ranking, exits, targets, universe, LLM/news, heat, slots, and the
separate Industrials breakout-gap rule unchanged. Gate 4 failed decisively:
even the best `0.10x` variant moved aggregate EV `7.7654 -> 6.8741`
(`-0.8913`) and aggregate PnL `$230,390.92 -> $194,601.06`
(`-$35,789.86`). Only `late_strong` improved slightly (`+0.0079` EV /
`+$180.42`), while `mid_weak` regressed `-0.4788` EV / `-$13,029.54` and
`old_thin` regressed `-0.4204` EV / `-$22,940.74`; max drawdown drift breached
the guardrail at `+1.84 pp`. The adjusted tickers were `CAT`, `DE`, `RTX`, and
`GE`; the weak/old-window losses mean the current zero-risk rule remains the
production default. Do not retry nearby Industrials trend risk scalars without
a materially new production-visible discriminator or forward replacement-value
evidence.

Latest rejected sample-thin Technology / semiconductor scout:
`exp-20260516-012` tested a replay-only post-sizing haircut for existing
`trend_long` semiconductor / AI-chip signals whose signal-day candle was not
green. The best scalar was `0.00x` and the result was directionally positive
across the canonical windows without a regressed window: aggregate EV
`+0.0044` and aggregate PnL `+$143.90`, with `late_strong` `+0.0017` EV /
`+$40.86`, `mid_weak` `+0.0027` EV / `+$103.04`, and `old_thin` unchanged.
However, the adjusted cohort was only two `TSM` signals, below the mature-
cohort guardrail, so no shared policy was promoted. Treat this as a forward
attribution clue, not a production rule; do not retry nearby hand-bounded
semiconductor non-green trend haircuts without a broader industry field or
forward ticker-level contribution evidence.

Latest promising replay-only event allocation result: `exp-20260517-010`
revalidated the `rotation_breakout_leadership` surface after the accepted
`exp-20260517-009` core stack. It changed only default-off paper event notional
inside the event bundle; core entries, sizing, exits, ranking, LLM/news, and
live orders were unchanged. The best variant was a `3.0x`
`rotation_breakout_leadership` scalar above the current `2.0x` non-generic
positive event-surface add-on. Versus the current paper lead, aggregate EV
improved `+0.5389` and aggregate PnL improved `+$7,987.90`, with all three
windows positive (`late_strong +0.3138`, `mid_weak +0.2171`, `old_thin
+0.0080` EV). The sample guard passed and there were no EV-regressed windows.
The default-off paper attribution path is shared in `quant/event_sleeve_bundle.py`,
but this remains replay-only: do not route live/default capital until closed
forward replacement-value evidence and explicit trade-enabled adapter
configuration exist. Prior supporting revalidations: `exp-20260517-001` and
`exp-20260516-044`.

Latest rejected SEC completeness alpha search: `exp-20260516-045` tested a new
cash-flow forecast/guidance/outlook context field inside the accepted
default-off SEC financial-report T+1 paper sleeve. The best scalar was a
`0.50x` haircut, but Gate 4 failed: aggregate EV improved only `+0.0470` while
aggregate PnL fell `-$395.04`, only `late_strong` improved, `mid_weak` and
`old_thin` regressed, and the target field had only 8 closed sleeve trades
versus the 20-trade guard. Do not retry cash-flow forecast notional scalars on
the frozen sample; future SEC completeness work needs broader production-visible
forecast fields, better text coverage, or forward replacement-value evidence.

Latest rejected execution alpha scout: `exp-20260516-007` tested a replay-only
delayed open-pullback entry for rank-1 `trade_quality_score >= 0.95`
`gap_cancel` candidates. It did not change production logic. Aggregate EV
improved `+0.6019` and aggregate PnL improved `+$7,876.57`, but Gate 4 failed:
only `late_strong` improved, `old_thin` regressed, replacement trades were only
3 across 2 windows, and the positive PnL was concentrated in one `CRDO` trade.
Do not promote or retry the simple open-pullback variant without a materially
different production-visible execution discriminator.

Latest accepted alpha result: core `exp-20260516-009` keeps entries, exits,
ranking, universe, filters, targets, slots, heat, LLM, and news logic
unchanged, but gives already-qualified `trend_long` / `breakout_long` signals
with own signal-day green confirmation, positive decelerating 10d-vs-20d
momentum, `trade_quality_score >= 0.95`, and sector outside Consumer
Discretionary / Communication Services an additional 1.025x cap-aware
post-sizing top-up. Aggregate EV improved `+0.0309` and aggregate PnL improved
`+$754.19` across the three canonical windows: `late_strong` EV
`5.1064 -> 5.1344`, `mid_weak` EV `2.0987 -> 2.1016`, and `old_thin` EV stayed
`0.5294`. Max drawdown drift stayed inside Gate 4 (`+0.20 pp` worst window),
trade count stayed `62`, and minimum survival stayed `79.25%`. The rule lives
in shared `risk_engine.py` / `portfolio_engine.py`, backtester attribution
keys, and focused production-parity tests. Larger 1.05x+ values regressed
`old_thin`; 1.075x failed drawdown.

Previous accepted alpha result: core `exp-20260515-028` keeps entries, exits,
ranking, universe, filters, targets, slots, heat, LLM, and news logic
unchanged, but gives already-qualified `trend_long` / `breakout_long` signals
with `trade_quality_score >= 0.95`, `rs20_entry_state_leader=true`, and
`signal_day_ticker_green_candle=true` an additional 1.075x cap-aware
post-sizing top-up. Aggregate EV improved `+0.0866` and aggregate PnL improved
`+$2,604.84` across the three canonical windows: `late_strong` EV
`5.0334 -> 5.1064`, `mid_weak` EV `2.0900 -> 2.0987`, and `old_thin` EV
`0.5245 -> 0.5294`. Max drawdown drift stayed inside Gate 4 (`+0.49 pp` worst
window), trade count stayed `62`, minimum survival stayed `79.25%`, and
`old_thin` survival moved `90.00% -> 86.67%`. The rule lives in shared
`risk_engine.py` / `portfolio_engine.py`, backtester attribution keys, and
focused production-parity tests. Larger 1.08x+ values failed the drawdown
guardrail.

Previous accepted alpha result: core `exp-20260515-026` keeps entries, exits,
ranking, universe, filters, targets, slots, heat, LLM, and news logic
unchanged, but gives already-qualified `trend_long` non-ETF/non-commodity
stock signals with `price_vs_200ma_extension_state=true` an additional 1.125x
cap-aware post-sizing top-up after the accepted broad extension top-up.
Aggregate EV improved `+0.0943` and aggregate PnL improved `+$3,086.63`
across the three canonical windows: `late_strong` EV stayed `5.0334`,
`mid_weak` EV improved `2.0103 -> 2.0900`, and `old_thin` EV improved
`0.5099 -> 0.5245`. Max drawdown drift stayed inside Gate 4 (`+0.47 pp` worst
window), trade count stayed `62`, minimum survival stayed `79.25%`, and
`old_thin` survival moved `91.67% -> 90.00%`. The rule lives in shared
`portfolio_engine.py`, backtester attribution keys, and focused
production-parity tests. Larger 1.15x+ values failed the drawdown guardrail.

Previous accepted alpha result: core `exp-20260515-018` keeps entries, exits,
ranking, universe, filters, targets, slots, heat, LLM, and news logic
unchanged, but tags already-qualified `trend_long` / `breakout_long`
non-ETF/non-commodity stock signals whose `price_vs_200ma_pct` is in the
same-day top quartile and applies a 1.025x cap-aware post-sizing top-up.
Aggregate EV improved `+0.0208` and aggregate PnL improved `+$882.67` across
the three canonical windows: `late_strong` EV `5.0322 -> 5.0334`, `mid_weak`
EV `1.9947 -> 2.0103`, and `old_thin` EV `0.5059 -> 0.5099`. Max drawdown
drift stayed inside Gate 4 (`+0.10 pp` worst window), trade count and survival
were unchanged, and the rule lives in shared `risk_engine.py` /
`portfolio_engine.py` with focused production-parity tests. Nearby larger
scalars failed because they regressed `late_strong` or drawdown.

Previous accepted alpha result: core `exp-20260515-013` keeps entries, exits,
ranking, universe, raw clean-SPY and RS20 risk multipliers, heat, slots, and
LLM/news logic unchanged, but allows already-qualified clean-SPY cap-only
leaders with `rs20_entry_state_leader=true` to use a 70% single-position cap.
Aggregate EV improved `+0.3865` and aggregate PnL improved `+$8,878.68` across
the three canonical windows: `late_strong` EV `4.7144 -> 5.0322`, `mid_weak`
EV `1.9376 -> 1.9947`, and `old_thin` EV `0.4943 -> 0.5059`. Max drawdown
drift stayed inside Gate 4 (`+0.30 pp` worst window), trade count and survival
were unchanged, and the rule lives in shared `portfolio_engine.py` with focused
production-parity tests.

Previous accepted alpha result: core `exp-20260515-008` keeps entries, exits,
ranking, universe, raw clean-SPY risk, heat, slots, and LLM/news logic
unchanged, but allows clean-SPY cap-only leaders to use a 60% single-position
cap. Aggregate EV improved `+0.1809` and aggregate PnL improved `+$4,488.22`
across the three canonical windows, with unchanged trade count and survival.

Previous accepted alpha result: core `exp-20260514-050` keeps entries, exits,
ranking, universe, raw Commodity risk, heat, slots, and LLM/news logic
unchanged, but allows already-qualified `trend_long` GLD/IAU Commodity
near-high signals to use a 57.5% single-position cap. Aggregate EV improved
`+0.0380` and aggregate PnL improved `+$1,472.29` across the three canonical
windows.

Previous accepted alpha result: core `exp-20260514-049` keeps entries, exits,
ranking, universe, raw Commodity risk, heat, slots, and LLM/news logic
unchanged, but allows the already-qualified `breakout_long` Commodities sleeve
to use a 57.5% single-position cap. Aggregate EV improved `+0.1092` and
aggregate PnL improved `+$2,119.18` across the three canonical windows:
`late_strong` EV `4.4853 -> 4.5701`, `mid_weak` EV `1.8580 -> 1.8824`, and
`old_thin` stayed `0.4749`. Max drawdown did not worsen, trade count and
survival were unchanged, and the rule lives in shared `portfolio_engine.py`
with focused production-parity tests.

Previous accepted alpha result: core `exp-20260514-030` keeps entries, exits,
ranking, universe, raw Financials risk, heat, slots, and LLM/news logic
unchanged, but allows the already-accepted `trend_long` Financials
sector-leader sleeve to use a 55% single-position cap only when
`mid_sector_dispersion=true`. Aggregate EV improved `+0.0123` and aggregate
PnL improved `+$618.16` across the three canonical windows: `late_strong`
unchanged at EV `4.4853`, `mid_weak` EV `1.8502 -> 1.8580`, and `old_thin` EV
`0.4704 -> 0.4749`. Max drawdown drift stayed inside Gate 4 (`+0.13 pp` worst
window), trade count and survival were unchanged, and the rule lives in shared
`portfolio_engine.py` with focused production-parity tests.

Previous accepted alpha result: `exp-20260514-027` keeps entries, exits, ranking,
universe, raw clean-SPY risk multiplier, heat, slots, and LLM/news logic
unchanged, but allows already clean `risk_on` SPY-relative leaders whose ticker
also beat SPY on the signal day to use a 52.5% single-position cap. Aggregate
EV improved `+0.0719` and aggregate PnL improved `+$1,897.40` across the three
canonical windows: `late_strong` EV `4.4313 -> 4.4853`, `mid_weak` EV
`1.8324 -> 1.8502`, and `old_thin` EV `0.4703 -> 0.4704`. Max drawdown drift
stayed inside Gate 4 (`+0.11 pp` worst window), trade count and survival were
unchanged, and the rule lives in shared `portfolio_engine.py` with focused
production-parity tests.

Latest rejected Space alpha search: `exp-20260517-018` swept only
`space_vsat_forward_benchmark_same_theme_satcom_fallback_risk_scalar`
(`0.125x`, `0.25x`, `0.5x`, `0.75x`, `1.0x`) on top of the accepted
`exp-20260516-029` Space stack. The best raw variant was `1.0x`: aggregate EV
improved `+5.1468` and aggregate PnL improved `+$101,063.13`, but Gate 4 still
rejected it because `old_thin` regressed by EV `-0.0408` / PnL `-$1,520.10`
and the max drawdown ceiling worsened by `+3.22 pp`. Smaller risk scalars kept
the same `old_thin` regression and the same drawdown breach. No shared policy,
backtester adapter, run adapter, or live Space slot changed. Do not retry
VSAT/satcom fallback membership or risk scalars on these frozen windows without
new closed forward rows or a production-visible field that prevents peer-basket
contamination.

Latest accepted default-off Space alpha result: `exp-20260516-029` keeps live
Space slots at zero and adds only the shared
`space_source_diversity_dual_catalyst_benchmark_breadth_trend_risk_scalar=1.0125`
helper on top of accepted `exp-20260516-024`. It applies only to
source-diverse official Space `trend_long` signals whose event profile contains
both `customer_win` and `government_space_contract` and whose closed
event-state replacement rows are cash-, SPY-, QQQ-, UFO-, and ARKX-positive.
Aggregate EV improved `+0.1868` and aggregate PnL improved `+$5,124.39` across
the three frozen Space replay windows: `late_strong` EV `+0.0476`,
`mid_weak` EV `+0.1392`, and `old_thin` unchanged. Trade count and survival
were unchanged; aggregate max drawdown ceiling drift stayed inside Gate 4 at
`+0.27 pp`. The changed slice was 4 LUNR/RKLB signals across late/mid windows.
The helper lives in shared `space_catalyst_sleeve.py`, is surfaced in the
production observation slot/report, has focused parity tests, and remains
observe-only/default-off.

Previous accepted default-off Space alpha result: `exp-20260516-024` keeps live
Space slots at zero and adds only the shared
`space_source_diversity_dual_catalyst_financing_profile_trend_risk_scalar=1.0125`
helper on top of accepted `exp-20260516-023`. It applies only to
source-diverse official Space `trend_long` signals whose event profile contains
both `customer_win` and `government_space_contract` and whose production
registry `event_guard_profile` is financing/dilution sensitive. Aggregate EV
improved `+0.2847` and aggregate PnL improved `+$8,154.32` across the three
frozen Space replay windows: `late_strong` EV `+0.0413`, `mid_weak` EV
`+0.2434`, and `old_thin` unchanged. Trade count and survival were unchanged;
aggregate max drawdown ceiling drift stayed inside Gate 4 at `+0.25 pp`. The
helper lives in shared `space_catalyst_sleeve.py`, is surfaced in the
production observation slot/report, has focused parity tests, and remains
observe-only/default-off. Stronger nearby `1.025x`/`1.05x` variants had higher
raw EV but failed the drawdown guardrail.

Previous accepted default-off Space alpha result: `exp-20260516-023` keeps live
Space slots at zero and adds only the shared
`space_source_diversity_dual_catalyst_near_perfect_trend_risk_scalar=1.0125`
helper on top of accepted `exp-20260516-019`. It applies only to source-diverse
official Space `trend_long` signals whose event profile contains both
`customer_win` and `government_space_contract` and whose TQS is near-perfect
but not perfect (`0.95 <= TQS < 1.0`). Aggregate EV improved `+0.0809` and
aggregate PnL improved `+$1,777.65` across the three frozen Space replay
windows: `late_strong` EV `+0.0345`, `mid_weak` EV `+0.0464`, and `old_thin`
unchanged. Trade count and survival were unchanged; aggregate max drawdown
ceiling drift stayed inside Gate 4 at `+0.26 pp`. The helper lives in shared
`space_catalyst_sleeve.py`, is surfaced in the production observation
slot/report, has focused parity tests, and remains observe-only/default-off.

Previous accepted default-off Space alpha result: `exp-20260516-019` keeps live
Space slots at zero and adds only the shared
`space_source_diversity_dual_catalyst_same_theme_winner_trend_risk_scalar=1.0125`
helper on top of accepted `exp-20260516-015`. It applies only to source-diverse
official Space `trend_long` signals whose event profile contains both
`customer_win` and `government_space_contract` and whose closed defense-budget
`government_space_contract` event rows are cash- and same-theme
replacement-positive. Aggregate EV improved `+0.1421` and aggregate PnL
improved `+$4,954.90` across the three frozen Space replay windows:
`late_strong` EV `+0.0399`, `mid_weak` EV `+0.1022`, and `old_thin`
unchanged. Trade count and survival were unchanged; aggregate max drawdown
ceiling drift stayed inside Gate 4 at `+0.26 pp`. The helper lives in shared
`space_catalyst_sleeve.py`, is surfaced in the production observation
slot/report, has focused parity tests, and remains observe-only/default-off.

Latest rejected default-off Space alpha search: `exp-20260516-017` and
`exp-20260516-018` tested dual-catalyst peer-leader and peer-nonleader scalars
on top of accepted `exp-20260516-015`. After retaining the accepted IWM-leader
helper in the true baseline, both produced zero incremental EV/PnL across the
three frozen Space replay windows. `exp-20260516-017` selected the identity
scalar (`1.0`); `exp-20260516-018` selected `0.95` for four ASTS/RKLB signals
across two windows but still had aggregate EV/PnL delta `0.0`. No shared helper
was promoted, and live Space slots remain zero/default-off.

Previous accepted default-off Space alpha result: `exp-20260516-015` keeps live
Space slots at zero and adds only the shared
`space_source_diversity_dual_catalyst_iwm_leader_trend_risk_scalar=1.0125`
helper on top of accepted `exp-20260516-014`. It applies only to source-diverse
official Space `trend_long` signals whose event profile contains both
`customer_win` and `government_space_contract` while IWM 20d momentum is above
SPY 20d momentum. Aggregate EV improved `+0.2377` and aggregate PnL improved
`+$6,670.29` across the three frozen Space replay windows: `late_strong` EV
`+0.0125`, `mid_weak` EV `+0.2252`, and `old_thin` unchanged. Trade count and
survival were unchanged; aggregate max drawdown ceiling drift stayed inside Gate
4 at `+0.25 pp`. The helper lives in shared `space_catalyst_sleeve.py`, is
surfaced in the production observation slot/report, has focused parity tests,
and remains observe-only/default-off.

Previous accepted default-off Space alpha result: `exp-20260516-014` keeps live
Space slots at zero and adds only the shared
`space_source_diversity_dual_catalyst_trend_risk_scalar=1.025` helper on top
of the accepted `exp-20260515-044` Space stack. It applies only to
source-diverse official Space `trend_long` signals whose event profile contains
both `customer_win` and `government_space_contract`. Aggregate EV improved
`+0.5574` and aggregate PnL improved `+$14,086.09` across the three frozen
Space replay windows: `late_strong` EV `+0.0804`, `mid_weak` EV `+0.4770`, and
`old_thin` unchanged. Trade count and survival were unchanged; aggregate max
drawdown ceiling drift stayed inside Gate 4 at `+0.50 pp`. The helper lives in
shared `space_catalyst_sleeve.py`, is surfaced in the production observation
slot/report, has focused parity tests, and remains observe-only/default-off.

Previous accepted alpha result: `exp-20260514-023` keeps entries, exits, ranking,
universe, raw Financials risk, heat, slots, and LLM/news logic unchanged, but
allows the already-accepted `trend_long` Financials sector-leader sleeve to
use a 50% single-position cap. Aggregate EV improved `+0.1173` and aggregate
PnL improved `+$3,782.63` across the three canonical windows: `late_strong`
EV stayed `4.4313 -> 4.4313`, `mid_weak` EV improved `1.7334 -> 1.8324`,
and `old_thin` EV improved `0.4520 -> 0.4703`. Max drawdown drift stayed
inside Gate 4 (`+0.24 pp` worst window), trade count and survival were
unchanged, and the rule lives in shared `portfolio_engine.py` with a focused
production-parity test.

Previous accepted alpha result: `exp-20260514-018` keeps entries, exits, ranking,
universe, raw commodity risk, heat, slots, and LLM/news logic unchanged, but
allows the already-accepted `trend_long` Commodities sleeve within 3% of its
52-week high to use a 50% single-position cap. Aggregate EV improved `+0.1319`
and aggregate PnL improved `+$5,902.08` across the three canonical windows:
`late_strong` EV `4.3768 -> 4.4313`, `mid_weak` EV `1.6788 -> 1.7334`, and
`old_thin` EV `0.4292 -> 0.4520`. Max drawdown drift stayed inside Gate 4
(`+0.42 pp` worst window), trade count and survival were unchanged, and the
rule lives in shared `portfolio_engine.py` with a focused production-parity
test.

Previous accepted alpha result: `exp-20260513-036` computes signal-day
ticker-minus-SPY open-to-close return in shared `risk_engine.py` and applies a
1.10x cap-aware post-sizing top-up in `portfolio_engine.py` only to already
clean `risk_on` SPY-relative leaders whose ticker also beat SPY on the signal
day. Aggregate EV improved `+0.0246` and aggregate PnL improved `+$2,620.01`
across the three canonical windows, with unchanged trade count and survival.
The rule lives in shared `risk_engine.py` and `portfolio_engine.py`, with
backtester attribution and focused tests, so it is production-visible and not a
replay-only branch.

Previous accepted alpha result: `exp-20260513-030` computes 60-trading-day
momentum in shared `feature_layer.py`, tags already-qualified `trend_long` /
`breakout_long` stock signals whose same-day return is in the top quintile of
the feature-complete non-ETF/non-commodity stock universe, and applies a
1.15x cap-aware post-sizing top-up. Aggregate EV improved `+0.1094` and
aggregate PnL improved `+$4,615.93` across the three canonical windows, with
unchanged trade count and survival. The rule lives in shared `feature_layer.py`,
`risk_engine.py`, and `portfolio_engine.py`, with backtester attribution and
focused parity tests, so it is production-visible and not a replay-only branch.

Previous accepted alpha result: `exp-20260513-007` tags signals whose own
signal-day candle closes above its open and applies a conservative 1.05x
cap-aware post-sizing top-up. Aggregate EV improved `+0.0626` and aggregate
PnL improved `+$2,223.59` across the three canonical windows, with unchanged
trade count and survival. The rule lives in shared `feature_layer.py`,
`risk_engine.py`, and `portfolio_engine.py`, with backtester attribution and
focused parity tests, so it is production-visible and not a replay-only branch.

Latest accepted default-off SEC paper stack: `exp-20260511-112`,
`exp-20260512-001`, `exp-20260512-006`, `exp-20260512-007`, and
`exp-20260512-020` now define the current financial-report T+1 paper baseline.
The accepted sleeve is:
non-platform `earnings_8k` / `periodic_report` rows only, `max_positions=3`,
`t1_excess_return_vs_spy >= 1%`, 10-trading-day hold, `$15,000` base paper
notional, `periodic_report` at `1.25x` that base, and `10-Q periodic_report`
at `2.00x`. The latest accepted three-window sleeve datapoint is aggregate EV
`8.558004`, total PnL `$234,762.79`, sleeve PnL `$48,332.18`, and max
drawdown ceiling `10.0721%`. `exp-20260512-025` then rejected 10-Q-first queue
priority despite positive aggregate EV/PnL because only `old_thin` improved
while `late_strong` regressed, so the next valid SEC step is forward
replacement value or a new earnings-quality field, not another same-sample
queue-order or lifecycle retune.

Latest accepted SEC semantic paper refinement: `exp-20260518-009` keeps the
financial-report T+1 sleeve default-off and live orders disabled, but adds a
production-visible neutral-language underreaction notional scalar. Covered
`neutral_or_mixed_language` candidates with `t1_excess_return_vs_spy <= 2%`
receive an additional `2.00x` paper-notional scalar. Versus the accepted SEC
paper baseline over the same three fixed windows, aggregate EV improved
`+0.7177` and aggregate PnL improved `+$16,836.09`; `late_strong` improved EV
`+0.1009` / PnL `+$1,397.31`, `mid_weak` improved EV `+0.2856` / PnL
`+$4,293.29`, and `old_thin` improved EV `+0.3312` / PnL `+$11,145.49`.
Max drawdown worsened by at most `0.3957` percentage points. The adjusted
sample is thin at 7 closed paper trades and positive PnL is concentrated in
`COIN`, so promotion still requires closed forward replacement-value evidence
before any trade-enabled adapter.

Latest accepted SEC market-context paper refinement: `exp-20260518-014` keeps
the accepted `exp-20260518-009` neutral-underreaction rule fixed, but adds a
production-visible SPY T+1 context override. Accepted neutral-underreaction
rows with `spy_t1_return >= -0.5%` receive an additional `1.50x` default-off
paper-notional scalar. Versus `exp-20260518-009`, aggregate EV improved
`+0.6754` and aggregate PnL improved `+$16,748.28`; all three windows improved
(`late_strong +0.0953` EV / `+$1,397.32`, `mid_weak +0.2790` EV /
`+$4,293.30`, `old_thin +0.3011` EV / `+$11,057.66`). The adjusted sample is
6 closed paper trades across all windows. Positive PnL is still concentrated
in `COIN`, so this remains default-off paper and requires closed forward
replacement-value evidence before any trade-enabled adapter.

Latest rejected SEC semantic paper scout: `exp-20260518-011` tested covered
`negative_language` financial-report rows as a separate paper-notional scalar
on top of the accepted neutral-underreaction stack. The best non-baseline
variant was a `1.50x` top-up: aggregate EV improved `+0.1110` and PnL improved
`+$1,469.90`, but Gate 4 rejected it because `old_thin` regressed
(`-0.0175` EV / `-$516.31`) while the gains came from `late_strong` and
`mid_weak`, especially two `CRDO` rows. Haircuts also failed by hurting
`late_strong` and `mid_weak`. Do not retry nearby negative-language notional
scalars on these frozen windows without a new semantic field or closed forward
replacement-value evidence.

Latest rejected SEC buyback alpha search: `exp-20260514-010` tested a
default-off event overlay for SEC text disclosures with buyback credibility
signals: actual execution updates, accelerated share repurchases, or
cash-supported authorization increases. The frozen sample produced 16
qualified events across six tickers, but failed the three-window gate:
aggregate EV `6.4848 -> 6.2417`, aggregate PnL `$193,903.95 -> $192,280.62`,
and `late_strong` EV regressed `4.3768 -> 4.1264` despite small positive reads
in `mid_weak` and `old_thin`. Do not promote or retry this exact public-archive
buyback credibility ladder without richer fields such as completion status,
remaining authorization, cash-richness, or forward closed evidence.

Latest accepted default-off Space forward stack: the accepted official-catalyst
Space baseline from `exp-20260511-011`, `019`, `021`, `031`, `032`, and `105`
now extends through `exp-20260512-004`, `008`, `013`, `031`, `032`, `037`,
`038`, `041`, `112`, `exp-20260513-012`, `exp-20260513-014`,
`exp-20260513-015`, `exp-20260513-020`, `exp-20260513-028`,
`exp-20260513-032`, `exp-20260513-038`, `exp-20260513-039`, and
`exp-20260513-108`, `exp-20260513-110`, `exp-20260513-113`,
`exp-20260514-002`, `exp-20260514-009`, `exp-20260514-024`,
`exp-20260514-026`, `exp-20260514-028`, `exp-20260514-030`,
`exp-20260514-041`, `exp-20260514-044`, `exp-20260514-047`,
`exp-20260514-051`, `exp-20260514-053`, `exp-20260515-021`, and
`exp-20260515-024`, `exp-20260515-044`, and `exp-20260516-014`.
The supported direction is quality-conditioned risk allocation, peer-relative
breakout leadership, small-cap risk-appetite allocation, and production-visible
catalyst-quality allocation: perfect-TQS official Space signals get a `1.5x`
top-up, near-perfect official Space `trend_long` gets a `1.10x` top-up,
peer-nonleader official Space `breakout_long` gets `0.00x` extra risk, official
Space signals get `1.10x` extra default-off risk when IWM 20d momentum is above
SPY 20d momentum, official Space `trend_long` signals get `1.15x` extra
default-off risk when IWM leads SPY and the ticker's 20d momentum leads the
official Space basket average, `launch_lunar` theme-segment signals get
`1.10x` extra default-off risk, and official Space signals with production registry
`liquidity_tier=ok` get `1.10x` extra default-off risk, and official Space
signals tied to `customer_win` event seeds from official/regulatory/company
primary sources get `1.10x` extra default-off risk, and official Space signals
with source-qualified `customer_win` plus Space peer momentum leadership get
`1.10x` extra default-off risk, and official Space signals with
`government_space_contract` from official/government sources plus Space peer
momentum leadership get `1.05x` extra default-off risk, and official Space signals
whose production registry `event_guard_profile` contains financing/dilution get
`1.075x` extra default-off risk, and official Space signals with production
registry `liquidity_tier=watch` get `1.10x` extra default-off risk, and
official Space signals with at least two official non-attention event seed rows
get `1.075x` extra default-off risk, and official Space signals with exactly
one official non-attention defense-budget `government_space_contract` seed and
no `customer_win` seed get `1.05x` extra default-off risk, and official Space
signals whose event-seed profile has both an attention-only seed and an official
non-attention seed get `1.25x` extra default-off risk, official Space signals
with non-attention source diversity get `1.075x` extra default-off risk, and
source-diverse official Space signals that also lead the Space peer basket get
`1.15x` extra default-off risk, and source-diverse official Space signals also
get `1.05x` extra default-off risk when IWM 20d momentum beats SPY 20d
momentum, and source-diverse official Space signals that also lead the Space
peer basket while IWM beats SPY get a further `1.05x` extra default-off risk,
and source-diverse official Space `trend_long` signals get a further
`1.025x` extra default-off risk, and that source-diverse trend bucket gets a
further `1.025x` extra default-off risk when Space peer momentum state is
`nonleader`, a further `1.025x` when that nonleader bucket has near-perfect
TQS, and a further `1.025x` when the source-diverse trend profile contains
both `customer_win` and `government_space_contract`, a further `1.0125x` when
that dual-catalyst trend profile also has IWM 20d momentum above SPY, and a
further `1.0125x` when that dual-catalyst trend profile also has closed
defense-budget same-theme winner evidence, a further `1.0125x` when that
dual-catalyst trend profile has near-perfect but not perfect TQS, and a
further `1.0125x` when that dual-catalyst trend profile also has a production
registry financing/dilution event-guard profile,
and official non-attention Space tickers whose closed 10d event-state profiles
are both cash-positive and same-theme replacement-positive get a further
`1.05x` extra default-off risk, and the narrower BKSY/RDW/RKLB closed-forward
profile bucket with average 10d same-theme replacement value `>= $500` gets
another `1.05x` extra default-off risk, and that same closed-forward
same-theme-strength bucket gets a further `1.05x` extra default-off risk only
on `trend_long` signals, and the same trend-only closed-forward strength bucket
gets a further conservative `1.025x` extra default-off risk when IWM 20d
momentum leads SPY, and the same trend-only closed-forward strength bucket gets
a further conservative `1.025x` extra default-off risk when the event seed
profile includes `company_release` + `customer_win`.
Official Space `trend_long` signals whose closed 10d event-state profiles are
positive versus cash, SPY, QQQ, UFO, and ARKX get a further `1.025x` extra
default-off risk, the same benchmark-breadth trend bucket gets another
`1.025x` when average 10d same-theme replacement value is `>= $500`, and it
gets another `1.025x` only when Space peer momentum state is `nonleader`, and
another `1.0125x` only when IWM 20d momentum leads SPY.
Defense-budget `government_space_contract` `trend_long` signals whose mature
10d profile also beats the same-theme basket get another `1.05x`.
This remains
metadata/helper only with live Space slots at zero. `exp-20260512-010` rejected
nearby near-perfect breakout TQS gating, `exp-20260512-031` accepted the
IWM-relative state only at `1.10x`, `exp-20260512-032` accepted launch/lunar
theme risk only at `1.10x`, `exp-20260512-035` rejected data/defense theme
scaling, `exp-20260512-037` accepted liquidity-tier anchor risk only at
`1.10x`, and `exp-20260512-038` accepted customer-source risk only at `1.10x`;
`exp-20260512-041` accepted financing/dilution profile risk only at `1.075x`;
`exp-20260512-112` accepted watch-liquidity risk only at `1.10x`;
`exp-20260513-012` accepted multi-event official catalyst-depth risk only at
`1.075x`; `exp-20260513-014` accepted customer-source peer-leader risk only at
`1.10x`; and `exp-20260513-015` accepted government-contract peer-leader risk
only at `1.05x`; and `exp-20260513-020` accepted IWM-plus-peer-leader
`trend_long` risk only at `1.15x`; and `exp-20260513-028` accepted
single-event defense-only risk only at `1.05x`; and `exp-20260513-032`
accepted attention-overlay-with-official-catalyst risk only at `1.25x`. The
`exp-20260513-032` aggregate improved versus the accepted `exp-20260513-028`
stack from EV `17.8725` / PnL `$436,331.45` to EV `18.7513` / PnL
`$444,450.36`; all three windows improved EV and max drawdown ceiling improved
by `3.84 pp`. `exp-20260513-038` then accepted source-diversity risk only at
`1.075x`, and `exp-20260513-039` accepted the source-diversity peer-leader
interaction only at `1.15x`: aggregate EV moved from `22.1922` to `22.9617`,
PnL from `$529,603.76` to `$550,143.02`, with no trade-count or survival
change. `exp-20260513-108` then accepted the source-diversity IWM-leader
interaction only at `1.05x`: aggregate EV moved from `22.9617` to `23.4374`,
PnL from `$550,143.02` to `$564,173.22`, all three windows improved EV, max
drawdown drift stayed inside Gate 4 at `+0.47 pp`, and live Space slots still
zero. `exp-20260513-110` then accepted the source-diversity peer+IWM-leader
interaction only at `1.05x`: aggregate EV moved from `23.4374` to `23.6930`,
PnL from `$564,173.22` to `$570,527.21`, `mid_weak` and `old_thin` improved
while `late_strong` was unchanged, max drawdown drift stayed inside Gate 4 at
`+0.40 pp`, trade count and survival stayed unchanged, and live Space slots
still zero. `exp-20260513-113` then accepted forward replacement-positive
official Space risk only at `1.05x`: aggregate EV moved from `23.6930` to
`24.0468`, PnL from `$570,527.21` to `$584,613.67`, all three windows improved
EV, max drawdown drift stayed inside Gate 4 at `+0.48 pp`, trade count and
survival stayed unchanged, and live Space slots still zero.
`exp-20260514-002` then accepted same-theme replacement-strength risk only at
the `$500` floor / `1.05x` scalar: aggregate EV moved from `24.0468` to
`24.4642`, PnL from `$584,613.67` to `$599,684.05`, all three windows improved
EV, max drawdown drift stayed inside Gate 4 at `+0.49 pp`, trade count and
survival stayed unchanged, and live Space slots still zero.
`exp-20260514-009` then accepted the trend-only same-theme-strength interaction
at `1.05x`: aggregate EV moved from `24.4642` to `24.8880`, PnL from
`$599,684.05` to `$612,354.95`, all three windows improved EV, max drawdown
drift stayed inside Gate 4 at `+0.39 pp`, trade count and survival stayed
unchanged, and live Space slots still zero.
`exp-20260514-024` then accepted the IWM-leader tape interaction for the same
closed-forward same-theme-strength `trend_long` bucket at `1.025x`: current
three-window replay moved aggregate EV from `25.5557` to `25.7839`, PnL from
`$627,135.82` to `$633,988.67`, all three windows improved EV, max drawdown
drift stayed inside Gate 4 at `+0.34 pp`, trade count stayed `68`, minimum
survival stayed `65.33%`, and live Space slots still zero. Stronger nearby
scalars (`1.05x+`) were rejected because max drawdown damage exceeded the
`0.5 pp` guardrail despite higher raw EV.
`exp-20260514-026` then accepted the company-release customer-win interaction
for that same closed-forward same-theme-strength `trend_long` bucket at
`1.025x`: current three-window replay moved aggregate EV from `25.7882` to
`25.9506`, PnL from `$634,670.79` to `$639,550.70`, improved `late_strong` and
`mid_weak`, left `old_thin` unchanged, kept max drawdown drift inside Gate 4 at
`+0.35 pp`, and kept trade count `68` / minimum survival `65.33%`. The target
slice was narrow (`RKLB`, 3 adjusted signals), so do not retry nearby
company-source or RKLB-only Space multipliers on these frozen windows without
new closed forward evidence.
`exp-20260514-028` then accepted the source-diversity trend interaction at
`1.025x`: current three-window replay moved aggregate EV from `25.9506` to
`26.3533`, PnL from `$639,550.70` to `$649,167.44`, improved `late_strong` and
`mid_weak`, left `old_thin` unchanged, kept max drawdown drift inside Gate 4 at
`+0.34 pp`, and kept trade count `68` / minimum survival `65.33%`. The target
slice was broader than the RKLB-only company-source branch (`ASTS`, `LUNR`,
`RKLB`, 6 adjusted signals), but still source-diversity/trend specific, so do
not retry nearby source-diversity trend scalars on these frozen windows without
new closed forward evidence or a materially different catalyst-quality field.

`exp-20260514-051` accepted the defense-budget delayed benchmark interaction
at `1.025x`: current three-window replay moved aggregate EV from `27.3987` to
`27.5836`, PnL from `$679,878.08` to `$685,729.18`, improved `late_strong` and
`mid_weak`, left `old_thin` unchanged, kept max drawdown drift inside Gate 4 at
`+0.39 pp`, and kept trade count `68` / minimum survival `65.33%`.
`exp-20260514-053` then accepted the benchmark-breadth IWM-leader trend
interaction at `1.0125x`: aggregate EV moved from `27.5836` to `27.6442`, PnL
from `$685,729.18` to `$688,767.01`, improved `late_strong` and `mid_weak`,
left `old_thin` unchanged, kept max drawdown drift inside Gate 4 at `+0.20 pp`,
and kept trade count `68` / minimum survival `65.33%`. The adjusted slice was
narrow (`LUNR`, `RKLB`, 4 signals), so do not retry nearby benchmark-breadth
IWM-leader scalars on these frozen windows without new closed forward evidence
or a materially different production-visible catalyst-quality field.
`exp-20260515-021` then accepted the defense-budget same-theme winner trend
interaction at `1.05x`: current three-window replay moved aggregate EV from
`24.6984` to `24.9753`, PnL from `$652,524.40` to `$665,315.40`, improved
`late_strong` and `mid_weak`, left `old_thin` unchanged, kept aggregate max
drawdown ceiling drift inside Gate 4 at `+0.34 pp`, and kept trade count `68`
/ minimum survival `64.00%`. The adjusted slice was narrow (`LUNR`, `RKLB`, 4
signals), so do not retry nearby defense-budget same-theme winner scalars on
these frozen windows without new closed forward evidence or a materially
different production-visible catalyst-quality field.
`exp-20260515-024` then accepted a source-diversity peer-nonleader trend
interaction at `1.025x`: current three-window replay moved aggregate EV from
`24.9753` to `25.1824`, PnL from `$665,315.40` to `$672,412.69`, improved
`late_strong` and `mid_weak`, left `old_thin` unchanged, kept aggregate max
drawdown ceiling drift inside Gate 4 at `+0.42 pp`, and kept trade count `68`
/ minimum survival `64.00%`. The adjusted slice was `ASTS` and `RKLB`, 4
signals; stronger nearby values had higher raw EV but failed the drawdown
guardrail, so do not retry adjacent source-diversity peer-nonleader trend
scalars without new closed forward evidence.

Latest rejected core allocation alpha search: `exp-20260515-041` tested an
unreduced high-R:R refinement on top of the accepted core stack. The single
changed variable was `exec_lag_rr_unreduced_leadership_risk_multiplier`:
already-qualified `trend_long` / `breakout_long` non-ETF/non-commodity stock
signals had to be in the same-day top quartile of `exec_lag_adj_net_rr` and
also have no existing shared sizing haircut (`*_risk_multiplier_applied < 1`)
before receiving a cap-aware post-sizing top-up. The best scalar was the
smallest tested value, `1.0125x`, but Gate 4 rejected it: aggregate EV moved
`7.7345 -> 7.7102`, PnL moved `$229,636.73 -> $227,890.27`, only `mid_weak`
improved (`+0.0011` EV / `+$44.71`), and `old_thin` regressed by `-0.0254` EV
/ `-$1,791.17`. No shared production policy was changed. Do not retry simple
`exec_lag_adj_net_rr` top-quartile allocation or no-prior-haircut R:R scalars
on the frozen windows without a genuinely new production-visible drawdown or
catalyst-quality discriminator.

Prior rejected core allocation alpha search: `exp-20260515-032` tested a
confirmed-quality sector-thrust interaction on top of the accepted core stack.
The single changed variable was
`confirmed_sector_thrust_risk_multiplier`: already-qualified
`trend_long` / `breakout_long` non-ETF/non-commodity stock signals had to
satisfy both `core_confirmed_quality_state=true` and same-day top-quartile
ticker-minus-sector-proxy thrust before receiving a cap-aware post-sizing
top-up. The best scalar was `1.025x`, with aggregate EV only `+0.0019` and PnL
`+$309.65`; Gate 4 rejected it because only `mid_weak` improved while
`old_thin` regressed by `-0.0010` EV / `-$77.24`. Do not retry this exact
confirmed sector-thrust interaction on the frozen windows without forward
attribution or a materially different production-visible state.

Latest rejected Space alpha search: `exp-20260515-035` tested the remaining
non-displacing mature-satcom admission design on top of `exp-20260515-024`.
The single changed variable was
`space_fast_5d_10d_same_theme_satcom_trend_fallback_pool_membership`: VSAT
still had to pass the all-positive 5d forward gate and positive 10d same-theme
replacement-value gate, but it was admitted only as a `trend_long` fallback
when no base official Space signal existed on the same signal date. The
fallback rule filtered `2` non-trend VSAT signals and `0` official-same-day
trend signals, so the three-window result remained effectively the stricter
VSAT-only admission result: aggregate EV improved `+5.0217` and PnL improved
`$105,371.20`, but Gate 4 rejected it because `old_thin` regressed by
`-0.0306` EV and `-$1,229.23`, while late-window drawdown worsened by
`+2.98 pp`. Do not retry VSAT-only, IRDM/VSAT, or mature-satcom fallback
candidate admission on these frozen windows without new closed forward rows or
a genuinely new production-visible catalyst-quality field.

Prior rejected Space alpha search: `exp-20260513-019` tested whether the
accepted customer-source edge should also top up peer-nonleader official Space
signals. Aggregate EV improved `+0.1320`, but the result did not clear the
Space three-window gate, so customer-source allocation should stay tied to
stronger peer-quality buckets. Do not promote customer-source peer-nonleader
scaling on the frozen snapshots.

Latest rejected core entry alpha search: `exp-20260512-024` tested a
deterministic OHLCV `pullback_reclaim_long` entry shape for leadership
pullbacks above the 200MA, 5-15% below 52-week highs, with positive 10d/20d
momentum and no 20d breakout/breakdown. It failed all three canonical windows:
aggregate EV `6.2882 -> 3.9873`, aggregate PnL `-$48,599.83`, and max drawdown
ceiling worsened `+2.07 pp`. Do not promote or retune nearby pullback/reclaim
entry thresholds on the frozen windows; this candidate-pool direction adds too
many lower-quality trades under the current exit/risk stack.

Latest rejected core exit alpha search: `exp-20260513-112` tested converting
the observed early SPY-relative underperformance loss family into a next-open
full exit after the third holding-session close. It executed only three exits,
all in `old_thin`, and failed Gate 4: aggregate EV `6.4848 -> 6.4440`,
aggregate PnL `$193,903.95 -> $192,217.84`, with no improved window and
`old_thin` EV `0.4292 -> 0.3884`. Do not retune nearby day-count or
relative-weakness exit thresholds without forward lifecycle attribution.

Recent slot alpha-search scout: `exp-20260510-018` rejected effective core slot
accounting from observed-only slot-missed replacement value. All blocked rows
were positive in aggregate (`25` rows, `+$8,330.63`), but failed the gate because
win rate was only `40%` and only `1/3` windows was positive. Pure one-extra-slot
rows were positive but too concentrated in PLTR; breakout rows need
`available_slots > 1` because the accepted scarce-slot breakout deferral is
still active.

Latest alpha-search discovery: `exp-20260510-023` found that the newly completed
non-OHLCV SEC snapshots can support a three-window T+1 event-drift shadow
surface. The broad positive T+1 excess-drift SEC label was only paper-watch
quality (`363` valid 10d rows, 10d avg return `+1.22%`, win rate `51.79%`,
positive 10d-average windows `2/3`). `exp-20260510-024` then isolated the useful
semantic slice: `earnings_8k` plus `periodic_report` events with positive T+1
excess drift produced `184` valid 10d rows, 10d avg return `+2.23%`, win rate
`53.80%`, and positive 10d-average return in `3/3` windows. This is still
observed-only and must not become live trading without forward paper outcomes.

Latest production-visible alpha surface: `exp-20260510-025` moved that exact
SEC financial-report + positive T+1 excess label into a default-off paper queue
and sleeve. It is production-visible, but not trade-enabled: no orders, no core
ranking changes, no sizing changes, and no slot use. Focused tests passed
(`22 passed`), and the canonical three-window core metrics stayed unchanged:
`late_strong` EV `4.2340`, `mid_weak` EV `1.6689`, and `old_thin` EV `0.3853`.

Latest queue-quality refinement: `exp-20260510-027` keeps the SEC
financial-report T+1 queue default-off but freezes its forward observation pool
to non-platform candidates. On the same three fixed windows, excluding
`platform_pool` improved the 10d average from `0.022332` to `0.027636` across
`157` valid 10d non-platform rows, while the excluded platform slice averaged
`-0.008507`. This changes only the shared observe-only queue policy and still
requires closed forward paper outcomes before any trade-enabled promotion.

Latest SEC blocking audit: `exp-20260511-001` confirms the older filing-shock
branch is still blocked by missing directional event fields, not by PIT
timestamp plumbing. Same-accession repair checks found only sparse directional
rows and still no usable B/C candidate cohort, so do not spend another loop on
filing-recency retunes, Companyfacts weighting, or adjacent filing-shock
threshold work until PIT-safe EPS/revenue surprise or guidance fields exist on
actual candidate dates.

Latest candidate-pool alpha search: `exp-20260511-002` tested the
`SPACE_CATALYST_SHADOW` operating equities in deterministic snapshot copies.
The static replay was raw-positive in all three canonical windows: aggregate EV
`+2.3036`, aggregate PnL `+$64,577.73`, and added space trades contributed
`+$79,995.67` across `25` trades. It is still rejected for production alpha
because the pool is selected with 2026-05-10 knowledge and old-window max
drawdown worsened from `8.15%` to `11.71%`. Keep the space theme observe-only;
the next valid evidence is forward shadow replacement value, not live slot
enablement or core universe promotion.

Latest forward-observation alpha surface: `exp-20260511-003` accepted the
space catalyst theme as a production-visible, default-off shadow surface. The
daily run now exposes `SPACE_CATALYST_SHADOW` records, event fields, and
promotion gates in the universe state, report, and `quant_signals` output, but
keeps live slots at `0` and changes no orders, ranking, sizing, filters, or core
candidate pool. The canonical three-window core metrics stayed unchanged:
`late_strong` EV `4.2340`, `mid_weak` EV `1.6689`, and `old_thin` EV `0.3853`.
The next evidence is closed forward direct PnL and replacement value, not a
static space-pool promotion.

Latest space catalyst attribution step: `exp-20260511-008` started an
event-state shadow ledger for the space theme instead of re-mining a static
space basket. It seeded six official/attention events across
`fundamental_contract_regulatory`, `defense_budget_theme`, and `attention_only`
buckets, then tracked cash-relative, core/benchmark-relative, and same-theme
replacement value. Only the `LUNR` NASA CLPS event is mature so far: on a
`$10k` notional it was `-6.42%` after 1 trading day, `-1.51%` after 5 trading
days, and `+6.91%` after 10 trading days, with positive 10d same-theme value
and positive 10d `UFO`-relative value. The gate remains failed because only
`1/10` required closed decisions is mature. Keep the sleeve observe-only until
official catalyst buckets, not attention-only rows, prove positive forward
replacement value.

Current priority: do not retune local add-on trigger, cap, heat, reserve,
strategy-cohort variants, ETF overlay parameters, nearby RS20 or RS60 risk
scalars, single-ticker sector taxonomy, global `MAX_POSITIONS`, or scarce-slot
breakout thresholds on the same frozen samples. Future slot work needs a shared
exposure/risk-based effective-slot accounting design with full portfolio replay
and production visibility, not another global slot-count sweep. Do not keep
retuning the SEC financial-report T+1 label or adjacent cohort slices on the
same frozen sample; after the non-platform queue freeze, the next evidence for
that branch is closed forward paper replacement value. For space catalyst, do
not mine adjacent tickers or enable live slots without closed forward
replacement-value evidence.

Latest Space risk-allocation alpha search: `exp-20260511-009` swept a sleeve-level risk scalar on the rejected static Space catalyst pool. The highest-EV variant was `1.0x`: aggregate EV delta `+2.3036`, aggregate PnL delta `$64,577.73`, max drawdown damage `3.56%`, and Gate passed `False`. The closest risk-controlled variant was `0.75x`, but it still regressed `late_strong` EV. Conclusion: simple static-pool risk discount is not enough; Space should remain official-catalyst forward paper, not broad static universe enablement or attention-headline ranking.

Latest low-deployment ETF alpha search: `exp-20260512-777` tested whether the
accepted default-off low-deployment ETF overlay should change its candidate
pool from the current `QQQ` / `SPY` / `IWM` / `GLD` / `SLV` set. No tested
variant beat v1 across the canonical three-window gate. `equity_only` improved
2/3 windows but regressed one; `add_energy` and `cross_asset_plus` had positive
aggregate EV/PnL but were single-window/unstable with drawdown damage. Keep the
v1 paper pool unchanged and do not retry adjacent ETF pool variants on the same
frozen samples without forward replacement-value evidence.

### 2026-05-11 alpha search note: TQS-conditioned sector follower risk

`exp-20260511-010` tested a relative-TQS discriminator on the rejected same-day
sector follower haircut. It improved aggregate EV by
`+0.1144` and PnL by
`$+1,481.64`, but touched only the late window, so no
shared production/backtest sizing policy was promoted.

Latest accepted Space forward hypothesis: `exp-20260511-011` locked the official-catalyst Space subpool from `exp-20260511-010` and swept only the risk budget. The best passing scalar was `0.75x`: aggregate EV delta `+1.5598`, aggregate PnL delta `$32,256.34`, and max drawdown damage `1.97%`. This is production-visible but default-off: live Space slots remain zero until forward replacement-value evidence matures.

Latest Space sleeve refinement: `exp-20260511-012` tested whether the accepted official-catalyst Space 0.75x forward hypothesis should be restricted to `trend_long` entries. The result was `rejected_trend_only_refinement`: aggregate EV delta versus exp-20260511-011 was `-0.3072` and aggregate PnL delta was `$-1,909.20`. Keep the official-catalyst 0.75x hypothesis unchanged unless forward strategy-family replacement value says otherwise.

Latest same-sector cluster risk scout: `exp-20260511-013` broadened the relative-TQS same-day same-sector follower haircut from the prior risk-on-only scout to all core A/B entries. The result was `rejected_replay_only`: aggregate EV moved `+0.0740`, but aggregate PnL fell `$-529.66` and `old_thin` regressed by EV `-0.0404` / PnL `$-2,011.30`. Do not promote or repeat all-core same-sector TQS follower haircuts on the frozen windows without forward cluster-quality evidence or a different orthogonal discriminator.

Latest Space breakout refinement: `exp-20260511-015` tested a Space official-catalyst `breakout_long` entry-to-stop risk-distance cap on top of the accepted 0.75x default-off hypothesis. The result was `rejected_breakout_risk_distance_refinement`: best cap `10%`, aggregate EV delta versus exp-20260511-011 `+0.0000`, aggregate PnL delta `$+0.00`. Keep Space live slots at zero; any accepted refinement remains default-off until forward replacement-value evidence matures.

## Latest Space Add-On Refinement

Latest Space add-on refinement: `exp-20260511-014` tested disabling follow-through add-ons for the accepted 0.75x official-catalyst Space sleeve. The refinement was rejected versus `exp-20260511-011`; keep the accepted sleeve unchanged and do not disable all Space add-ons without a more selective ex-ante lifecycle signal.

Latest Space RS20 refinement: `exp-20260511-016` tested whether the accepted official-catalyst Space 0.75x forward hypothesis should require the existing `rs20_entry_state_leader` flag. The result was `rejected_rs20_leader_refinement`: aggregate EV delta versus exp-20260511-011 `+0.0000`, aggregate PnL delta `$+0.00`. Keep the official-catalyst 0.75x hypothesis unchanged unless forward RS20-bucket replacement value says otherwise.

Latest core broad-rotation alpha search: `exp-20260511-017` tested `breakout_long` risk allocation when `IWM` 20d momentum beat `SPY` by more than 2pp. The best variant was `1.50x`, with aggregate EV delta `+0.1269` and PnL delta `$+1,740.56`, but only `late_strong` improved, `mid_weak` was unchanged, and `old_thin` regressed slightly. No shared policy was promoted; do not retry nearby broad-rotation breakout multipliers on this same threshold without event/news context, candidate replacement value, or a richer breadth discriminator.

Latest Space data-vendor refinement: `exp-20260511-018` tested whether the accepted official-catalyst Space 0.75x forward hypothesis should allow PL/BKSY only as `trend_long` entries. The result was `rejected_data_vendor_trend_gate`: aggregate EV delta versus exp-20260511-011 `-0.4195`, aggregate PnL delta `$-1,137.22`. Do not generalize this to all Space breakout entries; keep it scoped to the data-vendor subsegment.

Latest Space data-vendor breakout risk refinement: `exp-20260511-019` swept an extra risk scalar for PL/BKSY `breakout_long` entries inside the accepted official-catalyst Space 0.75x forward hypothesis. The best scalar was `0.25` with decision `accepted_default_off_data_vendor_breakout_risk_haircut`: aggregate EV delta versus exp-20260511-011 `+0.2741`, aggregate PnL delta `$+3,774.55`. This is now shared default-off Space sleeve metadata/helper only; live Space slots remain zero and no core order/ranking/sizing path changed.

Latest Space launch/connectivity trend risk refinement: `exp-20260511-021` tested an extra bounded scalar for RKLB/ASTS `trend_long` entries on top of the accepted official-catalyst Space 0.75x hypothesis and PL/BKSY breakout 0.25x haircut. The best scalar was `1.25` with decision `accepted_default_off_launch_connectivity_trend_risk_topup`: aggregate EV delta versus exp019 `+0.3686`, aggregate PnL delta `$+6,661.77`.

Latest Space non-data-vendor breakout risk refinement: `exp-20260511-022` swept an extra scalar for RKLB/ASTS/RDW/LUNR-style `breakout_long` entries while keeping the accepted PL/BKSY breakout haircut and RKLB/ASTS trend top-up fixed. The best scalar was `0.25` with decision `rejected_non_data_vendor_breakout_risk_haircut`: aggregate EV delta versus the accepted Space + PL/BKSY haircut + RKLB/ASTS trend before state `+0.2184`, aggregate PnL delta `$-44.75`.

Latest Space remaining trend risk refinement: `exp-20260511-023` tested extending the accepted trend top-up beyond RKLB/ASTS to remaining official-catalyst `trend_long` entries. The best scalar was `1.5` with decision `rejected_remaining_trend_risk_topup`: aggregate EV delta versus exp021 `+0.2263`, aggregate PnL delta `$+10,047.75`. The result was positive but underpowered because it improved fewer than two canonical windows.



## exp-20260511-026 Space satcom breadth low-risk

- timestamp: 2026-05-11T14:18:24+00:00
- lane: alpha_search
- decision: rejected_satcom_breadth_low_risk_extension
- changed_variable: space_satcom_breadth_risk_scalar
- best_satcom_breadth_risk_scalar: 0.75
- expected_value_score_delta_vs_before: 0.9043
- before_aggregate: {'expected_value_score_sum': 8.4907, 'total_pnl_sum': 227137.08, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- after_aggregate: {'expected_value_score_sum': 9.395, 'total_pnl_sum': 242349.79, 'trade_count_sum': 83, 'min_survival_rate': 0.8462, 'max_drawdown_pct_max': 0.1013}
- interpretation: Space alpha should stay focused on the official-catalyst operating sleeve and the already accepted PL/BKSY and RKLB/ASTS risk refinements. Mature-satcom breadth is not strong enough to add without a future PIT event trigger.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260511-026\space_satcom_breadth_low_risk.json`

## exp-20260511-027 Post-news item-composition gate

- timestamp: 2026-05-11T15:06:44+00:00
- lane: alpha_search
- decision: rejected_item_composition_gate
- changed_variable: post_news_8k_item_composition_gate
- best_variant: exclude_auxiliary_items
- result: versus raw post-news, aggregate EV improved `+0.2028` but only `late_strong` improved; `mid_weak` and `old_thin` regressed versus the raw post-news surface.
- core comparison: the best gated stack was still positive versus accepted core in all three windows (`aggregate EV +0.4491`, PnL `+$8,407.30`), but missed the materiality gate and worsened old-window drawdown.
- interpretation: post-news continuation remains a forward candidate-pool lead, but 8-K auxiliary-item exclusion is not a stable discriminator on the frozen sample.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'live_slots_changed': False}
- artifact: `data\experiments\exp-20260511-027\post_news_item_composition.json`


## exp-20260511-028 Space launch/connectivity breakout risk

- timestamp: 2026-05-11T15:17:38+00:00
- lane: alpha_search
- decision: rejected_launch_connectivity_breakout_risk_haircut
- changed_variable: space_launch_connectivity_breakout_risk_scalar
- best_launch_connectivity_breakout_scalar: 0.25
- expected_value_score_delta_vs_before: 0.2184
- before_aggregate: {'expected_value_score_sum': 8.4907, 'total_pnl_sum': 227137.08, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- after_aggregate: {'expected_value_score_sum': 8.7091, 'total_pnl_sum': 227092.33, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1016}
- interpretation: The RKLB/ASTS trend top-up remains the supported launch/connectivity refinement. Do not add a separate breakout haircut for RKLB/ASTS on this frozen replay sample.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260511-028\space_launch_connectivity_breakout_risk.json`
## exp-20260511-029 Post-news surprise-direction gate

- timestamp: 2026-05-11T16:10:40+00:00
- lane: alpha_search
- decision: rejected_surprise_direction_gate
- changed_variable: post_news_surprise_direction_gate
- best_variant: unknown_only
- expected_value_score_delta_vs_raw: 0.0012
- gate4_passed: False
- interpretation: The PIT surprise_direction semantic label did not improve the locked post-news continuation surface enough to justify promotion. Explicit positive/negative labels were sparse and did not rescue the raw PEAD-like sleeve from the materiality problem.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'alters_signal_generation': False, 'alters_candidate_ranking': False, 'alters_sizing': False, 'alters_orders': False, 'live_slots_changed': False}
- artifact: `data\experiments\exp-20260511-029\post_news_surprise_direction.json`


## exp-20260511-030 Space theme momentum risk

- timestamp: 2026-05-11T16:26:26+00:00
- lane: alpha_search
- decision: rejected_theme_weak_space_risk_scalar
- changed_variable: space_theme_weak_risk_scalar
- best_theme_weak_risk_scalar: 0.0
- expected_value_score_delta_vs_before: 0.0
- before_aggregate: {'expected_value_score_sum': 8.4907, 'total_pnl_sum': 227137.08, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- after_aggregate: {'expected_value_score_sum': 8.4907, 'total_pnl_sum': 227137.08, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- interpretation: Do not add a theme ETF momentum risk gate to the Space sleeve. The accepted Space stack should stay focused on catalyst bucket and ticker/strategy lifecycle scalars, not theme ETF timing.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260511-030\space_theme_momentum_risk.json`


## exp-20260511-031 Space data-vendor breakout zero sweep

- timestamp: 2026-05-11T16:52:12+00:00
- lane: alpha_search
- decision: accepted_default_off_data_vendor_breakout_0_1_scalar
- changed_variable: space_data_vendor_breakout_risk_scalar
- best_data_vendor_breakout_risk_scalar: 0.1
- expected_value_score_delta_vs_before: 0.0572
- before_aggregate: {'expected_value_score_sum': 8.4907, 'total_pnl_sum': 227137.08, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- after_aggregate: {'expected_value_score_sum': 8.5479, 'total_pnl_sum': 227864.06, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- interpretation: A lower PL/BKSY breakout scalar improved the accepted Space stack under the three-window gate. Promote only as default-off forward metadata because Space live slots remain zero.
- production_impact: {'shared_policy_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': True, 'daily_report_metadata_changed': True, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260511-031\space_data_vendor_breakout_zero_sweep.json`

## exp-20260511-032 Space event ledger adapter

- timestamp: 2026-05-11
- lane: measurement_repair
- decision: accepted_observe_only_daily_event_ledger_adapter
- changed_variable: space_event_ledger_daily_adapter
- result: the daily path now builds and persists a `SPACE_CATALYST_EVENT_STATE_SHADOW_LEDGER`, includes it in `trend_signals` / `quant_signals`, and renders it in the report without enabling Space live slots.
- validation: focused tests `20 passed`; snapshot probe on the augmented late window at `2026-04-21` produced `2` active seed events, `2` event rows, `1` closed 10d decision, and a blocked promotion gate.
- interpretation: Space should now collect forward event-state evidence daily. Do not promote `SPACE_CATALYST_SPECIALIST` until official catalyst buckets produce at least `10` mature closed decisions with positive direct and replacement value.
- production_impact: {'shared_policy_changed': False, 'shared_observation_helper_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': True, 'replay_only': False, 'parity_test_added': True, 'live_slots_changed': False, 'live_slots': 0}


## exp-20260511-032 Space trend target extension

- timestamp: 2026-05-11T17:14:31+00:00
- lane: alpha_search
- decision: accepted_default_off_space_trend_target_extension
- changed_variable: space_official_trend_target_atr_mult
- best_space_trend_target_atr_mult: 5.0
- expected_value_score_delta_vs_before: 0.4081
- before_aggregate: {'expected_value_score_sum': 8.5479, 'total_pnl_sum': 227864.06, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- after_aggregate: {'expected_value_score_sum': 8.956, 'total_pnl_sum': 237013.66, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- interpretation: Wider targets for official-catalyst Space trend entries improved the accepted default-off Space stack. Promotion must remain default-off metadata/helper only because live Space slots are zero.
- production_impact: {'shared_policy_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': True, 'daily_report_metadata_changed': True, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260511-032\space_trend_target_extension.json`


## exp-20260511-037 Space breakout target extension

- timestamp: 2026-05-11T18:07:37+00:00
- lane: alpha_search
- decision: rejected_space_breakout_target_extension
- changed_variable: space_official_breakout_target_atr_mult
- best_space_breakout_target_atr_mult: 6.0
- expected_value_score_delta_vs_before: 0.0179
- before_aggregate: {'expected_value_score_sum': 8.956, 'total_pnl_sum': 237013.66, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- after_aggregate: {'expected_value_score_sum': 8.9739, 'total_pnl_sum': 237817.62, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- interpretation: Space breakout convexity is not the next supported same-sample refinement. Keep the accepted trend target extension, PL/BKSY breakout haircut, and RKLB/ASTS trend top-up unchanged.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'daily_report_metadata_changed': False, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260511-037\space_breakout_target_extension.json`

## exp-20260511-038 Space trend target bucket scope

- timestamp: 2026-05-11T18:15:03+00:00
- lane: alpha_search
- decision: rejected_space_trend_target_scope
- changed_variable: space_official_trend_target_bucket_scope
- best_variant: exclude_data_vendor_trend
- expected_value_score_delta_vs_before: -0.0270
- before_aggregate: {'expected_value_score_sum': 8.9564, 'total_pnl_sum': 237030.87, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- after_aggregate: {'expected_value_score_sum': 8.9294, 'total_pnl_sum': 235932.28, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- interpretation: Keep the accepted official-catalyst Space 5 ATR trend target broad across the full official bucket. Narrowing it away from PL/BKSY data-vendor trend or toward launch/connectivity did not add alpha on the frozen three-window sample.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'daily_report_metadata_changed': False, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260511-038\space_trend_target_bucket_scope.json`

## exp-20260511-105 Space launch/connectivity trend target

- timestamp: 2026-05-11T19:12:47+00:00
- lane: alpha_search
- decision: accepted_default_off_launch_connectivity_trend_target_extension
- changed_variable: space_launch_connectivity_trend_target_atr_mult
- best_launch_connectivity_trend_target_atr_mult: 7.0
- expected_value_score_delta_vs_before: 0.9838
- before_aggregate: {'expected_value_score_sum': 8.9564, 'total_pnl_sum': 237030.87, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- after_aggregate: {'expected_value_score_sum': 9.9402, 'total_pnl_sum': 253985.68, 'trade_count_sum': 73, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- interpretation: Keep the accepted 5 ATR target for all official Space trend signals, but use 7 ATR for RKLB/ASTS launch/connectivity trend_long signals. This is default-off Space metadata/helper only; live Space slots remain zero.
- production_impact: {'shared_policy_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': True, 'replay_only': True, 'parity_test_added': True, 'daily_report_metadata_changed': True, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260511-105\space_launch_connectivity_trend_target.json`

## exp-20260511-106 Space lunar/manufacturing trend target

- timestamp: 2026-05-11T20:46:58+00:00
- lane: alpha_search
- decision: rejected_lunar_manufacturing_trend_target_extension
- changed_variable: space_lunar_manufacturing_trend_target_atr_mult
- best_variant: lunar_manufacturing_7_0
- expected_value_score_delta_vs_before: -0.0788
- pnl_delta_vs_before: $-4,380.35
- interpretation: RKLB/ASTS launch-connectivity trend convexity does not transfer to LUNR/RDW lunar/manufacturing trend signals. Keep non-launch official Space trend targets at the accepted 5 ATR path.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260511-106\space_lunar_manufacturing_trend_target.json`

## exp-20260511-110 Space breakout stop width

- timestamp: 2026-05-11T21:22:33+00:00
- lane: alpha_search
- decision: rejected_space_breakout_stop_width
- changed_variable: space_official_breakout_stop_atr_mult
- best_variant: breakout_stop_2_0
- expected_value_score_delta_vs_before: -0.2752
- pnl_delta_vs_before: $+964.57
- interpretation: Widening official Space breakout stops helped late_strong but damaged mid_weak and old_thin EV. Space breakout fragility is not fixed by simply giving breakouts more stop room; keep the accepted exp-105 stack unchanged.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260511-110\space_breakout_stop_width.json`

## exp-20260511-111 Space data-vendor trend target

- timestamp: 2026-05-11T22:18:26+00:00
- lane: alpha_search
- decision: rejected_data_vendor_trend_target_extension
- changed_variable: space_data_vendor_trend_target_atr_mult
- best_variant: data_vendor_trend_target_6_0
- expected_value_score_delta_vs_before: -0.3228
- pnl_delta_vs_before: $-13,201.24
- interpretation: PL/BKSY data-vendor trend target widening damaged old_thin and did nothing in late_strong or mid_weak. Keep PL/BKSY trend targets at the accepted broad 5 ATR Space trend setting; do not retry nearby data-vendor trend target widths on the frozen snapshots.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260511-111\space_data_vendor_trend_target.json`

## exp-20260511-112 SEC financial-report T+1 paper sleeve capacity

- timestamp: 2026-05-11T22:24:41+00:00
- lane: alpha_search
- decision: accept_default_off_paper_capacity_candidate
- changed_variable: sec_financial_report_event_sleeve_max_positions
- baseline_max_positions: 1
- promoted_default_max_positions: 3
- expected_value_score_delta: +0.174785
- sleeve_pnl_delta: +$6,351.95
- total_pnl_delta: +$6,766.07
- before_aggregate: {'expected_value_score_sum': 6.414058, 'total_pnl_sum': 187675.61, 'trade_count_sum': 88, 'min_survival_rate': 0.792453, 'max_drawdown_pct_max': 0.092599, 'sleeve_total_pnl_sum': 2204.51, 'sleeve_closed_trade_count_sum': 26}
- after_aggregate: {'expected_value_score_sum': 6.588843, 'total_pnl_sum': 194441.68, 'trade_count_sum': 124, 'min_survival_rate': 0.792453, 'max_drawdown_pct_max': 0.118812, 'sleeve_total_pnl_sum': 8556.46, 'sleeve_closed_trade_count_sum': 62}
- interpretation: The SEC financial-report positive T+1 queue supports a larger default-off paper observation capacity, but not full max=5/10 capacity because old_thin drawdown rises too much. Promote max=3 only for paper observation; keep live orders disabled.
- production_impact: {'shared_policy_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': True, 'replay_only': False, 'parity_test_added': True, 'default_off_paper_only': True, 'alters_orders': False, 'alters_signal_generation': False, 'alters_sizing': False}
- artifact: `data\experiments\exp-20260511-112\exp_20260511_112_sec_financial_report_t1_sleeve_capacity.json`

## exp-20260512-001 SEC financial-report T+1 excess floor

- timestamp: 2026-05-12T00:08:20+00:00
- lane: alpha_search
- decision: accepted_default_off_t1_excess_floor
- changed_variable: sec_financial_report_t1_excess_return_floor
- promoted_floor: 0.01 ticker-vs-SPY T+1 excess return
- expected_value_score_delta: +0.820356
- total_pnl_delta: +$15,448.11
- sleeve_pnl_delta: +$15,448.11
- before_aggregate: {'expected_value_score_sum': 6.588843, 'total_pnl_sum': 194441.68, 'trade_count_sum': 124, 'min_survival_rate': 0.792453, 'max_drawdown_pct_max': 0.118812, 'sleeve_total_pnl_sum': 8556.46, 'sleeve_closed_trade_count_sum': 62}
- after_aggregate: {'expected_value_score_sum': 7.409199, 'total_pnl_sum': 209889.79, 'trade_count_sum': 114, 'min_survival_rate': 0.792453, 'max_drawdown_pct_max': 0.090703, 'sleeve_total_pnl_sum': 24004.57, 'sleeve_closed_trade_count_sum': 52}
- interpretation: The SEC financial-report positive T+1 queue should require at least +1% ticker-vs-SPY T+1 excess before entering the default-off paper sleeve. This improved EV and PnL in all three canonical windows while reducing max drawdown and keeping 52 closed sleeve trades.
- production_impact: {'shared_policy_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': True, 'replay_only': False, 'parity_test_added': True, 'default_off_paper_only': True, 'alters_orders': False, 'alters_signal_generation': True, 'alters_sizing': False}
- artifact: `data\experiments\exp-20260512-001\exp_20260512_001_sec_financial_report_t1_excess_floor.json`

## exp-20260512-004 Space perfect-TQS risk

- timestamp: 2026-05-12T01:31:38+00:00
- lane: alpha_search
- decision: accepted_default_off_space_perfect_tqs_risk
- changed_variable: space_perfect_trade_quality_score_risk_scalar
- best_space_perfect_tqs_risk_scalar: 1.5
- expected_value_score_delta_vs_before: +1.2496
- total_pnl_delta_vs_before: +$26,296.52
- before_aggregate: {'expected_value_score_sum': 10.2590, 'total_pnl_sum': 261960.17, 'trade_count_sum': 73, 'min_survival_rate': 0.8070, 'max_drawdown_pct_max': 0.1056}
- after_aggregate: {'expected_value_score_sum': 11.5086, 'total_pnl_sum': 288256.69, 'trade_count_sum': 72, 'min_survival_rate': 0.7746, 'max_drawdown_pct_max': 0.1056}
- interpretation: Space optimization should now prioritize signal-quality-conditioned risk allocation. The accepted perfect-TQS 1.5x top-up remains default-off metadata/helper only; live Space slots remain zero.
- production_impact: {'shared_policy_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': True, 'replay_only': True, 'parity_test_added': True, 'daily_report_metadata_changed': True, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260512-004\space_perfect_tqs_risk.json`

## exp-20260512-002 SEC financial-report hold days

- timestamp: 2026-05-12T01:06:19+00:00
- lane: alpha_search
- decision: rejected_hold_days
- changed_variable: sec_financial_report_event_sleeve_hold_days
- best_hold_days: 12
- expected_value_score_delta: -0.126504
- total_pnl_delta: -$2,705.41
- sleeve_pnl_delta: -$2,481.89
- before_aggregate: {'expected_value_score_sum': 7.409199, 'total_pnl_sum': 209889.79, 'trade_count_sum': 114, 'min_survival_rate': 0.792453, 'max_drawdown_pct_max': 0.090703, 'sleeve_total_pnl_sum': 24004.57, 'sleeve_closed_trade_count_sum': 52}
- after_aggregate: {'expected_value_score_sum': 7.282695, 'total_pnl_sum': 207184.38, 'trade_count_sum': 106, 'min_survival_rate': 0.792453, 'max_drawdown_pct_max': 0.089763, 'sleeve_total_pnl_sum': 21522.68, 'sleeve_closed_trade_count_sum': 44}
- interpretation: Keep the accepted 10-trading-day SEC financial-report paper sleeve hold. Shorter/later fixed holds did not beat the accepted max-3 plus 1% T+1 excess setup across the three canonical windows.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'default_off_paper_only': True, 'alters_orders': False, 'alters_signal_generation': False, 'alters_sizing': False, 'alters_exit_lifecycle': True}
- artifact: `data\experiments\exp-20260512-002\exp_20260512_002_sec_financial_report_hold_days.json`

## exp-20260512-006 SEC financial-report event notional

- timestamp: 2026-05-12T02:24:05Z
- lane: alpha_search
- decision: accepted_default_off_event_notional_15000
- changed_variable: sec_financial_report_event_sleeve_event_notional_usd
- promoted default: $15,000 per default-off paper event, with max_positions=3, T+1 excess >= 1%, and 10-trading-day hold unchanged.
- expected_value_score_delta: +0.505389
- total_pnl_delta: +$12,237.07
- before_aggregate: {'expected_value_score_sum': 7.409199, 'total_pnl_sum': 209889.79, 'trade_count_sum': 114, 'min_survival_rate': 0.792453, 'max_drawdown_pct_max': 0.090703, 'sleeve_total_pnl_sum': 24004.57, 'sleeve_closed_trade_count_sum': 52}
- after_aggregate: {'expected_value_score_sum': 7.914588, 'total_pnl_sum': 222126.86, 'trade_count_sum': 114, 'min_survival_rate': 0.792453, 'max_drawdown_pct_max': 0.093657, 'sleeve_total_pnl_sum': 36006.85, 'sleeve_closed_trade_count_sum': 52}
- interpretation: After the accepted event-quality floor, the SEC financial-report T+1 sleeve can carry a larger default-off paper budget. This is risk allocation, not candidate expansion: no live orders, candidate ranking, hold period, or queue filter changed.
- production_impact: {'shared_policy_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': True, 'replay_only': False, 'parity_test_added': True, 'default_off_paper_only': True, 'alters_orders': False, 'alters_signal_generation': False, 'alters_candidate_ranking': False, 'alters_sizing': True}
- artifact: `data\experiments\exp-20260512-006\exp_20260512_006_sec_financial_report_event_notional.json`

## exp-20260512-008 Space near-perfect TQS trend risk

- timestamp: 2026-05-12T03:24:26Z
- lane: alpha_search
- decision: accepted_default_off_space_near_perfect_tqs_trend_risk
- changed_variable: space_near_perfect_tqs_trend_risk_scalar
- best scalar: 1.10 for official Space `trend_long` signals with `0.95 <= trade_quality_score < 1.0`, on top of the accepted exp-20260512-004 Space stack.
- expected_value_score_delta: +0.2392
- total_pnl_delta: +$5,210.37
- window evidence: EV and PnL improved in all three canonical Space augmented windows: `late_strong +0.0971` EV / `+$2,048.33`, `mid_weak +0.1270` EV / `+$2,317.91`, and `old_thin +0.0151` EV / `+$844.13`.
- interpretation: Space optimization should stay in signal-quality-conditioned risk allocation. The accepted near-perfect TQS trend top-up remains default-off metadata/helper only; live Space slots remain zero.
- production_impact: {'shared_policy_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': True, 'replay_only': True, 'parity_test_added': True, 'daily_report_metadata_changed': True, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260512-008\space_near_perfect_tqs_trend_risk.json`

## exp-20260512-010 Space near-perfect TQS breakout risk

- timestamp: 2026-05-12T05:44:12Z
- lane: alpha_search
- decision: rejected_space_near_perfect_tqs_breakout_risk
- changed_variable: space_near_perfect_tqs_breakout_risk_scalar
- best scalar: 0.25 for official Space `breakout_long` signals with `0.95 <= trade_quality_score < 1.0`, on top of the accepted exp-20260512-008 Space stack.
- expected_value_score_delta: +0.2498
- total_pnl_delta: +$3,033.22
- window evidence: only `mid_weak` improved (`+0.2498` EV / `+$3,033.22`); `late_strong` and `old_thin` were unchanged, so Gate 4 failed with only one improved window.
- interpretation: near-perfect TQS is useful for Space trend risk, but it is not a robust Space breakout discriminator. Do not add a separate high-TQS breakout scalar on these frozen snapshots.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260512-010\space_near_perfect_tqs_breakout_risk.json`

## exp-20260512-007 SEC financial-report periodic-report notional

- timestamp: 2026-05-12T03:15:31Z
- lane: alpha_search
- decision: accepted_default_off_periodic_report_notional_1.25x
- changed_variable: sec_financial_report_periodic_report_notional_scalar
- promoted default: `periodic_report` rows use `1.25x` of the accepted `$15,000` base paper notional; `earnings_8k` stays at `1.0x`.
- expected_value_score_delta: +0.190856
- total_pnl_delta: +$3,408.57
- before_aggregate: {'expected_value_score_sum': 7.914587, 'total_pnl_sum': 222126.86, 'trade_count_sum': 114, 'min_survival_rate': 0.792453, 'max_drawdown_pct_max': 0.093657, 'sleeve_total_pnl_sum': 36006.85, 'sleeve_closed_trade_count_sum': 52}
- after_aggregate: {'expected_value_score_sum': 8.105443, 'total_pnl_sum': 225535.43, 'trade_count_sum': 114, 'min_survival_rate': 0.792453, 'max_drawdown_pct_max': 0.096499, 'sleeve_total_pnl_sum': 39337.77, 'sleeve_closed_trade_count_sum': 52}
- interpretation: Semantic event-family risk allocation improved the default-off SEC financial-report T+1 sleeve after the accepted $15k base budget. This changes no live orders, queue qualification, ranking, capacity, or hold period.
- production_impact: {'shared_policy_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': True, 'replay_only': False, 'parity_test_added': True, 'default_off_paper_only': True, 'alters_orders': False, 'alters_signal_generation': False, 'alters_candidate_ranking': False, 'alters_sizing': True}
- artifact: `data\experiments\exp-20260512-007\exp_20260512_007_sec_financial_report_periodic_notional.json`

## exp-20260512-013 Space peer-nonleader breakout risk

- timestamp: 2026-05-12T06:37:30+00:00
- lane: alpha_search
- decision: accepted_default_off_space_peer_nonleader_breakout_risk
- changed_variable: space_peer_nonleader_breakout_risk_scalar
- best scalar: 0.00 for official Space `breakout_long` signals whose own 20d momentum is not above the official Space basket average, on top of the accepted exp-20260512-008 Space stack.
- expected_value_score_delta: +0.3297
- total_pnl_delta: +$4,209.46
- window evidence: `late_strong +0.0180` EV / `+$375.38`, `mid_weak +0.3117` EV / `+$3,834.08`, and `old_thin unchanged`; no window regressed.
- interpretation: Space breakout work has a stronger ex-ante peer-leadership discriminator than the rejected near-perfect TQS breakout scalar. Nonleader breakouts should be zero-risk in the default-off Space forward stack; live Space slots remain zero.
- production_impact: {'shared_policy_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': True, 'replay_only': True, 'parity_test_added': True, 'daily_report_metadata_changed': True, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260512-013\space_peer_nonleader_breakout_risk.json`

## exp-20260512-031 Space IWM-relative momentum risk

- timestamp: 2026-05-12T12:30:02+00:00
- lane: alpha_search
- decision: accepted_default_off_space_iwm_relative_momentum_risk
- changed_variable: space_iwm_relative_leader_risk_scalar
- best scalar: `1.10x` for official Space signals when IWM 20d momentum is above SPY 20d momentum, on top of the accepted exp-20260512-013 Space stack.
- expected_value_score_delta: +0.4142
- total_pnl_delta: +$9,550.74
- window evidence: EV and PnL improved in all three Space augmented windows: `late_strong +0.1072` EV / `+$2,267.34`, `mid_weak +0.2138` EV / `+$3,541.68`, and `old_thin +0.0932` EV / `+$3,741.72`.
- interpretation: Space official-catalyst risk should modestly scale up when small caps lead the broad tape. This is default-off observation-slot metadata/helper only; live Space slots remain zero.
- production_impact: {'shared_policy_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': True, 'replay_only': True, 'parity_test_added': True, 'daily_report_metadata_changed': True, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260512-031\space_iwm_relative_momentum_risk.json`

## exp-20260512-032 Space launch/lunar theme-segment risk

- timestamp: 2026-05-12T13:27:47+00:00
- lane: alpha_search
- decision: accepted_default_off_space_launch_lunar_theme_risk
- changed_variable: space_launch_lunar_theme_segment_risk_scalar
- best scalar: `1.10x` for official Space signals whose production universe-registry `theme_segment` is `launch_lunar`, on top of the accepted exp-20260512-031 Space stack.
- expected_value_score_delta: +0.2404
- total_pnl_delta: +$5,233.68
- window evidence: EV and PnL improved in all three Space augmented windows: `late_strong +0.1048` EV / `+$2,447.13`, `mid_weak +0.1227` EV / `+$2,092.83`, and `old_thin +0.0129` EV / `+$693.72`.
- interpretation: Space official-catalyst risk has a modest production-visible launch/lunar bucket edge that survived the three-window gate. This is default-off observation-slot metadata/helper only; live Space slots remain zero.
- production_impact: {'shared_policy_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': True, 'replay_only': True, 'parity_test_added': True, 'daily_report_metadata_changed': True, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260512-032\space_launch_lunar_theme_risk.json`

## exp-20260512-035 Space data/defense theme-segment risk

- timestamp: 2026-05-12T14:33:05+00:00
- lane: alpha_search
- decision: rejected_space_data_defense_theme_risk
- changed_variable: space_data_defense_theme_segment_risk_scalar
- best scalar: `1.25x` for official Space signals whose production universe-registry `theme_segment` is `space_data_defense`, on top of the accepted exp-20260512-032 Space stack.
- expected_value_score_delta: +0.1986
- total_pnl_delta: +$8,204.94
- before_aggregate: {'expected_value_score_sum': 12.7321, 'total_pnl_sum': 312460.94, 'trade_count_sum': 70, 'min_survival_rate': 0.7746, 'max_drawdown_pct_max': 0.1128}
- after_aggregate: {'expected_value_score_sum': 12.9307, 'total_pnl_sum': 320665.88, 'trade_count_sum': 70, 'min_survival_rate': 0.7746, 'max_drawdown_pct_max': 0.1191}
- window evidence: only `old_thin` improved (`+0.2051` EV / `+$8,350.90`); `mid_weak` regressed (`-0.0065` EV / `$-145.96`) and `late_strong` was unchanged. Max drawdown worsened by `0.63` percentage points, above the gate guardrail.
- interpretation: Space data/defense bucket scaling is old-window concentrated and does not survive the accepted three-window Space gate. Do not retry adjacent BKSY/PL/RDW data/defense theme scalars on these frozen snapshots.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'daily_report_metadata_changed': False, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260512-035\space_data_defense_theme_risk.json`

## exp-20260512-038 Space official customer-source risk

- timestamp: 2026-05-12T16:01:19+00:00
- lane: alpha_search
- decision: accepted_default_off_space_official_customer_source_risk
- changed_variable: space_official_customer_source_risk_scalar
- best scalar: `1.10x` for official Space signals whose production event seed profile has `customer_win` from official/regulatory/company primary sources, on top of the accepted exp-20260512-037 liquidity-tier stack.
- expected_value_score_delta: +0.5354
- total_pnl_delta: +$10,864.99
- before_aggregate: {'expected_value_score_sum': 12.9711, 'total_pnl_sum': 318249.96, 'trade_count_sum': 70, 'min_survival_rate': 0.7746, 'max_drawdown_pct_max': 0.1161}
- after_aggregate: {'expected_value_score_sum': 13.5065, 'total_pnl_sum': 329114.95, 'trade_count_sum': 70, 'min_survival_rate': 0.7746, 'max_drawdown_pct_max': 0.1197}
- window evidence: EV and PnL improved in all three Space augmented windows: `late_strong +0.1156` EV / `+$2,965.84`, `mid_weak +0.4107` EV / `+$7,037.53`, and `old_thin +0.0091` EV / `+$861.62`.
- interpretation: Space catalyst-quality allocation should prefer source-qualified customer-win events over another local theme/ticker scalar. This remains shared default-off observation metadata/helper only; live Space slots remain zero.
- production_impact: {'shared_policy_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': True, 'replay_only': True, 'parity_test_added': True, 'daily_report_metadata_changed': True, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260512-038\space_official_customer_source_risk.json`

## exp-20260512-040 Space defense-budget source risk

- timestamp: 2026-05-12T16:32:04+00:00
- lane: alpha_search
- decision: rejected_space_defense_budget_source_risk
- changed_variable: space_defense_budget_source_risk_scalar
- best scalar: `1.25x` for official Space signals whose event seed profile has `defense_budget_theme` + `government_space_contract` from `official_government_release`, on top of the accepted exp-20260512-038 customer-source stack.
- expected_value_score_delta: +2.3678
- total_pnl_delta: +$52,220.36
- before_aggregate: {'expected_value_score_sum': 13.5065, 'total_pnl_sum': 329114.95, 'trade_count_sum': 70, 'min_survival_rate': 0.7746, 'max_drawdown_pct_max': 0.1197}
- after_aggregate: {'expected_value_score_sum': 15.8743, 'total_pnl_sum': 381335.31, 'trade_count_sum': 70, 'min_survival_rate': 0.7746, 'max_drawdown_pct_max': 0.1351}
- window evidence: EV and PnL improved in all three Space augmented windows, but max drawdown drift exceeded the Gate 4 guardrail: `1.10x` already worsened max drawdown by `0.62` percentage points and `1.25x` by `1.54` percentage points.
- interpretation: broad official defense-budget source exposure behaves like a high-beta Space exposure amplifier, not a safe catalyst-quality discriminator. Do not retry adjacent defense-budget/government-contract source scalars on these frozen snapshots.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'daily_report_metadata_changed': False, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260512-040\space_defense_budget_source_risk.json`

## exp-20260512-041 Space financing/dilution profile risk

- timestamp: 2026-05-12T16:43:03+00:00
- lane: alpha_search
- decision: accepted_default_off_space_financing_dilution_profile_risk
- changed_variable: space_financing_dilution_event_guard_profile_risk_scalar
- best scalar: `1.075x` for official Space signals whose production registry `event_guard_profile` contains `financing` or `dilution`, on top of the accepted exp-20260512-038 customer-source stack.
- expected_value_score_delta: +0.5022
- total_pnl_delta: +$11,012.31
- before_aggregate: {'expected_value_score_sum': 13.5065, 'total_pnl_sum': 329114.95, 'trade_count_sum': 70, 'min_survival_rate': 0.7746, 'max_drawdown_pct_max': 0.1197}
- after_aggregate: {'expected_value_score_sum': 14.0087, 'total_pnl_sum': 340127.26, 'trade_count_sum': 70, 'min_survival_rate': 0.7746, 'max_drawdown_pct_max': 0.1243}
- window evidence: EV and PnL improved in all three Space augmented windows: `late_strong +0.0915` EV / `+$2,463.78`, `mid_weak +0.3582` EV / `+$6,053.43`, and `old_thin +0.0525` EV / `+$2,495.10`. Max drawdown drift was `+0.46` percentage points, inside the Gate 4 guardrail.
- interpretation: production registry event-guard profile terms are a usable Space catalyst-quality allocation field when sized conservatively. `1.10x` had higher raw EV but failed drawdown; keep `1.075x` and do not retry adjacent financing/dilution profile scalars on these frozen snapshots.
- production_impact: {'shared_policy_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': True, 'replay_only': True, 'parity_test_added': True, 'daily_report_metadata_changed': True, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260512-041\space_financing_dilution_profile_risk.json`

## exp-20260512-043 Space mission-binary profile risk

- timestamp: 2026-05-12T17:41:41+00:00
- lane: alpha_search
- decision: rejected_space_mission_binary_profile_risk
- changed_variable: space_mission_binary_event_guard_profile_risk_scalar
- best scalar: `0.50x`, but all tested scalars from `0.50x` through `1.25x` produced zero EV/PnL delta versus the accepted exp-20260512-041 Space stack.
- expected_value_score_delta: +0.0000
- total_pnl_delta: +$0.00
- before_aggregate: {'expected_value_score_sum': 14.0087, 'total_pnl_sum': 340127.26, 'trade_count_sum': 70, 'min_survival_rate': 0.7746, 'max_drawdown_pct_max': 0.1243}
- after_aggregate: {'expected_value_score_sum': 14.0087, 'total_pnl_sum': 340127.26, 'trade_count_sum': 70, 'min_survival_rate': 0.7746, 'max_drawdown_pct_max': 0.1243}
- window evidence: `mission_binary` matched only `LUNR` and adjusted just 2 signals; neither adjusted signal changed executed shares enough to move any of the three fixed windows.
- interpretation: mission-binary registry profile is not a material Space risk-allocation alpha on the frozen Space replay. Do not retry adjacent mission-binary profile scalars without forward replacement-value evidence or a different production-observable catalyst field.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'daily_report_metadata_changed': False, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260512-043\space_mission_binary_profile_risk.json`

Latest core state-allocation alpha search: `exp-20260512-106` and
`exp-20260512-107` tested signal-day sector-proxy tape as a production-knowable
risk allocation state. The adverse-tape 0.5x haircut failed Gate 4 with
aggregate EV `-0.0251` and PnL `-$1,901.95`; it only improved `mid_weak` and
regressed `old_thin`. The positive-tape 1.10x top-up was directionally positive
but underpowered, with aggregate EV `+0.0140` and PnL `+$820.26`, improving only
`old_thin`. No shared policy was promoted. Do not retry fixed +/-1% signal-day
sector-tape scalars without forward attribution or a stronger state
discriminator.

Latest Form 4 alpha search: `exp-20260512-108` tested a PIT-safe 5-trading-day
pre-entry relative-strength confirmation on top of the latest single-owner
Form 4 forward-queue replay. The confirmed slice stayed positive versus core
(`aggregate EV +0.2115`, PnL `+$4,014.97`, no core EV regression), but it
regressed the single-owner baseline in all three windows (`aggregate EV
-0.1074`, PnL `-$1,900.00`) and left only 5 selected event trades, below the
sample guard. No shared policy or production adapter was changed. Keep Form 4
in forward observation and do not add pre-entry RS qualification to the frozen
single-owner queue without new forward replacement-value evidence.

Latest core breakout alpha search: `exp-20260513-001` tested a cap-aware risk
scalar for already-qualified `breakout_long` signals whose existing
`conditions_met.volume_spike_ratio > 2.0`. The best scalar was only `1.05x`,
with aggregate EV `+0.0002` and PnL `+$2.62`; it improved only `mid_weak` and
left `late_strong` / `old_thin` unchanged. No shared sizing policy was promoted.
Do not retry fixed core breakout strong-volume scalars on these frozen windows
without forward breakout volume-bucket attribution or a stronger orthogonal
entry-quality state.

Latest rejected core state-allocation alpha search: `exp-20260513-013` tested
whether the previously rejected broad momentum-acceleration top-up becomes
robust when restricted to signals that also have the accepted signal-day own
green candle. The best scalar was `1.25x`: aggregate EV improved `+0.0869` and
PnL improved `+$1,344.23`, but `old_thin` still regressed by EV `-0.0080` /
PnL `-$387.79`, so Gate 4 failed and no shared policy was promoted. Do not
retry adjacent core momentum-acceleration scalars on these frozen windows
without a materially different production-visible discriminator.

Latest rejected core setup-quality alpha search: `exp-20260513-016` tested a
cap-aware risk top-up for core `trend_long` / `breakout_long` signals with
near-perfect `trade_quality_score >= 0.95`. The best scalar was `1.20x`:
aggregate EV improved `+0.0376` and PnL improved `+$4,016.23`, but `old_thin`
EV regressed slightly and the max drawdown ceiling worsened by `+1.42`
percentage points, failing Gate 4. Do not promote or retry broad high-TQS core
sizing on the frozen windows without a narrower production-visible
discriminator or forward setup-quality attribution.

Latest rejected core stacked-quality alpha search: `exp-20260513-018` tested
whether the already accepted own-green candle and RS20 leader states become
promotion-grade when stacked with high setup quality. The best scalar was a
confirmed-quality `1.20x` top-up, but aggregate EV improved only `+0.0534`
and PnL `+$4,540.10` while the edge stayed old-window concentrated and failed
the multi-window gate. Do not stack own-green, RS20, and near-perfect
setup-quality multipliers on the frozen core windows without forward
setup-quality attribution showing this state is not just local overfit.

Latest rejected index ETF lifecycle alpha search: `exp-20260513-017` tested
whether `QQQ` / `SPY` / `IWM` should receive a separate wider target-width pool
after a live QQQ `SIGNAL_TARGET` felt early. The sweep changed only the index
ETF target ATR multiple (`5.0x`, `6.0x`, `7.0x`) and left entries, ranking,
sizing, universe, LLM/news, and hard stops unchanged. The best variant was
`5.0x`: aggregate EV fell `-0.1030` / `-1.62%` and PnL fell `-$2,267.28` /
`-1.21%`; the only changed trade was `IWM` in `mid_weak`, where delaying the
target exit reduced PnL from `$4,783.80` to `$2,513.69`. Do not split broad
index ETFs into a promoted target pool without forward target-touch evidence
or a narrower state-conditioned lifecycle discriminator.

Latest rejected core slot-priority alpha search: `exp-20260513-027` tested
whether the accepted signal-day own-green state should also rank ahead of
non-green candidates during same-day slot slicing. The scout changed only the
slot ordering after existing filters, sizing, and scarce-slot breakout
deferral; it did not change entry logic, sizing, exits, universe, LLM/news, or
add-ons. Gate 4 failed: aggregate EV fell `-2.2683` and PnL fell
`-$40,404.08`, entirely from `late_strong`, where replacing GLD/IAU exposure
with green IWM/AMD and later META materially hurt results. Keep own-green as
the accepted small sizing helper, not as a slot-priority ranking key, unless
forward collision evidence changes the prior.

Latest rejected core clean-leader refinement: `exp-20260513-038` tested an
extra cap-aware top-up only for already accepted clean SPY-relative leader
signal-day winners whose existing stop had at least the 2% gap cushion. No
entry, ranking, exit, target, universe, LLM/news, or production policy changed.
Gate 4 failed: best `1.025x` moved aggregate EV `-0.0002` while adding
`$589.77` PnL, improved only `old_thin`, and regressed `late_strong`. Do not
promote or keep retuning clean-leader execution-cushion overlays on the frozen
windows without forward evidence or a genuinely independent state variable.

Latest rejected core clean-leader non-confirmation search: `exp-20260513-109`
tested a post-sizing risk haircut for already clean risk-on SPY-relative
leaders whose signal-day ticker return did not beat SPY. The best `0.90x`
variant improved `mid_weak` and `old_thin` EV by only `+0.0006` combined, but
regressed `late_strong` by `-0.0791` EV and cut aggregate PnL by `$2,006.90`.
Keep signal-day SPY outperformance as the accepted positive-confirmation top-up
only; do not add the mirror-image haircut without forward evidence.

Latest Space alpha search: `exp-20260513-020` tested a Space `trend_long`
risk scalar conditioned on both IWM 20d momentum beating SPY and the ticker's
20d momentum beating the official Space basket average, on top of the accepted
`exp-20260513-015` Space stack. The accepted scalar is `1.15x`. Aggregate EV
improved `+0.7810` to `17.6697` and PnL improved `+$17,229.17` to
`$421,418.99`, with no EV-regressed window. `mid_weak` improved `+0.6377` EV /
`+$10,980.05`, `old_thin` improved `+0.1433` EV / `+$6,249.12`, and
`late_strong` was unchanged. Max drawdown drift was `+0.44` percentage points,
inside the Gate 4 guardrail; min survival stayed `70.42%`, well above the
guardrail. Promote only as shared default-off Space
metadata/helper; live Space slots remain zero.

Latest rejected Space peer-bucket alpha search: `exp-20260513-019` tested
whether the accepted customer-source edge should also top up peer-nonleader
official Space signals. Aggregate EV improved `+0.1320`, but the result did
not clear the Space three-window gate, so customer-source allocation should
stay tied to stronger peer-quality buckets. Do not promote customer-source
peer-nonleader scaling on the frozen snapshots; the next valid Space step is
forward replacement value by catalyst family/source/peer bucket or a genuinely
new production-visible official catalyst-quality field.

Latest rejected Space lifecycle alpha search: `exp-20260513-026` tested
whether the accepted IWM-plus-peer-leader `trend_long` state should also get a
wider target ATR floor. The best 8 ATR floor raised aggregate EV by `+0.4165`
but cut aggregate PnL by `$21,220.04`, improved only `mid_weak`, and regressed
`old_thin` by `-1.1259` EV / `-$42,518.52` with max drawdown worsening to
`19.68%`. Keep the accepted exp020 state as a sizing helper, not a lifecycle
target-width rule, until forward target-touch evidence exists.
