# Alpha Optimization Playbook

Last refreshed: 2026-06-19.

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
- VBB / VCP / Space observe-only buckets where nonzero forward rows exist.

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

## Anti-Repeat Rules

Do not repeat these without forward rows or a materially different
production-visible field:

- broad filter/gate tightening on the core stack;
- simple risk scalar / top-up sweeps;
- state-surface rank/profile/notional retunes below the hard EV threshold;
- ticker-specific exceptions from one or two trades;
- simple target, stop, time-stop, or fixed max-loss exit changes;
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
  historical coverage or a forward-only observation ledger has vendor-as-of,
  publication-lag, stale-chain, and fill-cost controls. `exp-20260617-004`
  blocks this as a measurement surface, not as a rejected alpha;
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
- missing archive/text availability as an alpha field.

## Update Discipline

Update this file only when a result changes mechanism-level priors, freezes a
research family, changes the next 1-3 research queues, or adds external
research that maps to concrete replayable fields. Keep experiment details in
the logs.
