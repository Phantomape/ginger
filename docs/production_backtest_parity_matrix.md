# Production / Backtest Parity Matrix

This file holds adapter-specific parity facts moved out of `docs/production_backtest_parity.md`.
Use it when an experiment needs the exact shared-source, replay, production, allowed-difference, or promotion-state row for an accepted/default-off adapter.

The core production/backtest contract remains in `docs/production_backtest_parity.md`.

## V2 SEC 8-K Research Universe Runtime

The V2 SEC 8-K adapter is a source-bounded, research-only membership consumer.
It now feeds only a read-only pre-Engine-0 observation boundary; it does not feed
the legacy production runner, an Engine-0 policy/baseline, a market decision
clock, orders, or paper/live policy. The immutable source manifest keeps
`parity_status=contract_only_unwired`; adapter and observation alias parity are
recorded separately and cannot upgrade PIT or authority.

The opt-in segmented sidecar is still not a runtime backend. Full-checkpoint
HEADs retain the legacy storage marker, while compact HEADs carry a distinct
self-hash-bound capability marker that an older reader rejects before checkpoint
access. Deployment is reader-first and one-way within a root; rotation remains
explicit and unscheduled. This capability contract changes no adapter identity,
membership, daily/replay result, PIT tier, authority, or default-off boundary.

| Decision point | Shared source | Replay use | Daily use | Allowed difference |
| --- | --- | --- | --- | --- |
| Exact SEC 8-K materialization membership | `v2_sec_8k_runtime_adapter.py`, `v2_sec_8k_universe.py`, `v2_universe_ledger.py` | caller must supply the exact committed `manifest_id` and timezone-aware `as_of`; the full source/envelope/ledger/coverage graph is validated before the sole shared membership reader runs | same callable, same mandatory identity tuple, same normalized snapshot and canonical hashes; there is no implicit latest manifest or process-clock fallback | none in membership, ordering, clocks, identity, hashes, or default-off boundary; Engine-0, production/backtest, canonical, and execution parity remain unclaimed |
| Pre-Engine-0 universe membership observation | `v2_universe_observation.py` consumes the exact runtime adapter snapshot in memory | `observe_sec_8k_replay_universe` is a true alias that forwards the explicit identity tuple once, revalidates adapter/input/reader/membership identities and full research-only ceilings, and emits only exact membership rows | `observe_sec_8k_daily_universe` is the same callable and produces the same normalized observation hash across equivalent offsets and copied paths | none in membership, state, ordering, identity, hashes, or default-off boundary; status is `daily_replay_alias_verified_research_only`. Engine-0 policy/baseline, market clock, scheduler, production/backtest, execution, canonical, and paper/live parity remain unclaimed |

## ORTEX Cost-to-Borrow-New Observer

`exp-20260718-003` adds a shared, default-off ORTEX borrow-economics
observer. Historical source dates are conservatively mapped to the strictly
next caller-supplied NYSE session; same-day use is forbidden. The fixed
research surface contains 20 Moomoo-covered stocks across three predeclared
40-session blocks. Daily collection rotates through at most four names that
are at least five calendar days stale, stops before a 250-credit reserve, and
can be disabled with `ORTEX_BORROW_REFRESH_DISABLED=1`. Every snapshot and
outcome remains `trade_enabled=false`.

| Decision point | Shared source | Backtester use | Production use | Allowed difference |
| --- | --- | --- | --- | --- |
| Default-off ORTEX CTB-new observer and generic H5/H10 outcomes | `ortex_data_sidecar.py`, `ortex_borrow_observer.py`, `data/non_ohlcv/ortex/`, `run.py` | canonical core backtests do not consume the observer; research replays may use only the append-only normalized rows, the fixed 20-name/three-block universe, strict next-session usable clock, usable-session open entry, and fifth/tenth later-session close outcomes versus cash/SPY/QQQ | daily run performs bounded stale-name refresh only once per US equity session, always settles locally available rows, and mounts the result under `non_ohlcv_snapshot["ortex_borrow_observer"]`; failures are isolated in a default-off stub | historical rows use the conservative inferred next-session clock while prospective rows also retain local collection time; neither path may change candidates, orders, ranking, sizing, exits, or claim short executability without a separate shared alpha policy, broker locate/availability evidence, and Gate 1-4 experiment |
| Rejected ORTEX CTB-new × Moomoo short-volume pair spread (`exp-20260718-004`) | `ortex_moomoo_borrow_pair_paper_sleeve.py`, `experiments/exp_20260718_004_ortex_moomoo_borrow_pair.py` | frozen replay uses the exact 20-name same-date cross-section, top-4 intersection, highest rank-sum short without fallback, lowest-stress correlated cluster peer, next-open entry, fifth-session close, cash collateral, marked-gross guard, 45bp per leg, and observed CTB accrual | shared daily builder was implemented and tested before Gate 4, then all pair-specific `run.py` mounts were removed after rejection; the helper remains only for reproducibility and emits no executable orders | Gate 2/3 passed but 38 pairs lost `$584.28`; 90/10 EV fell `6.2057 -> 5.4239`, PnL fell `$130,992.36 -> $114,688.52`, and 3/3 windows materially regressed. Do not wire or retune this family on the same rows. Bulk coverage was 17/20 at 75.55 credits/request and Moomoo locate fields were empty, so it was also not forward-operational or live-ready. |

## SEC Same-Issuer Dual-Class Spread

`exp-20260718-007` tests a new non-price pair-linkage source: the official SEC
same-CIK identity of dual-class common shares. Six identities are audited, but
GOOG/GOOGL is outcome-blind excluded because its historical legs do not share
one provider/adjustment vintage; the five-pair economic whitelist is frozen in
the shared helper. Candidate prices come only from the saved, hash-bound cold
panel; hot warehouse overlays are forbidden.

| Decision point | Shared source | Backtester use | Production use | Allowed difference |
| --- | --- | --- | --- | --- |
| Rejected same-CIK dual-class robust premium spread (`exp-20260718-007`) | `sec_same_issuer_dual_class_spread_paper_sleeve.py`, `experiments/exp_20260718_007_sec_same_issuer_dual_class_spread.py`, `data/reference/sec_company_tickers.json` | shared replay uses exactly 120 strictly prior common sessions, robust median/MAD, `|z| >= 2.5`, at least 1% anchor deviation, next-common-session whole-share long-cheap/short-rich entry, one open-or-pending pair, ten-session same-pair cooldown, convergence/3% adverse/ten-session exits, cash collateral, 45bp round trip per leg, 5% annualized short carry, and measurement-only final-window settlement | the same helper exposes an exact-date, fail-closed default-off daily snapshot and append-only lifecycle API, but it is not mounted in `run.py` after economic rejection and never emits orders; current SEC identity is not effective-dated and broker locate/size is absent | Gate 2/3 passed, but 23 funded pairs lost `$1,454.49` after costs, standalone EV was `-0.4463`, and 0/3 windows were nonnegative on both EV/PnL. SPY beta was only `0.0105`, yet 90/10 EV fell `6.2057 -> 5.3236`, PnL fell `$130,992.36 -> $113,458.64`, and all three windows materially regressed. Do not wire or retune this frozen policy; GOOG/GOOGL requires a same-batch two-leg refreeze before any separate revisit. |

## Shared Paper-Sleeve Execution-Sizing Boundary

`exp-20260712-018` adds one repository-wide, fail-closed sizing audit in
`quant/paper_sleeve_execution_contract.py`. Historical and forward paper
notionals remain each sleeve's unchanged evidence units. The five event-ledger
adapters freeze `paper_notional_usd` on pending creation so a later config
change cannot resize an aged signal. `run.py` annotates all 40 built paper
surfaces, publishes their aggregate contract in trend and quant JSON, and also
publishes the previously omitted deep-drawdown rebound surface.

| Decision point | Shared source | Backtester use | Production use | Allowed difference |
| --- | --- | --- | --- | --- |
| Paper evidence notional vs executable experiment amount | `paper_sleeve_execution_contract.py`, five event-ledger adapters, `run.py` | core backtests and existing paper replays keep their original notional and PnL rules; this measurement repair does not alter selection, sizing, exits, or Gate-1 metrics | daily snapshots label paper notionals as evidence-only and emit `experiment_notional_usd=null` unless a complete envelope, passed forward gate, and enabled trade adapter are all present | paper surfaces may have different evidence notionals by design; no paper notional may silently become an order size, and live activation still requires its own declared and measured execution envelope |

## USAspending Obligation-Conversion First-Seen Observer

`exp-20260713-007` adds a shared, default-off observer over a locally frozen
official USAspending transaction snapshot. `exp-20260727-003` restores its
daily producer, `exp-20260729-008` journals resumable async jobs, and
`exp-20260730-001` drains a still-valid prior-day job before the next daily
request while durably exposing its health. The historical current
snapshot is seed-only: agency action dates are regulatory metadata and may not
be used as policy availability. Availability begins only at the locally persisted
`first_seen_at`. This means local first observation, not proof of first public
availability. The observation clock must be monotonic, later rows must pass a
post-initialization `initial_report_date` freshness guard before they can count
as prospective evidence, Department of Defense and USACE transactions are
excluded, and the observer remains `trade_enabled=false`.

| Decision point | Shared source | Backtester use | Production use | Allowed difference |
| --- | --- | --- | --- | --- |
| Default-off USAspending obligation-conversion first-seen observer | `usaspending_obligation_observer.py`, `data/non_ohlcv/usaspending_obligation_observer/`, `run.py` | canonical backtests do not consume the historical current snapshot; all initial rows are `seed_not_forward`, action dates cannot backdate availability, and a replay may begin only from persisted local `first_seen_at` rows after the seed that also passed the source-freshness guard | when no explicit local override is configured, the daily run requests the fixed official transaction download with a bounded wait, freezes a validated immutable ZIP plus manifest, and binds availability to actual retrieval UTC. Immediately after a job is created, a durable dated receipt journals the `submitted`, polling, and `finished-awaiting-download` phases; transient status or file GET failures therefore resume the same job before another POST, including across a UTC date boundary. Resume uses the receipt's original run date and frozen request only when official HTTPS URLs, bounded status history, monotonic clocks, and the 24-hour TTL all revalidate. A prior job that is still pending blocks the current-day POST; once finished, its original dated snapshot is consumed first, its journal is explicitly retired as completed, and the current day may then proceed. Invalid or expired receipts remain non-ok. Pending, failed, missing, or stale production is persisted as non-ok health and atomically copied into the dated non-OHLCV snapshot, while a fresh zero-event snapshot remains an explicit successful heartbeat. An explicit local snapshot override is still supported. Every row remains observer-only and `trade_enabled=false`, so it cannot alter candidates, orders, ranking, sizing, or exits | production may accumulate eligible prospective rows while backtests have no eligible historical rows; performance evaluation remains parked until >=75 settled unique eligible events across >=15 local first-seen dates and >=3 mapped public-company tickers, max ticker share <=30%, with complete cash/SPY/QQQ outcomes |

## Drugs@FDA Original NDA/BLA First-Seen Observer

`exp-20260713-006` adds a default-off observer over the official CDER
Drugs@FDA ZIP; `exp-20260728-001` repairs its silently starved daily producer.
The observer records original NDA/BLA
approval rows and assigns `first_seen_at` only when this policy first reads the
snapshot. The current ZIP is a current-state snapshot, not a historical
point-in-time archive, so its older approval dates cannot be treated as
historically observable decisions. The surface has no issuer/ticker mapping
and therefore cannot generate candidates, signals, or orders. The daily path
now acquires the fixed official FDA ZIP before consuming it, freezes a dated
snapshot plus manifest, and exposes source freshness separately from process
success; failures remain isolated from strategy execution but no longer look
healthy.

