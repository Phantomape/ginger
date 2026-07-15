# Alpha Optimization Playbook

Last refreshed: 2026-07-15.

This is Ginger's long-lived alpha research playbook. It is not an experiment
log. Detailed trial records belong in `docs/experiment_log.jsonl`,
`experiments/logs/*.json`, experiment cards, and artifacts. This file keeps the
current operating readout, research queue, frozen retry zones, and anti-repeat
rules. Mechanism cards and external research notes live in linked detail files.

For default LLM context, start with `docs/alpha_context_pack.md`, then
`docs/current_state_snapshot.md` when current-state orientation is needed.
These are generated short memory surfaces; this playbook remains the durable
policy and research-prior reference. Mechanism-specific short lessons live
under `docs/lessons/*.md` and should be refreshed with:

```powershell
.\.venv\Scripts\python.exe -B scripts\build_alpha_memory.py --git-ref HEAD
```

North-star metric:

```text
expected_value_score = strategy_total_return_pct * sharpe_daily
```

## Operating Rules

Before strategy-affecting work, answer:

1. What is the alpha hypothesis, and is it entry, exit, ranking, capital
   allocation, candidate-pool, LLM event scoring, or risk allocation?
2. Has the same or adjacent family been tried before, and what failed?
3. What is the one changed decision hypothesis or fixed policy bundle, and
   which edits are only implementation/parity/live-realism work needed to
   evaluate it?
4. What Gate 1-4 standard from `docs/backtesting.md` decides acceptance?
5. If it fails, can the next agent reproduce the trial from repository records?

Priority rules:

- Prefer `alpha_search` unless a measurement gap directly blocks a high-value
  alpha test.
- Prefer new production-visible fields over threshold/scalar sweeps.
- Prefer default-off paper adapters before core or live expansion.
- For any alpha that may become live-capital eligible, include the live-realistic
  execution envelope in the experiment rather than postponing it: notional,
  capital cap, liquidity/slippage, portfolio displacement, exposure limits,
  kill switch, and order semantics.
- Prefer replacement value against the displaced candidate over standalone PnL.
- Prefer shared-paper-first experiments for high-potential default-off paper
  alpha: the first serious test should use a shared historical replay plus daily
  snapshot helper, not private runner-only selection code. The default runnable
  form is the full-stack candidate-pool contract
  (`--change-type candidate_pool_full_stack`, see
  `docs/agent_experiment_protocol.md`), which reaches a paper-sleeve verdict in
  one experiment instead of a scout round plus a promotion round.
- Prefer shared production/backtest policy over replay-only logic. A positive
  private replay scout is only a lead until a shared helper reproduces it.
- Treat high aggregate EV with window regression or drawdown drift as a rejected
  clue, not as a retained strategy.

## Current Readout

The strongest current pattern is not more filters. It is:

1. find broad, cheap, point-in-time candidate sources;
2. when the idea is credible, test it through a shared-paper-first helper that
   can drive both historical replay and daily default-off snapshots;
3. define the live-realistic execution envelope early, even while
   `trade_enabled=false`;
4. collect closed forward replacement-value rows under that envelope;
5. if the envelope was already measured and remains unchanged, live enablement
   is a release checklist/config change; otherwise run only a narrow
   activation-envelope Gate 1-4, not a new alpha search.

Private replay scouts should be reserved for uncertain data-shape discovery or
very speculative ideas. They should not be treated as accepted alpha even when
Gate 4 is positive; the next retained asset must be the shared helper or daily
default-off wiring that reproduces the lead.

Meta-research continues to rank production-visible default-off paper adapters
above raw filters, ticker exceptions, and cap releases. The research report is
queue guidance only; it is not a trading signal.

The June 6-8 readout tightens the rule: relation-aware free-data candidate
sources can work, but only when the relation itself is the edge. Accepted
examples use macro-event relief, volatility-relief leadership,
rolling-correlation peer shock with core-flow confirmation, or
industry-relative laggard repair. Rejected neighbors show what does not count
as a new relation: sector ETF laggards, core-selected anchor peer lags with
zero target trades, short-horizon reversal/reclaim, macro sector confirmation
that fails versus the accepted comparator, broad cross-asset proxies, and SEC
guidance/outlook phrase matching with same-day price alignment. These are
mostly weak confirmers, not new information.

The June 8 batch adds a sharper boundary. Copper strength, oil-cost relief,
IWM breadth thrust, DIA/MDY "real economy" leadership, and simple VIX/SPY/QQQ
tail guards did not create enough after-cost next-open replacement value. The
one useful lead was not another broad proxy: it was a narrower
industry-stable-leadership source admitted only when the existing core A/B stack
also had same-day entry flow and same-ticker overlap was excluded. Treat this
as evidence that relation alpha needs an internal flow or displacement anchor,
not just a macro ETF or commodity tape label.

The late June 8 and June 9 readout adds two more rules. First, narrow-range
compression can be useful when the full policy bundle is fixed: prior range
compression, signal-day range expansion, high close-location, volume
confirmation, SPY-relative trend, next-open entry, 10-day exit, costs,
cooldown, and core-overlap exclusion. Second, most intuitive "institutional
demand" relabels are still too generic. Gap-and-hold, breadth-confirmed
gap-and-hold, post-thrust inside-day absorption, accumulation-base variants,
market-pullback reclaim, and extra core-flow or volatility-relief confirmation
did not beat the accepted comparators. Treat these as evidence that price
formation labels need an independent displacement edge, not just cleaner
momentum vocabulary.

The June 10 readout makes the allocator lesson sharper. A source-priority
allocator across already accepted default-off helpers can add value when it
chooses one ex-ante highest-priority paper row per day and avoids same-ticker
overlap. Revision-surprise low-extension earned a fixed rank-5 slot inside that
allocator because it supplied distinct expectation evidence. Simple additions
of already accepted helpers, such as macro relief, 52-week-high, or
post-earnings rows, did not add enough incremental replacement value after
higher-priority rows and cooldown. Calendar and event labels also narrowed:
turn-of-month leadership remains accepted, while OPEX week, quarter-end,
holiday-adjacent, pre-earnings DTE/low-bar, broad SEC business-update labels,
Companyfacts quality gates layered onto 52-week anchors, and extra compression
tail gates did not beat accepted comparators. A fixed semiconductor/AI hardware
basket breadth-thrust scout was also rejected despite positive aggregate EV
because it regressed old_thin, failed concentration, and did not beat the
accepted source-priority allocator. The useful question is now source
arbitration and distinct evidence, not more date labels, helper stacking, or
hand-built theme baskets.

The June 11 readout strengthens the same conclusion. Lagged independent
free-data consensus became the next accepted shared allocator source because it
added distinct multi-source confirmation across all windows after being moved
into the shared daily/backtest boundary. Distribution-day absorption leadership
also earned an accepted default-off shared helper, but nearby additions show the
new boundary: VBB allocator rows, distribution rank-3/precompression variants,
low-beta defensive distribution-pressure variants, SEC FTD/FINRA rank-3 rows,
slot-sliced core candidates, and allocator source pruning can all look positive
versus the core baseline while failing the accepted allocator or accepted
distribution comparator. SEC text/event ideas also remain weak unless the
semantic field is materially richer: complexity and change-density,
periodic-report absorption, delayed SEC confirmation, and quantified
counterparty commitment did not add reliable replacement value. Pocket-pivot,
market follow-through, and peer-revision shock variants reinforced that broad
momentum or confirmation labels are not enough. The durable queue is therefore
forward maturation, relation/source evidence, and comparator-aware allocator
arbitration, not another rank, threshold, or helper-stacking sweep.
Forward maturation measurement also moved from blocker to usable surface:
exp-20260611-020 repaired 36/36 existing closed forward rows with
cost-adjusted replacement-value fields versus cash, SPY, and QQQ. Future
forward activation reads should use `replacement_value_vs_cash_usd`,
`replacement_value_vs_spy_usd`, and `replacement_value_vs_qqq_usd`; raw paper
PnL is no longer sufficient evidence.

The June 13 regime-router readout adds one retained state-conditioned paper
allocation, not a broad license to tune regimes. The only robust cell promoted
so far is `industry_stable_core_flow x mixed|balanced|normal`: exp-20260613-005
found the replay-only 1.5x notional tilt positive across all three canonical
windows, and exp-20260613-010 reproduced it through the shared default-off
helper with aggregate EV `+0.0804`, PnL `+$1,872.59`, 32 tilted rows, zero
window regression, and concentration/drawdown guards passing. It is still
`accepted_paper_pending_forward`, not live-ready, because the cell was screened
on the same windows. Do not sweep scalar, cell boundaries, state lookbacks,
top-N, hold, cooldown, or allocator rank. The next evidence must be closed
forward industry-stable core-flow rows tagged with entry-time state and
replacement value.

The later June 13 batch narrows the queue further. Source-choice diagnostics
show a real ex-post arbitration gap, but source maturity, source percentile,
candidate microstructure, same-ticker confirmation, alpha-score rows, and
front-loaded extension filters did not create a usable ex-ante allocator rule:
they either lost to the accepted allocator, had too few changed selections, or
regressed windows. Broad OHLCV variants also stayed weak: overnight absorption,
SPY-residual compression, and post-thrust pause/reclaim mostly relabeled
crowded momentum and failed on PnL, drawdown, or accepted-compression
comparators. New SEC ownership surfaces are now ingestible after the 13F repair,
but first alpha attempts were negative or fragile: Form 144 isolated sale
absorption, 13F sponsorship acceleration, and 13F new-holder initiation all
failed window/drawdown gates. Treat 13F/Form144 as delayed ownership/crowding
context first, not standalone entry alpha.

A separate June 14 scout adds one informative non-momentum lead.
`exp-20260614-020` tested a genuinely new free SEC field: annual accruals /
cash-conversion quality (NetIncome vs OperatingCashFlow, matched on the same
fiscal-year end, scaled by assets), which the accepted fundamental_growth_rs
CompanyfactsFundamentalIndex never loads. As a fixed top-1 next-open 10-day
default-off candidate pool it was positively predictive: aggregate EV `+0.99`,
PnL `+$21,322`, positive EV/PnL in all three windows with no regression, clean
concentration (HHI 0.12), beating the accepted compression and distribution
comparators on gross deltas. It was nonetheless REJECTED on the binding
guardrail: drawdown drift `+5.2pp` versus the 0.5pp cap. The cause is
deployment size, not signal weakness: 36/47 universe names pass the quality
gate so price confirmation does most of the discrimination, and overlaying 369
trades (~10 concurrent momentum-tilted positions) scales both PnL and drawdown.
This is the "high aggregate EV with drawdown drift is a rejected clue, not a
retained strategy" rule in action. Follow-up tests closed the obvious risk
envelope path: `exp-20260614-021` low deployment still regressed `old_thin`, and
`exp-20260614-023` daily-close 7% protective stop still regressed
`late_strong`/`old_thin` EV and left drawdown drift at `+3.17pp`. The useful
next step is no longer another deployment cap or stop. It is a sharper PIT
quality discriminator (TTM same-period accruals, accrual-change momentum,
quarterly cash-flow where reported) or materially new closed forward
replacement-value rows. It is NOT a threshold sweep of the rejected fixed
bundle.

The June 14 batch adds one narrow retained allocation field and closes several
tempting near-neighbors. The retained result is `exp-20260614-004`: within the
already accepted SEC financial-report T+1 drift sleeve, pre-entry 20-session
SPY-relative leadership (`ticker_minus_spy_ret20 >= 5pp`) earned a default-off
1.15x paper-notional scalar, improving aggregate EV by `+0.1582` and PnL by
`+$3,235.38` across all three fixed windows with 24 RS20-leader closed trades
and no survival/trade-count change. Keep it default-off and do not retune the
lookback, threshold, or scalar without forward replacement rows. The rest of
the day mostly tightened anti-repeat boundaries: forward activation is still
not ready because accepted adapters lack enough mature closed rows; same-day
source-pair routers still do not beat the accepted allocator; relation variants
based on correlation breakdown or earnings peer underreaction failed accepted
relation comparators; SEC AI-demand, forward-guidance-quality, and dividend
text labels were too sparse or already captured by SEC RS20 / accepted
comparators; Kova Companyfacts capital efficiency overlapped accepted
Companyfacts low-liability/RS; broad clustered Form 4 open-market buying was
slightly negative even with broad sample; and accepted-allocator market breadth
is attribution context, not a tail filter.

Default next question for any new broad candidate pool:

- what exact relation makes this ticker a better replacement than cash, ETF
  substitute, or the already accepted default-off comparator;
- whether the relation is point-in-time and production-visible;
- whether the candidate improves all windows against the accepted comparator,
  not only against the core baseline;
- whether the result survives costs, concentration, and drawdown before any
  notional, top-N, hold-day, or cooldown tuning.

The June 15 readout is another warning against treating positive aggregate EV
as accepted evidence when the accepted comparator, window, and drawdown tests
fail. Industry-relative asset-growth quality (`exp-20260615-006`), free
cash-flow / capex coverage quality (`exp-20260615-008`), and operating
leverage acceleration (`exp-20260615-016`) were all legitimate PIT SEC
Companyfacts candidate-pool attempts and each showed positive aggregate EV.
They were rejected because at least one canonical window or drawdown/comparator
guard failed, usually with old_thin or late_strong fragility and target
concentration. The lesson is not "try another Companyfacts threshold"; it is
that free fundamental fields need either a sharper PIT discriminator or a
different relation surface before they deserve another shared-paper-first run.
The same batch kept 13F in the context bucket: low-crowding sponsorship
leadership (`exp-20260615-009`) regressed aggregate EV/PnL and drawdown, so
13F remains delayed ownership/crowding context rather than direct entry timing.
Quantified SEC backlog/RPO/book-to-bill text (`exp-20260615-013`) was too
sparse at 3 trades and failed the accepted SEC RS20 comparator; generic
quantified-demand text is not enough without structured customer/supplier
contract economics. The non-repeat blocker scan (`exp-20260615-015`) found no
Gate-4-ready fresh alpha: low-deployment ETF has 17 closed positive rows but
threshold/list/hold/notional retunes are frozen, state-surface rows are still
too thin, the analyst-revision ledger exists but has zero candidate matches,
and FINRA/FTD still needs a real borrow-cost / hard-to-borrow / availability
field.

The final cash-conversion follow-up also closed negative. `exp-20260614-026`
tested interim TTM same-period cash-conversion acceleration, the next
discriminator suggested after the static accruals drawdown failure. It improved
aggregate EV/PnL (`+0.1311`, `+$4,444`) and kept drawdown within the 0.5pp
guard, but failed Gate 4: `late_strong` EV regressed, `old_thin` had zero target
coverage, only one window improved EV, and it did not beat accepted compression
or distribution comparators. Treat this as evidence that the cash-conversion
family is exhausted on frozen windows unless new forward replacement rows or a
materially different PIT evidence surface appears.

The June 16 readout adds one useful Companyfacts quality source and rejects the
obvious allocator overreach. SBC burden improvement (`exp-20260616-015`) passed
as a shared default-off paper adapter: raw filed-date Companyfacts showed
falling stock-based-compensation burden versus revenue, with positive revenue /
gross-profit context and liquid SPY-relative leadership, producing aggregate EV
`+0.9438`, PnL `+$15,748.19`, 108 trades, three improved windows, and passing
drawdown/concentration guards. The mechanism is dilution-quality improvement,
not another generic profitability or asset-growth filter. But forcing the same
source into the accepted-helper source-priority allocator at rank 2
(`exp-20260616-016`) failed: aggregate EV stayed positive but lagged the
accepted allocator, regressed `late_strong`, and worsened drawdown too much.
The first proposed sharper discriminator also failed: per-share SBC net of
buybacks with share-count discipline (`exp-20260616-017`) improved aggregate
EV/PnL but regressed `mid_weak`, failed concentration, and did not beat the
accepted SBC or distribution comparators. Keep SBC burden as its own
default-off forward-maturation source; do not tune rank, thresholds, per-share
or buyback tags, notional, hold, or cooldown on frozen windows. Valid new
evidence now needs closed forward replacement-value rows, option-exercise /
vesting context, or grant-value normalization, not another SBC ratio variant.

A later June 16 scout adds one more "directionally real but window-fragile"
balance-sheet field and one decisive data-coverage boundary. Inventory-to-revenue
leanness (`exp-20260616-018`) tested the Thomas-Zhang inventory anomaly as a free
SEC Companyfacts candidate source: production names whose annual InventoryNet /
revenue ratio is falling YoY (lean inventory vs sales = demand sell-through) with
non-declining revenue and liquid SPY-relative confirmation. InventoryNet is a
balance-sheet INSTANT fact the accepted fundamental index never loads, matched to
the trailing FY revenue ending the same date. It was REJECTED: aggregate EV
`+0.9345`, PnL `+$11,706.74`, 151 trades, and it actually beat both the accepted
compression and distribution comparators on aggregate, but `old_thin` regressed
on EV (`-0.119`) and PnL (`-$4,698`) while `mid_weak`/`late_strong` were strongly
positive, and drawdown drift was `+0.99pp` (>0.5pp cap). This is the same
"high aggregate EV with old_thin window regression and drawdown drift is a
rejected clue, not a retained strategy" pattern seen in accruals
(`exp-20260614-020`), asset growth, and operating leverage: the demand-side
inventory field is real in 2025 but does not survive the 2024-10→2025-04 window
after costs.

The early June 17 replacement-cycle follow-up closed the obvious CapEx/D&A
escape hatch from the D&A and fixed-asset-turnover failures. `exp-20260617-007`
tested annual raw SEC CapEx-to-depreciation reinvestment-cycle acceleration
with non-contracting revenue and liquid SPY-relative confirmation. It was
directionally positive in aggregate (EV `+0.7777`, PnL `+$11,550.79`, 161
trades) and beat compression/distribution aggregate comparators, but was
REJECTED because `old_thin` regressed (EV `-0.0741`, PnL `-$2,733.18`) and
drawdown drift reached `+1.09pp`. This confirms that the recent Companyfacts
asset-productivity / reinvestment fields still mostly capture the 2025 liquid
momentum regime, not a robust cross-window candidate-pool edge.

The full June 17 batch generalizes that lesson beyond CapEx/D&A. Working-capital
and balance-sheet relief fields often looked attractive in aggregate, but kept
failing hard guards: DPO extension, D&A burden relief, fixed-asset turnover,
impairment relief, AOCI relief, and industry down-shock resilience all regressed
one or more windows or failed drawdown/comparator gates. Sparse accounting and
SEC text surfaces were worse. Treat raw Companyfacts relief/overhang fields and
generic industry-resilience OHLCV labels as frozen on the standard windows.
Valid retries need materially new PIT decomposition, such as segment/customer
capacity, OCI components, borrow/options, numeric contract economics, or closed
forward replacement-value rows. Options-chain alpha is blocked by historical
coverage and vendor-as-of/open-interest lag controls, so it belongs in forward
observation before any Gate-4 claim.

FINRA short interest is now a data source, not an alpha queue. `exp-20260616-020`
repaired the archive to full three-window settlement coverage, but the core and
broad replays (`exp-20260616-024`, `exp-20260616-026`) rejected share-count
borrow-pressure: signs flip by universe/window, drawdown worsens, and broad PnL
is effectively zero after costs. The accepted FINRA/IWM paper helper was
retired in `exp-20260616-028` while leaving the archive and `sec_ftd_finra`
context intact. Do not rerun FINRA directional or squeeze tests from share
counts; a valid reopen needs PIT borrow fee / utilization / loan availability,
or closed forward replacement-value rows from a genuinely new source.

