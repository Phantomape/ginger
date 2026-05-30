# Kova Research Directions

This note records the research directions implied by the Kova PDF and the
current Ginger evidence. It is a memory aid for future agents, not a trading
rule. Use it together with `docs/backtesting.md`,
`docs/alpha-optimization-playbook.md`, `docs/current_state.md`, and
`docs/experiment_log.jsonl`.

## Current Anchor

The only Kova/VCP direction with strong replay evidence is the default-off,
observe-only QQQ-confirmed volatility-contraction paper sleeve:

- `exp-20260525-022`: QQQ-confirmed VCP replay improved all three canonical
  windows.
- `exp-20260525-037`: top-2 candidate expansion improved the VCP sleeve.
- `exp-20260526-007`: accepted the shared rank-notional profile `[1.0, 1.25]`.

This is still not live capital. It remains a paper sleeve until closed forward
replacement value, concentration, drawdown, and kill-gate evidence pass a
separate Gate 1-4 activation experiment.

## What Kova Points Toward

Kova is best treated as a research map around five surfaces:

1. VCP leader selection: contraction, breakout, volume confirmation, leadership,
   and market confirmation.
2. Non-daily or non-OHLCV context: intraday 15m/60m structure, CAN SLIM
   fundamentals, real RS rating or proxy, and 13F/institutional sponsorship.
3. Sell-side lifecycle: 8-week 20% rule, climax runs, churning, high-volume
   support breaks, earnings gap-downs, and trendline/50dma breaks.
4. Market regime: confirmed uptrend and distribution-day pressure.
5. Operator process: pyramid only after confirmation, cut losers, reduce risk
   after repeated stops, and journal every setup.

## Already Tested Or Frozen

Do not re-propose these as fresh Kova ideas on the same frozen VCP sample:

| Direction | Evidence | Current status |
|---|---|---|
| QQQ-confirmed VCP top-2 | `exp-20260525-022`, `exp-20260525-037`, `exp-20260526-007` | Accepted as default-off paper anchor; no QQQ/SPY, top-N, or rank-notional retune without new forward evidence. |
| Pocket-pivot support / accumulation | `exp-20260525-027`, `exp-20260526-009` | Rejected or metadata-only. |
| Pre-signal event/catalyst support | `exp-20260525-030`, `exp-20260525-033` | Read-only context; not a gate. |
| Volume dry-up, breakout-day quality, weekly tightness, MA stack | `exp-20260525-032`, `exp-20260526-023`, `exp-20260526-024`, `exp-20260526-025` | Attribution only; not actionable gates. |
| Higher-low/base geometry | `exp-20260526-022` | Explanatory but not a promotable gate. |
| Cup-with-handle / flat-base proxy | `exp-20260527-911` | Textbook bucket was not useful; inverse clue only. |
| Companyfacts growth + Ginger RS proxy variants | `exp-20260527-015`, `exp-20260527-017` through nearby variants | Adjacent threshold retunes are frozen unless a materially richer PIT fundamental surface is added. |
| Entry-day-low stop | `exp-20260527-016` | Rejected. |
| Fixed 7.5% max-loss stop | `exp-20260527-910` | Rejected. |
| Confirmation pyramid add-on | `exp-20260527-909` | Rejected despite PnL lift because risk-adjusted proxy / return on deployed notional regressed. |
| High-volume weak-close support-break exit | `exp-20260528-002` | Rejected: only 3/117 triggers, aggregate PnL `-$970.54`, EV proxy `-0.005483`, late_strong regressed. |
| Distribution-day / confirmed-uptrend context | `exp-20260528-010` | Observed-only attribution: coverage was `117/117`; high distribution pressure underperformed the rest on average but still had positive PnL (`+$5,363.45`), so it is context, not a VCP gate. |
| Sell-side lifecycle taxonomy | `exp-20260528-014` | Observed-only taxonomy: coverage was `117/117`; `failed_breakout_low_mfe` was the only populated negative bucket (`14` trades, `-$3,935.60`) and can only nominate a later shared lifecycle replay, not a direct exit rule. |
| Day-3 low-MFE failed-breakout exit | `exp-20260528-031` | Rejected: the ex-ante day-3 proxy triggered 11 trades but cut aggregate PnL by `-$7,010.02`, regressed late_strong and mid_weak, and mostly missed the taxonomy target (`27.27%` failed-low-MFE label share). |
| Shakeout/reclaim lifecycle bucket | `exp-20260529-006` | Observed-only, not promotable: early shakeout/reclaim was positive (`7` trades, `+$4,039.29`, avg `+$577.04`) and beat shakeout/no-reclaim (`20` trades, `-$2,148.34`, avg `-$107.42`), but failed the pre-set sample gate (`7 < 10`). Treat as a forward monitoring clue, not an exit or re-entry rule. |
| Closed-ledger loss-streak de-risking | `exp-20260529-025` | Rejected: after two already-closed losing VCP paper trades, a `0.50x` notional scalar triggered 11 trades and improved EV proxy by `+0.003721`, but cut aggregate PnL by `-$856.33` after scaling 6 winners and 5 losers. Do not retest this same frozen-sample loss-streak scalar without new forward replacement-value evidence. |
| VCP forward replacement-value readiness | `exp-20260530-004` | Observed-only blocker audit: the production VCP paper sleeve and default-off attribution surface are wired, but snapshots through `2026-05-28` had `candidate_count=0`, `closed_forward_outcomes=0`, and failed activation blockers `min_closed_trades`, `positive_net_pnl`, `min_win_rate`, concentration checks, and `needs_closed_forward_outcomes`. No activation review or VCP retune until real forward rows exist. |