| Decision point | Shared source | Backtester use | Production use | Allowed difference |
| --- | --- | --- | --- | --- |
| Default-off CDER original NDA/BLA first-seen observer | `drugsfda_approval_observer.py`, `data/non_ohlcv/drugsfda_approval_observer/raw/`, `run.py` | canonical backtests do not consume this surface; the current snapshot is not historical PIT evidence, older approval dates may not be backdated to strategy decisions, and no replay is allowed until separately frozen timestamped snapshots and a PIT issuer/ticker relation exist | without an explicit local override, the daily path requests the fixed official FDA HTTPS endpoint with bounded timeout and size, validates the required ZIP tables, freezes `drugsatfda_YYYYMMDD.zip` plus `snapshot_manifest_YYYYMMDD.json`, and binds `first_seen_at` to the manifest retrieval UTC. Missing, unavailable, stale, or unverifiable production persists non-ok health; an unchanged valid daily snapshot emits an explicit healthy zero-event heartbeat. Every row remains `trade_enabled=false` | production may accumulate prospective first-seen rows while backtests have no eligible rows; no ticker mapping, candidate generation, live/default orders, ranking, sizing, exits, watchlists, or LLM/news policy may consume this observer without a separate shared policy and Gate 1-4 experiment |

## Rejected FDA Orange Book Monthly NEWA Release Basket

`exp-20260715-004` evaluated the official monthly Orange Book
Additions/Deletions PDFs as a hash-bound historical PIT archive. The shared
helper uses the PDF HTTP `Last-Modified` UTC value as availability, treats the
approval date only as a 0-45-day freshness field, accepts only `>A>` rows with
terminal `NEWA`, and divides a fixed `$16,000` release budget equally across
all exact-mapped issuers for next-open through tenth-session-close replay.
Fresenius Kabi was explicitly excluded after audit because FMS is not its
economic parent. Gate 4 rejected the sleeve, so its temporary `run.py` wiring
was removed.

| Decision point | Shared source | Backtester use | Production use | Allowed difference |
| --- | --- | --- | --- | --- |
| Rejected Orange Book fresh-NEWA release basket | `orange_book_newa_release_basket_paper_sleeve.py`, `data/non_ohlcv/fda_orange_book_newa/` | the experiment runner may replay only the frozen 19-PDF manifest with exact SHA-256 verification, the official HTTP availability clock, event-date issuer mapping, one issuer leg per release, equal release budget, next-open entry, fixed 10-session close, and 35bps round-trip cost | no daily adapter is retained and `run.py` does not call the helper; the policy cannot alter candidates, orders, ranking, sizing, exits, watchlists, LLM, or news | the helper retains a default-off seed/forward lifecycle callable for reproducibility, but canonical production accumulates no Orange Book decisions; any future observer wiring or activation requires a separately authorized experiment and new evidence |

## Entity-Theme News Prospective First-Seen Observer

`exp-20260713-003` adds a production-visible, default-off evidence observer for
the entity-theme news lead. Policy availability is the timestamp at which the
daily policy first observes an exact URL (`first_seen_at`); source
`published_at` is retained only as metadata and may never backdate a decision.
Each new exact URL receives one stable decision ID and a fixed `$4,000` paper
event notional split equally across its unique mapped tickers. Outcomes use a
next-session-open entry and fixed 10-trading-session exit. This surface is
evidence-only: `trade_enabled=false`, and it cannot change live/default
orders, core universe, ranking, sizing, exits, watchlists, or LLM/news policy.

| Decision point | Shared source | Backtester use | Production use | Allowed difference |
| --- | --- | --- | --- | --- |
| Default-off entity-theme prospective first-seen observer | `entity_theme_news_event_forward_observer.py`, `run.py` | canonical core backtests do not consume or trade this surface; any future replay must use persisted policy-time `first_seen_at`, one stable exact-URL decision, equal unique-ticker legs sharing `$4,000`, next-session-open entry, and fixed 10-session exit; `published_at` remains metadata only | daily run appends unseen exact-URL decisions idempotently, advances pending outcomes only from available market sessions, and emits observer summaries with `trade_enabled=false` | production may have pending rows without future prices while a completed replay has settled rows; neither path may use `published_at` as availability or feed orders/ranking/sizing/exits; performance evaluation remains parked until >=75 settled unique-URL events across >=15 decision dates and >=3 themes, max theme share <=30%, with complete cash/SPY/QQQ outcomes |

## Rejected SEC Item 1.01 Contract-Relation Paper Candidate

`exp-20260703-019` tested promotion of the fixed `exp-20260703-018`
observed-only SEC 8-K Item 1.01 issuer-self contract-relation lead into
`quant/sec_item101_contract_relation_paper_sleeve.py` plus a daily
default-off snapshot in `run.py`, but Gate 4 rejected the candidate. Any
historical replay or retained daily observation must use the same frozen
helper semantics: local `sec_contract_relation_provenance` rows, `accepted_at`
mapped to `usable_trade_date` as the public-archive PIT proxy, specific
relation phrases only, one best row per accession, the fixed relation-priority
ordering, top-1 accession per usable trade date, `$4,000` paper notional,
first available open on or after the usable date, 10-trading-session close
exit, slippage, and round-trip cost. Daily observation, if retained, may emit
pending rows without future exit bars, but it may fill, advance, or close the
paper ledger only from exact `as_of` OHLCV rows. This is not an accepted alpha
and must remain observe-only: `trade_enabled=false`, no live/default orders,
no core universe/ranking/sizing/exit/watchlist/LLM/news changes, and no
prompt-facing `trend_signals_dict` entry. A valid retry requires materially
more closed forward rows or a genuinely different source/gate shape; do not
retune relation buckets, regexes, item codes, top-N, notional, hold days, or
response curves on the same frozen sample.

## Companyfacts Cost-Liquidity Paper Support

`exp-20260601-030` promoted the Companyfacts cost-liquidity support field into
`quant/fundamental_growth_rs_paper_sleeve.py`. Backtests and production must
use the same shared default-off paper adapter semantics: already-selected
`FUNDAMENTAL_GROWTH_RS_PAPER` candidates receive `1.05x` paper notional only
when the signal-day OHLCV row shows `avg_dollar_volume_20 >= $200m` and
`(high-low)/close <= 0.10`. The adapter emits `cost_liquidity_*` candidate
metadata and a `cost_liquidity` snapshot summary. It remains observe-only:
`trade_enabled=false`, live/default orders disabled, and no core universe,
ranking, sizing, exit, LLM/news, or watchlist path may diverge between replay
and production.

## Companyfacts Sector-Residual Paper Support

`exp-20260602-010` promoted the positive `exp-20260602-009` sector-residual
support lead into `quant/fundamental_growth_rs_paper_sleeve.py`. Backtests and
production must use the same shared default-off paper adapter semantics:
already-selected `FUNDAMENTAL_GROWTH_RS_PAPER` candidates receive `1.05x`
paper notional only when their signal-date close-to-close 20-day return exceeds
the persisted public-sector median by at least `3pp` and the sector has at
least `5` same-date return observations. The source of sector labels is the
offline deterministic `data/reference/broad_market_sector_map.json` cache, and
all returns are computed from OHLCV rows with `date <= signal_date`. The adapter
emits `sector_residual_*`, `companyfacts_sector_residual_*`, and a
`sector_residual` snapshot summary. It remains observe-only:
`trade_enabled=false`, live/default orders disabled, and no core universe,
ranking, sizing, exit, LLM/news, or watchlist path may diverge between replay
and production.

## Rejected Companyfacts Peer-Confirmed Filing Drift Adapter Candidate

`exp-20260605-015` tested the production-realistic version of the positive
`exp-20260605-014` broad Companyfacts same-industry peer-confirmation lead.
It failed Gate 4, so there is no active production/default-off adapter for this
family. The failed replay is the parity guardrail: production cannot use
reverse-chronology standard-window cooldown behavior where later-window
selections suppress earlier-window candidates. Any future retry must use
chronological same-ticker cooldown semantics from the start, must not be wired
into `run.py`, reports, attribution, watchlists, ranking, sizing, exits, or
orders before passing Gate 1-4, and must treat the current shared adapter
candidate module as experiment-only evidence.

## SBC Burden Improvement Paper Adapter

`exp-20260616-015` promoted the positive `exp-20260616-014` replay lead into
`quant/sbc_burden_improvement_paper_sleeve.py`. Backtests and production
observation must use the same shared default-off paper adapter semantics: raw
SEC Companyfacts annual stock-based compensation, revenue, and gross-profit
facts are admitted only when their filed date is `<= signal_date`; the current
SBC/revenue ratio must improve versus the prior annual period using the same
SBC tag; revenue, gross profit, gross margin, current SBC burden, and fact-age
guards are fixed; signal-date OHLCV must pass the same price, ADV20,
signal-day return, close-location, realized-volatility, and SPY-relative
20/60-day leadership gates. Historical replay must require a 10-trading-day
exit bar before accepting a closed target trade; daily production may emit an
observe-only same-day pending candidate without future bars, but cannot fill,
advance, or close paper ledger state unless the ticker has an exact `as_of`
OHLCV row. The adapter is default-off and paper-only: fixed `$4,000` paper
notional, top-1/day, 10-trading-day same-ticker cooldown, next-open paper
entry, 10-trading-day close exit, slippage plus round-trip cost, concentration
guard before promotion, and forward replacement-value gate. It remains
observe-only: `trade_enabled=false`, no live/default orders, no core universe
expansion, and no core ranking, sizing, exit, watchlist, LLM/news, or
activation behavior may diverge between replay and production.

SBC burden-improvement decision matrix addendum:

| Decision point | Shared source | Backtester use | Production use | Allowed difference |
| --- | --- | --- | --- | --- |
| Default-off SBC burden-improvement paper sleeve | `sbc_burden_improvement_paper_sleeve.py`, `run.py` | default core backtests do not trade it; historical evidence comes from positive `exp-20260616-014` and accepted shared-helper promotion `exp-20260616-015`; replay must use the shared helper with raw SEC Companyfacts filed-date `<= signal_date` annual SBC/revenue/gross-profit facts, same-SBC-tag prior-period comparison, fixed dilution-quality gates, signal-date SPY-relative OHLCV confirmation, top-1/day, fixed `$4,000` paper notional, 10-trading-day same-ticker cooldown, next-open paper entry, 10-trading-day close exit, costs, and concentration guard before promotion | daily observation derives candidates from the same broad-market free-OHLCV universe plus `SPY`, reads the same raw Companyfacts cache and warehouse CIK map, may emit same-day pending candidates without future exit bars, and advances pending/open/closed paper ledger state only when exact `as_of` OHLCV rows exist | observe-only; no core universe expansion, no live/default orders, no core ranking/sizing/exit/watchlist/LLM/news changes, and live activation requires >= 30 closed forward 10-day paper trades, positive forward PnL, replacement value, and kill-switch parity under the declared envelope |

## Supplier-Financing Debt-Relief Risk-Scaled Paper Adapter

`exp-20260620-009` accepts the production-faithful shared `$4,000` version of
the supplier-financing/debt-relief risk-scaled lead into
`quant/supplier_financing_debt_relief_paper_sleeve.py`. `exp-20260620-008`
rejected exact promotion of the larger private `exp-20260620-007` replay
magnitude; that private magnitude is retained only as a diagnostic drift.
Backtests and production observation must use the same shared default-off
paper adapter semantics: raw SEC Companyfacts quarterly accounts-payable DPO
extension and annual principal debt/revenue burden relief must both be known by
filed date `<= signal_date`; signal-date OHLCV confirmation, top-1/day,
10-trading-day same-ticker cooldown, next-open paper entry, 10-trading-day
close exit, slippage, round-trip cost, and the one-way PIT 20-day
volatility/ADV20 paper-notional scalar are fixed. Production daily observation
may emit same-day pending candidates without future exit bars, but historical
replay must require a 10-trading-day exit bar before counting a closed target
trade. The sleeve remains observe-only: `trade_enabled=false`, no live/default
orders, no core universe expansion, and no core ranking, sizing, exit,
watchlist, LLM/news, or activation behavior may diverge between replay and
production.

Supplier-financing debt-relief decision matrix addendum:

| Decision point | Shared source | Backtester use | Production use | Allowed difference |
| --- | --- | --- | --- | --- |
| Default-off supplier-financing debt-relief risk-scaled paper sleeve | `supplier_financing_debt_relief_paper_sleeve.py`, `run.py` | default core backtests do not trade it; full-stack evidence comes from `exp-20260620-009`; replay must use the shared helper with the fixed `exp-20260620-005` DPO+debt-relief source, `$4,000` base paper notional, and the `exp-20260620-007` PIT volatility/liquidity notional envelope | daily observation derives candidates from the broad-market free-OHLCV universe plus `SPY`, reads the same raw Companyfacts cache and warehouse CIK map, may emit same-day pending candidates without future exit bars, and advances pending/open/closed paper ledger state only when exact `as_of` OHLCV rows exist | observe-only; no live/default orders, no core ranking/sizing/exit/watchlist/LLM/news changes, and live activation requires >= 30 closed forward 10-day paper trades, positive forward PnL, replacement value, and kill-switch parity under the declared envelope |

## Post-Earnings Underpriced Drift Paper Adapter

`exp-20260602-026` promoted the positive `exp-20260602-023` lead into
`quant/post_earnings_underpriced_drift_paper_sleeve.py`. Backtests and
production must use the same shared default-off paper adapter semantics:
positive EPS surprise transitions are detected from daily earnings snapshots
only when the prior snapshot had `days_to_earnings <= 7`, the current snapshot
has `days_to_earnings >= 20`, and actual EPS or the surprise-history tail
changed. A paper candidate can be admitted only in the 0-5 trading days after
that event, with average dollar volume >= `$40m`, close above prior 50-day
average, close-location >= `0.55`, 20-day RS vs SPY > `0`, event-to-signal
return and excess vs SPY >= `0`, and pre-event 20-day ticker return minus SPY
return <= `0`. The adapter is default-off and paper-only: fixed `$10k` base
paper notional, top-1/day, next-open paper entry, 10-trading-day close exit,
forward replacement-value gate, `trade_enabled=false`, and no live/default
orders, core ranking, sizing, exit, LLM/news, or watchlist changes.

`exp-20260602-027` adds one shared default-off paper support field on top of
that adapter: already-selected candidates receive `1.10x` paper notional only
when signal-date `avg_dollar_volume_20d >= $1B`. The field is computed from
the prior 20 trading days of OHLCV rows before next-open paper entry. The
adapter emits `high_liquidity_support` metadata and a high-liquidity support
snapshot summary. It remains observe-only: `trade_enabled=false`, no
live/default orders, and no core ranking/sizing/exit/LLM/news/watchlist path may
diverge between replay and production.

`exp-20260603-004` adds one additional shared default-off paper support field
on top of the same adapter: already-selected candidates receive another `1.05x`
paper-notional scalar only when signal-date 20-day return is at least the
public-sector median, with at least `3` same-sector return observations from
`data/reference/broad_market_sector_map.json`. The adapter emits
`sector_residual_*` candidate metadata and a `sector_residual_support` snapshot
summary. It remains observe-only with the same no-live-orders boundary.

`exp-20260603-022` adds one more shared default-off paper support field on the
same adapter: already-selected candidates receive another `1.05x` paper-notional
scalar only when `core_entry_tickers_by_date` is available and the signal date
has no same-day core A/B entry overlap for that ticker. `run.py` supplies this
context from the selected core entry signals after `plan_entry_candidates`;
historical replay must pass the same date-keyed selected-core ticker map into
the shared helper. The adapter emits `non_core_overlap_*` candidate metadata
and a `non_core_overlap_support` snapshot summary. It remains observe-only:
`trade_enabled=false`, no live/default orders, and no core universe, ranking,
sizing, exit, watchlist, LLM/news, or activation behavior may diverge between
replay and production.

## Macro Relief Leadership Paper Adapter

`exp-20260606-020` promoted the positive `exp-20260606-019` macro relief top-2
stock leadership lead into `quant/macro_relief_leadership_paper_sleeve.py`.
Backtests and production must use the same shared default-off paper adapter
semantics: the fixed official CPI/FOMC/NFP calendar, same-day `SPY` and `QQQ`
relief-return plus close-location gates, broad-market sector-known liquid stock
universe feed, stock leadership score fields, same-day selected-core ticker
overlap exclusion, top-2/day selection, same-ticker cooldown, next-open paper
entry, 10-trading-day close exit, slippage plus round-trip costs, and forward
paper gate. The adapter emits macro context, candidate-universe coverage,
pending/open/closed paper ledger state, default-off alpha-attribution metadata,
and a human-report block. It remains observe-only: `trade_enabled=false`, no
live/default orders, and no core universe, ranking, sizing, exit, watchlist,
LLM/news, or activation behavior may diverge between replay and production.

## Volatility Relief Leadership Paper Adapter

`exp-20260607-019` promoted the positive `exp-20260607-018` VIXY volatility
relief stock-leadership lead into
`quant/volatility_relief_stock_leadership_paper_sleeve.py`. Backtests and
production must use the same shared default-off paper adapter semantics:
same-day `VIXY` selloff and weak close-location gate, same-day `SPY` and `QQQ`
risk-relief confirmation, broad-market sector-known liquid stock universe,
stock leadership score fields, same-day selected-core ticker overlap
exclusion, top-2/day selection, same-ticker cooldown, next-open paper entry,
10-trading-day close exit, slippage plus round-trip costs, and forward paper
gate. The adapter emits volatility-relief context, candidate-universe
coverage, pending/open/closed paper ledger state, default-off
alpha-attribution metadata, and a human-report block. It remains observe-only:
`trade_enabled=false`, no live/default orders, and no core universe, ranking,
sizing, exit, watchlist, LLM/news, or activation behavior may diverge between
replay and production.

## MOVE Rate-Volatility Relief Paper Adapter

`exp-20260711-004` promotes the positive `exp-20260711-002` MOVE replay lead
into `quant/move_rate_volatility_relief_paper_sleeve.py`. Historical replay
and daily observation must use the same fixed first MOVE close below its
trailing 20-session mean, the unchanged `exp-20260607-018` sector-known liquid
stock-leadership selector, same-day selected-core same-ticker exclusion,
top-2/day, `$4,000` paper notional, next-open entry, 10-session close,
same-ticker cooldown, slippage, and round-trip costs. Daily delivery uses the
Yahoo `^MOVE` mirror and records it internally as `MOVE`; the signal is known
only after the signal-day close. The adapter emits context, pending/open/closed
paper state, attribution, and report output with `trade_enabled=false`. It does
not enter the accepted-helper allocator and cannot change live/default orders,
core universe, ranking, sizing, exits, watchlists, or LLM/news behavior.

## Industry-Relative Laggard Repair Paper Adapter

`exp-20260607-008` promoted the positive `exp-20260607-007`
industry-relative laggard repair lead into
`quant/industry_relative_laggard_repair_paper_sleeve.py`. Backtests and
production must use the same shared default-off paper adapter semantics: the
broad-market sector-known liquid stock universe, persisted public industry or
sector groups, signal-date `SPY` OHLCV, group 20-day relative-strength medians,
group 5-day repair context, individual lag/reclaim fields, same-day selected
core ticker overlap disclosure, top-1/day, fixed `$4,000` paper notional,
same-ticker cooldown, next-open paper entry, 10-trading-day close exit,
slippage plus round-trip cost, and concentration guard before promotion.
Historical replay must require the target ticker's 10-trading-day exit bar
before including it in group medians or candidates; daily production may emit
observe-only same-day pending candidates without future bars, but cannot fill,
advance, or close paper ledger state unless exact `as_of` OHLCV rows are
available. The adapter emits industry-repair context, candidate-universe
coverage, pending/open/closed paper ledger state, default-off
alpha-attribution metadata, and a human-report block. It remains observe-only:
`trade_enabled=false`, no live/default orders, and no core universe, ranking,
sizing, exit, watchlist, LLM/news, or activation behavior may diverge between
replay and production.

## Industry Stable Core-Flow Paper Adapter

`exp-20260608-008` promoted the positive `exp-20260608-007`
industry-stable core-flow lead into
`quant/industry_stable_core_flow_paper_sleeve.py`. Backtests and production
must use the same shared default-off paper adapter semantics: broad-market
sector-known liquid stock universe, persisted public industry or sector groups,
signal-date `SPY` OHLCV, stable/strong industry group medians, stable leader
fields, same-day selected core A/B entry-flow confirmation, same-ticker selected
core overlap exclusion, top-1/day, fixed `$4,000` paper notional, 15-trading-day
same-ticker cooldown, next-open paper entry, 10-trading-day close exit,
slippage plus round-trip cost, and concentration guard before promotion.
Historical replay must require the target ticker's 10-trading-day exit bar
before accepting a closed target trade; daily production may emit observe-only
same-day pending candidates without future bars, but cannot fill, advance, or
close paper ledger state unless exact `as_of` OHLCV rows are available. The
adapter emits industry-stable core-flow context, candidate-universe coverage,
pending/open/closed paper ledger state, default-off alpha-attribution metadata,
and a human-report block. It remains observe-only: `trade_enabled=false`, no
live/default orders, and no core universe, ranking, sizing, exit, watchlist,
LLM/news, or activation behavior may diverge between replay and production.

## Narrow-Range Compression Breakout Paper Adapter

`exp-20260608-013` promoted the positive `exp-20260608-012` replay lead into
`quant/narrow_range_compression_breakout_paper_sleeve.py`. Backtests and
production observation must use the same shared default-off paper adapter
semantics: broad-market sector-known liquid stock universe, signal-date `SPY`
OHLCV, prior 10-day range compression versus 40-day reference range,
signal-day range expansion, positive signal-day return, high close-location,
volume confirmation, SPY-relative 20-day and 60-day trend guards, 5-day and
20-day extension guards, top-1/day, fixed `$4,000` paper notional,
10-trading-day same-ticker cooldown, same-ticker selected core overlap
exclusion, next-open paper entry, 10-trading-day close exit, slippage plus
round-trip cost, and concentration guard before promotion. Historical replay
must require the target ticker's 10-trading-day exit bar before accepting a
closed target trade; daily observation may emit observe-only same-day pending
candidates without future bars, but cannot fill, advance, or close paper ledger
state unless exact `as_of` OHLCV rows are available. The helper emits
compression-breakout context, candidate-universe coverage, pending/open/closed
paper ledger state, and forward gate metadata. It remains observe-only:
`trade_enabled=false`, no live/default orders, and no core universe, ranking,
sizing, exit, watchlist, LLM/news, or activation behavior may diverge between
replay and production.

## Turn-of-Month Liquid Leadership Paper Adapter

`exp-20260609-027` promoted the positive `exp-20260609-026` replay lead into
`quant/turn_of_month_liquid_leadership_paper_sleeve.py`. Backtests and
production observation must use the same shared default-off paper adapter
semantics: broad-market sector-known liquid stock universe, signal-date `SPY`
OHLCV, last trading day through first three trading days of a month,
SPY-relative 20-day and 60-day leadership guards, positive signal-day return,
high close-location, bounded volume ratio, bounded 5-day and 20-day extension,
bounded realized volatility, same-ticker selected core overlap exclusion,
top-1/day, fixed `$4,000` paper notional, 10-trading-day same-ticker cooldown,
next-open paper entry, 10-trading-day close exit, slippage plus round-trip
cost, and concentration guard before promotion.

Historical replay must pass the full loaded trading calendar into the shared
helper so last-trading-day labels are computed from an untruncated calendar.
Daily observation may emit observe-only same-day pending candidates without
future bars, but it must not infer last-trading-day labels from truncated OHLCV.
As of `exp-20260704-009`, the daily prep wrapper supplies deterministic
`known_month_end_dates` when `as_of` is the last regular US equity session of
the month; explicit `calendar_dates` or `known_month_end_dates` remain valid
for replay/probe calls. First three trading days can be labeled from the
observed daily sequence. The helper emits turn-of-month context,
candidate-universe coverage, pending/open/closed paper ledger state, and
forward gate metadata. It remains observe-only:
`trade_enabled=false`, no live/default orders, and no core universe, ranking,
sizing, exit, watchlist, LLM/news, or activation behavior may diverge between
replay and production.