The June 18 batch closes another set of near-neighbor escape hatches. SEC item
and form-event absorption sources (Item 2.05 restructuring, business
combination/tender, Item 1.02 termination, Item 5.07 vote results, Item 4.02
nonreliance, offerings, S-8 employee equity, NT late filing, non-management
proxy pressure) did not beat accepted comparators, were too sparse, or regressed
windows. Annual and quarterly filing-timeliness broad runs also failed, closing
the universe-width caveat. Advertising-efficiency Companyfacts was directionally
interesting but failed window/drawdown/concentration/comparator gates. Static
intra-industry lead-lag, even with direction-stability history, stayed
window-fragile and drawdown-worse; equity-curve adaptive sizing cut into
V-shaped recoveries. The useful next work is not another threshold sweep. It is
building PIT structured data edges: 13G/13D primary documents with
holder/stake/action parsing, offering economics text, historical 10-K/10-Q
filer-status cover-page fields, full-window options chains, borrow-fee history,
and customer/supplier/payment-term disclosures.

The follow-up `exp-20260618-019` closed the simple 13D Item-4 phrase-classifier
escape hatch. A fixed active strategic/governance Item-4 text gate plus
same-day SPY-relative absorption produced only 6 paper trades and failed Gate 4:
aggregate EV `-0.0145`, PnL `-$368`, `mid_weak` and `old_thin` regressed, and
positive contribution concentrated in WEX. Treat deterministic Item-4 phrase
matching as ownership context, not an executable candidate-pool signal.

The June 19 batch did not add an accepted alpha; it narrowed what still counts
as new evidence. Earnings-date revision has zero reliable PIT event rows, so it
is a surface-readiness blocker, not a replay. Interest-burden and
industry-normalized reinvestment-productivity retries were correctly blocked by
novelty because they did not add a new financing or capacity field. The
replayed candidates then confirmed the same pattern across raw Companyfacts,
FINRA/public-float, ownership, Form 4, and SEC text: customer concentration,
inventory component mix, debt-maturity cliff relief, public-float-normalized
short pressure, parsed 13D/A stake decrease, Form 4 conversion-without-disposal,
reportable-segment count reduction, and issuer 8-K governance-resolution text
all failed Gate 4 through thin samples, window regression, drawdown drift,
concentration, or accepted-comparator weakness. The durable rule is now:
Companyfacts and SEC metadata retries need richer structured provenance
(customer identity/contract terms, segment mix, refinancing/covenants, borrow
cost/availability, conversion purpose, board-seat/standstill economics) or
closed forward replacement-value rows. Do not spend another run sweeping raw
tag lists, phrase lists, top-N, hold, cooldown, liquidity, or notional on these
frozen windows.

The later June 19 batch closed the last open 13G/13D sub-gap. `exp-20260619-014`
BUILT the parsed Schedule 13G/A amendment stake-change DIRECTION surface that
`exp-20260618-018` was BLOCKED on: `quant/sec_13d13g_ingest.py` now parses the
authoritative item4 `classPercent` current level, the `previousAccessionNumber`
PIT prior-stake chain, and the `classOwnership5PercentOrLess` drop-below-5% exit
flag, over 2,700 13G/A amendments on the broad warehouse universe. The read-only
forward diagnostic is decisive: the long-side bucket (non-Big3 stake INCREASE,
n=169) drifts only +0.16% median / +0.22% mean forward-10d SPY-excess at a 50.3%
win rate — below the exp-016 initial-crossing baseline (+0.5 to +1.3%) — and is
window-fragile (late_strong +0.26%, mid_weak -1.18%, old_thin +6.77% on n=7
noise). The only clean, well-sampled signal is the opposite direction: non-Big3
drop-below-5% exits (n=676) precede -0.31% median underperformance, real
ownership-distribution context that a long-only book cannot trade directly.
Verdict `observed_only`; the durable product is the reusable direction surface
plus parser tests. The 13G/A direction axis is now CLOSED on the frozen windows.

The June 20 batch produced one retained default-off source and closed several
nearby distractions. Theme and defensive relation sources are still weak unless
the relation itself creates displacement value: uranium/nuclear leadership
(`exp-20260620-001`) was aggregate-positive but failed window and concentration
gates, its core-flow confirmation variant (`exp-20260620-002`) became too thin,
and defensive-sector relative strength (`exp-20260620-003`) was outright
negative. SEC text and Form 4 variants also stayed too generic:
refinancing/covenant text, issuer contract-value-to-market-cap materiality, and
multi-year equity-retention footnotes failed on aggregate, windows, sample, or
accepted comparators. Routine compensation plumbing did not improve the
accepted SBC helper.

The useful exception was supplier-financing plus debt-relief. The raw
intersection (`exp-20260620-005`) was high-upside but drawdown-fragile; a
private risk-scaled replay lead (`exp-20260620-007`) was not enough; the first
shared adapter attempt (`exp-20260620-008`) failed to reproduce the lead; the
fixed `4k` risk-scaled shared default-off adapter (`exp-20260620-009`) was
accepted with aggregate EV `+0.6801`, PnL `+$12,355.48`, no live/default
orders, and the supplier/debt relief execution envelope preserved as
observe-only. Do not promote it live from frozen-window evidence. The next
evidence should be closed forward replacement value under the accepted `4k`
envelope, or a genuinely new provenance field: payment-term disclosure,
supplier/customer contract identity, covenant/refinancing terms, or parsed
counterparty economics. Do not retry by sweeping DPO/debt thresholds, risk
scalars, adapter notional, allocator rank, theme baskets, Form 4 compensation
code lists, SEC phrase lists, top-N, hold, or cooldown on the frozen windows.

`exp-20260620-032` added a narrow accepted allocator-capital lesson after the
read-only sleeve independence map (`exp-20260620-029`) and zero-fire correction
(`exp-20260620-031`): keep accepted-helper source selection unchanged, but give
selected `industry_laggard_repair` and `revision_surprise_low_extension` rows a
fixed `1.25x` default-off paper notional scalar. The shared helper and daily
snapshot path now expose the same source scalar, improving the current
unscaled allocator by aggregate EV `+0.0667` and PnL `+$1,245.12` across all
three canonical windows, with `201` affected rows and clean drawdown /
concentration. This is accepted paper-only capital allocation, not a license to
sweep allocator ranks or scalars. Future allocator capital changes need closed
forward source-family replacement-value rows or a materially new out-of-sample
independence surface.

`exp-20260621-001` extended that same accepted paper-only allocator-capital
lesson to the one low-correlation source left out of `exp-20260620-032`:
selected `rolling_peer_shock` rows now also receive the fixed `1.25x`
default-off paper notional scalar. The before state was the current accepted
allocator with laggard/revision scalars already active; adding only peer-shock
capital improved aggregate EV by `+0.0780` and PnL by `+$1,071.90`, with all
three canonical windows positive, `37` affected rows, zero drawdown drift, and
clean concentration. This is accepted default-off paper sizing only; do not
retry by sweeping peer-shock scalar, source rank, top-N, hold, cooldown, or
peer-shock OHLCV thresholds on frozen windows. Further allocator capital work
requires closed forward source-family replacement-value rows or a genuinely
new out-of-sample independence surface.

`exp-20260621-006` extends the same allocator-capital lesson to selected
`turn_of_month` rows, but only after fixing the before state to include the
already accepted laggard/revision/peer-shock scalars. Adding only the
turn-of-month `1.25x` default-off paper scalar improved the current accepted
allocator by aggregate EV `+0.0336` and PnL `+$745.80`, with all three
canonical windows positive, `54` affected rows, zero incremental drawdown
drift, and clean concentration. This remains paper-only source-family capital
allocation; do not retry by sweeping turn-of-month scalar, source rank, top-N,
hold, cooldown, calendar labels, or OHLCV thresholds on frozen windows.
Further allocator-capital work requires closed forward source-family
replacement-value rows or a materially new out-of-sample independence surface.

`exp-20260621-007` extends the allocator-capital lesson to selected
`lagged_cross_source_consensus` rows, again using the corrected current
allocator before state with all prior accepted source scalars active. Adding
only the lagged-consensus `1.25x` default-off paper scalar improved the current
accepted allocator by aggregate EV `+0.1716` and PnL `+$3,018.50`, with all
three canonical windows positive, `42` affected rows, no incremental drawdown
degradation, and clean concentration. This is accepted paper-only sizing for
the existing rank-1 consensus source; do not retry by sweeping consensus
source-set, source rank, scalar, top-N, hold, cooldown, or timing on frozen
windows. Further work needs closed forward replacement-value rows or a new
out-of-sample independence surface.

`exp-20260621-008` rejects the obvious post-scalar allocator capacity retry.
After the accepted source-scalar stack, raising accepted-helper
`daily_entry_slots` from `1` to `2` looked positive in raw overlay metrics
(aggregate EV `+0.6548`, PnL `+$10,126.90`) but failed the binding
production-consistent execution-envelope comparison: `late_strong` regressed
by EV `-0.0769` and PnL `-$341.03`, the current slots=1 allocator already had
`46` max-concurrent envelope skips, the expanded slots=2 allocator had `192`
skips, and the second slot displaced `2` existing top-1 rows through cooldown.
Do not retry allocator daily slots, top-N capacity, max-active cap release, or
adjacent gap-fill capacity on frozen windows. A retry needs closed forward
second-slot replacement-value rows or a materially new PIT field that predicts
which second candidate should survive the envelope.

The later quarterly inventory-turnover acceleration proposal
(`exp-20260620-017`) was correctly blocked before strategy logic because it
collapsed into the already rejected `exp-20260616-022` quarterly
InventoryNet/CostOfRevenue DIO-turnover family. Inventory/COGS retunes remain
closed until finished-goods/raw-materials decomposition, richer segment detail,
or closed forward replacement-value rows exist.

Two later replay scouts tightened the SEC-source boundary rather than opening
new work. `exp-20260620-018` used the new accession-level SEC primary-text rows
to parse offering amount, security type, use-of-proceeds, and market-cap
materiality, but still failed aggregate/window/sample/concentration gates and
accepted comparators. A retry needs materially richer financing provenance:
actual takedown versus shelf capacity, float-normalized dilution, lockup or
hedging terms, underwriter quality, closed deal outcome, or forward
replacement-value rows. `exp-20260620-019` tested raw SEC annual
`CommonStockDividendsPerShareDeclared` increases with revenue context and
SPY-relative leadership; it was also rejected, with drawdown and comparator
failures. Do not sweep offering regexes, amount/market-cap thresholds,
security/use weights, dividend-growth thresholds, revenue floors, fact
freshness, top-N, hold, cooldown, or notional on these frozen windows. A valid
capital-return retry needs dividend-initiation evidence, payout sustainability
tied to free cash flow, special-dividend exclusion from declaration text, or
closed forward rows.

The June 21 post-scalar batch says the current accepted-helper allocator is
near the end of frozen-window capital tuning. Peer-shock, turn-of-month, and
lagged-consensus source-family `1.25x` default-off scalars were accepted only
because each was tested against the corrected current before state with all
prior accepted source scalars active, affected a real selected-source cohort,
and improved all three fixed windows without drawdown or concentration drift.
The obvious next allocator move failed: `daily_entry_slots=2` added gross
overlay PnL but regressed `late_strong`, created far more envelope skips, and
displaced existing top-1 rows through cooldown. Treat the one-slot accepted
allocator plus fixed source scalars as the current frozen-window endpoint
unless closed forward replacement-value rows identify a specific second-slot
candidate or a genuinely new PIT independence surface appears.

The same batch closed several tempting escape paths. A prior-close SPY
trend-down beta hedge was negative after the strict risk-allocation comparator;
factor-residual leadership was blocked because the production-visible warehouse
lacks PIT MTUM/QUAL/VLUE/USMV/SIZE rows; FX OCI drawdown-aware sizing remained
aggregate-positive but still failed drawdown and accepted-distribution
comparators; available-proxy residual leadership produced high aggregate EV/PnL
but regressed windows, worsened drawdown, and missed the accepted distribution
PnL comparator; stricter SEC no-covenant credit-facility and customer
prepayment/capacity-commitment text tuples produced zero useful target events.
The current queue is therefore not another hedge, residual, SEC phrase, or
allocator-capacity retry. It is new PIT data construction with parity-safe
coverage, or forward replacement-value maturation under already accepted
paper-only envelopes.

The June 22 batch reinforces that new data surfaces matter only after they are
replayable and comparator-aware. SEC 13F same-manager co-accumulation was a
valid new relation axis after static co-ownership failed, but it still did not
beat the accepted rolling-correlation peer-shock helper: quarterly ownership
lag, thin sample, concentration, and window regression dominated the apparent
aggregate lift. Moomoo capital-flow is no longer merely a current snapshot:
`exp-20260702-016` proved DAY history exists and `exp-20260702-019`
materialized a dated archive, but the fixed top-1 main-inflow helper still
failed full-stack Gate 4 versus drawdown/comparator/full-stack contract bars.
Moomoo daily short-volume is a separate data-engineering lead because the live
probe and raw archive reached the canonical history, but the first activity
absorption helper was negative and concentrated. Treat both flow surfaces as
activity/liquidity/borrow-context surfaces until materially more forward rows,
new intraday provenance, or borrow fee/utilization/availability evidence exists.
The forward-replacement refresh also says no accepted helper is activation-ready
yet: comparator-session repair made the ledger measurable, but no sleeve/source
family has enough enriched closed rows across cash, SPY, and QQQ. Finally, the
6-K repair is a measurement win, not an alpha win: daily SEC event/text surfaces
now expose 6-K/6-KA, but the first positive operating-update semantic helper
found zero tradable target rows, and the first structured financial-result
growth scout then blocked because the generated historical SEC event/text/cache
artifacts still contained zero replayable 6-K rows. Do not sweep 6-K phrase
lists, numeric regexes, or price guards. The next valid work is a measurement
repair that materializes historical 6-K/6-KA text rows across the canonical
windows, then a fixed structured semantic helper with guidance-revision
magnitude, issuer-country/ADR liquidity provenance, translation quality, or
forward rows.

The June 23 work moved the queue toward forward measurement rather than a new
accepted trading rule. Entry-time `regime_chop_state` tags are now attached to
closed forward replacement rows, which is the right surface for sleeve-specific
regime validation; the first read found no activation-ready sleeve/regime cell.
The pilot scorecard now treats a breached predeclared drawdown ceiling as an
immediate KILL verdict, so manual pilot recommendations cannot keep adding
entries after the envelope fails. Options and Kova now have append-only forward
observation ledgers, but first closed-row reads rejected monotonic options-skew
and Kova RS/fundamental-alignment edges. Exit/LLM attribution produced only
observed-only leads: high-urgency exit lifecycle rows and LLM exit-pressure
states can separate worse forward outcomes, but confluence, above-cost subsets,
and next-open replacement-value checks did not yet produce a deployable shared
exit policy. Do not convert these diagnostics into exits, scalars, or live
pilot promotion; the next evidence is more closed forward replacement-value
rows with fixed schemas, not a frozen-window threshold sweep.

The June 24 batch tightened the same forward-first boundary. Same-entry-date
multi-sleeve breadth did not prove allocation readiness, and a broader source
triage found no compliant gate-ready alpha surface after novelty and
source-saturation checks. The useful work was measurement repair around
activation evidence: cross-pilot overlap rows now carry participant verdict and
status context, accepted-allocator open rows now carry current close/unrealized
price attribution, and current allocator price materialization cleared
`no_price` rows without changing any order path. That still did not make the
allocator activation-ready: there are zero closed allocator-top1 rows, the
scorecard is not graduate, and DDOG still overlaps a killed pilot. The new
positive lead is narrower and forward-only: Kova rows can now attach PIT SEC13F
holder/value sponsorship from the local holdings summary, partial 1d/3d/5d
cash/SPY/QQQ outcomes are settled, and high-sponsorship rows beat low/missing
sponsorship across those short horizons. This is not a promoted helper and not
canonical fixed-window evidence. A follow-on coownership-network attribution on
the same ledger did not separate primary 5d cash/SPY/QQQ outcomes, so the
relation graph is not a free upgrade over sponsorship context. Do not sweep
Kova sponsorship score, holder-count, value, coownership peer count/lift/shared
manager/Jaccard fields, RS, source-count, top-N, hold, cooldown, notional, or
allocator thresholds on the same partial forward ledger. The next admissible
evidence is enough closed 10d replacement rows, materially richer PIT
manager/active-flow provenance, borrow/options cross-evidence, or a shared
default-off helper with historical PIT coverage.

The June 25-26 readout compresses to a forward-first rule: the current partial
forward ledgers are useful for blocker discovery, not for endless adjacent
condition slicing. Options demand quality, Kova realized-quality/SEC13F context,
Form 4 conflict tags, SEC FTD joins, project-finance text, volume dry-up, and
estimate-revision match probes did not produce allocation-ready evidence on the
current rows. A valid retry needs materially more closed 10d replacement-value
rows, a new production-visible PIT field, or a shared helper with historical
coverage that can beat the accepted comparator after costs.

Short-volume is the clearest anti-repeat update. Treat Moomoo
`short_volume_ratio` as a real but non-incremental crowding/quality context:
the sign-corrected informed-short-flow read was directionally useful versus a
core momentum pool, but the hard exclusion and notional-downweight shapes both
failed against the accepted source-priority allocator. Do not retry quintile
cutoffs, scalars, source scoping, momentum/proximity thresholds, hold, cooldown,
or top-N on frozen windows. Reopen only with closed forward rows tagged at entry
by short-volume percentile, or with materially new borrow fee, utilization, or
loan-availability economics.

`exp-20260626-018` (measurement_repair) built the first half of that reopen
condition: the shared forward replacement-value enricher
(`quant/forward_replacement_value.py`) now writes a read-only entry-time PIT
`short_volume_ratio` percentile tag on closed forward rows
(`entry_short_volume_ratio_percentile / _quintile / _toxic_flag / _status`),
reusing the exp-018 expanding strictly-prior per-ticker percentile over the
broad 51-name archive (exp-20260623-008) so the forward tag is
parity-consistent with the attribution. The daily `run.py` enrich call
auto-loads the archive, so new closed rows are tagged going forward. Coverage is
already usable: 37/40 current closed rows carry a real percentile across all
five quintiles (toxic Q5 n=7 ≈ 19%, matching the exp-018 selection overlap), and
a read-only forward diagnostic is directionally consistent with the
informed-flow sign (clean Q1-Q2 mean replacement-value-vs-cash +$225 n=21 vs
toxic Q5 −$204 n=7). Per-quintile N is single digits and NOT significance-tested:
this is the validation SURFACE, not an alpha verdict. Do not read the tag as
permission to re-run any frozen-window short-volume gate; the only sanctioned
next step is a SOFT short-flow tilt validated once materially more closed
forward rows accumulate per quintile.

The June 26 maintenance records confirm that the next high-value work is data
materialization, not alpha retuning. SEC 6-K and selected 10-K/10-Q rows still
need local text/cache and parsed cover-page fields keyed by accession and
accepted timestamp; current Kova intraday/RS-proxy rows are features, not true
entry-open/close settlement OHLCV; borrow availability lacks fee, utilization,
and loan-availability economics. Until those surfaces are repaired, missing
archive/text/borrow/OHLCV availability is a blocker ledger, not an alpha field.