## Still Valid, But Gated

These remain legitimate Kova directions only if their blockers are addressed.

| Direction | Why it matters | Required next evidence |
|---|---|---|
| Forward replacement value for the accepted VCP sleeve | The paper sleeve has replay evidence but no activation evidence. `exp-20260530-004` confirmed the current production ledger has zero candidates and zero closed outcomes. | Closed forward rows versus cash/core displacement, concentration, drawdown, and kill-gate results. If `candidate_count` stays zero after more production days, inspect candidate-feed/readiness before any new alpha retune. |
| Intraday 15m/60m entry timing | Kova uses intraday structure for pocket pivots and precise entries. | PIT intraday coverage across accepted VCP dates; `exp-20260527-902` found current coverage insufficient. |
| Institutional sponsorship / 13F accumulation | Kova emphasizes fund accumulation. | PIT ticker-mapped 13F ownership coverage; `exp-20260527-906` found current rows insufficient. |
| Full CAN SLIM fundamentals | The PDF uses EPS acceleration, annual growth, sales growth, and supply. | Audited PIT fields beyond partial Companyfacts + RS proxy; no threshold retune on incomplete fields. |
| Forward distribution-day / confirmed-uptrend monitoring | This is Kova's market regime layer, distinct from QQQ > SPY, but frozen-sample attribution did not justify a gate. | Only forward replacement-value rows by bucket; do not turn distribution-day counts into a VCP gate, scalar, or exit without a separate Gate 1-4 experiment. |
| Full sell-side lifecycle replay | Kova's exits are a system, not one stop threshold. `exp-20260528-014` found a populated negative `failed_breakout_low_mfe` taxonomy bucket, but `exp-20260528-031` rejected the simple day-3 low-MFE proxy. | Only revisit with a materially richer ex-ante lifecycle state that distinguishes delayed winners from real failed breakouts, plus replacement value, drawdown, survival, and production/backtest parity. Do not promote from taxonomy alone. |
| Shakeout and re-entry after reclaiming pivot | Kova allows re-entry after false breakouts; `exp-20260529-006` found a positive but thin reclaim bucket. | Full lifecycle/re-entry replay with slot, heat, and replacement-value accounting plus forward rows. Do not promote from the `7`-trade historical bucket. |
| Broader portfolio-state pause after repeated stops | Kova halves exposure after repeated stops and pauses after more. | Only with new forward portfolio-state rows and replacement-value accounting. The narrow VCP closed-ledger halve-after-two-losses scalar was rejected in `exp-20260529-025`; do not repeat it on the same frozen sample. |
| Trading journal fields | Kova requires setup, market, stop, add plan, and post-review notes. | Measurement repair only; useful if it improves attribution and prevents repeated failed experiments. |

## Recommended Next Work

Prefer one of these before any more frozen-sample Kova threshold scans:

1. Keep accumulating the VCP forward replacement-value report for the accepted
   top-2 paper sleeve; `exp-20260530-004` found the report is wired but not
   mature (`0` candidates and `0` closed outcomes through `2026-05-28`).
2. Revisit sell-side lifecycle only with a materially richer ex-ante state:
   the simple day-3 low-MFE proxy from `exp-20260528-031` is rejected, and
   the shakeout/reclaim clue from `exp-20260529-006` is positive but too thin
   to promote.
3. Improve PIT coverage for intraday or 13F, then rerun readiness before any
   alpha test.
4. Extend distribution-day / confirmed-uptrend context only through forward
   monitoring and replacement-value accounting, not another frozen-sample gate.

Avoid more single-threshold Kova stop, MA, base-shape, pocket-pivot, or volume
quality rules on the same frozen sample. The evidence so far says that path is
mostly explaining trades after the fact rather than improving expected value.