## 52-Week-High Proximity Core-Flow Paper Adapter

`exp-20260610-008` promoted the positive `exp-20260610-007` replay lead into
`quant/fiftytwo_week_high_proximity_paper_sleeve.py` through the full-stack
candidate-pool contract. Backtests and production observation must use the same
shared default-off paper adapter semantics: broad-market sector-known liquid
stock universe, signal-date `SPY` OHLCV, close within 3% of the trailing
252-trading-day high AND a new 60-day-high breakout, 20-day SPY-relative
leadership, positive signal-day return, high close-location, bounded volume
ratio, bounded 5-day extension, bounded realized volatility, same-day core A/B
entry-flow confirmation, same-ticker selected core overlap exclusion,
top-1/day, fixed `$4,000` paper notional, 10-trading-day same-ticker cooldown,
next-open paper entry, 10-trading-day close exit, slippage plus round-trip
cost, and concentration guard before promotion.

The candidate rule needs at least 252 prior trading days of OHLCV; with less
history the rule fails closed in both historical replay and daily snapshots.
Historical replay loads a deep snapshot (470 calendar days of lookback) of
past bars only. The sleeve also implements a parity-tested kill switch:
realized peak-to-trough drawdown of the closed paper ledger at 8% of committed
paper capital (hard kill) or 5% (sleeve drawdown stop), plus a positive-PnL
concentration kill; when triggered the sleeve stops creating new pending paper
entries. It remains observe-only: `trade_enabled=false`, no live/default
orders, and no core universe, ranking, sizing, exit, watchlist, LLM/news, or
activation behavior may diverge between replay and production.

## Accepted-Helper Source-Priority Allocator Paper Adapter

`exp-20260611-005` promotes the positive replay lead from `exp-20260611-004`
into `quant/accepted_helper_source_priority_allocator_paper_sleeve.py`.
Backtests and production observation must use the same shared default-off
allocator semantics: accepted lagged cross-source consensus rows are admitted
as fixed rank 1, followed by volatility relief, rolling peer shock,
turn-of-month, industry-relative laggard repair, revision-surprise
low-extension, narrow-range compression, and industry-stable core-flow. The
allocator selects top-1/day, uses fixed `$4,000` base paper notional with only
the accepted shared `source_notional_scalar` overlays, applies the
12-trading-day same-ticker cooldown, and keeps each underlying helper's own
PIT data boundary and candidate gates.

Historical replay sources lagged-consensus rows from the accepted
`exp-20260604-009` lagged independent source-family artifact; daily production
passes the shared `free_data_cross_source_consensus_paper_sleeve` snapshot into
the same allocator source family. The helper emits source-priority context,
candidate/rejection metadata, pending/open/closed paper ledger state, and
forward paper gate metadata. It remains observe-only: `trade_enabled=false`,
no live/default orders, and no core universe, ranking, sizing, exit, watchlist,
LLM/news, or activation behavior may diverge between replay and production.

## Decision Matrix