The June 27 readout keeps the same boundary but adds sharper data surfaces.
Borrow availability wiring, current 6-K semantic forward ledgers, SEC periodic
cover-page parser variants, and DEI checkbox parsing were accepted as
measurement repairs or forward-enabling surfaces; they do not change live
orders, ranks, sizing, or exits. The alpha attempts and diagnostics stayed
negative or blocked: pilot graduation was not ready, factor-residual leadership
and unconditional trend-long precursors failed accepted-comparator or window
checks, short-volume and sector-crowding oracle slices did not explain enough
loss, historical 6-K text/cache is still missing for standard-window replay,
historical DEI filer-status materialization is not yet complete, and the
supplier-financing/debt-relief helper has zero closed forward rows. The next
alpha hypothesis is still attractive but gated: periodic cover-page filer
status upgrades/downgrades may become a candidate-pool or allocation-quality
field only after historical DEI status is accession-keyed across canonical
windows and daily snapshots share the same parser. Until then, do not retry by
text-cache availability, current-only parser fields, trend-long latency,
factor-residual proxy lists, or supplier-financing activation slices.

The June 28 readout confirms that the current constraint is still maturity and
tradeable coverage, not another frozen-window retune. The day produced no new
accepted alpha. Useful work was mostly blocker classification: Kova SEC13F
settlement can read the hot warehouse through immutable SQLite mode but lacks
10d mature rows; ORTEX borrow fees are real new economics but only for one AAPL
sidecar without usable publication-date/daily-ledger parity; the forward regime
scorecard has 41 tagged rows but zero non-risk-on coverage; consumer-platform
and allocator-current surfaces are still open-row marks rather than settled
replacement value; the pilot scorecard confirmed one hard KILL on
fundamental_growth_rs but no graduate candidate. The negative alpha tests also
closed tempting escapes: weak-tape top300 expansion still buys unacceptable
drawdown/survival damage, ex-ante cost-adjusted stop-risk buckets did not
explain the loss tail, and SBC allocator admission was a duplicate stale
near-neighbor. Next alpha work should wait for materially more closed forward
rows or a genuinely new PIT data surface, especially borrow economics with
publication timing and replacement outcomes. `exp-20260628-011` retained this
as measurement repair by turning those blockers into machine-checkable reopen
conditions. Do not answer these blockers by re-slicing the same partial rows or
daily "still not mature" readiness audits.

The June 29-30 readout is useful mostly because it separates evidence plumbing
from deployable alpha. Retained work added machine-checkable guardrails and
forward surfaces: sleeve health now reads `as_of`-keyed core-risk rows;
allocator-top1 time exits explicitly mark `target_price` as not applicable;
Form 4 sale-overhang fields are shared daily context; Form 144 planned-sale /
float is parked behind cached primary documents, parseable ratios, and closed
forward rows; 13D Item-4 governance terms are shared provenance; saturated
source overrides reject same-source field churn; parked-surface
`reopen_condition` counts block readiness-audit re-reservations; daily and
intraday news now have text sanitation plus structured event observation
ledgers; OnclickMedia options ledgers gained more pending/settled outcome
rows; and fixed-entry exit-oracle diagnostics now persist full denominator
trade rows. None of that changes live orders, ranking, sizing, exits, or core
candidate selection.

The alpha reads were negative or only leads. Daily positive-event keyword
taxonomy failed forward edge checks; structured daily-news relation-quality
rows produced an observed-only 2026-forward lead but lack canonical-window
coverage; bearish options put-demand did not underperform consistently;
intraday advisory shadow actions did not show stable h1/h3 edge; the first
exit-oracle artifact was incomplete; close-confirmed static stops failed Gate
4; but the repaired full-denominator oracle rows produced one positive
observed-only lead: high account-risk trades (`actual_risk_pct >= 2%`) had
larger avoidable oracle regret than the lower-risk complement in all three
canonical windows. That is not an accepted exit rule because oracle best exits
use future prices; it only justifies a separately predeclared shared lifecycle
policy using fields known before exit. Breakout-without-2x-volume and 13D
governance candidate-pool retries stayed
rejected. The next compliant alpha should come from materially more closed
forward replacement rows, historical PIT coverage for a now-forward-only
surface, or a genuinely new economic data source such as borrow economics,
options/flow with fill-cost controls, campaign outcome provenance, parsed Form
144 sale pressure, or structured event tuples with canonical-window replay. Do
not spend another run on adjacent OHLCV precursor thresholds, positive-news
keyword lists, options moneyness/skew buckets, Form 4/Form 144 response curves,
close-confirmed stop retunes, intraday advisory reslices, or daily maturity
audits that only confirm unchanged reopen counts.

The July 1 maintenance batch did not add an accepted alpha, but it tightened
several operating boundaries. `exp-20260701-001` confirmed that rebuilding the
fixed-entry full-trade exit-oracle ledger was a duplicate of the June 30 repair;
future exit work must start from a new shared pre-exit lifecycle rule or new
settled shadow-exit rows, not another denominator materialization. Kova SEC13F
sponsorship attribution (`exp-20260701-002`) remained observed-only/rejected:
the score has broad row coverage, but no stable 10-day replacement edge, so
13F stays delayed ownership/crowding context unless non-quarterly flow,
campaign outcomes, or materially more settled rows appear. `exp-20260701-003`
accepted a measurement repair by recovering the missing 2026-06-30 daily
`clean_trade_news` final artifact from a valid atomic temp and restoring
structured event observation rows; those rows are forward evidence to mature,
not a reason to slice relation labels today. `exp-20260701-004` repaired a
paper-state parity defect in `alpha_score_market_regime`: same-signal-day
reruns now subtract already-pending entries for the same `as_of`, and the daily
report renders the persisted pending queue, so state and operator output cannot
silently diverge. `exp-20260701-005` was only a duplicate reservation closure.
`exp-20260701-006` accepted a narrow estimate-revision measurement repair after
the hot warehouse advanced to 2026-06-30: the five 2026-06-29 matched candidate
rows now have h1 replacement outcomes, but only one row is non-flat and h3/h5/h10
remain pending, so estimate-revision alpha is still not allocation-ready and
must not be sliced by thresholds, direction, top-N, hold, notional, or response
shape.

The practical queue is unchanged but sharper: first collect closed
forward-replacement rows for accepted/default-off and structured-news surfaces;
second, if exit alpha is revisited, test one production-visible lifecycle rule
through shared code and Gate 1-4; third, treat paper ledgers and reports as
stateful systems that need idempotency and pending-queue parity, not as loose
daily snapshots. Do not reserve new experiments for duplicate record repair,
same-day rerun explanations, Kova/13F sponsorship reslices, or news relation
condition cuts until the underlying row counts and horizons have actually
matured.

The July 2 batch adds data surfaces but does not promote a new tradable rule.
Most accepted records were measurement repairs: SEC FTD publication refresh,
current SEC semantic forward-readiness, estimate-revision candidate recovery,
Form 4 sale-overhang context, options forward-observation deltas, structured
daily/intraday news deltas, the SEC corporate-event stream, and the first
entity-exposure map. The one promising new alpha direction is not a raw SEC
event source. `exp-20260702-011` found a positive observed-only propagation
lead when SEC corporate events are mapped to exposed listed peers, but
`exp-20260702-012` rejected the first top-1/day deployable candidate source.
Treat SEC event exposure as a relation surface that still needs a fixed
ex-ante selection policy, PIT SIC-as-of-filing repair, daily default-off
snapshot wiring, and fresh settled replacement rows. Do not retune the same
event classes, theme overlay, SIC caps, liquidity gates, hold/cooldown, or
notional on the observed rows.

The same day closed several tempting retries. High actual-risk entry caps
failed the >10% EV materiality hurdle because high-risk rows were often winners
or too sparse; do not retune adjacent risk caps on the same fixed-entry rows.
Space Catalyst defense-budget events remain good versus broad ETFs but failed
same-theme opportunity cost, so do not promote semantic-bucket Space rows
without same-theme replacement evidence. Institutional 13F active flow stayed
window-fragile even when using actual structured-ZIP `FILING_DATE` availability;
13F remains delayed ownership/crowding context until non-quarterly flow,
campaign outcomes, borrow/loan cross-evidence, or materially more closed
10-day rows arrive. IPO and 425 merger theme-peer propagation both failed
stable sign tests; valid retries need richer deal economics such as pricing
range, consideration mix, bidder/target role, deal size versus peer float,
amendment/withdrawal/termination trajectory, or fresh forward rows under a
shared helper. Moomoo `get_capital_flow` graduated from data-source probe to a
full-stack rejection in `exp-20260702-019`: the archive covered mid_weak from
2025-07-02 and late_strong, but old_thin is structurally unrecoverable; the
fixed top-1/day main-inflow helper improved EV/PnL on covered windows but failed
drawdown drift, accepted-distribution comparator, and daily snapshot exposure
requirements. Do not turn this into a main-flow threshold or hold/notional
sweep.

The July 3 batch is mostly forward-row infrastructure, not an accepted alpha
promotion. Entity/theme news and prediction-market event observers were wired
into the daily path, relevance-gated, and given automatic cash/SPY/QQQ outcome
ledgers; estimate-revision candidate matching now refreshes after same-day
`quant_signals`; Moomoo capital-flow rows are exposed daily for forward
observation. The direct alpha reads were weak: second-order negative news failed
deployable top-1 compression, resolved S-1 peer substitution found no stable
edge, and entity/theme source-bundle rows were observed-only rejected. The
correct next step is to wait for these new default-off ledgers to accumulate
settled replacement-value rows, then test one fixed source-ranking rule or
relation graph. Do not reslice the first partial rows by source, keyword,
theme, prediction-market wording, or event-age buckets.

The July 3 late / July 4 batch tightens the same lesson: new surfaces are
valuable only when they create durable, PIT, settled rows. SEC Item 1.01
contract-relation provenance is now a useful observer surface, and economic
term tags are exposed through the shared daily observer, but issuer-self,
peer-target, public-counterparty, and amount/duration top-1 candidate sources
failed or remained observed-only. Do not turn that into regex, priority,
top-N, hold, cooldown, or notional sweeps; the next valid evidence is
prospective closed rows, normalized customer/supplier identity, contract value
/ duration / revenue exposure, or a non-SEC relation source. Prediction-market
rows needed semantic relevance repair before attribution; after the repair,
probability markets are event-risk context until closed replacement rows
mature. Accepted-sleeve forward maturation is now partly a parity problem:
volatility-relief and industry-stable core-flow underfiring was real current
sparsity, while turn-of-month had a concrete daily calendar parity defect that
was repaired. Let the repaired turn-of-month ledger collect outcomes before
activation work. Options event-distance / earnings-surprise-history joins and
Kova RS-proxy / static SEC13F breadth slices were not allocation-ready; current
observer alphas also remain blocked until a PIT settlement price surface covers
their entry sessions.

The July 5 batch produced no accepted alpha; it converted several "maybe ready"
surfaces back into concrete forward-data requirements. Narrow-range compression
and post-earnings underpriced drift passed representative admission/lifecycle
parity probes, so do not spend another ID on those probes unless a specific
daily helper input drifts. Observer outcome ledgers now distinguish true
no-entry price gaps from rows whose future entry date has not arrived, and
latest prediction-market / entity-theme summaries were refreshed under that
semantics; alpha reads still need more settled entry/open bars and replacement
value. Duplicate same-ticker same-entry exposure remains only an observed lead:
the historical validation and fixed cap simulation both failed on sample,
concentration, or Gate-4 evidence, so no cap/scalar/response change is allowed
until materially more independent duplicate rows close. Form 4 sale-overhang
context is now wired into daily non-OHLCV collection by default, but a risk
response needs at least 25 closed shared-helper context rows, at least 8
high-overhang rows, cash/SPY/QQQ replacement values, and max single-ticker share
<=40%. Turn-of-month has post-repair row supply (one open and one pending as of
the July 5 audit), but zero closed post-repair cash/SPY/QQQ replacement rows;
activation remains blocked. The orphan atomic-temp line was hardened after the
initial blocked cleanup: permission-retry cleanup is accepted measurement repair
only, and does not justify retuning observer, prediction-market, or contract
relation alpha fields. CISA KEV catalog additions became a rejected observed
lead: mapped MSFT/AAPL/GOOG/META event-study drift was mixed, baseline replay
had zero KEV-flagged trades, and the source remains context-only until a broader
issuer map or materially more flagged core entries can support a shared-helper
Gate 4 risk test.

The July 6 batch turned three tempting risk/allocation ideas into wait-for-rows
surfaces rather than policies. Deep QQQ drawdown rebound has one useful
artifact: a shared default-off observer with a one-entry-per-episode budget,
kept `trade_enabled=false`, because full repeated-entry replay lost heavily in
secular bears while the episode-budget variant was positive but too thin and
failed SPY-excess support. Do not retune stabilization, 200d, VIX, TLT, volume,
range, entry-budget, hold, or notional on frozen rows; valid evidence is new
settled live episodes or a genuinely new ex-ante capitulation/breadth source.
The first broad-OHLCV breadth/capitulation retry (`exp-20260706-017`) then
failed as a coverage read, not as alpha: only 2 of 17 historical first-entry
episodes had enough broad-warehouse breadth context, so do not retune breadth
thresholds until at least 12 of 17 rows are PIT-covered or new forward episodes
settle with the same fields.
Sector-concurrency and duplicate-exposure reads did not validate a cross-sleeve
cap: crowded rows were not a stable loss cohort, and pilot sector concentration
is now risk reporting, not alpha. Estimate-revision outcome settlement and
core-risk-intensity heartbeat wiring are accepted measurement repairs; both are
alpha-enabling only. Reopen estimate-revision and core-risk allocation after
prospective rows have cash/SPY/QQQ replacement value, not through another
readiness audit or risk-multiplier threshold sweep. FINRA weekly venue-share
also failed the useful-control bar after the non-ATS internalization-retreat
full-stack test (`exp-20260706-018`): aggregate EV/PnL was positive, but one
window regressed and the source did not beat accepted compression/distribution
comparators. Keep the archive and default-off snapshot for forward rows; do not
retune ATS/non-ATS direction, share ratios, trailing weeks, guards, hold,
cooldown, or notional on frozen windows. New observer/provenance orphan temp
cleanup remains blocked by filesystem permission-denied remnants; that is
operational hygiene, not a new text/event alpha axis.

The July 7 batch mostly rejected "small overlay" rescue attempts and tightened
measurement contracts. The portfolio covariance lane consumed the July 6
ranked rejected-source list as fixed 10% daily mark-to-market overlays; FINRA
short pressure, purchase-obligation, receivables/DSO, industry-breadth repair,
volatility-curve relief, gap-hold core-flow, distribution-pressure low-beta,
and peer-earnings-reaction overlays all remained observed-only rejected. Do not
keep replaying rejected candidate sources as tiny equity overlays unless the
evidence axis is materially new rows, a new risk model, or a different
execution envelope that is predeclared. The tick-to-ATR20 microstructure field
is a useful attribution lead but not a deployable gate: the observed split was
positive across short-trend artifacts, yet the leave-one-window admission test
failed after source-specific cutoffs and top-1/day compression. Reopen only
with richer PIT spread/depth/impact data or prospective replacement rows, not a
threshold retune. Entity/theme observer row growth also failed to clear the
replacement-value bar, so source-bundle/news-theme reslices remain frozen until
materially more settled rows or a genuinely new entity-relation source appears.
Accepted July 7 repairs are alpha-enabling only: estimate-revision catch-up now
settles recent ledgers through the daily path, live-drift reconciliation reads
the hot warehouse, pilot-scorecard fingerprints classify under their own data
source, and pilot concentration output exposes OR-rule metadata. The next valid
work is row accumulation, attribution, and parity checks on those repaired
surfaces, not immediate policy promotion.

The July 8 batch reinforced the same row-maturation boundary. Most accepted
work was measurement repair: daily July 7 orphan artifacts were recovered,
entity-theme daily output was advanced, estimate-revision writes became atomic,
Yahoo rate-limit retries were hardened, pilot stop-hit rows now expose
actionable status, and ORTEX / space-catalyst / news-exposure fingerprints now
have dedicated data-source keys. These are alpha-enabling repairs, not new
alpha evidence. The alpha reads were mostly negative: SEC Item 5.02 leadership
clarity, raw Item 2.05/2.06 restructuring/impairment, and text-confirmed
Item 2.05/2.06 did not produce deployable entry-risk drift; the production
crypto sleeve did not beat fee-aware BTC buy-and-hold; and fundamental-growth,
supplier-financing, and accepted-allocator forward packages remained too thin
or weak for activation. The one useful lead, a source-level default-off
kill-switch cohort, failed chronological validation because no pre-cutoff
source qualified for selection. Default next work is forward row collection,
source/fingerprint guard maintenance, and train-before-test source governance,
not SEC item/text regex retunes, crypto EMA retunes, or all-row kill-switch
threshold sweeps.

The July 9 batch was mostly plumbing plus negative alpha reads. The accepted
repairs are valuable because they protect future evidence: live position-control
ledger/daily wiring makes OK-to-add and core-slot state machine-checkable,
warehouse split repair fixes frozen pre-split OHLCV rows before refresh upserts,
and options-forward autowiring can now settle rows from the SQLite warehouse
without manual snapshot paths. These are measurement contracts, not alpha
promotions. Broad dispersion/skew/source-state routers, APP/META single-name
timing, split-repaired theme-peer revalidation, expectation-theme lifecycle,
and broad-dispersion core-entry admission did not create deployable policy
evidence. The only positive idea was official-government space catalyst events,
but promotion failed because canonical coverage is not ready. SEC 6-K historical
text and SBC grant-value normalization are still blocked by local text/evidence
coverage. Default next work is to let the repaired ledgers accumulate settled
replacement-value rows, not to retune dispersion, skew, single-name archetypes,
space catalyst filters, 6-K text regexes, or SBC ratio variants.

The July 10 batch extended the same pattern: most value came from making future
evidence surfaces machine-checkable, while the first candidate-pool attempts on
those surfaces failed or blocked. Candidate meta-labeling now has a canonical
and daily training ledger, but the first cohort read found no stable missed-alpha
bucket. SEC 13D/13G work added Item-4 campaign provenance, fingerprint coverage,
and 13G/A amendment direction materialization; fixed board-change and non-Big3
stake-increase candidate pools were rejected, so ownership remains a structured
context surface rather than a deployable source. GDELT tone, SEC 425 deal
economics, entity/theme news row growth, live rejected-source mirror positions,
and news-event exposure reads did not clear readiness or replacement-value bars.
Exit-lifecycle and advisory rows are now fingerprinted and daily-settled, but
the first materially-more-settled severity refresh did not preserve a usable
loss-separation edge, so it remains attribution only. Default next work is
data-surface maturation, relation/economics provenance, and predeclared cohort
validation, not field/threshold churn.

The July 11 batch added one accepted shared paper helper and closed a broad set
of tempting macro-relief near-neighbors. The retained edge is narrow:
`exp-20260711-004` promoted MOVE rate-volatility relief into a shared
default-off helper after reproducing the fixed private replay through daily and
report paths with `trade_enabled=false`. Treat the mechanism as
option-implied Treasury-rate volatility relief plus stock leadership, not a
generic credit or volatility-relief license. HYG/JNK full coverage, direct
high-yield OAS compression, VVIX relief, SKEW relief, curve steepening,
mortgage-rate relief, MOVE duration-priority ranking, and MOVE reentry
kill-switch variants failed or stayed observed-only negative. The same day also
fixed a live-drift measurement boundary: stale broker position IDs cannot stand
in for lot identity; current-lot entry dates must be reconstructed from
quantity continuity after full exits. SEC 13F chronological manager-skill
selection produced positive aggregate PnL, but failed Gate 4 because old_thin
regressed and drawdown drifted; treat delayed 13F manager alpha as context until
a non-quarterly flow or materially new manager-quality source appears. Default next work is forward
replacement-value maturation for the accepted MOVE helper and richer
non-price macro relation surfaces, not macro proxy threshold/rank/exit retunes.

The July 12 batch was mostly protocol and broker-execution measurement work,
with several tempting alpha reads rejected. Broker-authoritative order/fill
ledger wiring, real-fee calibration, pilot execution provenance, and centralized
PSR/DSR daily-return evidence are accepted measurement assets; they improve
future evaluation but do not promote live trading. The broker-fill alpha reads
failed as policy evidence: actual exits did not show robust five-session
avoidance value, and actual entries only looked partly positive before failing
the all-comparator median bar versus QQQ. The accepted MOVE helper should remain
standalone: forcing it into the accepted source-priority allocator at the
predeclared rank lost EV/PnL and regressed windows. DoD revenue-materiality was
the allowed richer relation after prior award failures, but it produced only
8 trades and failed the accepted comparators. Accruals/cash-conversion
revalidation under the repaired schema-v1 MTM protocol kept positive aggregate
PnL but still failed on window regression and drawdown. NFCI easing and
session semivariance similarly remain diagnostics. Default next work is
forward settlement, cost/provenance adoption in evaluation, and new genuinely
different data surfaces; not retuning broker-fill cohorts, MOVE allocator rank,
DoD thresholds, accruals deployment, or macro easing labels.

The July 13 batch reinforced two operating rules. First, entity/theme news still
has one plausible relation lead, but only after row duplication is removed:
exact-URL event baskets with equal-weight ticker allocation showed positive
observed-only replacement value, while the duplicate reservation that followed
added no evidence. The retained asset is the first-seen prospective observer
and shared default-off event ledger, not another frozen July reslice. Reopen
performance only after enough prospective unique-URL rows settle with complete
cash/SPY/QQQ replacement values and theme concentration controls. Second,
measurement identity matters as much as strategy identity: the MOVE/mortgage
compact-log wrapper bug showed how a stale delegated log writer can corrupt
novelty, failure-rate, and DSR trial accounting without changing strategy
behavior. Wrapper identity repairs are guard plumbing, not alpha axes. The new
Drugs@FDA CDER original-approval surface is the right kind of new evidence
source, but it is only a prospective observer until first-seen approvals,
public-sponsor mapping, and next-open/10-session outcomes mature. Default next
work is prospective settlement and relation/economic provenance, not source
filter, theme, approval-type, URL, or wrapper-identity retunes.

The July 14 batch says the new-data-source bar is working, but official-source
novelty is not enough by itself. USAspending non-DoD obligations joined the
right queue only as a prospective first-seen observer; performance must wait for
settled, mapped forward rows. ClinicalTrials, FDA device Class I recalls, CPSC /
NHTSA safety events, FDIC call-report deposit repair, EIA WPSR de-stocking, and
USDA FAS export-sales all failed the frozen-window promotion bar for the same
mechanism reasons: weak after-cost replacement value, old-window regression,
cluster-thin events, concentration, direct commodity/sector benchmark loss, or
non-PIT current-vintage mappings. FDIC also hit the Gate 3 survival floor, so
adding filters is explicitly forbidden. The portfolio covariance preflight
added a governance lesson: parked positive overlay shards cannot be recombined
through a historically selected subset or cross-protocol baseline. Default next
work is prospective first-seen settlement, first-release/as-of source vintages,
and independently authorized joint portfolio protocols; not field, basket,
threshold, hold, notional, or benchmark-retune loops on the same rows.

## Detail Sources

Generated mechanism memory lives in `docs/lessons/*.md`; exact facts live in
`experiments/tickets`, `experiments/logs`, `experiments/cards`,
`experiments/artifacts`, and committed code.

External research mappings live in `docs/alpha_external_research_map.md`.

Use detail sources only when choosing or auditing a concrete family. Keep this
playbook focused on the current operating readout, queue, and anti-repeat
rules.

## Research Queue

### 1. Forward Maturation Of Accepted Default-Off Adapters

Highest-value near-term work is not another replay sweep. It is forward
evidence on accepted paper adapters:

- low-deployment ETF cash substitute;
- lagged independent free-data consensus;
- SEC FTD confirmation and FINRA short-interest context, but not FINRA/IWM
  directional borrow-pressure unless a new borrow-fee/utilization source exists;
- post-earnings underpriced drift;
- Fundamental Growth RS;
- macro relief, volatility relief, rolling-correlation peer shock,
  industry-relative laggard repair, industry-stable core-flow,
  narrow-range compression breakout, turn-of-month liquid leadership, and
  52-week-high proximity core-flow (full-stack
  `accepted_paper_pending_forward`, exp-20260610-008);
- accepted-helper source-priority allocator with revision-surprise
  low-extension and lagged consensus as fixed accepted sources;
- distribution-day absorption leadership shared default-off adapter;
- SEC financial-report T+1 drift with RS20-leader default-off notional support
  from `exp-20260614-004`;
- SBC burden-improvement dilution-quality shared default-off adapter from
  `exp-20260616-015`;
- MOVE rate-volatility relief stock-leadership shared default-off helper from
  `exp-20260711-004`;
- VBB / VCP / Space observe-only buckets where nonzero forward rows exist.
- entry-regime-tagged forward replacement rows, options forward observations,
  Kova multi-source observations, and exit/LLM advisory outcomes as
  attribution surfaces only until closed-row replacement value is stable.
  Kova SEC13F sponsorship is now a positive observed-only 1d/3d/5d lead, but
  remains forward-only until 10d rows and/or historical PIT helper coverage
  mature.

Minimum forward package:

- candidate id and source family;
- exact displaced candidate or cash alternative;
- cost-adjusted replacement value;
- closed 5/10/20-day outcome where relevant;
- concentration and top-contributor share;
- replay-vs-forward parity status;
- reason no live order was placed.

Since exp-20260611-020, closed rows in `data/paper_sleeves/*/state.json`
carry replacement-value fields where comparable data exists. A readiness audit
should wait for materially more closed rows per adapter and use those fields as
the activation surface, not rerun a generic "replacement fields missing" audit.

July 5 status: admission/lifecycle parity is confirmed for narrow-range
compression and post-earnings underpriced drift, while turn-of-month has
post-repair supply but no closed comparator-ready rows. The next valid action is
collection and settlement, not threshold, rank, notional, hold-day, cooldown, or
activation-envelope retuning. CISA KEV is not a ready gate; reopen only with a
broader predeclared issuer map plus materially nonzero KEV-flagged replay trades,
or with a distinct cybersecurity event source.

July 6 status: accepted repairs improved row collection and health reporting,
not trade policy. Estimate-revision now settles matched-row outcomes through the
daily path; core-risk-intensity now writes a heartbeat even when there are zero
candidates; pilot reports now expose sector/industry concentration across manual
pilot sleeves. The next valid action is to let those ledgers accumulate closed
replacement-value rows and use them for attribution, not to retune sector caps,
risk multiplier stacks, or pilot admission rules. FINRA weekly ATS rise and
non-ATS retreat are both historical rejections now; keep them as default-off
forward ledgers only until settled rows or PIT borrow-fee/utilization evidence
create a new axis.

July 7 status: estimate-revision, live-drift, pilot-scorecard classification,
and pilot concentration metadata repairs are accepted plumbing only. The
portfolio overlay rescue lane and entity/theme row-growth refresh both failed
to create allocation evidence; tick-to-ATR20 is attribution-only until richer
microstructure fields or new prospective rows mature. Default next step is
settled-row collection and comparator-aware attribution, not another overlay,
threshold, source-bundle, or microstructure gate retune.

July 8 status: daily artifact recovery, entity-theme recovery,
estimate-revision atomic writes, yfinance retry handling, pilot stop-hit status,
and fingerprint coverage repairs restored or protected row collection. They do
not promote any sleeve. Fundamental-growth RS has only 10 enriched closed rows
and negative aggregate replacement value; supplier-financing has 5 enriched
closed rows and sector concentration; accepted allocator/source-consensus has
6 enriched closed rows. The forward package to wait for is still at least
watchlist-scale enriched closed cash/SPY/QQQ replacement rows with acceptable
concentration. The only fresh alpha hypothesis worth carrying forward is a
train-selected source-level kill switch once enough pre-cutoff rows exist; the
July 8 all-row lead is not policy-ready.

July 9 status: live position-control, split-adjusted OHLCV refresh, and
options-forward warehouse settlement are accepted measurement surfaces. They
should improve future row quality but do not change trading policy. The broad
dispersion/skew family, APP/META single-name timing, and current source-state
router attempts are rejected or observed-only negative. Space catalyst direct
official events are a watchlist lead only; do not promote until canonical
coverage and shared-helper replay exist. SEC 6-K and SBC grant-value work should
wait for richer local text/proxy evidence rather than another regex or ratio
reslice.

July 10 status: candidate-decision training ledger, SEC 13D/13G Item-4 and
13G/A direction materialization, GDELT/news/contract-relation/SEC-filing
fingerprints, and exit-lifecycle settlement are alpha-enabling measurement
surfaces only. The rejected reads say the next edge is not in retuning
same-source labels. Candidate meta labels need more leak-free complete rows and
a train-selected cohort; 13D/13G needs richer campaign outcome or forward rows;
GDELT and SEC 425 need coverage plus deal-economics fields; entity/theme news
needs fresh settled replacement value; exit lifecycle needs materially more
rows again plus slot-reuse/winner-collateral accounting or a shared pre-exit
policy. Crypto sleeve transfer reads should treat the current EMA/SMA target
policy as BTC-specific until a separately predeclared ETH/shared crypto policy
beats fee-aware buy-and-hold on EV, not only drawdown.

July 11 status: MOVE rate-volatility relief is now an accepted
`accepted_paper_pending_forward` helper; collect closed forward rows with
cash/SPY/QQQ replacement value before any activation-envelope work. The
neighboring macro-proxy family is mostly rejected: HYG/JNK breadth, direct
high-yield OAS, VVIX, SKEW, Treasury-curve steepening, mortgage-rate relief,
MOVE duration priority, and MOVE reentry kill-switch did not add robust
incremental value. Moomoo entry-date repair should use current-lot continuity
after full exits; do not reuse stale broker position ids as lot identity. SEC
13F prior-manager skill is still a rejected delayed-ownership context signal
after `exp-20260711-019`; do not retune manager skill thresholds without a new
flow surface. Official DoD award events also failed both the awarded-prime
self candidate and the predeclared non-awarded peer-substitution response:
the peer version produced only `+0.0460` aggregate EV / `+$222.13`, regressed
two windows, and concentrated 57.56% of positive PnL in one ticker. Treat DoD
awards as context until richer obligated-vs-ceiling/backlog economics or fixed
shared forward rows exist; do not invert the response or sweep peers again.

July 12 status: broker-authoritative execution rows are now a measurement
surface, not a promotion surface. Use them to calibrate fees, provenance, fill
identity, and future entry/exit attribution, but do not convert the first closed
broker cohorts into exit or entry policy. PSR/DSR evidence is now centralized
for future live eligibility; missing or non-recomputable trial panels fail
closed for live activation while leaving default-off acceptance unchanged.
MOVE stays as its own accepted helper until forward rows mature; the allocator
source-rank promotion failed. DoD awards need a second PIT economics source
or fixed forward rows, not another award/revenue threshold. Static accruals /
cash-conversion remains a rejected clue under schema-v1 MTM unless a new PIT
quality discriminator or forward replacement evidence appears.

July 14 intraday early readout (`exp-20260714-010`): the counterfactual
scorecard had counted Saturday and Sunday reviews that mapped to the same
ticker/next-open execution as independent evidence. Latest-pre-execution
economic-cohort aggregation preserves all 33 raw settled rows but leaves 22
effective next-close cohorts (11 duplicates excluded). On those effective
cohorts the fixed policy is `-$108.47` versus no adjustment and `-$66.53`
versus always adding; all 22 final actions equal the machine default, so
semantic lift is exactly zero and the LLM component is not identified. Keep
this as an early negative observed-only read. Review again at 50 effective
cohorts; do not reserve a frozen promotion hypothesis before 100 effective
cohorts, and do not treat raw ticker-day counts as independent sample size.

June 15 status: low-deployment ETF has only 17 positive closed rows and its
threshold/list/hold/notional retunes are frozen; the state-surface sleeve has
only 3 relevant rows; and the analyst-revision ledger has 1246 rows but zero
candidate matches. Forward work should build missing match surfaces and collect
more closed replacement-value rows before any activation or retune experiment.

### 2. PIT Structured Data Edges

The default alpha queue after the June 17-18 failures is data-edge construction,
not another replay. The repository has enough evidence that raw Companyfacts
ratios, raw SEC item codes, current-only filer metadata, metadata-only
ownership events, and static relation labels are mostly exhausted on frozen
windows.

June 18 readout (`exp-20260618-016`): the parsed Schedule 13D/13G surface is now
BUILT, not just a request. `quant/sec_13d13g_ingest.py` ingests EDGAR structured
`primary_doc.xml` (schemas `schedule13D`/`schedule13G`) into a PIT
holder/stake/intent table (`data/non_ohlcv/sec_13d13g_holdings/rows.json`, 3,318
parsed rows: 13D init+amend + 13G init across the three windows), joined to the
broad ~8,500-name warehouse for next-open-after-filing-date forward returns. A
read-only forward-10d SPY-excess diagnostic shows the parsed *holder identity*
field is the decisive axis that metadata-only exp-015/016 could not see: Big-3
(Vanguard/BlackRock/State Street) 13G crossings drift NEGATIVE (mean −2.41%, win
31%, n=671) while non-Big3 13G initial crossings are modestly POSITIVE (mean
+0.52%, median +0.18%, win 52.3%, n=1,682), strongest in the 7.5–10% new-stake
bucket (mean +1.36%, median +0.51%, win 56.5%, n=313). So exp-016's rejection of
13G was index-fund noise, not absence of signal. BUT this is a LEAD, not a
Gate-4 alpha: the edge is small (~0.5–1.3% median), `fresh_concentrated_13g`
mean is right-tail-negative in `old_thin` (−0.45%) and `old_thin` structured-XML
coverage is only 51% (pre-2025 mandate gap), and outside-activist 13D on the
broad large-cap universe shows negative medians (often priced by next-open or
issuer-control insiders). Decision: `observed_only`; the durable product is the
reusable parsed surface + parser tests. Do NOT run a frozen-window
candidate-pool replay of this until 13G/A stake-change direction, 13D Item-4
purpose text, and old_thin coverage are added and forward rows exist.

Highest-priority build surfaces:

- parsed Schedule 13G/13D primary documents (BUILT, exp-20260618-016 —
  holder/filer identity, beneficial ownership `classPercent`, reporting-person
  type, share count via `quant/sec_13d13g_ingest.py`). 13G/A amendment
  *direction* is now ALSO BUILT (exp-20260619-014 — item4 `classPercent` +
  `previousAccessionNumber` chain + `classOwnership5PercentOrLess` exit flag),
  and the increase edge was found weak/window-fragile (observed_only, axis
  closed on frozen windows). Remaining gaps are 13D Item-4 purpose-text intent
  classification, and pre-2025 `old_thin` structured-XML coverage;
- offering/prospectus primary text: proceeds, offering amount normalized by
  market cap and dollar volume, security type, ATM/shelf/takedown status, use
  of proceeds, and dilution terms;
- historical 10-K/10-Q cover-page filer status keyed by accession and accepted
  timestamp, not current submissions category;
- options chains with vendor as-of, stale-chain, open-interest lag, spread, and
  fill-cost controls across the standard windows or a forward-only observation
  ledger with closed outcomes;
- PIT borrow fee / utilization / availability, not FINRA share counts;
- structured customer/supplier/payment-term or unit-economics fields that
  explain DPO, advertising efficiency, contract-economics mechanisms, or
  customer-concentration quality;
- segment-level revenue/profit/divestiture/spin-off provenance, not raw
  `NumberOfReportableSegments` direction;
- debt maturity, covenant, refinancing, and credit-quality event terms from
  primary text, not raw maturity-bucket relief.

Minimum acceptance path:

- first pass Gate 2 field availability and PIT timestamp audit;
- implement a shared historical/daily parser or default-off helper before any
  accepted alpha claim;
- compare against accepted SEC/event, relation, and allocator comparators after
  costs;
- record parser failures, missing primary text, and coverage gaps as first-class
  fields.

### 3. Tail-State Classifier For Momentum And Broad Candidate Pools

Broad recent-winner, gap-and-hold, post-thrust inside-day, accumulation-base,
and market-pullback reclaim tests suggest a real but crowded continuation
surface with unacceptable tail/comparator risk. The next experiment should be
diagnostic/field-building before adapter promotion.

June 14 readout: `exp-20260614-010` rejected an accepted-allocator
market-breadth support tail-state bucket. Virtually removing
`weak_or_narrow_market_support` rows regressed EV and PnL in all three
canonical windows (aggregate EV `-0.6320`, PnL `$-13,584.41`). Treat broad
market breadth as attribution context for the allocator, not as a frozen-window
allocator tail filter.

June 15 readout: `exp-20260615-019` (measurement_repair) built the first
diagnostic surface for this queue: a mechanical PIT regime classifier
(probability over `risk_on_trend / choppy_range / risk_off_stress`, plus
`risk_off_score` and `bull_score`, from free index OHLCV + 50d-SMA breadth,
conventional non-optimized constants) and read-only conditional attribution of
accepted-sleeve replay trades by entry-day regime. Finding: both the accepted
Fundamental-Growth-RS sleeve and the rejected deferred-revenue scout lose
specifically in `choppy_range` (FGRS −$197.56/trade, 27% win; deferred
−$179.36/trade, 17% win) while staying clearly positive in BOTH `risk_on_trend`
and `risk_off_stress`. So the loss axis is directionless chop, NOT stress:
Spearman(`risk_off_score`, PnL) ≈ 0, meaning a naive monotonic "cut in risk-off"
tilt would not help — the useful construct is a chop indicator (low `bull_score`
AND low `risk_off_score`). This is a LEAD, not actionable: it is not a clean
3-window confirmation (`mid_weak` was classified ~entirely risk-on, ~0 chop
trades) and chop-bucket N is modest. Next step is a portfolio-level SOFT chop
down-tilt across accepted default-off sleeves, validated on forward
state-tagged replacement-value rows, never a hard per-window on/off gate. Do not
retune the regime constants or thresholds on the frozen windows. Classifier and
attribution live in
`quant/experiments/exp_20260615_019_pit_regime_state_attribution.py`; promote to
a shared daily regime artifact + parity test before any execution role.

`exp-20260615-023` then tested the industry-standard chop axis and REJECTED it:
swapping the exp-019 trend-state regime for Kaufman Efficiency Ratio (ER) of SPY
plus a continuous exposure scalar did NOT reproduce the separation and arguably
inverted it (FGRS ER terciles non-monotonic, Spearman +0.105; deferred low-ER
chop was the BEST bucket, Spearman −0.114). The ER day distribution shows why:
`late_strong`, the strongest window, had the LOWEST mean ER (0.157), because a
steady grind-up has low index path-efficiency. So ER conflates "low net move
with wiggles" with the structurally-below-trend market that actually hurt these
strategies. Lesson: the ER / Choppiness-Index convention does not transfer here;
the relevant chop axis is the 2D trend-state × breadth construct from exp-019
(SPY near/below 200d MA + weak breadth, not stressed), not index path-efficiency.
Retain the exp-019 regime label; do not substitute ER or retune ER window /
exposure floor on the frozen windows.