| Decision point | Shared source | Backtester use | Production use | Allowed difference |
| --- | --- | --- | --- | --- |
| Universe and features | `data_layer.py`, `feature_layer.py` | historical/snapshot OHLCV | latest OHLCV | data date only |
| Earnings proximity and post-earnings continuation data | `data_layer.py`, `backtester.py`, `feature_layer.py`, `risk_engine.py`, `signal_engine.py`, `run.py` | canonical replay uses daily production earnings snapshots for `next_earnings_date` and `days_to_earnings` when present; when same-day actual EPS is known and a later future earnings date exists, it exposes `last_earnings_date`, `days_since_last_earnings`, `post_earnings_continuation_confirmed`, and `post_earnings_event_date`, then rolls forward DTE to the next future earnings date | daily run emits the production earnings snapshot used by the live feature path and the same continuation fields; same-day continuation is allowed only after actual EPS is known | fallback only for missing archived snapshots; canonical fixed-window Gate 1 metrics use PIT snapshot DTE as of `exp-20260601-025` plus explicit post-earnings continuation semantics as of `exp-20260602-003` |
| Default-off post-earnings underpriced drift paper sleeve | `post_earnings_underpriced_drift_paper_sleeve.py`, `run.py`, `default_off_alpha_attribution.py`, `report_generator.py` | default core backtests do not trade it; historical evidence comes from accepted `exp-20260602-026`, accepted `exp-20260602-027` high-liquidity support, accepted `exp-20260603-004` sector-residual support, and accepted `exp-20260603-022` non-core-overlap support, and must use the shared helper with daily earnings snapshot transition detection, the fixed positive-surprise drift gates, `pre_event_rs20_vs_spy <= 0`, fixed `$10k` base paper notional, `1.10x` paper support only when `avg_dollar_volume_20d >= $1B`, additional `1.05x` paper support only when signal-date 20-day return is at least the public-sector median with at least `3` sector-member return observations, additional `1.05x` paper support only when same-day selected core A/B ticker context is available and has no same-ticker overlap, top-1/day, next-open paper entry, 10-trading-day close exit, and concentration guard before promotion | daily run derives candidates from the already-loaded daily OHLCV universe plus `SPY`, loads local earnings snapshot history and `data/reference/broad_market_sector_map.json`, receives date-keyed selected core entry ticker context from `plan_entry_candidates`, emits candidate/audit/high-liquidity-support/sector-residual-support/non-core-overlap-support metadata, pending/open/closed paper ledger state, replacement-value report, forward paper gate, default-off alpha-attribution surface, and human-report block | observe-only; no core universe expansion, no live orders, no core ranking/sizing/exit changes, no LLM/news changes, and activation requires closed forward replacement-value outcomes plus a separate Gate 1-4 trade adapter |
| Default-off volatility relief leadership paper sleeve | `volatility_relief_stock_leadership_paper_sleeve.py`, `run.py`, `default_off_alpha_attribution.py`, `report_generator.py` | default core backtests do not trade it; historical evidence comes from accepted `exp-20260607-019` and must use the shared helper with fixed VIXY selloff / SPY+QQQ relief gates, broad-market sector-known liquid stock universe, selected-core same-ticker overlap disclosure, top-2/day, next-open paper entry, 10-trading-day close exit, fixed `$4,000` paper notional, costs, cooldown, and concentration guard before promotion | daily run derives candidates from the already-loaded broad-market OHLCV universe plus exact `SPY`/`QQQ`/`VIXY`, receives same-day selected core entry ticker context from `plan_entry_candidates`, emits volatility-relief context, pending/open/closed paper ledger state, forward paper gate, default-off alpha-attribution surface, and human-report block | observe-only; no core universe expansion, no live orders, no core ranking/sizing/exit changes, no LLM/news changes, and activation requires closed forward replacement-value outcomes plus a separate Gate 1-4 activation envelope |
| Default-off MOVE rate-volatility relief leadership paper sleeve | `move_rate_volatility_relief_paper_sleeve.py`, `run.py`, `default_off_alpha_attribution.py`, `report_generator.py` | default core backtests do not trade it; historical evidence comes from positive `exp-20260711-002` and accepted shared-paper promotion `exp-20260711-004`; replay must use the fixed MOVE20 first-cross-below event and unchanged stock selector, top-2/day, next-open entry, 10-session close, `$4,000` paper notional, costs, and cooldown | daily run loads Yahoo `^MOVE` point-in-time close history, maps it to the shared `MOVE` context, receives selected-core overlap context, and emits a separate paper ledger, attribution surface, and report block | observe-only and excluded from accepted-helper allocation; no live/default orders or core/LLM behavior changes; live eligibility requires at least 30 closed forward trades, positive replacement value, and kill-switch parity under the declared envelope |
| Default-off turn-of-month liquid leadership paper sleeve | `turn_of_month_liquid_leadership_paper_sleeve.py`, `run.py` | default core backtests do not trade it; historical evidence comes from positive `exp-20260609-026` and accepted shared-helper promotion `exp-20260609-027`; replay must use the shared helper with full loaded trading-calendar month labels, sector-known liquid stock universe, `SPY`-relative 20-day and 60-day leadership, high close-location, volume and volatility guards, same-ticker selected core overlap exclusion, top-1/day, fixed `$4,000` paper notional, 10-trading-day same-ticker cooldown, next-open paper entry, 10-trading-day close exit, costs, and concentration guard before promotion | daily observation derives candidates from the same broad-market free-OHLCV universe plus `SPY`; first-three-trading-day labels may use the observed sequence, but last-trading-day labels require explicit `calendar_dates` or `known_month_end_dates`; without explicit month-end context the month-end route fails closed; `exp-20260610-005` wires the snapshot into daily quant artifacts so the accepted-helper allocator can consume the same source surface | observe-only; no core universe expansion, no live/default orders, no core ranking/sizing/exit/watchlist/LLM/news changes, and activation requires daily forward closed replacement-value outcomes plus a separate Gate 1-4 activation envelope |
| Default-off 52-week-high proximity core-flow paper sleeve | `fiftytwo_week_high_proximity_paper_sleeve.py` | default core backtests do not trade it; historical evidence comes from positive `exp-20260610-007` and accepted full-stack promotion `exp-20260610-008`; replay must use the shared helper with a >= 252-prior-trading-day deep snapshot of past bars, trailing 252-day-high proximity (close >= 97% of the 252-day high), new 60-day-high breakout, sector-known liquid stock universe, `SPY`-relative 20-day leadership, signal-day return/close-location/volume/volatility guards, same-day core A/B entry-flow confirmation, same-ticker selected core overlap exclusion, top-1/day, fixed `$4,000` paper notional, 10-trading-day same-ticker cooldown, next-open paper entry, 10-trading-day close exit, costs, and concentration guard before promotion | daily observation derives candidates from the same broad-market free-OHLCV universe plus `SPY` and same-day selected core entry context; with fewer than 252 prior trading days the rule fails closed; the parity-tested kill switch (8% committed-capital realized drawdown hard kill, 5% sleeve stop, positive-PnL concentration kill) blocks new pending paper entries when triggered | observe-only; no core universe expansion, no live/default orders, no core ranking/sizing/exit/watchlist/LLM/news changes, and live activation requires >= 30 closed forward 10-day paper trades, positive forward PnL, and replacement value under the declared execution envelope (config/checklist change, not a new alpha search) |
| Read-only market-state / sentiment analysis | `regime_engine.py`, `sentiment_surface.py`, `market_state_analysis.py`, `backtest_sentiment_attribution.py`, `report_generator.py` | emits `result["market_state_sentiment_attribution"]` after canonical metrics are computed; diagnostic only | emits `market_state_snapshot` in daily quant artifacts and report; diagnostic only | no entry, ranking, sizing, exit, heat, LLM/news, or order behavior may read this block without a separate Gate 1-4 experiment |
| Default-off alpha attribution report | `default_off_alpha_attribution.py`, `report_generator.py` | not used by canonical core metrics; experiment/replay artifacts may use it as read-only activation/blocker context | daily run emits `default_off_alpha_attribution` in quant artifacts and the human report | read-only blocker rollup only; no entry, ranking, sizing, exit, heat, LLM/news, or order behavior may read this block without a separate Gate 1-4 experiment |
| Universe governance / pilot eligibility | `universe_manager.py`, `universe_adapter.py`, `pilot_sleeve.py` | point-in-time disclosure by default; `--include-pilot-sleeve` replays trade-enabled pilot eligibility day by day | daily run can emit separate `pilot_signals` for trade-enabled pilot records | pilot started on `2026-05-01`, so pre-activation historical windows cannot treat it as then-known production universe |
| Entry signal generation | `signal_engine.py` | required | required | none |
| Risk enrichment / targets | `risk_engine.py`, `regime_exit.py` | required | required | none |
| Sector-relative sizing features | `feature_layer.py`, `risk_engine.py`, `portfolio_engine.py` | required | required | data date only |
| Position sizing | `portfolio_engine.py` | required | required | fill price may differ |
| SPY-relative leader position cap | `portfolio_engine.py` | required | required | none |
| Financials sector-leader trend position cap | `portfolio_engine.py` | required | required | none |
| Financials mid-dispersion sector-leader trend position cap | `portfolio_engine.py` | required | required | none |
| Commodity near-high trend position cap | `portfolio_engine.py` | required | required | none |
| RS20 entry-state sizing top-up | `risk_engine.py`, `portfolio_engine.py` | required | required | none |
| Signal-day own-green-candle sizing top-up | `feature_layer.py`, `risk_engine.py`, `portfolio_engine.py` | required | required | data date only |
| RS60 top-quintile stock sizing top-up | `feature_layer.py`, `risk_engine.py`, `portfolio_engine.py` | required | required | data date only |
| Price-vs-200MA extension sizing top-up | `feature_layer.py`, `risk_engine.py`, `portfolio_engine.py` | required | required | data date only |
| Trend-only price-vs-200MA extension sizing top-up | `feature_layer.py`, `risk_engine.py`, `portfolio_engine.py` | required | required | data date only |
| Core confirmed-quality sizing top-up | `risk_engine.py`, `portfolio_engine.py` | required | required | data date only |
| Green-deceleration quality non-consumer sizing top-up | `risk_engine.py`, `portfolio_engine.py` | required | required | data date only |
| Technology trend DTE residual risk sizing | `portfolio_engine.py` / `constants.py` | required | required | none |
| TSM core long risk sizing | `portfolio_engine.py` / `constants.py` | required; `tsm_core_risk_multiplier_applied` is captured in sizing attribution | required through the same `portfolio_engine.size_signals` path used by production | ticker-specific only; do not generalize to semiconductors without a separate experiment |
| ISRG core long risk sizing | `portfolio_engine.py` / `constants.py` | required; `isrg_core_risk_multiplier_applied` is captured in sizing attribution | required through the same `portfolio_engine.size_signals` path used by production | ticker-specific only; do not generalize to Healthcare without a separate experiment |
| Clean SPY-relative signal-day sizing top-up | `risk_engine.py`, `portfolio_engine.py` | required | required | data date only |
| Clean SPY-relative signal-day position cap | `portfolio_engine.py` | required | required | data date only |
| Clean SPY cap-only leader position cap | `portfolio_engine.py` | required | required | data date only |
| Clean SPY cap-only RS20 leader position cap | `portfolio_engine.py` | required | required | data date only |
| Pilot sleeve sizing and slot priority | `pilot_sleeve.py` after `portfolio_engine.size_signals` | default off; `--include-pilot-sleeve` applies the shared pilot scalar and `trade_quality_score -> confidence -> risk/reward` slot policy in PIT replay | required for `pilot_signals`; production metadata marks pilot sleeve candidate ranking as strategy-affecting | canonical core backtest stays core-only unless the flag is explicit |
| Pilot outcome attribution | `candidate_competition_logger.py`, `performance_engine.py`, `pilot_sleeve.py`, `report_generator.py` | `--include-pilot-sleeve` computes in-memory direct PnL, cash-relative PnL, replacement value, and risk-adjusted replacement value | daily run reports direct PnL, cash-relative PnL, replacement value, pending counterfactual coverage, and read-only `AI_INFRA_AGGRESSIVE` promotion readiness blockers | backtester replay must not write `data/ledgers/pilot_competition_decisions.jsonl`; production appends real decisions only; promotion readiness cannot change slots/orders without a separate Gate 1-4 experiment |
| SEC negative-reaction event queue | `sec_event_queue.py`, `sec_negative_event_sleeve.py`, `report_generator.py` | default core backtests do not trade it; historical event-sleeve replays must use shared queue semantics before promotion | daily run emits default-off queue plus paper sleeve state/snapshots only | observe-only until forward replacement-value evidence and an explicit shared trade adapter exist |
| SEC governance/procedural event queue | `sec_event_queue.py`, `sec_event_sleeve.py`, `report_generator.py` | default core backtests do not trade it; historical event-sleeve replays must use shared queue semantics before promotion | daily run emits default-off queue plus paper sleeve state/snapshots only | observe-only until forward replacement-value evidence and an explicit shared trade adapter exist |
| SEC financial-report T+1 drift queue | `sec_event_queue.py`, `sec_financial_report_event_sleeve.py`, `report_generator.py` | default core backtests do not trade it; historical replays must use shared queue/sleeve semantics before promotion | daily run emits default-off non-platform financial-report positive T+1 excess >= 1% queue plus paper sleeve state/snapshots at the accepted $15k base notional, with non-10-Q `periodic_report` rows tracked at 1.25x paper notional, 10-Q `periodic_report` rows tracked at 2.00x paper notional, covered `neutral_or_mixed_language` rows with `t1_excess_return_vs_spy <= 2%` tracked with an additional 2.00x neutral-underreaction paper notional scalar, those accepted neutral-underreaction rows with `spy_t1_return >= -0.5%` tracked with an additional 1.50x market-context paper notional scalar, and covered `earnings_release_text` rows with `spy_t1_return >= -0.5%` tracked with an additional 1.10x earnings-release market-context paper notional scalar; as of `exp-20260704-016` the shared queue builder derives the replay-parity cohort (`platform_pool` for the static META/NFLX/GOOG/AMZN/SPOT/DIS/APP pool, else `other_equity`) for rows the daily collector leaves cohort-less, matching the accepted `exp-20260510-023/027` analysis-time derivation, and stamps `cohort_source` for provenance | observe-only until closed forward replacement-value evidence and an explicit shared trade adapter exist |
| Default-off external event overlay bundle | `event_sleeve_bundle.py`, `state_surface_sleeve.py`, `form4_event_sleeve.py`, `sec_negative_event_sleeve.py`, `sec_event_sleeve.py`, `report_generator.py` | default core backtests do not trade it; historical bundle replays must use shared source queues/sleeves, the shared state-surface add-on annotation, rotation-surface paper tilt, front-rank rotation paper tilt, broad-breadth event paper tilt, sec-governance source-quality paper tilt, negative-reaction event paper tilt, positive-state context paper tilt, non-narrow state-bucket context paper tilt, SEC governance item 5.03 paper haircut, and the shared forward-gated trade-plan helper before promotion | daily run emits aggregate default-off bundle attribution, normalized candidate schema, source-priority dedupe, state-surface paper add-on eligibility, rotation-surface, front-rank rotation, broad-breadth, sec-governance source-quality, negative-reaction, positive-state context, non-narrow state-bucket context, and SEC governance item 5.03 haircut counts, forward gate, kill-switch status, and default-blocked trade-plan status only | observe-only until closed forward outcomes pass the shared gate and the explicit trade adapter is enabled |
| Default-off broad-market leadership paper sleeve | `broad_market_paper_sleeve.py`, `report_generator.py` | default core backtests do not trade it; historical broad-market replays must use the shared `price_floor_40` feature/filter helper, candidate exclusion semantics, `[1.20, 1.00, 0.80]` source-rank paper-notional profile, the shared `ret5 <= 0.02` low-extension `1.15x` paper-notional scalar, the shared `realized_volatility_20 >= 0.055` high-volatility `1.15x` paper-notional scalar, the shared `positive_day_ratio_20 >= 0.55` trend-persistence `1.15x` paper-notional scalar, 20-trading-day paper hold, and concentration guard before promotion | daily run emits the default-off `BROAD_MARKET_LEADERSHIP_PAPER` candidate queue with the shared `[1.20, 1.00, 0.80]` source-rank paper-notional profile, the shared low-extension, high-volatility, and trend-persistence paper-notional metadata/scalars, pending/open/closed paper ledger state, source coverage metadata, forward paper gate, and report block; `data/state/broad_market_paper/universe.json` remains the static feed when present, otherwise `run.py` derives a conservative `broad_market_universe_state_observation_feed_v1` feed from the persisted daily `universe_state` observation records | observe-only until closed forward replacement-value outcomes pass a separate gate and an explicit trade adapter is enabled |
| Default-off macro relief leadership paper sleeve | `macro_relief_leadership_paper_sleeve.py`, `run.py`, `default_off_alpha_attribution.py`, `report_generator.py` | default core backtests do not trade it; historical evidence comes from accepted `exp-20260606-020` and must use the shared helper with official CPI/FOMC/NFP dates, same-day `SPY`/`QQQ` relief and close-location gates, broad-market sector-known liquid stock universe, stock leadership score fields, selected-core same-ticker overlap exclusion, top-2/day, next-open paper entry, 10-trading-day close exit, costs, cooldown, and concentration guard before promotion | daily run derives the candidate universe from the same broad-market paper universe feed, loads `SPY` and `QQQ` OHLCV, emits macro-relief context, candidate-universe coverage, selected/filtered candidates, pending/open/closed paper ledger state, forward paper gate, default-off alpha-attribution surface, and human-report block | observe-only; no core universe expansion, no live/default orders, no core ranking/sizing/exit/watchlist/LLM/news changes, and activation requires closed forward replacement-value outcomes plus a separate Gate 1-4 trade adapter |
| Default-off rolling-correlation peer-shock paper helper | `rolling_corr_peer_shock_paper_sleeve.py`, `run.py`, `default_off_alpha_attribution.py`, `report_generator.py` | default core backtests do not trade it; historical evidence comes from positive `exp-20260606-024` and accepted shared-helper promotion `exp-20260606-025`; replay must use the shared helper with signal-date free OHLCV, 60-prior-trading-day rolling return correlation, same-day core A/B flow confirmation, positive candidate signal-day return, selected-core same-ticker overlap exclusion, top-1/day, fixed `$4,000` paper notional, 10-trading-day same-ticker cooldown, next-open paper entry, 10-trading-day close exit, costs, and concentration guard before promotion | daily run derives candidates from the same broad-market free-OHLCV universe, receives same-day selected core entries from the production entry plan, advances pending/open/closed paper state with the same next-open and 10-trading-day close semantics as historical replay, emits peer-shock context, forward gate, default-off alpha-attribution surface, quant artifact, and human-report block | observe-only; no core universe expansion, no live/default orders, no core ranking/sizing/exit/watchlist/LLM/news changes, and activation requires daily forward closed replacement-value outcomes plus a separate Gate 1-4 trade adapter |
| Default-off industry-relative laggard repair paper sleeve | `industry_relative_laggard_repair_paper_sleeve.py`, `run.py`, `default_off_alpha_attribution.py`, `report_generator.py` | default core backtests do not trade it; historical evidence comes from positive `exp-20260607-007` and accepted shared-helper promotion `exp-20260607-008`; replay must use the shared helper with signal-date free OHLCV, persisted industry/sector group labels, group 20-day relative-strength medians, individual 20-day lag plus same-day reclaim fields, same-day selected-core overlap disclosure, top-1/day, fixed `$4,000` paper notional, 15-trading-day same-ticker cooldown, next-open paper entry, 10-trading-day close exit, costs, and concentration guard before promotion | daily run derives candidates from the same broad-market free-OHLCV universe plus `SPY`, receives same-day selected core entries from the production entry plan, advances pending/open/closed paper state with exact `as_of` OHLCV rows only, emits industry-repair context, forward gate, default-off alpha-attribution surface, quant artifact, and human-report block | observe-only; no core universe expansion, no live/default orders, no core ranking/sizing/exit/watchlist/LLM/news changes, and activation requires daily forward closed replacement-value outcomes plus a separate Gate 1-4 trade adapter |
| Default-off industry stable core-flow paper sleeve | `industry_stable_core_flow_paper_sleeve.py`, `market_state_router.py`, `run.py`, `default_off_alpha_attribution.py`, `report_generator.py` | default core backtests do not trade it; historical evidence comes from positive `exp-20260608-007`, accepted shared-helper promotion `exp-20260608-008`, replay-only state tilt `exp-20260613-005`, and shared-helper state-tilt promotion `exp-20260613-010`; replay must use the shared helper with signal-date free OHLCV, persisted industry/sector group labels, stable/strong group medians, individual stable-leader fields, same-day core A/B flow confirmation, selected-core same-ticker overlap exclusion, top-1/day, base `$4,000` paper notional, shared prior-close `SPY`/`QQQ` market-state router, fixed `mixed|balanced|normal` `1.50x` paper-notional scalar, 15-trading-day same-ticker cooldown, next-open paper entry, 10-trading-day close exit, costs, and concentration guard before promotion | daily run derives candidates from the same broad-market free-OHLCV universe plus exact `SPY` and `QQQ`, receives same-day selected core entries from the production entry plan, applies the same prior-close state-router metadata/scalar to pending rows, advances pending/open/closed paper state with exact `as_of` OHLCV rows only, emits industry-stable core-flow context, state-router summary, forward gate, default-off alpha-attribution surface, quant artifact, and human-report block | observe-only; no core universe expansion, no live/default orders, no core ranking/sizing/exit/watchlist/LLM/news changes, and activation requires daily forward closed replacement-value outcomes plus a separate Gate 1-4 trade adapter |
| Default-off narrow-range compression breakout paper sleeve | `narrow_range_compression_breakout_paper_sleeve.py`, `run.py` | default core backtests do not trade it; historical evidence comes from positive `exp-20260608-012` and accepted shared-helper promotion `exp-20260608-013`; replay must use the shared helper with signal-date free OHLCV, sector-known liquid stock universe, prior 10-day range compression versus 40-day reference range, signal-day range expansion, volume, high close-location, SPY-relative trend guards, 5-day and 20-day extension guards, same-ticker selected core overlap exclusion, top-1/day, fixed `$4,000` paper notional, 10-trading-day same-ticker cooldown, next-open paper entry, 10-trading-day close exit, costs, and concentration guard before promotion | daily observation derives candidates from the same broad-market free-OHLCV universe plus `SPY`, can emit pending rows without future bars, and advances pending/open/closed paper state only with exact `as_of` OHLCV rows; `exp-20260610-005` wires the snapshot into daily quant artifacts so the accepted-helper allocator can consume the same source surface | observe-only; no core universe expansion, no live/default orders, no core ranking/sizing/exit/watchlist/LLM/news changes, and activation requires daily forward closed replacement-value outcomes plus a separate Gate 1-4 trade adapter |
| Default-off distribution-day absorption leadership paper sleeve | `distribution_day_absorption_leadership_paper_sleeve.py`, `run.py` | default core backtests do not trade it; historical evidence comes from positive `exp-20260611-006` and accepted shared-helper promotion `exp-20260611-007`; replay must use the shared helper with recent `SPY`/`QQQ` high-volume distribution-pressure context, sector-known liquid stock universe, signal-day absorption/reclaim fields, SPY/QQQ relative leadership, close-location, volume, extension and volatility guards, same-ticker selected core overlap exclusion, top-1/day, fixed `$4,000` paper notional, 10-trading-day same-ticker cooldown, next-open paper entry, 10-trading-day close exit, costs, and concentration guard before promotion | daily observation derives candidates from the same broad-market free-OHLCV universe plus exact `SPY` and `QQQ`, can emit pending rows without future bars, advances pending/open/closed paper state only with exact `as_of` OHLCV rows, and exposes the snapshot in the daily quant artifact while leaving accepted-helper allocator source priority unchanged | observe-only; no core universe expansion, no live/default orders, no core ranking/sizing/exit/watchlist/LLM/news changes, and activation requires closed forward replacement-value outcomes plus a separate activation-envelope Gate 1-4 if the execution envelope changes |
| Default-off accepted-helper source-priority allocator | `accepted_helper_source_priority_allocator_paper_sleeve.py`, `run.py`, `default_off_alpha_attribution.py`, `report_generator.py` | default core backtests do not trade it; historical evidence comes from positive replay lead `exp-20260610-004`, accepted shared-helper promotion `exp-20260610-005`, accepted revision source extension `exp-20260610-014`, and accepted source-notional scalar overlays through `exp-20260621-007`; replay must use the shared helper with fixed source priority `lagged_cross_source_consensus`, `volatility_relief`, `rolling_peer_shock`, `turn_of_month`, `industry_laggard_repair`, `revision_surprise_low_extension`, `compression`, `industry_stable_core_flow`, top-1 selected paper trade per signal date, 12-trading-day same-ticker cooldown, fixed `$4,000` base paper notional plus accepted source-family scalar overlays only, the underlying helpers' next-open/10-trading-day exits and costs, and concentration/drawdown guards before promotion | daily run receives same-day snapshots from the accepted helper sources, including lagged cross-source consensus and the revision surprise low-extension earnings-snapshot source, emits source coverage, priority audit, source-notional scalar metadata, pending/open/closed paper ledger state, forward paper gate, default-off alpha-attribution surface, quant artifact, and human-report block; source snapshots that fail are represented in source coverage rather than silently substituted | observe-only; no core universe expansion, no live/default orders, no core ranking/sizing/exit/watchlist/LLM/news changes, and activation requires forward closed replacement-value outcomes plus a separate activation-envelope Gate 1-4 experiment |