`exp-20260615-025` then promoted the exp-019 construct into a shared, tested,
rule-versioned module `quant/regime_chop_state.py` (`regime_chop_state_v1`):
regime probabilities + `bull_score` + `risk_off_score` + a continuous
`exposure_scalar` that softly down-tilts ONLY the choppy regime (floor 0.5,
never a hard gate). Re-validated through the shared module on the canonical
windows it reproduced the lead MORE cleanly than the raw label: continuous
`Spearman(p_choppy, PnL)` = −0.324 (FGRS) / −0.241 (deferred), with mean
`exposure_scalar` lowest in chop (~0.776) vs risk_on/off (~0.89). The module is
wired as an additive read-only `regime_chop` field on
`build_market_state_snapshot` (schema_version 2; the snapshot is already
diagnostic_only, so zero order effect). IMPORTANT fidelity caveat: the daily
market-context path supplies only the THIN subset (trend + 20d momentum + VIX,
no breadth/drawdown), which is materially weaker (THIN replay Spearman −0.17
FGRS / +0.04 deferred) — breadth/stress are load-bearing. Full-fidelity
`regime_chop` can be recomputed from SPY+universe bars for any date via the
shared module. Next steps (NOT done): (1) plumb breadth + SPY drawdown/vol into
the daily market context so the live field is full-fidelity; (2) validate the
`exposure_scalar` soft tilt on forward / live-pilot rows tagged with entry-time
regime, never by re-slicing the frozen windows; (3) do not tune regime constants
or the exposure floor on these windows.

`exp-20260615-028` then upgraded the LIVE daily fidelity: `quant/market_context.py`
now emits `spy_drawdown_from_high` + `spy_vol_ratio` (the stress axis) from the
SPY frame the daily path already supplies, so the production `regime_chop` field
moves from thin to stress_only with NO run.py change, and the adapter reports a
fidelity tier. Verified upgrade in Spearman(p_choppy, PnL): FGRS thin −0.173 →
stress_only −0.219 → full −0.324; deferred thin +0.045 (no signal) → stress_only
−0.171 → full −0.241. Breadth (the last increment to full fidelity) needs the
run.py call site to pass universe frames and is DEFERRED behind exp-20260607-003's
active run.py claim — `build_readonly_market_state_context` already accepts an
optional `universe_ohlcv_by_ticker` param, so the remaining wiring is one kwarg
once run.py frees up. Then validate the exposure_scalar soft tilt on forward /
live-pilot rows; do not tune constants on frozen windows.

`exp-20260622-017` (read-only) closes the obvious over-generalization of the
chop tilt: it regime-attributed the **core accepted stack** (61 canonical
baseline trades, exp-20260602-003) at full fidelity, which exp-019 never did
(exp-019 only covered the FGRS sleeve plus one scout). The core stack does NOT
share the FGRS chop-loss -- sign reversed and consistent across all three
windows: pooled `Spearman(p_choppy, PnL)` = **+0.116** (per-window +0.119 /
+0.082 / +0.118) vs FGRS -0.324, chop-bucket mean PnL +$2,991 (positive), and
the core enters in chop only 6/61 = 10% of the time because its entry gates
already concentrate in trend regimes. Applying the shared exposure_scalar soft
down-tilt to the whole core book would have CUT core PnL by -$29,048 (~12%) on
the frozen windows. Lesson: chop-sensitivity is SLEEVE-SPECIFIC, not
portfolio-wide. Any chop down-tilt must be scoped to the specific default-off
sleeves with individually-negative `Spearman(p_choppy, PnL)` (confirmed FGRS),
NEVER the core stack or a portfolio-wide capital tilt, and still requires
forward entry-regime-tagged rows -- not a frozen-window re-slice. Chop-bucket N
is small (6 core trades), so the direction is robust across windows but the
magnitude is indicative.

Candidate fields:

- `winner_continuation_tail_state_bucket`
- `momentum_crash_regime_bucket`
- `candidate_gap_chase_decay_bucket`
- `ret5_ret20_extension_ratio_bucket`
- `market_breadth_support_bucket`
- `same_day_displacement_candidate_type`
- `accepted_etf_substitute_comparator_delta`
- `cost_adjusted_drawdown_contribution_bucket`
- `gap_hold_event_absorption_quality_bucket`
- `post_thrust_pause_quality_bucket`
- `compression_breakout_tail_state_bucket`

Acceptance path:

- first read-only attribution;
- then default-off paper only if tail-state separation beats the low-deployment
  ETF and accepted compression/relation comparators after costs and drawdown.

### 4. Relation-Aware Event / Peer Fields

Local same-ticker SEC recurrence and same-sector peer transfer have failed.
Future event graph work must improve the relation, not the event count.
Recent OHLCV relation work adds positive templates: rolling-correlation peer
shock with core-flow confirmation, industry-relative lag plus same-day repair,
industry-stable leadership with core-flow admission, and volatility/macro
relief leadership. Recent failures add the negative template: sector/ETF
labels, core-selected anchors, negative peer shocks, SEC-provenanced peer
shocks, characteristic-similar same-industry shocks, and generic peer lag are
not enough.

Candidate relation sources:

- characteristic-similarity peers built from sector, fundamentals, liquidity,
  momentum, analyst coverage, and event history;
- customer/supplier or contract counterparties when source text supports it;
- early peer earnings reaction;
- source-family propagation with explicit timestamp and source provenance;
- dynamic correlation or hypergraph edges with explicit as-of dates, decay, and
  relation type;
- correlation-network stress clusters for risk first, not direct alpha.

Minimum fields:

- `peer_relation_source_bucket`
- `peer_similarity_method_id`
- `peer_edge_weight`
- `peer_edge_asof_timestamp`
- `peer_relation_pit_valid_flag`
- `early_peer_event_age_trading_days`
- `peer_transfer_strength_score`
- `relation_displacement_value_bucket`
- `accepted_relation_comparator_id`
- `relation_edge_failure_mode`
- `dynamic_relation_edge_decay_bucket`
- `relation_graph_high_order_cluster_id`
- `relation_source_provenance_hash`

Acceptance path:

- first compare against the closest accepted relation comparator, such as
  rolling-correlation peer shock, macro relief leadership, volatility relief,
  industry-relative laggard repair, or industry-stable core-flow;
- require displacement value after costs, not only standalone paper PnL;
- if the relation is production-visible and PIT-safe, use shared-paper-first
  instead of a private replay scout.

### 5. Expectation Revision With Real PIT Trajectory

Analyst/estimate revision remains promising but proxy-grade. Current frozen
snapshot evidence is not enough.

Needed fields:

- EPS and revenue revision velocity;
- analyst-count delta;
- estimate dispersion change;
- guidance raise/cut language;
- surprise-history adjustment;
- PEAD bucket with PIT `last_earnings_date`;
- source freshness and created-after-asof blockers.

Accepted default-off observation: `exp-20260610-014` admits
`revision_surprise_low_extension` as fixed rank 5 inside the shared
accepted-helper source-priority allocator. Do not retune revision rank,
revision thresholds, allocator top-N, notional, hold, or cooldown on frozen
windows.

Only promote revision-driven behavior to live trading after the PIT revision
source and forward replacement rows are available.

June 15 status: a revision ledger now exists, but the candidate match surface is
empty. The next useful step is not replaying revision thresholds; it is joining
revision breadth/dispersion/velocity onto historical candidates with as-of
timestamps and source freshness so replacement value can be measured.

### 6. LLM As Bounded Semantic Infrastructure

LLM remains useful for event understanding, not direct trading authority.

Allowed roles:

- classify event type, source credibility, semantic direction, and uncertainty;
- bind evidence spans to source documents;
- produce structured, replayable fields for paper attribution;
- explain catastrophic risk cases for operator review.

Forbidden without separate Gate 1-4:

- direct buy/sell instructions;
- sizing, slot, exit, or risk-budget authority;
- hidden reliance on facts not present in prompt/log/archive.

Minimum LLM field standard:

1. schema-bound JSON;
2. source id, timestamp, and evidence span;
3. ontology/schema version;
4. retrieval/parse/reasoning failure buckets;
5. production artifact visibility;
6. PIT replay safety;
7. chronological evaluation before strategy use.

Near-term implication from 2026 research: LLM and agent systems should be
treated as auditable evidence-processing infrastructure. The useful product is
not an autonomous trade call; it is a timestamped, schema-bound, retrievable
field with source coverage, calibration, uncertainty, and failure-mode metadata.
If the field cannot be replayed or compared against a displaced candidate after
costs, keep it out of trading logic.

June 30 implementation implication: deterministic news sanitation and
structured event tuples are now the default path for LLM/news alpha. Raw
positive/negative keyword taxonomies are not enough. A valid text retry needs a
replayable actor/relation/object/magnitude schema, source and text hashes,
explicit-ticker provenance, forward replacement rows, and either canonical
window replay or materially more mature forward rows before it can affect a
helper, prompt veto, rank, size, or exit.

## Anti-Repeat Rules

Do not repeat these without forward rows or a materially different
production-visible field:

- broad filter/gate tightening on the core stack;
- simple risk scalar / top-up sweeps;
- state-surface rank/profile/notional retunes below the hard EV threshold;
- ticker-specific exceptions from one or two trades;
- simple target, stop, time-stop, or fixed max-loss exit changes;
- exit-lifecycle advisory, LLM position-state, above-cost, confluence, or
  next-open diagnostic exits before a shared policy shows closed forward
  replacement value against cash, SPY, QQQ, and the existing hold path;
- LLM direct buy/sell/sizing/exit authority;
- raw full-universe `alpha_score` top-N or weight tuning;
- broad OHLCV factor mining that only rediscovers momentum;
- commodity/ETF/macro proxy leadership variants that merely relabel broad beta
  or cyclical beta;
- fixed theme-basket breadth/thrust variants, including semiconductor/AI
  hardware baskets, unless supported by new PIT ETF/constituent/catalyst,
  borrow/options/ownership, or forward replacement-value evidence;
- OPEX-week, quarter-end, holiday-adjacent, or other calendar leadership
  variants unless the new date field beats turn-of-month and the accepted
  allocator after costs in every canonical window;
- pre-earnings liquid leadership, low-bar, DTE, or earnings-calendar timing
  variants unless a new PIT expectation-trajectory field is present;
- broad 5-day winner continuation variants unless they solve drawdown/tail and
  beat the accepted low-deployment ETF comparator;
- gap-and-hold, breadth-confirmed gap-and-hold, post-thrust inside-day
  absorption, accumulation-base, quiet high-close accumulation, and
  market-pullback reclaim variants unless they add a new independent
  production-visible displacement field and beat accepted compression/relation
  comparators;
- pocket-pivot volume-signature variants (signal-day up-volume above the prior
  N-day max down-volume inside an uptrend / pre-breakout base): exp-20260611-009
  fired ~1/day (360 trades), was strong in late_strong/mid_weak but regressed
  old_thin on EV and PnL with drawdown drift, so the volume signature is too
  broad and only relabels momentum; do not retry by sweeping down-volume
  lookback, pocket volume ratio, base-high distance, trend SMA, or extension
  guards without a new PIT flow field or forward replacement rows;
- extra core-flow, VIXY/volatility-relief, or breadth confirmation layered on
  an already accepted candidate source unless it improves all windows versus
  that accepted source, not only the core baseline;
- adding an already accepted standalone helper as another source-priority
  allocator row unless the added source has distinct evidence and improves all
  windows versus the current allocator;
- adding VBB, distribution absorption variants, SEC FTD/FINRA confirmation, or
  slot-sliced core rows into the accepted allocator without new forward
  replacement-value evidence or a field that beats the current accepted
  allocator and accepted distribution comparator;
- source-pair conflict routers, pair-relative source-family history, or other
  accepted-allocator arbitration retunes unless the rule changes enough
  selections and beats the accepted allocator in every canonical window;
- source maturity, source-score percentile, candidate microstructure,
  same-ticker source confirmation, alpha-score rank rows, front-loaded
  extension filters, accepted-allocator market-breadth support filters, or other
  accepted-allocator arbitration retunes unless the
  new field is ex-ante, changes enough selections, and beats the accepted
  allocator in every canonical window;
- SPY-residual compression, overnight absorption leadership, and post-thrust
  pause/reclaim variants unless supported by a materially new PIT flow,
  options, borrow, event-quality, or forward replacement-value field;
- 13F sponsorship acceleration, 13F new-holder initiation, Form 144 isolated
  sale notice absorption, or adjacent ownership-disclosure entry rules as
  standalone alpha; use these delayed disclosures first for crowding,
  overhang, and context attribution, and require a new timing/provenance edge
  before any default-off candidate-pool retry;
- distribution-pressure low-beta / low-volatility defensive-leadership
  variants unless they beat accepted distribution-day absorption and show why
  they are not merely stale resilience or slow low-beta laggard exposure;
- pruning accepted allocator sources based only on late/mid source attribution
  when old_thin coverage or displacement rows may be doing the work;
- low-deployment ETF threshold, ETF-list, hold-day, or notional retunes;
- lagged free-data consensus source-set/source-family/timing/notional retunes
  that do not beat the accepted lagged independent-family comparator;
- FINRA/IWM, SEC FTD, borrow-pressure, top-N, cooldown, hold, or notional
  retunes without a new PIT borrow-cost / availability source;
- Companyfacts support-scalar mining, quality-gated top-1 replacement,
  same-industry peer confirmation, fresh-underreaction, or dual-growth
  threshold variants;
- Companyfacts broad quality candidate pools based on industry-relative asset
  growth, free-cash-flow / capex coverage, operating leverage acceleration, or
  adjacent scalar/threshold/top-N/hold/cooldown variants on frozen windows;
  June 15 evidence says these fields can be directionally useful but fail
  accepted-window, drawdown, concentration, or comparator gates without a new
  PIT discriminator;
- SBC burden-improvement threshold, tag-list, revenue/gross-profit floor,
  per-share/share-count/buyback tag, fact-age, RS/close/volume/volatility,
  top-N, notional, hold, cooldown, or allocator-rank retunes on frozen windows:
  `exp-20260616-015` accepted the fixed source as a standalone shared
  default-off adapter, while `exp-20260616-016` rejected rank-2 allocator
  insertion and `exp-20260616-017` rejected per-share buyback-adjusted
  refinement. Retry only with closed forward replacement-value rows,
  option-exercise / vesting context, or grant-value normalization;
- inventory-to-revenue leanness (annual InventoryNet / revenue ratio falling
  YoY, the Thomas-Zhang inventory anomaly) candidate-pool retries that sweep the
  inventory tag list, inventory/revenue threshold, revenue-growth floor, annual
  fact freshness, RS/close/volume guards, top-N, hold, cooldown, or notional on
  the frozen windows: `exp-20260616-018` was directionally positive (aggregate
  EV `+0.9345`, PnL `+$11,706.74`, 151 trades, beat accepted compression and
  distribution comparators) but REJECTED on `old_thin` EV/PnL regression and
  `+0.99pp` drawdown drift. A valid retry needs a sharper PIT inventory
  discriminator (quarterly inventory turnover, finished-goods vs raw-materials
  decomposition, days-inventory-outstanding trajectory) or closed forward
  replacement-value rows, not another threshold sweep of the rejected bundle;
- accruals / cash-conversion quality (annual NetIncome vs OperatingCashFlow)
  candidate-pool retries that sweep cash-conversion ratio, accruals/assets
  threshold, fact freshness, RS/close/volume guards, top-N, hold, cooldown,
  notional, deployment cap, or protective-stop level on the frozen windows:
  exp-20260614-020 already showed the fixed bundle is positively predictive
  (EV `+0.99`, PnL `+$21,322`, all windows positive) but rejected on `+5.2pp`
  drawdown drift; exp-20260614-021 low deployment and exp-20260614-023 7%
  daily-close protective stop both failed Gate 4. A valid retry now requires a
  sharper PIT discriminator (TTM same-period accruals, accrual-change momentum,
  quarterly cash-flow where reported) or closed forward replacement-value rows,
  not another risk-envelope or threshold sweep;
- interim TTM same-period cash-conversion acceleration retries that sweep TTM
  acceleration, comparable-period lag, fact-age, RS/close/volume guards, top-N,
  hold, cooldown, or notional on the frozen windows: `exp-20260614-026` improved
  aggregate EV/PnL but failed late_strong EV, old_thin coverage, and accepted
  comparator gates. A valid retry now needs closed forward replacement-value
  rows, analyst breadth/dispersion confirmation, or a materially different PIT
  quarterly cash-flow evidence surface;
- raw Companyfacts deferred-revenue / contract-liability / RPO demand
  acceleration candidate-pool retries that sweep demand-growth, demand/revenue,
  current-demand floor, concept priority, fact-age, prior-gap, RS/close/volume,
  top-N, hold, cooldown, or notional thresholds on the frozen windows:
  exp-20260615-017 was directionally positive (aggregate EV `+0.4288`, PnL
  `+$12,317.53`, 2/3 windows up, DD drift `+0.29pp` within cap, 150 trades) but
  REJECTED on `window_ev_regression` (late_strong EV `-0.0824`) and
  `accepted_distribution_ev_not_beaten`. A valid retry needs a selected PIT
  Companyfacts daily surface, a cleaner cross-industry concept taxonomy, or
  closed forward replacement-value rows, not another threshold sweep of the
  rejected fixed bundle;
- raw Companyfacts CapEx-to-depreciation / reinvestment-cycle candidate-pool
  retries that sweep CapEx/D&A tags, replacement-cycle ratio thresholds,
  revenue floor, sector exclusions, fact freshness, RS/close/volume guards,
  top-N, hold, cooldown, or notional on the frozen windows: exp-20260617-007
  was directionally positive in aggregate (EV `+0.7777`, PnL `+$11,550.79`,
  161 trades) but rejected on `old_thin` EV/PnL regression and `+1.09pp`
  drawdown drift. A valid retry needs materially different PIT reinvestment
  evidence such as industry-normalized replacement-cycle productivity,
  segment/customer capacity disclosures, or closed forward replacement-value
  rows, not another raw CapEx/D&A threshold sweep;
- broad raw Companyfacts relief/overhang candidate pools based on
  accounts-payable DPO extension, D&A burden relief, fixed-asset turnover,
  impairment relief, AOCI relief, deferred-tax allowance release, warranty
  reserve relief, pension/postretirement obligation relief, advertising /
  selling-marketing efficiency, public float scarcity, or adjacent tag /
  threshold / fact-age / RS / top-N / hold / cooldown / notional sweeps on the
  frozen windows. The June 17-18 batches showed repeated aggregate-positive but
  window-fragile, drawdown-worse, sparse, or concentrated behavior. A valid
  retry needs materially different PIT decomposition, such as segment/customer
  capacity, unit economics, OCI component attribution, contractual numeric
  spans, borrow/options context, or closed forward replacement-value rows;
- options-chain skew / open-interest candidate-pool claims before fixed-window
  historical coverage or a materially stronger forward evidence surface.
  `exp-20260617-004` and `exp-20260618-023` blocked this as measurement
  coverage, `exp-20260623-009` built the forward observation ledger, and
  `exp-20260623-010` then rejected the first closed-forward monotonicity read
  despite 1,252 closed rows / 969 quality rows: call-led / low-put-protection
  skew did not beat the low-bullish bucket on mean, median, SPY, QQQ, or
  month-cohort checks. Do not retry by sweeping put/call ratio, IV skew, open
  interest, volume, expiration, moneyness, top-N, hold, cooldown, or notional
  on this ledger; a valid retry needs materially more closed rows with
  replacement value, PIT vendor-as-of controls, borrow / loan-availability
  context, or historical PIT options chains covering the canonical windows;