`exp-20260620-032` amends the accepted-helper allocator with one shared
default-off paper allocation rule: selected `industry_laggard_repair` and
`revision_surprise_low_extension` rows receive a fixed `1.25x`
`source_notional_scalar` (`$5,000` paper notional from the `$4,000` base).
Replay and daily snapshots must expose the same scalar metadata and must not
change source priority, top-1/day selection, same-ticker cooldown, exits, core
trading, LLM/news, watchlists, or live/default orders. The declared paper
execution envelope is now a `$40,000` bucket, `8` max concurrent positions, and
`$5,000` max position notional while `trade_enabled=false`.

`exp-20260621-001` adds the same fixed `1.25x` shared default-off
`source_notional_scalar` for selected `rolling_peer_shock` allocator rows after
the corrected sleeve-independence map in `exp-20260620-033` showed low
cross-sleeve correlation and zero ticker-date overlap. Replay and daily
snapshots must expose the same scalar metadata. This does not change source
priority, selected rows, top-1/day, same-ticker cooldown, exits, core trading,
LLM/news, watchlists, live/default orders, or the paper execution envelope.

`exp-20260621-006` adds the same fixed `1.25x` shared default-off
`source_notional_scalar` for selected `turn_of_month` allocator rows after the
corrected sleeve-independence map showed positive standalone turn-of-month
returns and the current allocator selected turn-of-month rows in all three
canonical windows. Replay and daily snapshots must expose the same scalar
metadata. This does not change source priority, selected rows, top-1/day,
same-ticker cooldown, exits, core trading, LLM/news, watchlists, live/default
orders, or the paper execution envelope.

`exp-20260621-007` adds the same fixed `1.25x` shared default-off
`source_notional_scalar` for selected `lagged_cross_source_consensus` allocator
rows after current allocator attribution showed those rank-1 rows selected in
all three canonical windows with positive realized paper PnL. Replay and daily
snapshots must expose the same scalar metadata. This does not change source
priority, selected rows, top-1/day, same-ticker cooldown, exits, core trading,
LLM/news, watchlists, live/default orders, or the paper execution envelope.

| Default-off revision surprise low-extension paper sleeve | `revision_surprise_low_extension_paper_sleeve.py` | default core backtests do not trade it; historical evidence comes from positive `exp-20260608-011` and accepted shared-helper promotion `exp-20260609-011`; replay must use the shared helper with daily earnings snapshot EPS estimate revision over 20 snapshots, positive historical surprise history, liquid 20-day breakout confirmation, selected-top1 `ret20_excess_spy <= 0.35` with no backup substitution, top-1/day, fixed `$4,000` paper notional, next-open paper entry, 10-trading-day close exit, costs, and concentration guard before promotion | daily observation uses the same helper and the same local earnings snapshot surface, can emit pending rows without future bars, and advances pending/open/closed paper state only with exact `as_of` OHLCV rows; run.py wiring is intentionally unchanged in `exp-20260609-011` | observe-only; no core universe expansion, no live/default orders, no core ranking/sizing/exit/watchlist/LLM/news changes; EPS estimate provenance remains proxy-grade, so activation requires forward closed replacement-value rows, PIT analyst-estimate provenance or analyst-count evidence, and a separate Gate 1-4 activation envelope |
| Default-off AI optical IWM-confirmed paper sleeve | `ai_optical_paper_sleeve.py`, `report_generator.py` | default core backtests do not trade it; historical optical replays must use the governed `ai_optical_connectivity` / `optical_connectivity` cohort, fixed `$10k` paper notional, prior-close 20-trading-day `IWM - SPY >= 0.003` confirmation, no core displacement, and concentration guard before promotion | daily run derives the `AI_OPTICAL_IWM_CONFIRMED_PAPER` feed from persisted `universe_state` observation records, reuses the normal trend/breakout signal stack for paper candidates only, emits IWM/SPY gate metadata, pending/open/closed paper ledger state, replacement-value report, forward paper gate, default-off alpha-attribution surface, and human-report block | observe-only; no core universe expansion, no live orders, no ranking/sizing/exit changes, and activation requires closed forward replacement-value outcomes plus a separate Gate 1-4 trade adapter |
| Default-off QQQ-confirmed volatility-contraction paper sleeve | `volatility_contraction_paper_sleeve.py`, `report_generator.py` | default core backtests do not trade it; historical volatility-contraction replays must use the exp-20260526-007 rank-notional profile `[1.0, 1.25]` on the exp-20260525-037 top-2 candidate expansion and exp-20260525-022 compression/breakout definition, base `$10k` paper notional, same-day `QQQ 20d return > SPY 20d return` close-to-close confirmation, next-open entry, 10-trading-day paper hold, and concentration guard before promotion; `pre_signal_pocket_pivot_seen_10d` from exp-20260525-027 is parity-required metadata only, not a gate | daily run derives up to two ranked candidates from the already-loaded daily OHLCV universe plus `SPY` / `QQQ`, emits QQQ/SPY confirmation, top-N rank metadata, rank-notional profile/scalar/intended-notional metadata, read-only pocket-pivot context fields, pending/open/closed paper ledger state, replacement-value report, forward paper gate, default-off alpha-attribution surface, and human-report block | observe-only; no core universe expansion, no live orders, no core ranking/sizing/exit changes, and activation requires closed forward replacement-value outcomes plus a separate Gate 1-4 trade adapter |
| Default-off volume-breadth breakout paper sleeve | `volume_breadth_breakout_paper_sleeve.py`, `report_generator.py` | default core backtests do not trade it; historical volume-breadth replays must use the exp-20260526-014 shared helper with the exp-20260526-013 fixed definition: same-date market up-volume breadth thrust, close above prior 20-day high and prior 50-day moving average, candidate volume ratio >= `1.25`, dollar volume >= `$40m`, signal-day RS vs SPY > `0`, top-1 per day, fixed `$10k` base paper notional, accepted exp-20260528-018 breadth-intensity support (`volume_breadth_fraction >= 0.25`, `1.10x` paper notional), accepted exp-20260528-022 high-close support (`signal_day_close_location_value >= 0.70`, `1.10x` paper notional), accepted exp-20260529-004 cost/liquidity support (`dollar_volume >= $200m` and signal-day range/close `<= 0.10`, `1.05x` paper notional), next-open paper entry, 10-trading-day close exit, and concentration guard before promotion | daily run derives candidates from the already-loaded daily OHLCV universe plus `SPY`, emits breadth-gate context, breadth-intensity support metadata/scalars, high-close support metadata/scalars, cost/liquidity support metadata/scalars, candidate rank/score metadata, pending/open/closed paper ledger state, replacement-value report, forward paper gate, default-off alpha-attribution surface, and human-report block | observe-only; no core universe expansion, no live orders, no core ranking/sizing/exit changes, and activation requires closed forward replacement-value outcomes plus a separate Gate 1-4 trade adapter |
| Default-off alpha-score market-regime paper sleeve | `alpha_score_market_regime_paper_sleeve.py`, `cross_sectional_ranking_surface.py`, `report_generator.py` | default core backtests do not trade it; historical evidence comes from accepted `exp-20260531-021` / `exp-20260531-023` plus accepted source-consensus support from `exp-20260531-025`, and must use the fixed full-universe PIT `alpha_score` surface, top-decile/top-1 route, stock-only ETF exclusions, average dollar volume >= `$40m`, SPY close above its 50-day average, `IWM 20d return - SPY 20d return >= 0`, fixed `$4,000` base paper notional, the `1.25x` paper-notional support only when the same ticker/signal date is also selected by accepted FINRA/IWM or VBB paper sources, next-open paper entry, 20-trading-day close exit, and concentration guard before promotion | daily run derives candidates from the already-loaded daily OHLCV/features universe plus `SPY` / `IWM`, receives same-day `VOLUME_BREADTH_BREAKOUT_PAPER` and `FINRA_IWM_CONFIRMED_PAPER` snapshots for source-consensus metadata, emits alpha-score rank/components, market-regime gate metadata, safe-notional and source-consensus support metadata, pending/open/closed paper ledger state, replacement-value report, forward paper gate, default-off alpha-attribution surface, and human-report block | observe-only; no core universe expansion, no live orders, no core ranking/sizing/exit changes, and activation requires closed forward replacement-value outcomes plus a separate Gate 1-4 trade adapter |
| Default-off accepted-source consensus paper sleeve | `accepted_source_consensus_paper_sleeve.py`, `alpha_score_market_regime_paper_sleeve.py`, `cross_sectional_ranking_surface.py`, `report_generator.py` | default core backtests do not trade it; historical evidence comes from positive `exp-20260531-026` and accepted adapter `exp-20260531-029`, and must use the fixed accepted alpha-score market-regime source from `exp-20260531-021`, stock-only ETF exclusions, average dollar volume >= `$40m`, SPY close above its 50-day average, `IWM 20d return - SPY 20d return >= 0`, fixed `$4,000` paper notional, no source-consensus notional scalar, and admission only when the same ticker/signal date is also selected by accepted `FINRA_IWM_CONFIRMED_PAPER` or `VOLUME_BREADTH_BREAKOUT_PAPER`; next-open paper entry, 20-trading-day close exit, and concentration guard apply before promotion | daily run derives candidates from the already-loaded daily OHLCV/features universe plus `SPY` / `IWM`, receives same-day VBB and FINRA/IWM paper snapshots, emits accepted-source consensus metadata, pending/open/closed paper ledger state, replacement-value report, forward paper gate, default-off alpha-attribution surface, and human-report block | observe-only; no core universe expansion, no live orders, no core ranking/sizing/exit changes, and activation requires closed forward replacement-value outcomes plus a separate Gate 1-4 trade adapter |
| Default-off accepted free-data cross-source consensus paper sleeve | `free_data_cross_source_consensus_paper_sleeve.py`, `run.py`, `report_generator.py` | default core backtests do not trade it; historical evidence comes from positive `exp-20260531-030`, accepted adapter `exp-20260601-001`, accepted current-baseline capacity gate `exp-20260601-028`, accepted independent source-family adapter `exp-20260603-015`, and accepted lagged independent-source timing promotion `exp-20260604-009` from the positive `exp-20260604-008` replay lead; replay must use current signal-date ticker source rows plus at most the prior 3 trading-session source snapshots, requiring at least two independent accepted free-data source families among `FUNDAMENTAL_GROWTH_RS_PAPER`, `VOLUME_BREADTH_BREAKOUT_PAPER`, `FINRA_IWM_CONFIRMED_PAPER`, `FINRA_BORROW_PRESSURE_PAPER`, and `ALPHA_SCORE_MARKET_REGIME_PAPER`, with `FINRA_IWM_CONFIRMED_PAPER` and `FINRA_BORROW_PRESSURE_PAPER` collapsed into one `finra_short_pressure` family; fixed `$4,000` paper notional, top-1/day, seven-calendar-day same-ticker admitted-candidate cooldown, production-visible core-capacity-available admission (`active core positions < MAX_POSITIONS`, missing capacity context blocks), next-open paper entry, 10-trading-day close exit, and concentration guard apply before promotion | daily run receives same-day snapshots from the accepted free-data paper sleeves plus a FINRA borrow-pressure consensus-source alias derived from the shared FINRA/IWM paper snapshot; the shared helper also loads bounded source-snapshot history from the same default-off paper sleeve snapshot logs and uses the same `strategy_active_positions` / `MAX_POSITIONS` core slot context used by production entry planning; it emits raw source, source-family, current/prior timing, lagged-confirmation, core-capacity gate, cooldown, pending/open/closed paper ledger, replacement-value, forward paper gate, default-off alpha-attribution, and human-report metadata | observe-only; FINRA+FINRA cannot satisfy consensus by itself; lagged confirmation can admit paper rows but cannot alter live orders, core universe, ranking, sizing, exits, watchlists, LLM, or news; activation requires closed forward replacement-value outcomes plus a separate Gate 1-4 trade adapter |
| Default-off Companyfacts operating-profit + RS paper sleeve | `fundamental_growth_rs_paper_sleeve.py`, `report_generator.py` | default core backtests do not trade it; historical evidence comes from `exp-20260528-008`, accepted low-volume participation support from `exp-20260528-015`, accepted filing-recency support from `exp-20260528-016`, accepted low-liability balance-sheet support from `exp-20260528-017`, accepted gross-margin quality candidate-source promotion from `exp-20260601-026`, accepted filing-timeliness support from `exp-20260601-027`, accepted cost-liquidity support from `exp-20260601-030`, and accepted sector-residual support from `exp-20260602-010`; any replay must use the same Companyfacts filed-date <= signal-date boundary, operating-income-positive quality gate, `gross_margin >= 0.40` from filed-date revenue plus gross profit or cost-of-revenue fallback with 60-400 day fiscal-duration guard, EPS/revenue growth points, RS percentile proxy, top-1/day fixed `$10k` base paper notional, accepted `volume_ratio_20 <= 0.90` low-volume `1.10x` paper-notional scalar, accepted `operating_income_filing_age_days <= 90` filing-recency `1.05x` paper-notional scalar, accepted filing-timeliness `1.05x` paper-notional scalar only when `operating_income_current_form == 10-Q` and filed within `45` days of period end or `10-K` and filed within `75` days of period end, accepted `liabilities/assets <= 0.35` low-liability `1.05x` paper-notional scalar, accepted cost-liquidity support (`avg_dollar_volume_20 >= $200m` and signal-day `(high-low)/close <= 0.10`, `1.05x` paper notional), accepted sector-residual support (20-day stock return beats persisted public-sector median by `>= 0.03` with at least `5` sector-member returns, `1.05x` paper notional), next-open paper entry, 10-trading-day close exit, and closed-ledger profit-cap/drawdown governor before promotion | daily run derives candidates from the already-loaded daily OHLCV universe plus `SPY`, reads local SEC Companyfacts rows and `data/reference/broad_market_sector_map.json`, emits candidate score/growth/RS/gross-margin/governor/low-volume participation/filing-recency/filing-timeliness/low-liability/cost-liquidity/sector-residual metadata, advances pending/open/closed paper ledger state only when that ticker has an exact `as_of` OHLCV row, emits replacement-value report, forward paper gate, default-off alpha-attribution surface, and human-report block | observe-only; stale latest-prior prices from weekend/holiday/data-lag runs may report metadata but cannot fill pending entries, advance hold days, or close paper positions; no core universe expansion, no live orders, no core ranking/sizing/exit changes, and activation requires closed forward replacement-value outcomes plus a separate Gate 1-4 trade adapter |
| Default-off FINRA short-pressure IWM-confirmed paper sleeve | `finra_iwm_paper_sleeve.py`, `report_generator.py` | default core backtests do not trade it; historical evidence comes from accepted `exp-20260530-007`, accepted shared adapter `exp-20260530-010`, accepted cost-liquidity support `exp-20260601-029`, and accepted borrow-pressure shared adapter `exp-20260603-007`; replays must use FINRA rows only when `publication_date <= signal_date`, the fixed OHLCV breakout gates from `exp-20260529-017`, the `IWM 20d return - SPY 20d return >= 0.003` confirmation from `exp-20260530-005`, the seven-calendar-day same-ticker admitted-candidate cooldown from `exp-20260530-007`, accepted borrow-pressure admission (`days_to_cover >= 3.0` and positive `short_interest_change_pct`), top-1/day fixed `$10k` base paper notional, accepted cost-liquidity support (`dollar_volume >= $200m` and signal-day `(high-low)/close <= 0.10`, `1.05x` paper notional), next-open paper entry, 10-trading-day close exit, and concentration guard before promotion | daily run derives candidates from the already-loaded daily OHLCV universe plus `SPY` / `IWM`, loads or fetches official FINRA short-interest rows with publication-date gating, emits FINRA score, IWM/SPY confirmation, borrow-pressure admission metadata, cooldown metadata, cost-liquidity support metadata/scalars, pending/open/closed paper ledger state, forward paper gate, default-off alpha-attribution surface, and human-report block | observe-only; no core universe expansion, no live orders, no core ranking/sizing/exit changes, and activation requires closed forward replacement-value outcomes plus a separate Gate 1-4 trade adapter |
| Default-off SEC FTD + FINRA-confirmed paper sleeve | `sec_ftd_finra_paper_sleeve.py`, `run.py`, `default_off_alpha_attribution.py`, `report_generator.py` | default core backtests do not trade it; historical evidence comes from positive `exp-20260604-026` and accepted shared adapter `exp-20260604-027`; replays must use SEC fails-to-deliver rows only when the publication-date policy makes them known by `signal_date`, require the fixed FTD pressure gates (`ftd_shares >= 100000`, `ftd_notional >= $1m`, `ftd_notional / ADV20 >= 0.006`, publication age <= 45 days), the fixed OHLCV breakout/liquidity/relative-strength gates, latest publication-date-safe FINRA confirmation (`days_to_cover >= 3.0` and positive `short_interest_change_pct`), no same-day selected core ticker overlap, top-1/day fixed `$4k` paper notional, next-open paper entry, 10-trading-day close exit, and concentration guard before promotion | daily run derives candidates from the already-loaded daily OHLCV universe plus `SPY`, loads or fetches SEC FTD and FINRA short-interest rows with publication-date gating, receives same-day selected core entry tickers from the production signal set, emits FTD pressure metadata, FINRA confirmation metadata, candidate rejects, pending/open/closed paper ledger state, forward paper gate, default-off alpha-attribution surface, and human-report block | observe-only; no core universe expansion, no live orders, no core ranking/sizing/exit changes, and activation requires closed forward replacement-value outcomes, replay-vs-forward parity audit, and a separate Gate 1-4 trade adapter |
| Default-off state-surface satellite | `state_surface_sleeve.py`, `report_generator.py` | default core backtests do not trade it; historical state-surface replays must use the shared queue/sleeve scoring, rotation-only surface eligibility, benchmark-momentum participation gate, ret20_excess_spy candidate floor, top-five daily candidate count, shared market-regime classifier, regime-aware queue-rank paper-notional profile, candidate-breadth rank-notional override, score-compression rank-notional override, rank-2 ret20-excess leadership rank-notional override, rank-2 ret20 plus score-gap rank-notional override, rank-1 ret20 dominance plus score-gap rank-notional override, top-2 Technology sector-cohesion rank-notional override, residual rank-1 60-day return rank-notional override, residual score-expansion rank-notional override, residual rank-1 score-isolation rank-notional override, recent same-ticker repeat notional scalar, rank-3 near-high support notional scalar, rank-2 near-high support notional scalar, rank-2 volume-confirmation notional scalar, rank-3 volume-confirmation notional scalar, top-3 positive ret5 follow-through notional scalar, broad-breadth market-state notional scalar, rank-queue alignment notional scalar, sleeve-capacity notional scalar, queue-lag support notional scalar, absolute-score support notional scalar, rank-depth score-volume support notional scalar, low-extension support notional scalar, and tail-aware forward promotion gate before promotion | daily run emits full scored-candidate audit, top-five rotation_breakout_leadership-only default-off paper candidates with the shared `[1.5, 1.25, 1.0, 0.75, 0.5]` default queue-rank paper notional profile, the accepted `chop` override `[1.625, 1.3, 1.0, 0.7, 0.375]`, the accepted candidate-breadth `>= 4` override `[1.6625, 1.315, 1.0, 0.675, 0.35]`, the accepted top-three score-compression `<= 0.40` override `[1.35, 1.45, 1.05, 0.675, 0.35]`, the accepted rank-2 ret20-excess leadership `>= 0.005` override `[1.3, 1.55, 1.1, 0.675, 0.35]`, the accepted rank-2 ret20-excess plus rank-1 score-gap `>= 0.30` override `[1.0, 1.85, 1.1, 0.675, 0.35]`, the accepted rank-1 ret20-excess dominance `>= 0.15` plus score-gap `>= 0.45` override `[1.6, 1.4, 1.0, 0.675, 0.35]`, the accepted top-2 Technology sector-cohesion override `[1.45, 1.7, 1.15, 0.675, 0.35]`, the accepted residual rank-1 60-day return `>= 0.50` override `[1.2, 1.85, 1.1, 0.675, 0.35]`, the accepted residual score-expansion `score_top3_spread >= 0.40` plus candidate-breadth `>= 4` override `[1.85, 1.25, 1.0, 0.675, 0.35]`, the accepted residual rank-1 score-isolation `score_top_to_second_gap >= 0.20` within the score-expansion branch override `[2.2, 1.0, 0.7, 0.675, 0.35]`, the accepted recent same-ticker repeat rule that scales a repeat paper entry by `1.50` when the ticker appeared in sleeve state within `60` calendar days, the accepted rank-3 near-high support rule that scales only rank 3 by `1.50` when `rank3_near_high_60 >= 0.98`, the accepted rank-2 near-high support rule that scales only rank 2 by `1.50` when the candidate's own `features.near_high_60 >= 0.975`, the accepted rank-2 volume-confirmation rule that scales only rank 2 by `1.10` when the candidate's own `features.volume_ratio_20 >= 1.10`, the accepted rank-3 volume-confirmation rule that scales only rank 3 by `1.50` when the candidate's own `features.volume_ratio_20 >= 1.10`, the accepted top-3 positive ret5 follow-through rule that scales only ranks 1-3 by `1.25` when the candidate's own `features.ret5 > 0.0`, the accepted broad-breadth support rule that scales candidates by `1.10` when `breadth_bucket == broad_breadth`, the accepted rank-queue alignment rule that scales candidates by `1.15` when `rank == queue_rank`, the accepted sleeve-capacity rule that scales all selected paper candidates by `1.15`, the accepted queue-lag support rule that scales candidates by `1.25` when `rank > queue_rank`, the accepted absolute-score support rule that scales candidates by `1.15` when `score >= 0.90`, the accepted rank-depth score-volume support rule that scales queue-rank 2-3 candidates by `1.075` when `score >= 0.90` and `features.volume_ratio_20 >= 1.10`, the accepted low-extension support rule that scales candidates by `1.05` when `features.ret5 <= 0.02`, plus market-regime/profile/candidate-breadth/score-dispersion/rank2-ret20-lead/rank1-ret20-dominance/top2-sector-cohesion/rank1-ret60-residual/score-expansion/rank1-score-isolation/recent-repeat/rank3-near-high-support/rank2-near-high-support/rank2-volume-confirmation/rank3-volume-confirmation/top3-ret5-followthrough/broad-breadth-support/rank-queue-alignment/sleeve-capacity/queue-lag-support/absolute-score-support/rank-depth-score-volume/low-extension-support metadata, surface-blocked audit rows, benchmark-momentum allow/block reason, ret20_excess_spy allow/block reason, pending/open/closed ledger state, a forward paper gate, and read-only tail diagnostics for closed paper outcomes only | observe-only until closed forward replacement-value outcomes pass the shared tail-aware gate and an explicit trade adapter is enabled |
| Default-off low-deployment ETF cash substitute | `low_deployment_etf_overlay.py`, `report_generator.py` | default core backtests do not trade it; accepted historical evidence comes from `exp-20260605-035` and the shared-adapter replay `exp-20260606-001`; any replay must use the shared helper with active core positions `<= 1`, candidate set `QQQ` / `SPY` / `IWM` / `GLD` / `SLV`, exact signal-date close above SMA200, positive 20-session momentum, top momentum candidate, one pending/open ETF paper position, next-open paper entry, 10-trading-day close exit, slippage plus round-trip cost, and concentration guard before promotion | daily run emits the same default-off cash-substitute candidate, pending/open/closed paper ledger, unrealized PnL, low-deployment diagnostics, and report block; it records core deployment as context and never places live/default ETF orders | observe-only; cash substitute activation requires closed forward replacement-value rows, explicit cash semantics, capital cap, kill switch, and a separate Gate 1-4 trade adapter |
| Default-off core-misfit paper sleeve | `core_misfit_paper_sleeve.py`, `report_generator.py` | default core backtests do not trade it; historical evidence is replay-only attribution until a separate adapter exists | daily run copies only `trend_long` `TSM` / `ISRG` / `V` / `DDOG` selected or slot-sliced core long signals into a no-trade / fast-long / inverse-short paper ledger only, per `exp-20260518-022` | observe-only; no live shorting, no core exclusion, no order/ranking/sizing changes until closed forward paper outcomes pass a separate gate |
| Default-off space catalyst shadow universe | `space_catalyst_sleeve.py`, `universe_manager.py`, `pilot_sleeve.py` | default core backtests do not trade it; space records are research/quarantine with zero live slots; forward hypotheses must use shared Space metadata/helpers before promotion | daily run may surface observe-only candidate pool, LLM event fields, default-off sub-bucket risk/target-hypothesis metadata/helpers, perfect-TQS, near-perfect trend TQS, trend high-close OHLCV metadata (`daily_close_location >= 0.84`), trend high-close intraday-thrust OHLCV metadata (`signal_day_ticker_open_close_return_pct >= 0.04`), ARKX>UFO breakout complement metadata/helpers, selected Space cost/liquidity paper-support metadata/helpers (`signal_day_ticker_dollar_volume >= $100M`, `signal_day_ticker_range_pct <= 0.11`, `1.05x` paper support, `trade_enabled=False`), peer-nonleader breakout risk, IWM-relative small-cap appetite risk, IWM-plus-peer-leader trend risk, launch/lunar theme-segment risk, liquidity-tier anchor/watch risk, official customer-source risk, customer-source peer-leader risk, government-contract peer-leader risk, financing/dilution event-guard profile risk, multi-event official catalyst-depth risk, single-event defense-only risk, attention-overlay-with-official-catalyst risk, source-diversity risk, source-diversity peer-leader risk, source-diversity IWM-leader risk, source-diversity peer+IWM-leader risk, source-diversity trend risk, source-diversity peer-nonleader trend risk, source-diversity peer-nonleader near-perfect trend risk, source-diversity dual-catalyst trend risk, source-diversity dual-catalyst IWM-leader trend risk, source-diversity dual-catalyst same-theme winner trend risk, source-diversity dual-catalyst near-perfect trend risk, source-diversity dual-catalyst financing-profile trend risk, source-diversity dual-catalyst benchmark-breadth trend risk, forward replacement-positive 10d risk metadata/helpers, forward same-theme replacement-strength metadata/helpers, forward same-theme replacement-strength trend-only metadata/helpers, forward same-theme replacement-strength IWM-leader trend metadata/helpers, forward same-theme replacement-strength company-source trend metadata/helpers, delayed-absorption trend metadata/helpers, benchmark-breadth trend metadata/helpers, benchmark-breadth same-theme strength trend metadata/helpers, benchmark-breadth peer-nonleader trend metadata/helpers, benchmark-breadth IWM-leader trend metadata/helpers, defense-budget delayed benchmark trend metadata/helpers, the one-slot blocked Space production observation plan, and the Space event-state shadow ledger only | observe-only until closed forward replacement-value evidence and a separate pilot promotion create explicit live slots |
| Portfolio heat | `portfolio_engine.py` | required | required | simulated vs latest prices |
| Already-held handling | shared adapter policy | required | required | none |
| Entry candidate gates | `production_parity.py` | required | required | none |
| Regime risk sizing override | `production_parity.py` | required | required | none |
| Scarce-slot rank-1 post-sizing top-up | `production_parity.py` / `constants.py` | required; `scarce_slot_rank1_risk_multiplier_applied` is captured in trade sizing attribution | required through the same `plan_entry_candidates` path used by production | none; applies only after slot slicing when exactly one slot remains |
| Ample-slot stock rank-1 post-sizing top-up | `production_parity.py` / `constants.py` | required; `ample_slot_stock_rank1_risk_multiplier_applied` is captured in trade sizing attribution | required through the same `plan_entry_candidates` path used by production | none; applies only after slot slicing when at least four slots remain and sector is known and not ETF / Commodities |
| Entry open cancel | `production_parity.py` / signal `entry_note` | simulated next open | instruction for next-session execution | production cannot know next open until execution |
| Scarce-slot routing | `production_parity.py` / backtester config | required | required | backtester records attribution; production emits plan |
| Operator entry candidate review | `production_parity.py`, `run.py`, `report_generator.py`, `llm_advisor.py` | diagnostic-only comparison of production core-strategy slot accounting versus shadow total-account slot accounting | daily run uses core-strategy slot capacity for executable core entry planning, while all real positions still count toward heat/cash/risk; it emits candidate-level `live_accounting`, `backtest_accounting`, and optional `total_accounting_shadow` buy/deferred labels for operator review and LLM news context | total-account shadow capacity may flag unmanaged/legacy/fomo/pilot crowding, but it must not silently consume core strategy slots unless a position explicitly has `slot_policy=consumes_core_slot` |
| Follow-through add-ons | `production_parity.py` / backtester config | schedule/execute in simulation with shared effective-stop heat cap | emit explicit `addon_actions` with the same cap policy, only when ticker and SPY latest OHLCV dates match; dated `current_prices` overrides must match the ticker latest OHLCV date | fill price timing only |
| Early relative-weakness exits | `production_parity.py` / backtester config | schedule/execute in simulation from same-date ticker/SPY OHLCV slices | emit explicit next-open exits only when ticker and SPY latest OHLCV dates match; dated `current_prices` overrides must match the ticker latest OHLCV date | fill price timing only |
| Rejected early relative-weakness exit scout | `production_parity.py` / explicit experiment config | disabled by default; used only by `exp-20260513-112` replay | not emitted in daily production because Gate 4 failed | rejected replay-only experiment; promotion would require `run.py` wiring and parity tests |
| Production advisory exit context | `trend_signals.py`, `position_manager.py`, `llm_advisor.py` | disclosed as `known_biases.exit_policy_unreplayed`; not executed except explicit shared replay hooks | required for daily report / LLM prompt / pending action memory; `LEGACY_TARGET_REVIEW` is surfaced as non-executable manual review only | advisory rules require shadow attribution before promotion |
| Backtest price exits | `backtester.py` execution model | full-position `stop_price` / `target_price` fills | manual/live execution from reported actions | `target_price` semantic gap disclosed |
| Trailing partial reductions | `production_parity.py` / backtester `REPLAY_PARTIAL_REDUCES` | replay container on by default; pure trailing trims disabled by shared policy unless explicitly enabled for comparison | disabled by shared policy | opt out only for diagnostics |
| Pending unexecuted actions | `pending_actions.py` | disclosed as `known_biases.pending_action_replay_unreplayed`; not replayed from current ledger | required | production-only execution memory without point-in-time ledger snapshots |
| LLM veto / ranking | `llm_advisor.py`, `llm_replay` path | replay archive when enabled | live prompt/response | archive coverage disclosed |
| News veto | `filter.py`, `news_replay.py` | replay archive when enabled | live news files | archive coverage disclosed |
| Fill / slippage | fill/backtester execution model | simulated next open | manual/live execution | disclosed execution model |