- Kova multi-source RS/fundamental-alignment, SEC13F-sponsorship, or
  SEC13F-coownership-network
  candidate-pool claims that only sweep alignment score, source count, RS
  threshold, growth breadth, sponsorship score, holder count, 13F value,
  coownership peer count, lift, shared-manager count, Jaccard, network score,
  top-N, hold, cooldown, notional, or allocator thresholds.
  `exp-20260623-013` built the forward ledger, `exp-20260623-014` rejected the
  first RS/growth monotonicity read, `exp-20260624-015`/`016`/`017` repaired
  PIT SEC13F sponsorship and partial forward outcomes, `exp-20260624-018` found
  a positive observed-only 1d/3d/5d sponsorship lead that is not promoted, and
  `exp-20260624-019` rejected the coownership-network follow-up. Reopen
  only with enough closed 10d replacement-value rows, materially richer PIT
  manager/flow provenance, borrow/options cross-evidence, a new Kova source
  with PIT provenance, or a shared default-off helper with historical PIT
  coverage that beats cash, SPY, QQQ, and accepted comparators after costs;
- post-earnings high-liquidity, sector-residual, core-overlap, DTE, latest
  surprise, average surprise, pre-event RS, score, rank, or scalar retunes;
- SEC item-code / phrase / same-day absorption retries without richer semantic
  provenance or relation structure;
- SEC quantified backlog, RPO, bookings, book-to-bill, or customer-order text
  retries that only expand regexes or phrase lists; a valid retry needs
  structured customer/supplier contract economics, PIT numeric extraction, and
  a sample large enough to beat accepted SEC RS20 after costs;
- broad SEC business-update labels, including generic 8-K Item 8.01/7.01/1.01
  leadership, without richer event semantics or relation provenance;
- SEC filing complexity, change-density, periodic-report absorption, delayed
  confirmation, or quantified counterparty/customer commitment variants unless
  the retry has materially richer PIT semantic provenance and beats accepted
  SEC/event and non-text comparators after costs;
- raw SEC same-family bursts, first/follow-on recurrence, same-ticker
  cross-family transitions, same-sector SEC peer transfer, or same-sector
  event breadth retries;
- sector-level, same-industry characteristic-similar, negative-shock, or
  SEC-provenanced peer-shock retries unless the relation edge is stronger than
  rolling-correlation peer shock and has explicit PIT provenance;
- correlation-breakdown idiosyncratic leader and earnings-catalyst peer
  underreaction variants unless the new relation field beats accepted
  rolling-correlation / industry relation comparators after costs;
- industry pullback / down-shock resilience leader variants that only sweep
  group ret5/ret20, same-day resilience, close-location, volume, volatility,
  top-N, hold, cooldown, or notional. `exp-20260617-017` showed this mostly
  relabels relative strength inside a falling local group and fails accepted
  industry-stable / industry-relative / distribution comparators. Retry only
  with a new PIT flow, ownership, borrow/options, or relation-provenance field;
- Form 4 owner-count or liquidity-intensity retries without forward
  replacement value;
- broad clustered Form 4 open-market purchase candidate pools as standalone
  alpha; first use them for insider-interest context and require a timing or
  cluster-quality edge before retry;
- 13F low-crowding or low-sponsorship leadership filters as direct entry alpha;
  use 13F first for crowding, ownership-delay, and overhang attribution unless a
  new filing-timing or provenance edge beats accepted relation/allocator
  comparators;
- SEC AI-demand evidence-span, forward-guidance-quality evidence-span, or SEC
  dividend-increase text leadership variants unless the semantic field is less
  generic, less sparse, and beats the accepted SEC RS20 support comparator;
- Kova Companyfacts capital-efficiency / operating-efficiency candidate pools
  unless they add a field orthogonal to accepted Companyfacts low-liability/RS
  and beat that comparator in all canonical windows;
- Space price-action, ETF relative, defense-budget, low-thrust absorption, or
  theme-segment retunes on frozen windows;
- SEC filing-timeliness early-disclosure (latest annual 10-K filed abnormally
  early vs the company's own trailing filed-lag norm) candidate-pool retries
  that sweep earliness-days, current-lag cap, prior-filing-count, event-age,
  liquidity floors, FY duration, top-N, hold, cooldown, notional, or
  core/broad universe scope. `exp-20260617-019` first rejected the underpowered
  CORE-universe scout (18 trades, old_thin regression), and `exp-20260617-020`
  then tested the sanctioned same fixed gate over the BROAD liquid universe.
  The broad run expanded coverage to 1,137 eligible history tickers and 107
  paper trades, but was still REJECTED: aggregate EV `+0.0193` with PnL
  `-$3,690`, old_thin EV/PnL regression, and drawdown drift `+2.80pp`, while
  failing both accepted compression and distribution comparators. The breadth
  caveat is now closed. `exp-20260617-022` then tested the materially different
  quarterly 10-Q same-fiscal-quarter timeliness field over the BROAD liquid
  universe (1,197 eligible history tickers, 161 paper trades) and was also
  REJECTED: aggregate EV `+0.4060` and PnL `+$5,534.90`, but old_thin EV/PnL
  regressed, drawdown drift was `+0.52pp` versus the `0.50pp` cap, and the
  accepted distribution comparator was not beaten. Do not retry annual 10-K or
  quarterly 10-Q timeliness by sweeping earliness, current-lag, prior-filing,
  event-age, liquidity, duration, top-N, hold, cooldown, notional, or universe
  scope. A valid retry needs a materially different disclosure-timing field such
  as accelerated-filer-status change, NT 10-K/10-Q late-filing notices,
  segment/customer disclosure timing, or closed forward replacement-value rows;
- raw SEC form/item absorption sources, including 8-K Item 2.05 restructuring,
  Item 1.02 contract termination, Item 4.02 nonreliance, Item 5.07 vote
  results, business-combination/tender forms, offerings, S-8 employee-equity
  registrations, NT late-filing notices, and non-management proxy pressure, when
  the retry only sweeps form lists, 8-K/A inclusion, signal excess,
  close-location, volume, volatility, ret20, price/ADV, event age, top-N, hold,
  cooldown, or notional. The June 17-18 runs showed raw event metadata is too
  sparse, stale, or comparator-weak. A valid retry needs primary-document text,
  structured event economics, holder/stake/action context, or relation
  provenance that can be shared by historical replay and daily snapshots;
- raw Schedule 13G/13D metadata gates, 13G-vs-13D form thresholds,
  amendment-only or initiation-only ownership replays, and liquidity/top-N/hold
  retunes without primary-document text and parsed holder/stake/action rows;
- raw customer-concentration, inventory-component, debt-maturity,
  reportable-segment-count, and adjacent Companyfacts candidate pools that only
  sweep tag lists, thresholds, fact freshness, revenue/growth floors,
  RS/close/volume/volatility guards, top-N, hold, cooldown, or notional. The
  June 19 runs showed these fields are either too sparse, window-fragile,
  drawdown-worse, concentrated, or accepted-comparator weak. A valid retry needs
  parsed customer identity and contract economics, segment revenue/profit mix,
  refinancing/covenant terms, finished-goods/raw-material context with demand
  provenance, or closed forward replacement-value rows;
- FINRA/public-float short-pressure candidate pools based on settlement
  short-interest shares, public float, days-to-cover, liquidity, top-N, hold,
  cooldown, or notional. `exp-20260619-007` confirms that float-normalizing the
  FINRA signal does not repair the window/drawdown/comparator problem. Reopen
  only with PIT borrow fee, utilization, loan availability, options/put-skew
  context, or closed forward replacement-value rows;
- FINRA weekly OTC venue-share candidate pools that only change ATS vs non-ATS,
  rise vs retreat, trailing-week count, share-ratio threshold, tier/notional
  field, top-N, hold, cooldown, or notional. `exp-20260703-016` (ATS rise) and
  `exp-20260706-018` (non-ATS internalization retreat) both failed accepted
  comparator standards; reopen only with settled default-off forward rows from
  the shared ledgers or true PIT borrow/loan-availability economics joined to
  the same names;
- uranium/nuclear theme relation leadership, same-day core-flow confirmation,
  and defensive-sector ETF breadth/stock-leadership candidate pools that only
  sweep fixed theme baskets, anchor ETF lists, breadth thresholds, core-flow
  overlap, liquidity, volatility, top-N, hold, cooldown, or notional. The
  June 20 runs showed theme beta and defensive rotation do not become
  deployable relation alpha without a new PIT relation-provenance field or
  closed forward replacement value;
- intra-industry liquidity-leader lead-lag (top-3 by 20d dollar volume per
  industry run up vs SPY over 10d; a same-industry member that has NOT yet
  moved drifts to catch up) as a STATIC always-on candidate pool, and sweeping
  its leader-K / min-leader-excess / diffusion-gap / candidate-excess cap /
  lookback / industry-member minimum / liquidity / hold / cooldown / notional
  on the frozen windows: `exp-20260617-021` tested it on the broad liquid
  universe (1,026 eligible, 383 trades, excellent concentration HHI ~0.017) and
  it was REJECTED but STATE-DEPENDENT, not noise: aggregate EV `+0.1661`, PnL
  `+$5,103`, driven entirely by the transitional `mid_weak` window (dPnL
  `+$7,058`, dEV `+0.347`) while BOTH `late_strong` (`-$823`) and `old_thin`
  (`-$1,132`) regressed, with drawdown drift `+2.59pp`. Reading: in a strong
  trend leaders keep leading (no catch-up) and in chop the leader move reverses;
  the diffusion bet only pays in a transitional regime. This is mechanically
  distinct from the accepted industry-relative laggard repair (whole-industry
  strength + same-day repair) and is a clean lead for the regime-router line.
  The only sanctioned next step is a regime-CONDITIONED deployment tagged with
  the shared PIT `quant/regime_chop_state.py` module and validated on forward /
  live-pilot rows tagged with entry-time regime, never by re-slicing these
  frozen windows; do not retry as a static source or sweep its thresholds;
- portfolio-level equity-curve adaptive sizing based on fixed drawdown
  threshold and sub-1.0 notional multiplier. `exp-20260618-008` showed the
  system's 6-11% drawdowns tend to recover quickly; static drawdown cuts reduce
  recovery entries in a low-trade-count strategy. A valid portfolio-risk retry
  needs a fundamentally different mechanism, such as regime-conditioned position
  count/capacity constraints with forward evidence;
- parsed Schedule 13D/13G holder-stake candidate-pool retries that sweep
  stake-percent (`classPercent`), holder-type, Big-3 vs non-Big3, init vs
  amendment, top-N, hold, cooldown, or notional on the frozen windows:
  `exp-20260618-016` built the parsed surface and found the non-Big3 fresh-13G
  drift is real but small (~0.5-1.3% median forward-10d SPY-excess) and
  right-tail-negative in `old_thin` (where structured-XML coverage is only 51%),
  while outside-activist 13D shows negative medians on the broad large-cap
  universe. `exp-20260618-019` then rejected a fixed 13D Item-4 active
  strategic/governance phrase classifier plus price absorption: aggregate EV
  `-0.0145`, PnL `-$368`, only 6 trades, `mid_weak`/`old_thin` regression, and
  target concentration failure. A valid retry needs 13G/A stake-change
  DIRECTION, campaign/board-seat outcomes or other materially richer Item-4
  provenance, repaired pre-2025 `old_thin` coverage, or closed forward
  replacement-value rows — not a threshold, phrase-list, holder-type, event-age,
  top-N, hold, cooldown, or notional sweep of the parsed fields. Keep 13D/13G
  as ownership/crowding context until then;
- Form 4 conversion-without-disposal and issuer 8-K governance-resolution text
  candidate pools when the retry only changes transaction-code filters, phrase
  lists, item codes, RS/close/volume/volatility guards, top-N, hold, cooldown,
  or notional. A valid retry needs conversion purpose/lockup/selling-plan
  context, counterparty identity, ownership threshold, board-seat count,
  standstill duration, evidence spans, or closed forward replacement-value rows;
- SBC burden-improvement plus Form 4 compensation-context allocation retries
  that sweep the lookback, A/M/S/F code lists, 10b5-1 handling, owner roles,
  notional scalars, top-N, hold, or cooldown. `exp-20260620-004` failed versus
  the accepted SBC helper and suggests routine grants/exercises are mostly
  compensation plumbing unless paired with materially richer grant-value,
  vesting, retention, or executive-ownership context;
- supplier-financing / accounts-payable DPO plus debt-relief Companyfacts
  intersections that sweep DPO extension, debt/revenue relief, COGS/revenue
  floors, fact freshness, RS/close/volume/volatility guards, top-N, hold,
  cooldown, risk scalar, allocator rank, or notional. `exp-20260620-009`
  accepted only the fixed shared `4k` risk-scaled default-off adapter after the
  raw high-deployment intersection and first shared attempt failed. A valid
  next step needs closed forward replacement-value rows under that unchanged
  envelope, or materially new supplier/payment-term, covenant/refinancing,
  customer/supplier contract, or counterparty-economics provenance;
- accepted-helper allocator capital/capacity retries after the
  laggard/revision/peer-shock/turn-of-month/lagged-consensus source scalar
  stack. Do not sweep source scalar, source rank, source-set, top-N, hold,
  cooldown, `daily_entry_slots`, max-active cap, or second-slot admission on
  the frozen windows. `exp-20260621-008` showed the second slot adds gross
  overlay PnL but regresses `late_strong`, creates many more envelope skips,
  and displaces existing top-1 rows. A valid retry needs closed forward
  source-family or second-slot replacement-value rows, or a materially new
  out-of-sample PIT independence surface;
- portfolio hedges based on prior-close SPY trend-down state, fixed hedge
  fraction, or adjacent beta-hedge thresholds. `exp-20260621-002` failed
  aggregate EV/PnL and window gates even with a state gate. A valid portfolio
  risk retry needs a different mechanism such as regime-conditioned capacity
  with forward evidence, not a SPY-threshold or hedge-size sweep;
- factor/style residual leadership candidate pools that rely on MTUM/QUAL/VLUE/
  USMV/SIZE or adjacent factor ETF lists before those references exist in the
  production-visible PIT warehouse. `exp-20260621-003` blocked at Gate 2; a
  diagnostic sidecar is not enough. Reopen only after warehouse/daily parity
  coverage exists or with a materially different PIT flow, ownership,
  borrow/options, or forward replacement-value field;
- FX translation OCI tailwind allocation or drawdown-envelope retries that
  sweep volatility, drawdown, liquidity, notional, top-N, hold, cooldown, hedge
  confirmation, or cash-effect confirmation on frozen windows. `exp-20260621-005`
  remained aggregate-positive but failed drawdown and accepted-distribution
  comparators, following the earlier raw/hedge/cash-effect OCI failures. Reopen
  only with closed forward rows or materially richer PIT OCI component /
  hedging provenance;
- available-proxy residual idiosyncratic leadership and adjacent proxy-residual
  OHLCV candidate pools that only change proxy lists, beta lookbacks, residual
  thresholds, close/volume/volatility gates, top-N, hold, cooldown, or notional.
  `exp-20260621-011` had high aggregate EV/PnL but regressed windows, worsened
  drawdown, and failed the accepted distribution PnL comparator. A valid retry
  needs a new PIT flow, ownership, borrow/options, event-quality, or forward
  replacement-value field rather than another residual momentum relabel;
- SEC no-covenant credit-facility and customer prepayment / capacity-commitment
  text tuples that sweep phrase lists, dollar/market-cap thresholds, item
  codes, RS/close/volume/volatility guards, top-N, hold, cooldown, or notional.
  `exp-20260621-012` and `exp-20260621-014` produced zero useful target events
  in the fixed historical text surface. A valid retry needs normalized named
  customer/lender identity, non-cancelable exposure, contract duration/funding
  certainty, covenant/refinancing economics, or closed forward rows;
- parsed Schedule 13G/A amendment stake-change DIRECTION candidate pools that
  sweep the increase/decrease/exit cut, stake-percent delta, holder-type, Big3
  vs non-Big3, top-N, hold, cooldown, or notional on the frozen windows:
  `exp-20260619-014` BUILT the 13G/A direction surface (item4 classPercent +
  previousAccessionNumber chain + classOwnership5PercentOrLess exit flag) and
  found the non-Big3 INCREASE bucket weak (+0.16% median forward-10d SPY-excess,
  n=169) and window-fragile (mid_weak -1.18%), below the exp-016 baseline, while
  drop-below-5% exits are negative-drift ownership context not tradeable
  long-only. A valid retry needs repaired pre-2025 old_thin structured-XML
  coverage, fuller item4 numeric percent parsing for BNY-style multi-filer
  blocks (1,724/2,700 rows stayed direction-unknown), 13D Item-4
  campaign/board-seat outcome provenance, or closed forward replacement-value
  rows;
- SEC 13F same-manager co-accumulation peer-shock relation retries that sweep
  accumulation thresholds, shared-manager counts, lift, manager holding-count
  bounds, edge top-K, hold, cooldown, or notional on the frozen windows.
  `exp-20260622-007` was a legitimate new edge after static co-ownership, but
  failed window, sample, concentration, and accepted rolling-correlation
  comparator gates. Reopen only with non-quarterly ownership/flow evidence,
  active-manager conviction attribution, or closed forward replacement rows;
- Moomoo capital-flow and daily short-volume retries that sweep main-flow,
  short-volume activity, RS/absorption, top-N, hold, cooldown, notional, or
  response curves on the same frozen rows. `exp-20260702-019` rejected the
  first replayable `get_capital_flow(DAY)` top-1 main-inflow helper despite
  positive EV/PnL deltas because drawdown drift, accepted-distribution
  comparators, and full-stack daily exposure failed. `exp-20260622-010`
  separately rejected the daily short-volume activity helper. A valid retry
  needs materially more settled forward rows, genuinely new intraday/vendor
  flow decomposition, a completed daily default-off adapter exposure gap, PIT
  borrow fee/utilization/loan availability, or closed forward replacement
  value;
- forward activation-envelope experiments for accepted default-off helpers
  before one helper/source family has enough enriched closed rows with positive
  replacement value versus cash, SPY, and QQQ. `exp-20260622-011` and
  `exp-20260622-012` repaired measurement; `exp-20260622-013` found no
  activation-ready family. Do not re-slice frozen windows to force readiness;
- SEC 6-K positive-operating-update text candidate pools that sweep positive
  phrase lists, operating terms, percentage thresholds, same-day absorption,
  RS/volume guards, top-N, hold, cooldown, or notional. `exp-20260622-014`
  repaired the production-visible 6-K event/text surface, but
  `exp-20260622-015` produced zero target trades, and `exp-20260622-016`
  blocked before replay because generated historical 6-K text/cache artifacts
  still contained zero rows. Reopen only after a measurement repair materializes
  replayable 6-K/6-KA text rows across the canonical windows, then test one
  materially richer semantic field such as structured earnings tables,
  guidance-revision magnitude, issuer-country/ADR liquidity, translation
  provenance, or closed forward rows;
- options demand-quality forward attribution retries that only reslice current
  OnclickMedia call demand, put hedge, liquidity, stale-chain, moneyness,
  expiry, open-interest, or spread fields on the same settled forward ledger.
  `exp-20260624-026` built the reusable outcome ledger, but
  `exp-20260625-001` found no fixed demand-quality edge. Reopen only with
  materially more closed options rows, historical PIT chain coverage, or a new
  execution-cost / event-distance field;
- Moomoo borrow-availability or borrow-squeeze retries while fee, utilization,
  and loan-availability fields remain unpopulated. `exp-20260625-003` blocks
  this as data coverage, not alpha. Reopen only after rows contain real PIT
  borrow economics and can be joined to forward replacement outcomes;
- SEC13F active-manager or active-flow candidate pools that sweep active-manager
  definitions, flow deltas, filing-delay caps, holder counts, values, top-N,
  hold, cooldown, or notional on the frozen windows. `exp-20260625-009` is only
  an observed-only short-horizon Kova lead, while `exp-20260625-010` and
  `exp-20260625-012` rejected historical candidate-pool promotion. Reopen only
  with closed 10d replacement-value rows, non-quarterly flow evidence, or
  materially richer manager provenance;
- SEC 6-K structured-growth retries that bypass the historical text/cache
  blocker by using only form-scoped Companyfacts or adjacent XBRL fields.
  `exp-20260625-011` materialized event accessions but confirmed text cache
  coverage is still missing, and `exp-20260625-014` rejected the Companyfacts
  scout. Reopen after replayable 6-K/6-KA text spans exist, then test one fixed
  semantic/economic field;
- SEC project-finance/capacity-contract terms, Kova Companyfacts forward
  quality, Form 4 forward conflict, SEC FTD forward context, and volume-dry-up
  breakout retries that only sweep thresholds, liquidity/RS guards, event age,
  top-N, hold, cooldown, or notional on the same rows. The June 25 runs found
  no allocation-ready edge; valid retries need a new PIT data field, more
  closed forward replacement rows, or a shared helper with historical coverage
  that beats accepted comparators;
- estimate-revision candidate-match outcome or observed-only condition retries
  before the selected/current rows have a true PIT 2026-06-24+ daily OHLCV or
  quote-bar settlement surface. `exp-20260625-017` confirmed that Kova intraday
  rows were skipped and RS proxy rows are feature rows, not entry-open/close
  settlement data;
- SEC 10-K/10-Q cover-page filer-status-upgrade candidate pools, and any further
  network materialization of historical cover-page TEXT for that line.
  `exp-20260627-018` (measurement_repair) showed the DEI filer-status surface is
  materializable OFFLINE as a PIT proxy from local `dei:EntityPublicFloat`
  threshold crossings (Rule 12b-2: $700M large-accelerated, $75M accelerated) —
  no network needed, resolving the exp-20260626-008..exp-20260627-015 fetch
  blocker — but the line is STRUCTURALLY UNTRADEABLE in the core warehouse: of
  297 canonical 10-K/10-Q events (48 tickers, 38 in-warehouse), there are 27
  full-history filer-status transitions and only 4 inside the canonical windows,
  all UP-crossings to large-accelerated in float-explosion names (CIFR, CORZ,
  WULF, APLD) that are NOT in the tradeable warehouse, while all 38 warehouse
  filers are permanently large-accelerated (0 in-window tradeable transitions).
  The signal and the tradeable universe are disjoint; the transitions are also
  momentum-confounded (float crosses $700M because the stock already rallied
  multi-x) and stale-dated (Q2 float reported on a later 10-K). Reopen only with
  an expansion-approved universe containing pre-graduation float-explosion names,
  a PIT field separating the eligibility transition from coincident momentum, and
  closed forward replacement-value rows;
- weak-tape top300 / broad liquid universe expansion retries that only condition
  on the same old_thin weakness, breadth state, market regime, liquidity, top-N,
  hold, cooldown, notional, or drawdown cap. `exp-20260628-005` confirmed that
  the old_thin raw-EV nuance is not deployable because the remaining expanded
  window still pays with unacceptable drawdown and survival damage. Reopen only
  with a new PIT universe membership edge or settled forward replacement rows
  from an expansion-approved surface;
- Kova SEC13F, allocator-current concurrency, consumer-platform pilot, regime
  scorecard, or pilot-scorecard activation retries that only reslice the same
  partial/open 2026-06-28 rows. `exp-20260628-002`, `007`, `008`, `009`, and
  `010` all ended on the same binding issue: insufficient settled 10d or closed
  replacement-value rows, all-risk-on regime coverage, zero closed rows for the
  active surface, missing target_price, or no graduate candidate. Reopen only
  after materially more closed rows exist under the unchanged rule, or after a
  new production-visible data surface creates new rows;
- ORTEX / borrow-fee alpha retries while the local sidecar has only one ticker,
  no provider publication or usable-trade-date field, no append-only daily
  snapshot ledger, and no joined forward replacement outcomes. `exp-20260628-004`
  makes this a real data source lead, not an alpha-ready field. Reopen after
  PIT borrow economics have ticker/date breadth, publication timing, daily
  parity, and settled outcome joins;
- breakout-without-2x-volume precursor candidate-pool retries, including
  adjacent OHLCV breadth-persistence selectors, volume-threshold retunes,
  prebreakout entry timing, rank/top-N/hold/cooldown/notional changes, or
  response-curve variants on the exp-20260628-015/019 and exp-20260629-008
  rows. The de-biased full-population read showed the actual-trade lead was
  selection-biased, the deployable top-1/day shape failed comparator/drawdown
  guards, and the breadth selector still regressed windows. Reopen only with a
  materially new non-OHLCV pre-volume-confirmation field or settled daily
  forward rows from an exact shared logger;
- Form 4 sale-overhang risk-allocation retries while the shared daily context
  logger has no closed replacement-value sample. The observed-only split is a
  lead, not policy: reopen only after at least 25 prospectively logged rows
  close with cash/SPY/QQQ replacement value, at least 8 high-sale-overhang rows,
  and max single-ticker share <=40%, or with a materially new executive
  ownership/compensation provenance field;
- Form 144 planned-sale/float retries while cached primary documents,
  parseable planned-sale-to-float or planned-sale-to-ADV ratios, and closed
  forward rows are absent. `exp-20260629-002` parks the surface; do not retry
  by changing notional haircuts, risk scalars, ranking, candidate pools, or
  readiness-audit wording until the reopen counts move;
- structured Schedule 13D Item-4 governance-term candidate pools that sweep
  governance buckets, phrase lists, holder types, classPercent, signal
  absorption, event age, top-N, hold, cooldown, notional, or response shape on
  the frozen windows. `exp-20260629-006` built the shared provenance surface,
  but `exp-20260629-009` failed Gate 4. Reopen only with campaign/board-seat
  outcome evidence beyond regex provenance, repaired `old_thin` structured XML
  coverage, or closed forward replacement-value rows;
- saturated-source overrides that name only another same-source field, tag,
  XBRL label, phrase list, threshold, or response curve inside an already dry
  saturated source/gate cell. After `exp-20260629-010`, legal override evidence
  is limited to a genuinely new data source, a new gate shape, or materially
  more closed/settled forward rows;
- parked-surface readiness audits or response-curve retries before the
  recorded quantitative `reopen_condition` counts have actually advanced.
  After `exp-20260629-011`, "still not mature" is a pre-flight count check, not
  a new experiment ID;
- daily or intraday news alpha retries that only swap positive-event keyword
  lists, sentiment labels, source filters, event-age windows, or LLM prompt
  wording. After `exp-20260630-002` and `exp-20260630-005`, the legal route is
  structured event tuples with canonical replay or materially more closed
  forward replacement rows;
- options-flow alpha retries that only reslice current OnclickMedia rows by
  put/call demand, IV, open interest, moneyness, expiration, stale-chain flags,
  or spread buckets. `exp-20260630-010` keeps options as attribution context
  until materially more closed rows, historical PIT chain coverage, borrow/loan
  economics, or a new cost/event-distance field exists;
- close-confirmed static stop, trailing stop, target trim, time stop, hold-day,
  or response-curve retries on the same fixed-entry exit rows. After
  `exp-20260630-011` and `exp-20260630-012`, a valid exit retry needs full-row
  oracle cohort evidence plus a shared production/backtest lifecycle policy.
  `exp-20260630-018` supplies only an observed-only high-account-risk cohort
  lead; do not retune the 2% risk threshold, stop distance, target multiple,
  hold length, or response curve on those oracle rows. Reopen only with one
  shared pre-exit lifecycle rule, or with materially more settled forward
  shadow-exit replacement-value rows;
- intraday advisory shadow-action allocation or exit retries that only reslice
  the current settled snapshots by action type, horizon, LLM wording, or
  confidence. `exp-20260630-014` found no stable h1/h3 edge; reopen only with
  materially more closed rows or a new timestamped decision-quality field;
- SEC corporate-event exposure propagation retries that only change form set,
  event-class priority, relation priority, theme overlay, SIC peer cap,
  liquidity gates, top-N, hold, cooldown, notional, or response shape on the
  `exp-20260702-011`/`012` rows. The observed-only exposure map lead did not
  survive as a fixed top-1/day candidate source. Reopen only with a shared
  daily/backtest helper using one fixed ex-ante source-ranking rule, PIT
  SIC-as-of-filing repair, materially richer entity/economic relation data, or
  fresh settled replacement rows under the unchanged map;
- high-actual-risk entry risk-cap or early-risk response-curve retries that
  sweep the 2% actual-risk cap, stop distance, target multiple, hold length,
  early-weakness combo, notional, or adjacent risk buckets on the same fixed
  entry rows. `exp-20260702-010` failed materiality because high-risk entries
  were often winners or too sparse. Reopen only with a new pre-entry
  risk-quality signal or materially more settled entry-time risk outcomes;
- institutional 13F active-flow candidate pools that only change active-manager
  definitions, holder/value/share flow deltas, actual filing-date offsets,
  top-N, hold, cooldown, notional, or allocator rank. `exp-20260702-015`
  failed Gate 4 even after actual structured-ZIP `FILING_DATE` controls.
  Reopen only with materially more closed 10-day forward rows, non-quarterly
  flow provenance, campaign outcome evidence, populated borrow/loan
  cross-evidence, or a shared helper/daily snapshot surface that adds new
  out-of-sample rows;
- IPO or 425 merger theme-peer propagation attribution retries that only
  re-slice the same private-issuer or merger rows by theme subset, keyword,
  horizon, entry lag, density, SIC peers, ticker-status, top-N, hold, cooldown,
  notional, or response shape. `exp-20260702-017` and `exp-20260702-018` found
  no stable 10-day SPY-excess separation versus same-ticker baselines. Reopen
  only with richer deal economics, such as S-1/A pricing range, priced deal
  size, cash/stock consideration, bidder/target role, amendment/withdrawal or
  termination trajectory, or new forward rows under a shared helper;
- Moomoo capital-flow alpha retries that use only `get_capital_distribution`,
  main-flow thresholds, bucket response curves, top-N, hold, cooldown, or
  notional. `exp-20260702-016` proved `get_capital_flow(DAY)` history exists;
  `exp-20260702-019` then rejected the fixed versioned-archive top-1 helper on
  Gate 4. Reopen only after materially more settled forward rows, a genuinely
  different intraday/vendor flow decomposition, PIT borrow economics, or a
  daily default-off exposure/parity repair that changes the full-stack contract;
- entity/theme news, prediction-market event, and news second-order exposure
  retries that only re-slice the first July 2026 observer/outcome rows by source
  bundle, market wording, source relevance, theme, event-age, polarity,
  same-day bar, top-N, hold, cooldown, or notional. `exp-20260703-001`,
  `004`, `006`, `008`, `011`, `012`, and `013` made the observers and outcome
  ledgers automatic; `exp-20260703-002` and `014` rejected the first deployable
  or observed-only alpha reads. Reopen after materially more settled
  cash/SPY/QQQ replacement rows, or with a truly new PIT entity-relation source
  such as supply-chain, customer, contract, or verified economic-exposure
  provenance;
- SEC Item 1.01 contract-relation retries that only adjust relation regexes,
  economic-term regexes, counterparty-count tags, relation priority, source
  ranking, top-N, hold, cooldown, notional, or public-counterparty / peer-target
  response shapes on the `exp-20260703-017..022` and `exp-20260704-001/004`
  rows. The provenance and economic-term observer surface is retained for
  forward evidence, but deployable issuer-self, peer, public-counterparty, and
  amount/duration candidate sources did not clear the bar. Reopen only with
  prospective closed replacement rows, normalized CIK-linked customer/supplier
  identity, contract value/duration/revenue exposure, or a genuinely different
  non-SEC relation source;
- accepted-sleeve activation or admission-parity retries that ignore the July
  4/5 autopsy split: volatility-relief and industry-stable core-flow currently
  have expected sparse admissions; turn-of-month had a daily calendar parity
  defect that was repaired and now has only open/pending post-repair rows;
  narrow-range compression and post-earnings underpriced drift have
  representative parity confirmed. Do not retune thresholds, ranks, scalars,
  hold days, cooldowns, or activation envelopes from zero or open-only rows;
  wait for post-repair closed cash/SPY/QQQ replacement value or a concrete
  helper-input drift;
- options event-distance / earnings-history and Kova RS-proxy / static SEC13F
  ownership-breadth retries that only reslice the same current forward rows by
  DTE, surprise-history bucket, 20d/120d RS ranks, holder breadth, top-N, hold,
  cooldown, or notional. `exp-20260704-002`, `011`, `013`, and `014` found no
  allocation-ready edge. Reopen only with materially more settled forward rows,
  historical PIT options-chain or Kova coverage, richer earnings guidance/call
  fields, non-quarterly ownership/flow provenance, borrow/options cross-evidence,
  or a new production-visible data source;
- current observer alpha retries before the settlement price surface is
  gate-ready. `exp-20260704-012` blocked prediction-market, entity-theme, and
  intraday structured-news reads because entry/open bars, `entry_date`, or
  `target_price` were missing and the hot warehouse update hit disk I/O errors;
  `exp-20260705-006/007` repaired future-entry versus true-no-entry semantics
  and refreshed summaries, but did not create allocation evidence. Reopen only
  after materially more settled observer rows have entry/open bars and
  cash/SPY/QQQ replacement value, or after a genuinely different PIT observer
  relation source appears;
- duplicate same-ticker same-entry paper-exposure caps, scalars, source
  priority changes, or response curves based only on the first July 5 forward
  lead. `exp-20260705-002` was observed-only positive, while
  `exp-20260705-003` and `exp-20260705-009` failed historical validation /
  policy evidence. Reopen only with materially more closed cross-sleeve
  duplicate forward rows, independent historical/default-off duplicate rows
  across at least two windows, or a full shared-policy Gate 1-4 cap test;
- Form 4 sale-overhang risk-allocation retries before the daily context logger
  accumulates the recorded minimum sample. `exp-20260705-011` wired the
  accepted data-only context into daily non-OHLCV collection; a valid alpha
  retry needs at least 25 closed shared-helper context rows, at least 8
  high-sale-overhang rows, cash/SPY/QQQ replacement values, and max
  single-ticker share <=40%, or a distinct new data source/gate shape;
- CISA KEV entry-risk gates on the first mega-cap issuer map. `exp-20260705-014`
  found mixed post-addition event-study drift and zero KEV-flagged canonical
  replay trades, so threshold/window/response retunes are frozen. A July 15
  zero-ID preflight tested the genuinely different direct-short event-basket
  shape against CISA's immutable `kev-data` blob
  `f7fae55e6c8b25cdcaceee246f2c36c6456d59fe` (catalog `2026.07.14`). Exact
  event-date public-company mapping produced 50/34/47 issuer-weeks across
  16/15/17 tickers with top-1 shares 30.00%/23.53%/21.28%, but the old-thin
  pass depended entirely on JNPR and SWI. Neither has old-thin bars in the
  canonical broad OHLCV warehouse; after intersecting with settlement-ready
  prices, old-thin falls to 48 issuer-weeks across 14 tickers and MSFT rises to
  31.25%, failing the predeclared 30% concentration cap. Do not reserve a
  short-basket ID by expanding aliases or dropping the price-coverage check.
  Reopen with immutable old-thin bars for at least two independent mapped
  issuer-weeks (plus an explicit short-borrow/execution envelope), materially
  settled fixed-policy forward rows, or a distinct cybersecurity incident
  source;
- deep-drawdown rebound candidate pools or observers that sweep stabilization
  day, one-entry budget, 200d correction classifier, VIX panic, TLT rate-relief,
  volume/range capitulation, hold, cooldown, or notional on the 2000-2026 QQQ
  replay rows. `exp-20260706-003` rejected repeated-entry rebound because
  secular-bear re-entry bleed overwhelmed correction gains; `exp-20260706-004`,
  `005`, `008`, `009`, and `015` did not supply stable quality gates; and
  `exp-20260706-006` retained only a default-off observer. `exp-20260706-017`
  tried the first broad-OHLCV breadth/capitulation gate but had only 2/17
  PIT-covered rows, so breadth threshold/lookback retunes are frozen until
  coverage reaches at least 12 of 17 historical rows or new forward episodes
  settle with the same fields. Reopen with those rows or a genuinely new
  ex-ante capitulation/breadth/macro data source fixed before replay;
- same-sector concurrency, pilot sector concentration, or duplicate-exposure
  risk caps based only on current default-off forward rows. `exp-20260706-001`
  accepted reporting only, while `exp-20260706-002` rejected the sector
  concurrency edge. Reopen with materially more closed cross-sleeve rows, a
  concrete missed-risk incident requiring a new fixed grouping, or a full shared
  Gate 1-4 cap policy;
- core-risk multiplier stack caps or response curves before prospective
  `core_risk_intensity` rows close with replacement value. `exp-20260706-013`
  found high-stack canonical entries were not a stable loss-tail cohort, and
  `exp-20260706-016` only repaired heartbeat state. Reopen with closed forward
  rows or a full shared production/backtest sizing-cap ablation;
- estimate-revision candidate-match alpha retries that only audit readiness
  after `exp-20260706-010`; outcome settlement is now wired, so the next alpha
  read needs newly matured H3/H5/H10 rows with cash/SPY/QQQ replacement value
  or a distinct revision data source;
- observer/provenance atomic-temp cleanup experiments that use stale hidden
  temp files as an alpha evidence axis. `exp-20260706-014` remained blocked by
  permission-denied orphan files after recovery attempts. Reopen only for a real
  cleanup regression or after materially more settled observer/provenance rows
  support an alpha read;
- per-rejected-source portfolio overlay consumption from the
  `exp-20260706-022` ranking list. Owner-authorized `exp-20260715-002` replaced
  the invalid additive/double-scaled overlays with one complete 31-family
  Gate 4-P batch: fixed 90/10 capital, a real `$10k` no-leverage candidate cash
  ledger, fixed non-overlapping calendars, boundary force-closes, and 10,000-draw
  simultaneous max-T inference. All 31 failed the formal comparison against
  100% core; the best sleeve had aggregate EV `-0.94934` and PnL `-$19,348.24`
  even though it added EV `+0.64143` and PnL `+$11,059.52` versus leaving the
  10% sleeve in cash. This distinguishes genuine sleeve contribution from the
  larger opportunity cost of displacing the current core. Do not consume or
  retune these 31 representatives again. Reopen only with a prospective ledger,
  a complete pre-frozen selection panel, a genuinely new candidate family, or
  a separately authorized risk-budget gate that explicitly permits return
  sacrifice for tail-risk reduction;
- SEC NT late-filing, Item 3.01 listing-compliance, Item 5.02 leadership-text,
  and Item 2.05/2.06 restructuring/impairment entry-risk gates that only retune
  item lists, primary-text regexes, price/ADV/liquidity gates, same-day return
  filters, event age, top-N, hold, cooldown, notional, or response shape. The
  July 7-8 reads found thin deployable samples, non-negative or positive long
  drift, concentration, or comparator failure. Reopen only with materially
  richer event economics, relation/counterparty exposure, restatement/legal
  outcome provenance, or settled forward replacement rows under a fixed shared
  helper;
- default-off source-level kill-switch policies selected from all available
  forward rows. `exp-20260708-017` is an observed-only lead, but
  `exp-20260708-018` failed chronological validation because the training
  segment selected no qualified kill sources. Reopen only after enough
  pre-cutoff complete rows exist to select sources ex ante, then validate on a
  later holdout segment with cash/SPY/QQQ replacement value and concentration
  controls;
- crypto sleeve EMA/SMA target-policy activation or parameter retunes based on
  the current saved production snapshots. `exp-20260708-010` failed the
  observed-only policy checks versus fee-aware BTC buy-and-hold and cash.
  `exp-20260710-017` then showed the same shared target policy transferred to
  ETH can reduce drawdown but still fails the predeclared EV win rule versus
  fee-aware ETH buy-and-hold. Reopen only with materially more saved production
  snapshots, a new execution cost/liquidity surface, or a different predeclared
  crypto policy family;
- broad dispersion, skew, source-state router, or core-entry admission gates
  that only retune dispersion percentile, average-correlation cutoffs, skew
  buckets, source/source-family slices, top-N, hold, cooldown, or response
  shape on the current forward rows. The July 9 reads did not produce a
  train-selected deployable policy. Reopen only with materially more settled
  replacement-value rows, a joint predeclared covariance/capacity model, or a
  new PIT breadth/dispersion data surface;
- APP/META single-name specialist timing retries that only change the same
  OHLCV archetypes, trend/reclaim/breakout labels, lookbacks, hold days,
  cooldown, or notional. `exp-20260709-009` did not justify a standalone
  ticker policy. Reopen only with a new ticker-specific event/source surface or
  materially more settled forward rows under a fixed helper;
- space catalyst direct-official promotion before canonical coverage and a
  shared helper exist. `exp-20260709-014` is a positive observed-only lead, but
  `exp-20260709-015` failed promotion coverage. Do not retune event wording,
  official-source filters, peers, top-N, hold, cooldown, or notional from the
  same sparse surface;
- SEC 6-K text and SBC grant-value normalization retries that only add regexes
  to currently missing local evidence. `exp-20260709-012` and
  `exp-20260709-018` show the blocker is coverage/evidence availability, not
  a threshold. Reopen with materially more accession-bounded local text,
  proxy/vesting/grant-value data, or a distinct production-visible document
  source;
- fingerprint/data-source coverage repairs as alpha evidence. ORTEX,
  intraday structured news, SEC filer status, pilot scorecard, space catalyst,
  and news-event exposure classification repairs are accepted guard plumbing.
  New data surfaces must update `_DATA_SOURCE_KEYWORDS` and tests when built,
  but the repair itself is not a valid new alpha axis;
- candidate meta-label alpha retries that only reslice current candidate-decision
  training rows by skip reason, rank, source, score, or horizon. July 9-10 built
  the canonical/daily ledger, but the first observed-only cohort read found no
  stable missed-alpha bucket. Reopen only with materially more leak-free complete
  forward rows, a train-before-test cohort, or a genuinely new candidate context
  field;
- GDELT tone/news-volume, entity/theme news, and news-event exposure retries
  that only change tone thresholds, source bundles, themes, event-age windows,
  or response shapes on the same July rows. GDELT is still coverage/fingerprint
  plumbing; entity/theme row growth did not create edge; split-repaired
  news-event rows are measurement repair. Reopen only with materially more
  settled cash/SPY/QQQ replacement rows, verified economic relation provenance,
  or a new PIT news data source;
- SEC 13D/13G Item-4 campaign or 13G/A stake-direction candidate pools that only
  sweep board-change phrases, holder classes, Big-3 exclusions, stake-increase
  thresholds, event ages, top-N, hold, cooldown, or notional. July 10 repaired
  provenance and fingerprints and materialized 13G/A direction, but fixed
  board-change and non-Big3 stake-increase sources were rejected. Reopen with
  richer campaign outcome evidence, old_thin coverage repair, non-quarterly flow
  provenance, or settled forward replacement-value rows;
- SEC 425 merger/deal-economics retries before local text coverage exposes
  bidder/target role, cash/stock/mixed consideration, amendment/withdrawal state,
  and deal-size economics. July 10 blocked on coverage; do not retry with only
  form-code, phrase-list, or event-age changes;
- exit-lifecycle/advisory severity risk-allocation retries that only slice the
  same settled rows by urgency, action type, horizon, LLM wording, or confidence.
  July 10 wired fingerprinting and daily settlement; policy promotion still
  requires a shared pre-exit lifecycle rule or materially more severity-tagged
  closed replacement-value rows. `exp-20260715-006` used the valid growth from
  320 to 482 total settled h5 rows to run one unchanged-policy validation on
  the post-2026-06-30 cohort. It rejected promotion: only 67 rows were settled
  in that fixed cohort (10 advisory, 5 hard-stop) versus preregistered minima
  of 100/20/8, and hard-stop mean and median returns were not worse than the
  no-advisory bucket. Park this exact surface; do not reserve another readiness
  or label/threshold reslice. Reopen only with a new source/gate shape, or when
  the same fixed post-cutoff cohort has at least 101 settled rows, 20 advisory
  rows, and 8 hard-stop rows;
- MOVE / credit / rate-relief macro-proxy retries that only change moving-average
  spans, relief thresholds, ETF proxy lists, duration/sector priority ranks,
  hold/cooldown/top-N/notional, or reentry kill-switch timing. July 11 accepted
  only the fixed MOVE stock-leadership shared paper helper; HYG/JNK, high-yield
  OAS, VVIX, SKEW, Treasury-curve, mortgage-rate, duration-priority, and MOVE
  reentry variants did not create robust incremental value. Reopen with
  materially more closed MOVE forward replacement rows, a distinct PIT macro
  relation source, or a new gate shape, not another proxy/rank/threshold retune;
- moomoo open-position entry-date repairs that infer current lot identity from
  stale broker position IDs after a full exit. July 11 rejected that fallback
  and accepted current-lot backward reconstruction from present quantity and
  deal continuity; future repairs must preserve lot continuity semantics;
- SEC 13F chronological manager-skill retries that only change prior-return
  horizons, min training additions, manager count, holder-growth/value-share
  thresholds, liquidity floors, top-N, hold/cooldown, or overlap exclusions.
  July 11 showed positive aggregate PnL but failed Gate 4 on old_thin regression
  and drawdown drift; reopen only with non-quarterly institutional-flow evidence
  or a materially new manager-quality source;
- DoD daily contract-award retries that sweep award thresholds, prime/branch/
  modification filters, peer lists, peer-rank weights, absorption thresholds,
  top-N, hold, cooldown, notional, or simply invert awardee versus peers.
  `exp-20260711-020` rejected the awarded-prime self candidate and
  `exp-20260711-023` rejected the non-awarded peer-substitution response across
  all three windows. Reopen only with obligated-versus-ceiling/new-award
  economics from a second PIT source, backlog/revenue normalization, a fixed
  shared helper with materially settled forward replacement rows, or a truly
  different supplier/customer relation;
- broker-authoritative fill alpha retries that only reslice the first trusted
  closed entry/exit cohorts by action type, fill route, hold horizon, ticker,
  or time cohort. July 12 observed-only reads failed the robust all-comparator
  entry/exit bars; reopen only with materially more trusted closed broker rows,
  a new predeclared execution-quality field, or a shared policy that changes
  the lifecycle before the fill;
- accepted MOVE allocator-source promotion retries that only change rank,
  scalar, source priority, top-N, hold/cooldown, or allocator tie-breaks. July
  12 showed the standalone helper does not survive source-priority arbitration
  under the predeclared rank; reopen only with materially more closed MOVE
  forward replacement rows or a new allocator gate shape;
- DoD award revenue-materiality retries that only adjust award/revenue cutoffs,
  new-award exclusions, branch/prime filters, peer lists, absorption gates,
  top-N, hold, cooldown, or notional. July 12 tested the richer allowed
  revenue-normalized relation and it was too sparse; reopen only with a second
  PIT obligation/backlog/segment-economics source or settled fixed-helper
  forward rows;
- annual accruals / cash-conversion retries that only change deployment,
  stop/hold/notional, static thresholds, or schema-v1 revalidation framing.
  July 12 confirmed the unchanged bundle remains rejected under corrected
  daily-MTM Sharpe evidence; reopen only with a materially new PIT quality
  discriminator such as fresher TTM/quarterly cash-flow evidence or forward
  replacement rows;
- entity/theme event-decision-basket retries that only change URL dedup,
  source bundle, theme, article-age, mapped-ticker weighting, polarity, top-N,
  hold, cooldown, or notional on the frozen July observer rows. July 13 found a
  positive observed-only exact-URL basket lead, then retained a prospective
  first-seen observer instead of promoting the frozen read. Reopen deployable
  evaluation only after the prospective helper has at least 75 settled
  unique-URL events across at least 15 first-seen decision dates and 3 themes,
  max theme share <=30%, with complete cash/SPY/QQQ replacement values;
- experiment-log wrapper identity repairs as alpha evidence. July 13 repaired a
  stale delegated compact-log writer that wrote a MOVE-derived identity into
  the mortgage-rate relief shard; future work should touch this lane only when
  a manifest hash mismatch, cross-ID shard write, or source-bundle identity
  defect is detected;
- Drugs@FDA / CDER original-approval alpha retries before prospective
  first-seen approval rows mature. The July 13 official source is valuable
  because it is a new PIT candidate surface, not because historical approvals
  can be replayed as newly known. Reopen performance only after at least 30
  prospective first-seen approvals across at least 20 approval dates with
  contemporaneous public-sponsor mapping and complete next-open/10-session
  cash/SPY/QQQ outcomes, or after obtaining an independently auditable official
  historical PIT snapshot archive;
- Wikimedia issuer-page attention retries that only change canonical page
  aliases, same-weekday baselines, lag days, sign thresholds, top-N, hold,
  cooldown, or response shape on the fixed 26-page accepted-core universe.
  July 13 achieved complete 26-page coverage and 50 joined trades, but the
  pooled positive surprise cohort underperformed non-positive surprise and
  continuous surprise was negatively monotonic. Reopen only with timestamped
  forward snapshots plus materially more settled replacement-value rows, or a
  genuinely different attention/provenance source;
- USAspending non-DoD obligation conversion alpha retries before the prospective
  first-seen observer matures. The July 13 surface is retained only for forward
  evidence. Reopen performance after at least 75 settled unique eligible events
  across at least 15 first-seen dates and 3 mapped public-company tickers, max
  ticker share <=30%, with complete next-open/10-session cash/SPY/QQQ outcomes;
- ClinicalTrials Phase 3, FDA device Class I recall, CPSC recall, and NHTSA
  defect-investigation retries that only sweep sponsor maps, severity wording,
  green/SPY-relative confirmation, source batches, top-N, hold, cooldown, or
  notional. July 13-14 official safety/medical reads were directionally weak or
  concentrated and did not beat accepted comparators. Reopen with a materially
  new PIT endpoint/severity/issuer-financial-materiality field, at least 30
  closed forward replacement-value rows, or a batch of at least 3 newly
  audit-ready official sources each covering all windows and contributing at
  least 20 expected settled trades;
- FDIC Call Report deposit-franchise candidate-pool retries that change
  DEPDOM/DEPUNINS fields, bank-size gates, dominant-bank share, merger filters,
  top-N, rank, hold, cost, mapping, or windows on the current-vintage sample.
  July 14 failed Gate 3 at 28/654 survived rows and also failed PIT validity.
  Reopen only with first-release/as-of FDIC vintages plus historical
  CERT/RSSDHCR/security mapping and exact-top5 sensitivity, or with materially
  sufficient prospectively first-seen settled QBP quarters;
- EIA WPSR and USDA FAS official physical-flow retries that only change series
  subsets, seasonal baselines, percentiles, baskets, weights, response shape,
  hold, cooldown, notional, or costs. July 14 EIA was positive but too thin and
  lost USO; USDA export sales lost cash/SPY/QQQ/DBA and direct corn-soy
  benchmarks. Reopen EIA after at least 30 prospectively closed unchanged-policy
  decisions with positive matched replacement value, and USDA only after at
  least 10 additional prospectively settled unchanged-policy releases or a
  genuinely independent PIT physical-supply/demand data source;
- joint covariance / portfolio-overlay synthesis retries that self-authorize a
  parked-lane reopen, select a subset from known winners, cross calendar
  boundaries, mix pre/post-MTM protocols, omit the complete family scope, or
  claim an incomplete DSR selection panel. July 14 stopped this before
  performance was computed. Reopen only with an independently authorized owner
  contract, complete required family scope on one active real-calendar
  protocol, leakage-free state transfer, and a declared complete DSR panel;
- historical borrow-fee / availability evaluation of the fixed
  `exp-20260712-013` old-thin admission policy before an explicitly licensed,
  redistributable PIT source covers `old_thin`. The local panel available on
  July 14 has 232,916 rows across 908 tickers but begins only on 2025-07-14, so
  it cannot repair the missing 2024-10-02 to 2025-04-22 evidence. Reopen only
  after the source owner, permitted use, point-in-time semantics, and all three
  canonical-window coverage are recorded;
- USPTO patent-grant observer reservation before an accessible official weekly
  XML archive covers all three canonical windows. On July 15 the official ODP
  catalog identified weekly `PTGRXML` coverage nominally through 2026-04-21,
  but USPTO registration has been required since 2026-06-18, both the product
  API and exact `ipg260421.zip` file API returned 401 without an API key, and
  the human bulk-data URL returned only the SPA shell rather than ZIP bytes.
  The legacy bulk host is retired/unresolvable, PatentsView still ends before
  `late_strong`, and no `USPTO_API_KEY` is configured, so the expected 81-file
  three-window manifest (plus the `ipg241001.zip` boundary sentinel) cannot be
  listed, downloaded, or hashed. A connectivity or row-count recheck does not
  consume an experiment ID. Reopen only with an explicitly authorized ODP
  account/key, a gap-free file manifest with size/ZIP/SHA-256 verification, and
  fixed issuer mapping reaching at least 20 issuer-weeks, 10 tickers, and
  top-1 share <=30% in every window;
- CMS NADAC brand-WAC price-increase candidate-pool reservation before an
  auditable issuer map and public-release clock pass the same three-window
  density gate. A July 15 zero-ID preflight joined the public NADAC Comparison
  dataset to the FDA NDC package/product directory by exact full NDC11; join
  coverage was 86.51%/92.41%/89.34%. After positive-change filtering and a
  fail-closed exact labeler-to-SEC-title map, old/mid/late contained only
  25/5/23 issuer-weeks across 24/4/22 tickers, with top-1 shares
  8.0%/40.0%/8.7%. `mid_weak` therefore fails both the >=20 issuer-week and
  >=10-ticker bars and exceeds the <=30% concentration bar. Do not reserve an
  ID for alias expansion or row recounting. Reopen only with a hash-bound
  weekly first-public/version archive plus an effective-dated, evidenced
  NDC-labeler-to-economic-parent/ticker map that independently clears all three
  bars in every window; a current NDC/SEC snapshot and the consolidated
  comparison `end_date` are not historical PIT proof, and a labeler may be a
  repackager, relabeler, or private-label distributor rather than the economic
  manufacturer;
- MSHA immediately-reportable accident peer-substitution observers that infer
  supply loss from `IMMED_NOTIFY_CD` alone or use the current full-replacement
  accident/mine files as historical PIT snapshots. The July 14 zero-ID
  preflight found adequate raw density (74/97/58 mapped issuer-weeks); a strict
  coal peer pool produced 323/291/221 candidate legs but only 9 peer tickers in
  every window, while the broader 776/752/594-leg pool mixed economically
  different commodities. Immediate-reporting status does not establish an
  operating interruption, and `DOCUMENT_NO` assignment dates do not establish
  first-publication dates. Reopen only with a hash-bound effective-dated
  controller-to-ticker and commodity/region peer graph, at least two ex-ante
  substitutes per event, and independent interruption materiality such as a
  matched 107(a) withdrawal/termination or at least 5% of issuer commodity
  capacity affected. Historical evaluation must then clear, in every window,
  20 settled event-peer trades, 8 target tickers, 3 commodity buckets, top-1
  ticker <=25%, and top-1 bucket <=40%; without historical weekly vintages,
  evaluate only after a prospective first-seen ledger reaches 30 closed rows
  across 10 peer tickers;
- Federal Register Commerce AD/CVD final-determination or order event retries,
  and the corresponding USITC final-injury petitioner-beneficiary observer,
  before both the economic decision clock and cross-window issuer density are
  valid. A July 14 zero-ID preflight reduced 1,548 Commerce documents to
  20/26/30 independent product-days, but only 12/9/6 mapped issuer-event legs
  across 8/8/6 tickers; top-product shares were 33%/50%/100%. Commerce final
  determinations are not the common economic clock: preliminary affirmative
  findings can start cash deposits, final determinations still await the ITC,
  and the later order is administrative. Moving to the USITC final vote did
  not rescue the surface: mapped legs were 23/63/2 across 3/11/1 tickers, with
  top-ticker shares 78.26%/22.22%/100% and top-product shares
  78.26%/44.44%/100%. USITC news pages also expose only a date and can be
  overwritten by a later revote. Reopen only with immutable official
  `published_at` plus version history and, in every window, at least 20 mapped
  legs, 10 effective listed tickers, 3 products, top-ticker share <=30%, and
  top-product share <=40%; otherwise wait for at least 30 settled prospective
  first-seen rows under one frozen policy;
- USPTO patent-assignment recordation as a historical corporate-technology-
  acquisition source before public visibility and ownership relations are
  auditable. An 18-issuer July 14 sample superficially produced 226/162/108
  issuer-weeks across 18/18/15 tickers, but the public endpoint truncated or
  unsorted large aliases and ordinary inventor-to-employer assignments made up
  the apparent density; zero rows were verified as gate-ready external
  corporate-assignor acquisitions. More importantly, `recordationDate` is not
  first-publication time, and documents involving unpublished applications can
  appear later while retaining an older recordation date. The official
  research dataset ends in 2023 and the current export service is scheduled to
  migrate on July 24, 2026. Reopen only after the replacement API has stable,
  complete pagination and an immutable first-publication/version contract,
  effective-dated assignor/assignee parent mapping, and each window has at
  least 20 verified external corporate-assignor issuer-weeks, 10 tickers, and
  top-1 share <=30%. Without historical snapshots, seed the then-current set
  and evaluate only after at least 30 settled forward first-seen events across
  10 tickers and 15 decision dates;
- GAO bid-protest decision-date replays before a historical public-release
  clock exists. GAO says an unprotected decision is normally released one or
  two days after the parties are notified, while a redacted decision may lag
  two or three weeks and occasionally months; the current product page and PDF
  do not expose a historical `first_public_at` or version ledger. Using the
  decision date for next-open execution would therefore be forward-looking.
  FY2025 had only 53 sustains across public and private protesters, so mapping
  cannot repair the missing clock and the listed-company per-window upper bound
  is already small. Reopen only with per-decision first-publication/version
  snapshots covering all windows, then require at least 20 listed-protester
  issuer-days, 10 tickers, and top-1 share <=30% in every window;
- FDA Orange Book monthly `NEWA` release-basket retunes on the frozen 19-PDF
  archive. `exp-20260715-004` corrected an invalid Fresenius Kabi-to-FMS
  ownership assumption, then retained 23/24/23 eligible issuer-release legs
  across 11/14/11 tickers. The fixed all-issuer, equal `$16k` release basket
  produced core+sleeve aggregate EV `+0.1240` and PnL `+$1,648.40`, but missed
  the accepted comparator (`+0.5286`, `+$10,432.91`), old-thin EV was
  `-0.0032`, and the top-five positive-contribution share was `79.93%` versus
  the preregistered 60% cap. Production daily wiring was therefore removed.
  Do not sweep approval-age thresholds, NEWA subtypes, holder aliases, top-N,
  weights, notional, hold, cost, or entry timing on these PDFs. Reopen only
  with a genuinely independent drug-commercialization data source/gate or at
  least 30 prospectively settled unchanged-policy release decisions across 10
  tickers and 15 publication dates with complete cash/SPY/QQQ replacement
  value;
- missing archive/text availability as an alpha field.

## Update Discipline

Update this file only when a result changes mechanism-level priors, freezes a
research family, changes the next 1-3 research queues, or adds external
research that maps to concrete replayable fields. Keep experiment details in
the logs.
