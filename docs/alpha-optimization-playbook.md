# Alpha Optimization Playbook

## 鏂囨。鑱岃矗

鏈枃浠舵槸闀挎湡 alpha 鎵嬪唽锛屼笉鏄疄楠屾祦姘磋处銆?

瀹冭礋璐ｅ洖绛斿洓涓棶棰橈細

- 褰撳墠绯荤粺鐨?alpha 浠庡摢閲屾潵锛?
- 鍝簺鏈哄埗宸茬粡琚獙璇併€佹殏缂撱€侀樆濉炴垨璇佷吉锛?
- 涓嬩竴杞渶鍊煎緱鐮旂┒浠€涔堬紝涓轰粈涔堬紵
- 鍝簺鎬濊矾涓嶈閲嶅灏濊瘯锛岄櫎闈炲嚭鐜版柊璇佹嵁锛?

鏂囨。鍒嗗伐锛?

- `AGENTS.md`锛氶棬鎺с€佷紭鍏堢骇绾︽潫銆佷細璇濆崗璁€佸疄楠岀邯寰嬨€?
- `docs/experiment_log.jsonl`锛氬崟娆″疄楠岀殑缁撴瀯鍖栦富鏃ュ織锛屼繚鐣欏弬鏁般€佺獥鍙ｃ€佹寚鏍囧拰缁撹銆?
- `docs/experiments/logs/*.json`锛氳緝鏂扮殑鍗曞疄楠岃缁嗚褰曘€?
- `docs/experiments/artifacts/*.json` 涓?`data/exp_*.json`锛氬疄楠屼骇鐗╁拰瀹¤鏄庣粏銆?
- 鏈枃浠讹細鎶婂杞疄楠屽悗浠嶆垚绔嬬殑缁撹鍘嬬缉鎴愰暱鏈?doctrine銆?

鑻ユ湰鏂囨。涓?`AGENTS.md` 鍐茬獊锛屼互 `AGENTS.md` 涓哄噯銆傝嫢闇€瑕佸鐜板疄楠岋紝鍏堟煡鏈枃妗ｇ殑瀹為獙绱㈠紩锛屽啀鏌ョ粨鏋勫寲鏃ュ織銆?

## 2026-05-10 accepted state

Latest refreshed accepted-stack checkpoint: keep the accepted lifecycle
allocation core from `exp-20260502-022` and treat the 2026-05-09 refresh as
the current source of truth for the replayable A+B stack. Use
`data/backtest_results_20260509.json` as the latest standalone canonical
artifact for `old_thin`, and use the unchanged carried-forward baseline blocks
in `exp-20260509-006`, `exp-20260509-007`, `exp-20260510-002`, and
`exp-20260510-003` for `late_strong` / `mid_weak`. The stack remains a
capital-allocation / event-quality baseline, not a new entry filter, universe
expansion, or sector priority rule.

Accepted fixed-window metrics after the current core stack:

| Window | EV | Return | Sharpe daily | Max DD | Win rate | Trades |
|---|---:|---:|---:|---:|---:|---:|
| `late_strong` | 4.2340 | +94.09% | 4.50 | 5.48% | 78.95% | 19 |
| `mid_weak` | 1.6678 | +61.77% | 2.70 | 9.41% | 52.38% | 21 |
| `old_thin` | 0.3693 | +28.19% | 1.31 | 9.15% | 40.91% | 22 |

Evidence: this refreshed checkpoint is the shared baseline after
`exp-20260510-012`. Earlier logs `exp-20260509-004`, `exp-20260509-006`,
`exp-20260509-007`, `exp-20260510-002`, and `exp-20260510-003` preserve the
pre-RS20 accepted-stack baseline for replay-only, data-gap-only, or blocked
comparisons. Aggregate accepted-stack EV is now `6.2711` with aggregate PnL
`+$184,040.96`, and convergence remains `8/8`.

Latest unchanged validation point: the 2026-05-03 through 2026-05-10
observed-only SEC/Form 4 queue, shadow-universe, event-harness, short-pressure,
options-overlay, entry-state oracle, earnings-estimate readiness, 10-K
forward-watch, add-on reserve, and event-bundle allocation experiments all
reused the same canonical three-window core metrics whenever no executable
policy was promoted into the core stack. Treat the `exp-20260510-012` shared
RS20 sizing record plus `data/experiments/exp-20260510-012/rs20_entry_state_shared_sizing.json`
as the latest checkpoint; `data/backtest_results_20260509.json` remains the
latest standalone CLI artifact before that promotion.

### 2026-05-10 mechanism update: RS20 entry-state shared sizing

Status: accepted shared core-sizing alpha.

Core conclusion: `exp-20260510-010` first found a broad RS20 entry-state
allocation lead in replay-only form. `exp-20260510-012` implemented the valid
follow-up as shared production/backtest policy: `risk_engine.py` tags signals
whose ticker 20-day return beats SPY by at least 5 percentage points, and
`portfolio_engine.py` applies a cap-aware 1.10x post-sizing share top-up inside
the already-selected position cap. Core entries, ranking, exits, add-ons, event
sleeves, LLM/news, and universe membership stayed locked.

Evidence: the accepted 1.10x variant improved EV and PnL in all three
canonical windows: `late_strong +0.1666` EV / `+$3,298.03`, `mid_weak +0.0483`
EV / `+$2,228.32`, and `old_thin +0.0110` EV / `+$837.68`. Aggregate EV
improved `+0.2259` (`+3.74%`) and aggregate PnL improved `+$6,364.03`
(`+3.58%`), with unchanged trade count and survival. Max drawdown drift stayed
bounded at `+0.62 pp`.

Mechanism insight: broad 20-day relative-strength leadership is a real but
small allocation edge when expressed as a modest shared sizing top-up, not as a
new entry source or a large scalar. The stronger shared-policy variants were
rejected: 1.25x improved aggregate EV more but pushed `mid_weak` drawdown from
8.79% to 10.40%, and 1.50x pushed it to 11.80%.

Do not repeat: nearby RS20 scalar sweeps, platform-RS20 threshold variants,
missed-candidate RS20 sleeves, or platform no-gap same-sample retries on the
same frozen windows. Future RS20 work needs forward attribution, concentration
evidence, or an orthogonal event/news/state discriminator.

### 2026-05-10 mechanism update: SEC / earnings filing-shock refreshed audit

Status: data-gap, no-alpha-change.

Core conclusion: `exp-20260510-002` rechecked the refreshed 2026-05-08 SEC
event/text/feature files to see whether the filing-shock branch finally gained
same-accession Companyfacts joins or directional shock fields that could grade
`earnings_event_long` or confirm A/B candidates. It did not. The refreshed rows
remain `D_unclear_or_missing_data`, so the bottleneck is still feature
availability, not PIT timestamp coverage.

Evidence: all three canonical core windows were intentionally carried forward
unchanged (`late_strong EV 4.0674`, `mid_weak EV 1.6195`, `old_thin EV 0.3583`)
because this was a pure data audit. Fresh SEC rows showed `0` same-accession
feature joins, `0` EPS/revenue surprise rows, `0` guidance raise/cut rows, and
`0` directional numeric filing-shock rows. Fresh 5/10/20/60-day outcomes are
also not mature, so there is still no basis for a new replay.

Mechanism insight: the SEC / earnings branch is blocked by directional event
fields, not by accepted-at / usable-trade-date plumbing. Do not spend another
loop on raw filing recency, C-sleeve re-enable, or Companyfacts score-weight
tuning until same-accession financial surprise or guidance fields exist.

Next valid step: build an accession-level join audit and directional field
extraction for 8-K / 10-Q / 10-K rows, or ingest PIT-safe consensus/guidance
data before retrying any filing-shock alpha search.

### 2026-05-10 mechanism update: Event rotation-surface tilt adapter

Status: accepted default-off paper adapter.

Core conclusion: `exp-20260510-001` found that the
`rotation_breakout_leadership` subset inside the default-off event bundle
deserves a higher paper-notional tilt than other positive non-generic
state-surface event rows. `exp-20260510-003` moved that exact lead into the
shared production-visible default-off event bundle adapter without enabling
live/default orders.

Evidence: versus the prior 2.0x non-generic state-surface event add-on, the
3.0x rotation-surface tilt improved EV in all three canonical windows:
`late_strong +0.3094`, `mid_weak +0.2209`, and `old_thin +0.0064`. Aggregate
event-paper EV improved `+0.5367` and PnL improved `+$7,987.90`. The canonical
core no-drift check stayed unchanged after adapter implementation:
`late_strong EV 4.0674`, `mid_weak EV 1.6195`, `old_thin EV 0.3583`.

Mechanism insight: event-overlay alpha is currently best expressed as
event-specific state-surface allocation, not broad benchmark gating, source
pruning, or more core A/B threshold work. Rotation-breakout leadership is the
first event-state subset strong enough to warrant a separate shared paper
allocation annotation.

Do not repeat: nearby 2.5x/3.0x/3.5x scalar sweeps, broader positive
state-score tilts, broad event benchmark gates, or event-source pruning on this
same frozen sample. The adapter now defines the exact forward paper hypothesis.

Next valid step: collect closed forward replacement-value outcomes under this
shared annotation. Live/default order routing remains blocked until the forward
gate and explicit trade adapter pass.

### 2026-05-10 mechanism update: Rotation event plus benchmark-gated state surface stack

Status: promising replay-only paper stack.

Core conclusion: `exp-20260510-005` revalidated the current paper stack after
the rotation-surface event tilt became the new event-bundle baseline. Adding
the frozen benchmark-momentum-gated state-surface satellite on top of the
rotation-tilted event bundle remains strongly additive versus the current
rotation-event baseline.

Evidence: versus the rotation-event baseline, EV improved in all three
canonical windows: `late_strong +0.9967`, `mid_weak +0.6846`, and
`old_thin +0.3729`. Aggregate EV improved `+2.0542` (`+25.02%`) and aggregate
PnL improved `+$39,729.22` (`+18.74%`). Versus core-only, the combined paper
stack improved aggregate EV by `+4.2201` and PnL by `+$74,060.98`. The
single-ticker positive PnL share was `29.84%`, inside the concentration guard.

Mechanism insight: the best current paper alpha is not another local event
scalar, state-score floor, source subset, or broad benchmark gate on the event
bundle. It is the combination of two already-frozen default-off surfaces:
event-specific rotation tilt plus benchmark-gated state-surface replacement
value. The benchmark gate remains a state-surface participation rule, not an
event-bundle gate.

Do not repeat: nearby state-surface top-N/hold/notional retunes, benchmark
threshold sweeps, event-source pruning, event state-score floor variants, or
ungated sleeve stacking on this frozen sample. This stack should now be
evaluated through forward paper replacement value rather than more same-sample
parameter search.

Next valid step: collect closed forward paper outcomes under the existing
default-off event bundle and state-surface adapters. Live/default order routing
still requires explicit shared trade adapters, parity tests, and a passed
forward gate.

### 2026-05-10 mechanism update: Low-deployment ETF overlay paper adapter

Status: accepted default-off paper adapter.

Core conclusion: `exp-20260510-007` is the strongest current non-LLM,
non-retune alpha direction, so `exp-20260510-008` moved it into a
production-visible paper attribution surface instead of retuning the same
frozen sample. The overlay remains default-off and cannot submit orders.

Evidence: the replay alpha from `exp-20260510-007` improved EV in all three
canonical windows and improved aggregate EV by `+0.3141` (`+5.20%`) with PnL
`+$10,376.82` (`+5.84%`). The adapter implementation kept the accepted core
three-window metrics unchanged: `late_strong EV 4.0674`, `mid_weak EV 1.6195`,
and `old_thin EV 0.3583`.

Mechanism insight: when the A/B core is materially under-deployed, a tiny
liquid ETF selector can be tracked as replacement-value alpha without adding
noisy core tickers or consuming scarce stock slots. This is a candidate-pool /
capital-allocation surface, not a broad universe expansion.

Do not repeat: same-sample ETF notional, nearby momentum/SMA, or candidate-list
retunes without forward paper outcomes. The next evidence must come from the
shared production paper ledger with actual daily deployment and cash context.

Next valid step: collect closed forward paper ETF overlay outcomes. Live/default
order routing remains blocked until cash semantics, an explicit trade adapter,
and run/backtest parity tests pass.

### 2026-05-10 mechanism update: Breakout add-on upper bound

Status: rejected upper bound.

Core conclusion: `exp-20260510-004` tested the current top lifecycle-alpha
question from the playbook: whether a state-specific follow-through add-on
discriminator could unlock enough materiality without repeating raw heat-cap
relaxation, generic entry reserve, same-day add-on ordering, second add-ons, or
local trigger retunes. The tested discriminator was existing `breakout_long`
positions that had already passed the accepted day-2 add-on checkpoint.

Evidence: even under the optimistic upper-bound assumption that every unfilled
requested breakout add-on share fills at the scheduled add-on price and exits
with the parent trade, the three canonical windows did not clear Gate 4.
Aggregate EV improved only `+0.3017` (`+4.99%`) and aggregate PnL improved
`+$5,843.77` (`+3.29%`). Window EV improved in all three windows, but no single
window passed Gate 4: `late_strong +0.2590` EV / `+$3,880.90`, `mid_weak
+0.0221` EV / `+$1,036.72`, and `old_thin +0.0206` EV / `+$926.15`.

Mechanism insight: the remaining add-on materiality ceiling is real but too
small even when measured with an optimistic breakout-specific fill assumption.
This rules out building a shared production adapter for breakout add-on cap or
heat relief from the current fixed-window evidence.

Do not repeat: breakout-specific follow-through add-on cap, heat, or full-fill
variants on the same accepted-stack windows without new forward evidence or an
orthogonal event/news discriminator attached to the add-on decision.

### 2026-05-10 mechanism update: Trend add-on upper bound

Status: rejected upper bound.

Core conclusion: `exp-20260510-009` tested the next lifecycle add-on cohort
after the breakout-only upper bound failed: existing `trend_long` positions
that had already passed the accepted day-2 add-on checkpoint. The test kept
entry logic, add-on trigger thresholds, add-on fraction, position caps, global
heat, exits, LLM/news, and universe membership locked.

Evidence: even under the optimistic assumption that every unfilled trend
add-on share fills at the scheduled add-on price and exits with the parent
trade, the three canonical windows did not clear Gate 4. Aggregate EV improved
only `+0.0796` (`+1.32%`) and aggregate PnL improved only `+$2,144.24`
(`+1.21%`). EV improved slightly in all three windows, but no window passed a
per-window Gate 4 test: `late_strong +0.0359` EV / `+$597.57`, `mid_weak
+0.0120` EV / `+$219.72`, and `old_thin +0.0317` EV / `+$1,326.95`.

Mechanism insight: the add-on materiality ceiling is not unlocked by switching
the extra budget from breakout follow-through to trend follow-through. The
remaining add-on alpha is too small without a genuinely new event/news,
replacement-value, or capital-routing discriminator.

Do not repeat: trend-only follow-through add-on cap, heat, reserve, or
full-fill variants on the same accepted-stack windows without new forward
evidence or an orthogonal event/news discriminator attached to the add-on
decision.

### 2026-05-09 mechanism update: Event-bundle benchmark momentum gate

Status: rejected.

Core conclusion: `exp-20260509-024` tested whether the broad benchmark
momentum gate that helped the separate state-surface satellite should also gate
the frozen event-bundle overlay. It should not. The gate preserved positive
edge versus core, but regressed the stronger full event bundle in all three
canonical windows because the blocked event trades were net winners.

Evidence: versus full event bundle, gated EV fell `7.0539 -> 6.7882`
(`-0.2657`, `-3.77%`) and PnL fell `$193,980.77 -> $190,205.06`
(`-$3,775.71`, `-1.95%`). Window EV deltas were `late_strong -0.2350`,
`mid_weak -0.0251`, and `old_thin -0.0056`; blocked trade PnL was positive in
all three windows.

Mechanism insight: event-bundle alpha is not simply a broad-risk-on satellite.
The broad tape gate that controls state-surface risk removes useful event
trades when applied to the SEC/event overlay family.

Do not repeat: direct `max(SPY, QQQ) 20d return > 0` participation gates on the
frozen event bundle, or simple benchmark-state migrations from state-surface to
event overlays, unless new event-specific forward replacement-value evidence
shows blocked trades have become negative.

Next valid retry requires: event-specific source/structure evidence or closed
forward paper replacement value, not another broad benchmark tape filter.

### 2026-05-09 mechanism update: State-surface self-leadership exception

Status: rejected.

Core conclusion: `exp-20260509-025` tested whether the current state-surface
benchmark-momentum gate should allow a blocked candidate when that candidate's
own 20-day return is positive and above `max(SPY, QQQ)` 20-day return. It
should not. The exception recovered some old-window exposure, but it damaged
the stronger `exp-20260509-014` benchmark-gated stack and reopened the
late-window risk that the benchmark gate had fixed.

Evidence: versus `exp-20260509-014`, aggregate EV fell `9.7092 -> 9.0506`
(`-0.6586`, `-6.78%`) and PnL fell `$243,750.01 -> $239,883.43`
(`-$3,866.58`, `-1.59%`). Window EV deltas were `late_strong -0.7886`,
`mid_weak +0.0000`, and `old_thin +0.1300`; late Sharpe fell `-0.36` and late
drawdown worsened `+0.71 pp`.

Mechanism insight: candidate-level short-term self-leadership is too blunt as
an exception to the state-surface benchmark gate. It mostly re-admits high-beta
late-window exposure rather than selectively rescuing the early leaders the
state-surface sleeve is meant to find.

Do not repeat: state-surface self-leadership exceptions, nearby ticker-vs-SPY
or ticker-vs-QQQ 20-day relative-return exceptions, or relative-return rescue
thresholds on this same frozen state-surface sample.

Next valid retry requires: a genuinely orthogonal event/news/lifecycle
discriminator or closed forward paper replacement-value evidence showing that
blocked candidates under the exact benchmark gate have become positive.

### 2026-05-09 mechanism update: Post-news continuation PEAD entry

Status: rejected positive but immaterial.

Core conclusion: `exp-20260509-020` tested a shadow-only PEAD-like entry pattern:
high-confidence `8k_item_2_02` earnings/results event, event-day close-to-close
reaction above `+1%`, event-day volume at least `1.5x` the prior 20-day average,
enter next open, and exit on the 10th trading day after the event. The pattern
was directionally positive, but not strong enough to justify a shared adapter or
production work.

Evidence: aggregate EV rose `6.0452 -> 6.2932` (`+0.2480`, `+4.10%`) and PnL
rose `$177,676.93 -> $185,806.72` (`+$8,129.79`, `+4.58%`). That missed Gate 4
materiality. Window EV deltas were `late_strong -0.0508`, `mid_weak +0.2408`,
and `old_thin +0.0580`; PnL was positive in all three windows, but late EV
regressed and aggregate PnL stayed below the `+5%` threshold.

Mechanism insight: price/volume-confirmed earnings-news continuation is real
enough to monitor, but it behaves like a mid/old-window repair sleeve rather
than a robust improvement over the accepted core stack. In the strongest
late-window tape, the same pattern adds trades while diluting quality.

Do not repeat: nearby PEAD thresholds around `+1%` event reaction, `1.5x`
volume confirmation, or 10-day event holds on this same sample.

Next valid retry requires: fresh forward paper outcomes or an orthogonal
semantic earnings-quality field, not another price/volume threshold variant.

Current alpha lead on top of that stack: `exp-20260509-006` confirmed the
frozen default-off event bundle as the strongest paper-only candidate-pool
extension versus core-only (`EV +1.0087`, `PnL +$16,303.84` aggregate), and
`exp-20260509-007` confirmed the best follow-on discriminator inside that
bundle is a bounded 2.0x paper-notional add-on only for positive PIT state
scores on non-generic state surfaces (`EV +0.6205`, `PnL +$10,040.02` versus
the full bundle). Both remain replay-only until shared run/backtester event
adapters and closed forward replacement-value outcomes exist.

Forward-only accepted support work on 2026-05-01 also matters:

- `exp-20260501-029` activated the bounded `AI_INFRA_PILOT` real-money sleeve
  for `BE`, `INTC`, and `LITE` without changing the historical core backtest
  windows.
- `exp-20260501-030` added pilot replacement-value and counterfactual outcome
  rollups so that future pilot promotion decisions can be based on forward
  evidence rather than more static watchlist sweeps.
- `exp-20260507-910` changed the single pilot sleeve slot from input-order
  selection to shared `trade_quality_score -> confidence -> risk/reward`
  priority. This is forward pilot capital-allocation alpha, not a core universe
  expansion. The three canonical historical windows stayed unchanged because
  pilot eligibility starts after those windows; future review should compare
  closed pilot outcomes against the recorded sliced pilot alternatives.

Do not repeat: nearby SPY-relative leader multipliers, nearby SPY-relative
leader initial-cap levels, nearby SPY-relative leader add-on cap levels above
60%, nearby Financials leader multipliers, or broader raw `risk_on`/sector risk
boosts without forward evidence, event/news context, or a materially richer
discriminator.

### 2026-05-08 mechanism update: Gap-cancel joint discriminators

Status: rejected.

Core conclusion: `exp-20260508-014` tested the pre-registered Phase B
gap-cancel bypass families from the `exp-20260507-920` oracle audit. The best
joint discriminator, `volume_vs_20d_avg < 3.263312` plus
`sector_5d_rs >= 0.13675`, improved `late_strong` but regressed `mid_weak` and
added only `+$230.22` aggregate PnL (`+0.14%`). The stronger-looking raw gap
families were actively harmful, with `gap_bucket_4_5` losing `-$23,713.29` and
`gap_abs_high` losing `-$21,476.26` across the canonical windows.

Evidence: no tested variant passed Gate 4. The Phase A oracle forward-return
lift did not survive executable replay once fills, sizing, slots, and exits were
restored.

Do not repeat: gap-cancel bypasses using these same thresholds, nearby raw
gap-size buckets, or the same volume/sector-RS/8-K severity combinations.

Next valid retry requires: a genuinely new information source or forward paper
evidence that predicts fill quality before entry; otherwise prioritize a
different alpha family.

### 2026-05-05 mechanism update: Positionable entry planning

Status: rejected.

Core conclusion: exp-20260505-005 tested whether zero-share candidates should be
removed before scarce-slot entry planning. The idea was plausible because
non-positionable candidates were still appearing in the entry-plan sequence, but
the replacement candidates were worse than the default path.

Evidence: the variant reduced aggregate `no_shares` by 30 and `slot_sliced` by
4, but aggregate EV fell `-0.2122` (`-4.10%`) and aggregate PnL fell
`-$9,506.06` (`-6.01%`). `mid_weak` and `old_thin` both regressed, while
`late_strong` was unchanged.

Do not repeat: dropping zero-share candidates before entry planning, or treating
lower `no_shares` counts as alpha without executed-trade improvement.

Next valid retry requires: candidate-level replacement evidence proving the
newly admitted positionable candidate beats the default skipped/no-share path,
plus a shared `production_parity.py` helper and run/backtester parity test before
promotion.

### 2026-05-06 mechanism update: Free short-pressure overlays

Status: rejected for promotion; shadow-only evidence remains weak.

Core conclusion: `exp-20260505-024` and `exp-20260506-008` both tested whether
free short-pressure proxies can improve an existing Ginger candidate by
overlaying PIT-safe FINRA publication-lag data, then adding SEC fails-to-deliver
and Nasdaq Reg SHO threshold flags. The answer is still no. FINRA-only high
short-crowding candidates trailed the rest by `-1.87%` on forward 20-day
returns, and the broader free regulatory bundle was even worse at `-2.60%`.

Evidence: both experiments were shadow-only and left the accepted stack's
canonical three-window metrics unchanged, but the slot-value evidence was
negative. `exp-20260506-008` also tagged 100% of the candidate cohort, so this
is no longer a "coverage was too sparse" excuse. The remaining gap is data
quality, not more threshold tuning: free regulatory stress proxies are not the
same thing as true borrow pressure.

Do not repeat: nearby FINRA days-to-cover thresholds, SEC FTD score-weight
tuning, Nasdaq threshold-flag variants, or "short squeeze overlay" promotion
attempts built only from these free proxies.

Next valid retry requires: true borrow-fee / availability / hard-to-borrow
data, or a replay proving a short-pressure tag improves same-day slot
replacement value across most windows.

### 2026-05-06 mechanism update: EOD options structure overlay

Status: rejected for promotion; historical rows are informative but not
decision-grade.

Core conclusion: `exp-20260506-009` showed that high-coverage options-chain
rows can be joined to most candidate days, but the naive "call-structure
support" packet is not bullish on aggregate and the downside-risk packet is not
stable enough across windows to justify a rule. This remains a research aid,
not production alpha.

Evidence: options coverage reached `97.83%` of historical candidate days, but
`call_structure_support` underperformed non-support names by `-0.82%` on
forward 20-day returns overall and was negative in `late_strong` and
`old_thin`. `downside_structure_risk` was directionally useful in
`late_strong` and `mid_weak` but flipped positive in `old_thin`, so the tag is
not robust enough for promotion.

Do not repeat: nearby call/put open-interest ratio thresholds, simple
call-dominance bullish gates, simple put-skew bearish vetoes, or same-sample
options overlay promotion on PIT-unsafe historical rows.

Next valid retry requires: forward PIT-safe vendor rows with as-of metadata, a
richer feature set such as IV-rank / IV-vs-realized / earnings-IV context, and
replay evidence that options tags improve slot replacement value rather than
just describing candidates.

### 2026-05-06 mechanism update: Event-leader profit ladder

Status: rejected in fixed-entry shadow replay.

Core conclusion: `exp-20260506-010` asked a sensible lifecycle question:
whether SPY-relative leaders that entered immediately after a sharp
price/volume re-rating event should use a partial-and-trail profit ladder
instead of the default all-or-nothing exit logic. The answer is still no with
current evidence. Even the best fixed-entry shadow variant failed the
two-window improvement test and did not create aggregate EV.

Evidence: the best variant, `target_half_trail_1_5r`, still had aggregate
expected-value delta `-0.1299`; the nearby replay variants ranged down to
`-1.8628`. The setup was deliberately narrow and did not alter entries,
sizing, or accepted backtest metrics, so this is a clean mechanism rejection
rather than a noisy whole-system sweep.

Do not repeat: nearby event-leader target-half-trail, profit-floor, or simple
"protect early profit after event repricing" exit variants without new forward
event semantics or a materially richer event definition than the current OHLCV
proxy.

Next valid retry requires: production-grade shared replay for event semantics,
forward event-tag attribution, and evidence that the affected cohort has enough
winner-giveback to offset the added exit complexity.

### 2026-05-06 mechanism update: Event-quality leader runner

Status: rejected in fixed-entry shadow replay; standalone cohort remains
interesting but underpowered.

Core conclusion: `exp-20260506-023` retried the event-leader lifecycle idea with
a materially richer qualifier than `exp-20260506-010`: SEC results-8K context,
current EPS surprise, positive excess reaction, post-event drift confirmation,
and retained event gain. This did reduce the broad false-positive problem, but
the fixed-entry replay touched only one accepted trade (`MU`) and therefore did
not create enough multi-window evidence for promotion.

Evidence: the accepted-trade overlay added `+$272.22` PnL but reduced proxy EV
by `-0.0748` because only one trade changed. The standalone qualified event
cohort had 3 late-window rows (`GOOG`, `MU`, `SNOW`) with positive average
5/10/20-day returns after confirmation, including 10-day average excess versus
SPY of `+8.68%`, but there is no mid/old window semantic-event coverage and no
slot/opportunity-cost replay.

Do not repeat: nearby event-quality runner thresholds, same exit ladder, or
META/NFLX-specific exceptions without multi-window event packets and a shared
event-state replay path. The current data says "possible research lead", not
"production exit policy".

Next valid retry requires: historical event-quality packets for all three
canonical windows, at least several touched accepted trades, and a slot-aware
runner replay that measures opportunity cost.

### 2026-05-07 mechanism update: Event-bundle source pruning

Status: rejected as an alpha improvement; full bundle remains the better
replay-only surface.

Core conclusion: `exp-20260507-012` tested whether the promising default-off
event bundle should be narrowed by source composition. The best pruned set,
`sec_negative_plus_governance`, exactly tied the full frozen bundle because the
current Form 4 source contributes zero selected trades under the frozen
capacity rules. Single-source variants were positive versus core, but weaker
than the combined SEC negative-reaction + SEC governance/procedural surface.

Evidence: full bundle versus current core still improved all three canonical
windows with aggregate EV `+0.9875` and PnL `+$16,275.66`. Best pruned versus
full produced aggregate EV delta `0.0000`, PnL delta `$0.00`, and `0/3`
windows improved, so pruning adds selection complexity without incremental
alpha.

Do not repeat: source-subset permutations inside the original three-source
event bundle, or treating "drop Form 4" as alpha when Form 4 has no selected
trades in the current replay.

Next valid retry requires: a new event source with incremental selected trades,
closed forward event-paper outcomes, or a genuinely new event-quality field
that changes source selection without retuning the existing frozen thresholds.

### 2026-05-07 mechanism update: Core-platform exit capture diagnostic

Status: observed-only; useful for triage, not for direct policy promotion.

Core conclusion: `exp-20260507-013` measured whether the accepted core-platform
pool (`NFLX`, `APP`, `META`, `GOOG`, `AMZN`, `SPOT`, `DIS`) is leaving enough
post-target upside on the table to justify a new exit family. The answer is
"some runner giveback exists, but not enough by itself to authorize a shared
exit rewrite." The treatment cohort had `11` accepted trades and `5`
runner-candidate target winners, which is finally enough to permit a bounded
replay, but the evidence is still diagnostic rather than executable alpha.

Evidence: treatment trades had median 40-day MFE capture `0.410675`, with `5`
runner candidates and median missed-after-exit 40-day upside `+5.10%`.
However, the positive giveback is highly concentrated and the diagnostic did
not alter entries, sizing, exits, or canonical backtest metrics. The accepted
three-window core stack stayed unchanged, so this experiment should be read as
"exit replay is now allowed to be tested," not "exit replay is already
validated."

Do not repeat: rerunning the same cohort-level winner-capture audit, or using
runner-candidate counts alone as justification for a new exit rule.

Next valid retry requires: a pre-registered shared-policy runner replay with
three-window Gate 4, touched-trade counts, single-ticker concentration limits,
and explicit opportunity-cost attribution.

### 2026-05-07 mechanism update: Core-platform runner exit replay

Status: rejected.

Core conclusion: `exp-20260507-014` converted the new exit-capture diagnostic
into a bounded replay-only alpha test by splitting target winners into a
partial target plus SMA20 runner. Both tested variants failed the pre-registered
proxy gate, so the current core-platform winner-capture evidence does not
justify promoting a runner exit family.

Evidence: the best variant, `target_67_runner_sma20_40d`, changed proxy
aggregate EV by `-0.1457` (`-1.76%`) and proxy aggregate PnL by `$-45.81`,
with EV improved in only `1/3` windows and regressed in `2/3`. It modified `5`
target trades, but `90.3%` of the positive contribution came from a single
ticker, so the apparent upside was too concentrated to pass promotion rules.

Do not repeat: nearby target-half/target-third runner splits, SMA20-only runner
variants, or same-sample "let core platform names run" exit tweaks without a
new event/news discriminator or forward lifecycle evidence.

Next valid retry requires: a materially different post-target discriminator,
forward paper evidence, or a shared-policy replay path that changes which
target winners are eligible rather than only how much size is left on.

## 1. 褰撳墠绯荤粺鐢诲儚

褰撳墠绯荤粺涓嶆槸楂橀銆佷笉鏄函缁熻濂楀埄锛屼篃涓嶆槸璁?LLM 鍏ㄦ潈浜ゆ槗鐨勯粦绠便€傚畠鏇村儚锛?

> 浜嬩欢澧炲己鍨嬩腑鐭嚎瓒嬪娍 / 绐佺牬浜ゆ槗绯荤粺銆?

褰撳墠鍙洖鏀句富鍔?sleeve锛?

- `trend_long`锛氭洿鍍忔寔浠撴湡绠＄悊鍜?winner capture 闂銆?
- `breakout_long`锛氭洿鍍忔爣鐨勮川閲忋€乻lot competition 鍜岄樁娈甸€傞厤闂銆?
- `earnings_event_long`锛歅EAD 澶х被浠嶆湁閲戣瀺閫昏緫锛屼絾褰撳墠浠撳簱瀹炵幇灏氭湭璇佹槑鍙ǔ瀹氬鍘?A+B銆?
- LLM / news锛氭渶閫傚悎浜嬩欢鐞嗚В銆佺伨闅?veto銆佺粨鏋勫寲 grading / ranking锛涗笉閫傚悎鎺ョ浠撲綅銆佹鎹熴€佺洰鏍囦綅鍜岀‖椋庢帶銆?

褰撳墠鍥哄畾涓夌獥鍙?baseline锛堟渶鏂?accepted stack锛屾暟鎹偣鏉ヨ嚜 `data/backtest_results_20260508.json` 鍜?`exp-20260509-006` / `exp-20260509-007` 鐨勫叡浜?baseline blocks锛夛細

| Window | Range | EV | Return | Sharpe daily | Max DD | Win rate | Trades | Main interpretation |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `late_strong` | 2025-10-23 -> 2026-04-21 | 4.0674 | +90.79% | 4.48 | 5.39% | 78.95% | 19 | accepted stack remains strongest here; latest checkpoint also serves as the baseline for the 5/9 event-bundle revalidation |
| `mid_weak` | 2025-04-23 -> 2025-10-22 | 1.6195 | +59.54% | 2.72 | 8.79% | 52.38% | 21 | still the main regime-routing explanation window, but the refreshed accepted stack improved again before any new event overlay was added |
| `old_thin` | 2024-10-02 -> 2025-04-22 | 0.3583 | +27.35% | 1.31 | 9.03% | 40.91% | 22 | still the weakest window, but the refreshed accepted stack keeps positive EV and stays inside the drawdown guardrail |

鏈€鏂?accepted-stack 娴嬮噺鐩插尯涔熻涓€骞惰浣忥細news archive coverage 宸插崌鑷?15/123 浜ゆ槗鏃ワ紙12.2%锛夛紝prompt/response archive_context 鎴愮啛搴﹀凡鍒?7/10锛屼絾 production-aligned LLM ranking-eligible replay 浠嶅彧鏈?3 澶?/ 8 涓俊鍙凤紱`exp-20260502-007` 杩涗竴姝ヨ瘉鏄庡綋鍓嶅彧鍓?1/8 涓?effective candidate row 鑳藉拰鍥炴斁 trade outcome 瀵归綈锛屽洜姝?LLM soft-ranking 渚濇棫灞炰簬 measurement-blocked銆俥xit advisory replay 涔熶粛澶勪簬 shadow-only 鎶湶闃舵锛沺ilot sleeve 鍒欏凡寮€濮嬬Н绱?forward replacement-value attribution锛屼絾杩樻病鏈夎冻澶熷凡骞充粨鏍锋湰銆?

鍖楁瀬鏄熶粛鏄?`expected_value_score = total_return_pct * sharpe_daily`锛屼絾浠讳綍绛栫暐閫昏緫鏀瑰姩蹇呴』鍋氬绐楀彛妫€鏌ワ紝涓嶈兘鍙紭鍖栦竴涓獥鍙ｃ€?

## 2. 闀挎湡缁撹

### 2.1 褰撳墠鏈€鏈変环鍊肩殑 alpha 涓嶆槸鏃犻檺鍔犳柊 entry

澶氳疆瀹為獙鍚庯紝绯荤粺鐨勯珮浠峰€兼柟鍚戞洿鍍忥細

- 鎻愮函宸叉湁 A+B 淇″彿璐ㄩ噺銆?
- 鏀瑰杽 exit / hold / add-on 鐢熷懡鍛ㄦ湡绠＄悊銆?
- 璁╅闄╅绠楁祦鍚戞洿楂樻湡鏈涙満浼氥€?
- 鐢?LLM 鍋氱粨鏋勫寲浜嬩欢 grading / ranking锛岃€屼笉鏄 LLM 鍋氱‖椋庢帶銆?

榛樿涓嶄紭鍏堬細

- 鍥寸粫灏戞暟浜忔崯鏍锋湰鏂板瑙勫垯銆?
- 缁х画鍫?OHLCV-only entry 鍙樹綋銆?
- 涓轰簡鍗曠獥鍙?Sharpe 濂界湅鑰岀壓鐗茶法绐楀彛绋冲畾鎬с€?
- 鎶婃瘡涓け璐?trade 閮借В閲婃垚缂轰竴涓繃婊ゅ櫒銆?

### 2.2 breakout 鍜?trend 鐨?alpha 杞戒綋涓嶅悓

`breakout_long` 鐨?alpha 鏇村亸锛?

- 鏍囩殑璐ㄩ噺绛涢€夈€?
- bucket 鍐呮帓搴忋€?
- 绋€缂轰粨浣嶆Ы浣嶇珵浜夈€?
- 瀵?fake breakout / crowded rotation 鐨勯€傞厤銆?

`trend_long` 鐨?alpha 鏇村亸锛?

- 鎸佷粨绠＄悊銆?
- target / stop / add-on / exit 璐ㄩ噺銆?
- 鍦ㄤ笉鍚?market state 涓嬫槸鍚︾户缁 winner run銆?

鍥犳锛宐reakout 涓婃湁鏁堢殑鎺掑簭瑙勫垯涓嶈兘榛樿杩佺Щ鍒?trend锛泃rend 鐨勪笅涓€姝ヤ篃涓嶅簲鍙嶅鎵?entry ranking key銆?

### 2.3 C 绛栫暐涓嶆槸琚案涔呭惁瀹氾紝浣嗏€滃彧宸ˉ鏁版嵁鈥濆凡缁忎笉鎴愮珛

PEAD / post-earnings drift 浣滀负澶х被 alpha 浠嶆湁鐮旂┒渚濇嵁锛屼絾褰撳墠浠撳簱閲岀殑 `earnings_event_long` 宸茬粡涓嶅啀鑳界畝鍗曞綊鍥犱簬鏁版嵁缂哄彛銆?

宸茬煡缁撹锛?

- `lxml` / earnings snapshot 淇鍚庯紝C 绛栫暐鍙互鐪熷疄鍥炴斁銆?
- repaired-data 鍚庯紝鍗曞瓧娈?gate銆佸皬 checklist銆佸叡浜川閲忓垎鏁?gate銆乻tandalone-day gate 閮芥湭鑳界ǔ瀹氳 `A+B+C` 璺戣耽 accepted `A+B`銆?
- C 绛栫暐鑻ラ噸鍚紝闇€瑕佹洿涓板瘜鐨勪簨浠跺垎绾с€佽竟闄呮Ы浣嶄环鍊兼満鍒讹紝鎴?LLM / news 瀵硅储鎶ヨ涔夌殑缁撴瀯鍖?grading銆?

涓嶈缁х画鎶娾€滃啀琛ヤ竴鐐?earnings 鏁版嵁鈥濆綋浣滈粯璁や富绾匡紝闄ら潪鏂板鏁版嵁鑳界洿鎺ラ噴鏀句竴涓竻鏅扮殑 C 绛栫暐瀹為獙銆?

### 2.4 LLM 鐨勬纭柟鍚戞槸鍙璁?ranking / grading

闀挎湡杈圭晫锛?

- 浠ｇ爜璐熻矗浠撲綅銆佹鎹熴€佺洰鏍囦綅銆乸ortfolio heat銆佽涓氭毚闇层€佺‖杩囨护銆?
- LLM 璐熻矗鏂伴椈鐞嗚В銆佷簨浠跺垎绫汇€佽涔夊己寮便€佺伨闅?veto銆佺粨鏋勫寲 ranking / grading銆?

褰撳墠闃诲锛?

- LLM replay 瑕嗙洊鍜?production-aligned effective sample 浠嶇劧寰堣杽銆?
- soft ranking 涓嶈兘鍙潬涓昏瑙夊緱鈥淟LM 搴旇鏈夌敤鈥濇潵涓婄嚎銆?
- 涔熶笉鑳藉洜涓哄巻鍙插洖鏀剧己鍙ｅ氨鍚﹀畾 LLM锛涙纭柟鍚戞槸琛ョ粨鏋勫寲杈撳叆杈撳嚭鍜屽綊鍥犳寚鏍囥€?

鏈€鏂版満鍒剁粨璁猴細

- backlog classification 宸插尯鍒?`snapshot_only` 涓庣湡瀹?`context_only` 缂哄彛锛岄伩鍏嶇户缁仮澶嶆病鏈夊疄闄呬笂涓嬫枃鐨勬棩鏈熴€?
- effective attribution subset 宸插姞鍏ワ紝鐢ㄤ簬鍙粺璁＄敓浜у榻愩€乺anking-eligible 鐨?LLM 鏍锋湰銆?
- 宸叉寔浠撹繃婊ゃ€佸悓鏃ヨ涓氫笂闄愩€乣BEAR_SHALLOW` 鍏ュ満 gate 涓?`NEUTRAL` / `BEAR_SHALLOW` 椋庨櫓闄嶆。閮藉凡鏀舵暃鍒板叡浜?helper锛涘悗缁笉瑕佸啀鎺ュ彈 run/backtester 鍙屼唤瀹炵幇銆?
- trailing partial-reduce 鐜板湪宸茬粡鍙互鍏变韩鍥炴斁锛涘湪鏈?15 娆?partial reduction 鐨?fixed-window replay 涓紝瀹冨褰撳墠 accepted stack 涓鸿礋锛屽洜姝も€滅敓浜ч噷鐪嬭捣鏉ュ悎鐞嗏€濅笉鍐嶆槸缁х画鎺ㄥ箍瀹冪殑璇佹嵁銆?

## 3. 褰撳墠浼樺厛绾?

榛樿涓嬩竴杞粠楂樺埌浣庯細

1. `alpha_search` 浼樺厛锛岄櫎闈炲瓨鍦ㄦ槑纭祴閲忛樆鏂」銆?
2. 澶栭儴 event candidate-pool allocation alpha锛屽綋鍓嶆渶寮虹殑 paper-only 鏂瑰悜鏄?`exp-20260509-006` 鐨?frozen event bundle锛屽叾涓?`exp-20260509-007` 鎸囧悜闈瀗eneric state surface + positive PIT score` 鐨?bounded add-on銆?
3. lifecycle alpha锛屽挨鍏舵槸宸叉柟鍚戞€т负姝ｄ絾鏈?production-promoted 鐨?entry follow-through add-on銆?
4. meta-allocation / regime routing锛岄噸鐐硅В閲?`mid_weak` 涓轰粈涔堣禋閽变絾璺戣緭鎸囨暟銆?
5. LLM / news attribution repair锛屽彧鍦ㄥ畠鑳介噴鏀?soft ranking銆乶ews-confirmed exit 鎴?C strategy grading 鏃舵彃闃熴€?
6. production/backtest parity 鍙湪瀹冭兘閲婃斁鏂扮殑 alpha 瀹為獙鎴栨秷闄ょ湡瀹炴紓绉绘椂鎻掗槦锛涗笉瑕佹妸绾?parity 鏁寸悊褰撲綔榛樿涓荤嚎銆?
7. 鏂?universe / 鏂?entry 鍙仛 shadow audit锛涗笉瑕佺洿鎺ユ帴 production銆?

褰撳墠涓嶅缓璁户缁秷鑰楄凯浠ｇ殑鏂瑰悜锛?

- 寮辨寔浠?day-5/day-10 price-only early exit銆?
- 绾?OHLCV pullback reclaim / leadership / compression entry 鐨勫眬閮ㄦ壂鍙傘€?
- broad macro defensive overlay 鐨勭畝鍗曢棬鎺с€?
- C 绛栫暐鐨勫崟瀛楁鎴栧皬 checklist 淇慨琛ヨˉ銆?
- entry follow-through add-on 鐨勯檮杩戦槇鍊煎井璋冦€?
- 娌℃湁 alpha 閲婃斁浠峰€肩殑 parity-only 閲嶆瀯銆?
- 浠呭嚟鐩磋缁х画寮哄寲 production trailing partial-reduce 寤鸿銆?

### 3.1 涓嬩竴杞閮?alpha 婧愭墿灞曚紭鍏堢骇

浠ヤ笅鎺掑簭鍙洖绛斾竴涓棶棰橈細濡傛灉褰撳墠 accepted A+B stack 瑕佸悜鏂扮殑澶栭儴浜嬩欢 /
鍩烘湰闈?alpha 鎵╁睍锛屽摢绫绘暟鎹簮鏈€鍊煎緱浼樺厛鐮旂┒銆傚畠涓嶆浛浠ｅ綋鍓?playbook 鐨?
accepted core stack锛屼篃涓嶆巿鏉冭烦杩囧绐楀彛 Gate 4 鎴?measurement repair銆?

1. `Earnings + SEC filings + financial surprise`
   - 鍚屾剰鎺掔涓€銆傝繖鏄綋鍓嶄粨搴撴渶鑷劧銆佹渶鍙В閲娿€佹渶閫傚悎 EOD 鑺傚鐨勫閮?
     alpha 鎵╁睍鏂瑰悜锛屼篃鍜?`earnings_event_long` 宸叉毚闇插嚭鐨?P-ERN 鏁版嵁鐩插尯
     鐩存帴鐩歌繛銆?
   - 棣栨壒鏈€鍊煎緱缁撴瀯鍖栫殑鐗瑰緛涓嶆槸鏇村妯＄硦 checklist锛岃€屾槸鍙洖鏀俱€佸彲姣旇緝鐨?
     earnings / filing shock锛歚SUE`銆乺evenue surprise銆乬ross margin delta銆?
     FCF / NI divergence銆乮nventory / receivables abnormal growth銆?-K item
     type銆乬uidance raise/cut銆乸ost-earnings gap + drift銆?
   - 杩欐潯绾跨殑姝ｇ‘钀藉湴鏂瑰紡鏄妸 `earnings_event_long` 浠庘€滃崟瀛楁淇ˉ鈥濆崌绾т负
     鈥滅粨鏋勫寲浜嬩欢鍒嗙骇 + slot opportunity cost + drift follow-through鈥濈爺绌剁嚎銆?

2. `Analyst revisions / estimate data`
   - 鍘熷垯涓婂悓鎰忔帓绗簩锛涘鏋滄湭鏉ユ帴鍙椾粯璐规暟鎹紝瀹冨彲浠ヤ笌绗?1 绫诲苟鍒楁渶楂樹紭鍏堢骇銆?
   - 杩欑被鏁版嵁鏈€閫傚悎鍜?earnings / guidance 鑱斿姩锛岃€屼笉鏄绔嬬湅鍗曟 beat/miss銆?
     閲嶇偣鏄?revision drift銆乪stimate dispersion銆佷笂淇垎鏋愬笀鏁伴噺鍙樺寲銆佷互鍙?
     鈥渂eat 浣嗘病浜轰笂淇€濊繖绫?fake-beat 璇嗗埆銆?
   - 鐜板疄绾︽潫鏄暟鎹垚鏈拰鐐规椂鍙緱鎬э紱鍦ㄦ病鏈夊彲闈?PIT 鐗堟湰鍓嶏紝涓嶅簲鎶婂畠鍐欐垚
     production 渚濊禆銆?

3. `Insider transactions / Form 4`
   - 鍚屾剰鎺掔涓夈€傚畠姣旂函鏂伴椈婧愭洿缁撴瀯鍖栵紝涔熸瘮 13F/13D 鏇村強鏃讹紝鍜屽綋鍓嶇郴缁熺殑
     5-90 涓氦鏄撴棩鎸佹湁妗嗘灦鍖归厤銆?
   - 浼樺厛鐪?open-market cluster buying銆丆EO/CFO buying銆侀娆′拱鍏ャ€佹毚璺屽悗
     涔板叆銆佷拱鍏ラ噾棰?/ market cap锛屼互鍙婃帓闄?option exercise 鍜?10b5-1
     璁″垝鍐呭櫔闊炽€?

4. `Short interest / borrow pressure`
   - 鍚屾剰瀹冨簲楂樹簬 options / 13F / macro锛屼絾鍓嶆彁鏄壙璁ゅ厤璐规暟鎹彧鑳藉厛鍋?
     shadow-quality 鐗堟湰銆?
   - 姝ｇ‘瀵硅薄涓嶆槸鎶?FINRA daily short volume 璇綋 short interest锛岃€屾槸鎶?
     short interest / float銆乨ays to cover銆乥orrow fee銆乤vailability銆乭ard-
     to-borrow 鐘舵€佷笌 breakout / trend 寮哄娍鑱斿姩锛屽鎵?squeeze-ready 缁撴瀯銆?

5. `EOD options data`
   - 鍚屾剰鏀惧湪涓悗娈点€備笉鏄洜涓哄急锛岃€屾槸鍥犱负娓呮礂澶嶆潅銆佹垚鏈珮銆佹祦鍔ㄦ€ц繃婊ら毦锛?
     瀹规槗鍙樻垚楂樿嚜鐢卞害杩囨嫙鍚堥潰銆?
   - 瀹冩洿閫傚悎浣滀负纭灞傦細IV-vs-realized銆乻kew change銆丱I concentration銆?
     earnings IV normalization銆佷互鍙婂拰 short-interest/squeeze 鑱斿悎瑙ｉ噴銆?

6. `13F institutional holdings`
   - 鍚屾剰鏀惧湪涓悗娈碉紝瀹氫綅搴旀槸涓湡 crowding / ownership overlay锛岃€屼笉鏄煭绾?
     entry engine銆?
   - 鏈€鏈変环鍊肩殑鏄?quality-manager 鏂拌繘/鍔犱粨涓庘€滀綆鍏虫敞搴?+ 鍩烘湰闈㈡敼鍠勨€濈殑
     缁撳悎锛岃€屼笉鏄窡鍗曟煇涓熀閲戠粡鐞嗐€?

7. `13D / 13G beneficial ownership`
   - 鎴戝悓鎰忓畠鍜?13F 鐩搁偦锛屼絾鑻ユ湭鏉ヨ鎵炬洿寮轰簨浠堕┍鍔ㄦ簮锛?3D 鐨勪氦鏄撲环鍊奸€氬父
     楂樹簬 13F锛屽洜涓哄畠鏇存帴杩?activist / control / strategic alternatives銆?
   - 鍥犳 playbook 閲屼繚鐣欏畠绱ч殢 13F 鐨勪綅缃紝浣嗙爺绌舵椂搴斾紭鍏堢湅 13D 鑰屼笉鏄?13G銆?

8. `ETF / index flow / forced flow`
   - 鍚屾剰鎶婂畠鏀惧湪鍚庡崐娈点€傚畠鏇撮€傚悎鍋?overlay銆乺eplacement-cost 瑙ｉ噴銆佷互鍙?
     reconstitution / inclusion / deletion 鍛ㄦ湡鐨勪簨浠惰ˉ鍏咃紝鑰屼笉鏄厛鍋氫富 alpha銆?

9. `Macro / rates / credit regime`
   - 寮虹儓鍚屾剰瀹冧笉璇ュ仛涓偂 alpha 涓诲紩鎿庛€傚畠鏈€閫傚悎浣滀负 risk overlay銆乸osition
     scaling銆乻leeve routing锛岃€屼笉鏄畝鍗?broad gate銆?
   - 杩欎篃涓庡綋鍓?playbook 宸茶瘉浼殑 broad macro defensive overlay 缁撹涓€鑷淬€?

10. `Alternative data`
   - 鍚屾剰鏀炬渶鍚庯紝浣嗕笉鏄惁瀹氬畠鐨勪笂闄愶紱鑰屾槸瑕佹眰瀹冨繀椤绘槸鈥滆涓氳仛鐒︺€佸彲瑙ｉ噴銆?
     鑳借惤鍒颁竴涓叿浣?alpha hypothesis鈥濄€?
   - 濡傛灉鏈潵鍋氳繖涓€绫伙紝鍙簲閫?1-2 涓湡姝ｇ悊瑙ｇ殑琛屼笟锛岄伩鍏嶆妸鏁版嵁閲囪喘鍜屾竻娲?
     鏈韩璇綋鎴?alpha 杩涘睍銆?

闄嶇骇椤逛篃鍚屾剰锛歚Level 2`銆乼ick銆佺绾?order flow銆乤uction imbalance銆佺函鐩樹腑
mean reversion銆乣0DTE` flow 閮戒笉绗﹀悎褰撳墠绯荤粺鐨?EOD / 浜嬩欢 / 缁撴瀯鎬?edge銆?

瀵瑰綋鍓嶄粨搴撶殑鐩存帴鍚箟锛?

- 涓嬩竴杞€滄柊澶栭儴 alpha 婧愨€濋粯璁や粠 `earnings + SEC + surprise` 寮€濮嬶紝鑰屼笉鏄啀
  鎵╁睍涓€涓函 OHLCV entry 鍙樹綋銆?
- 鑻ユ湭鏉ュ厑璁镐粯璐规暟鎹紝`analyst revisions` 鏄敮涓€鍙互鍜?earnings 绾垮苟鍒楁彁绾?
  鐨勫€欓€夈€?
- `macro`銆乣13F`銆乣ETF flow`銆乣options` 榛樿鍏堜綔涓?overlay / confirmation /
  attribution 鐮旂┒绾匡紝鑰屼笉鏄姠鍗犱富 entry sleeve銆?
- `insider` 涓?`short-interest` 鏄綋鍓嶆渶鍊煎緱鎺掑湪 earnings 涔嬪悗鐨勫厤璐规垨鍗婂厤璐?
  缁撴瀯鍖栦簨浠舵簮銆?

## 4. 鏈哄埗鐘舵€佽〃

| Mechanism family | Status | Long-term conclusion | Key experiments |
|---|---|---|---|
| Accepted A+B stack | accepted baseline | 涓夌獥鍙ｅ潎璧氶挶锛宭ate 寮猴紝mid 璺戣緭鎸囨暟锛宱ld win rate 涓嶇ǔ | fixed-window backtests |
| Technology trend wider target | accepted | winner-truncation repair 鍙湪绐?cohort 涓婃垚绔?| exp-20260425 target-width family |
| Commodity trend wider target | accepted narrow | 閮ㄥ垎 commodity trend winner 闇€瑕佹洿瀹?target锛屼絾涓嶅彲娉涘寲鍒?breakout | exp-20260425 target-width family |
| Single-position cap 25% | accepted | 鏀瑰杽 winner capture / risk allocation锛屼繚鐣?| exp-20260425 cap family |
| Trend Financials risk boost | accepted narrow | 宸插叆閫?Financials trend sleeve 鍦?mid/old 绐楀彛閲嶅璐＄尞锛岄€傚悎 sizing boost锛涗笉瑕佹硾鍖栨垚 sector priority | exp-20260429-015 |
| Financials sector-leader risk budget | accepted narrow | Within accepted trend Financials, only 20-day sector-relative leaders justify lifting total risk from 1.5x to 2.5x; do not retry nearby multipliers without forward/event evidence | exp-20260501-006 |
| Financials sector-leader position cap | rejected / too small | 45-50% caps improved mid_weak and old_thin but only +1.10% aggregate EV and +1.52% PnL, with no late_strong exposure; do not retry nearby cap scalars without forward concentration evidence or a new lifecycle/event discriminator | exp-20260503-050 |
| Risk-on SPY-relative leader risk budget | accepted | Otherwise-unmodified `risk_on` leaders versus SPY deserve 2.0x risk; this is the current accepted broad allocation overlay and already subsumes nearby plain-risk-on scalar ideas | exp-20260501-024 |
| Risk-on SPY-relative leader position cap | accepted | The accepted otherwise-unmodified SPY-relative leader sleeve was cap-constrained; only this sleeve may use a 50% initial position cap. Do not retry broader initial-cap unlocks without forward/event evidence. | exp-20260502-021 |
| SPY-relative leader follow-through add-on cap | accepted | The first day-2 follow-through add-on for already-accepted SPY-relative leaders may use a 60% position cap. Do not retry nearby higher caps without forward/tail evidence. | exp-20260502-022 |
| Entry follow-through add-on | promising, default-off | day2 `>= +2%` 涓?RS vs SPY `> 0` 鐨?25% add-on 涓夌獥鍙ｆ柟鍚戞€т负姝ｏ紝浣?materiality modest | exp-20260426-009/010/011/012/035, exp-20260427-010/011 |
| LLM soft ranking | blocked / high-upside | 鏂瑰悜浠嶉噸瑕侊紝浣嗗繀椤诲厛鏈夎冻澶?production-aligned replay sample | exp-20260426-015/022/023 |
| News-confirmed weak-hold exit | blocked, not falsified | 姒傚康姣?price-only exit 骞插噣锛屼絾 archive coverage 涓嶈冻 | exp-20260425-037 |
| Earnings C strategy revival | deferred | PEAD 澶х被鏈锛屼絾褰撳墠瀹炵幇涓嶆槸绠€鍗曡ˉ鏁版嵁鑳芥晳 | exp-20260418+, C-gate families |
| Meta-allocation / regime routing | promising but early | `mid_weak` 闂鏇村儚浠€涔堟椂鍊欑敤鍝釜 sleeve锛岃€屼笉鏄己涓€涓?entry | exp-20260423 meta series |
| Shared parity helpers | accepted governance | 鍏ュ満 gate銆乺egime risk sizing銆乸artial-reduce 璇箟閮藉簲鐢卞叡浜?helper 椹卞姩锛涙湭鏉ヤ笉鎺ュ彈 run/backtester 鍙屼唤閫昏緫 | exp-20260429-007/008/012 |
| AI infra pilot sleeve + attribution | accepted governance | `BE/INTC/LITE` 鍙兘鍏堜互 bounded forward pilot 鏀堕泦 replacement-value 璇佹嵁锛屼笉鏄?core watchlist promotion | exp-20260501-029/030 |
| Trailing partial reductions | measurable but rejected alpha | 鐜板湪鍙洖鏀撅紝浣?replay-on 瀵瑰綋鍓?stack 涓鸿礋锛涗繚鐣欎负鍏变韩鍙璁℃満鍒讹紝涓嶄綔涓洪粯璁?alpha | exp-20260429-012 |
| Residual narrow sector pockets | accepted but overfit-prone | 鍙綔涓虹嚎绱紝涓嶅簲鏃犻檺鎸栨畫宸?| exp-20260423/25 residual pocket series |
| Universe expansion scouts | observed-only | 浜嬩欢/楂?beta/mid-cap scouts 鏈夌嚎绱紝浣嗗彈 snapshot / coverage 闄愬埗 | exp-20260426-013/021/025/031 |
| Frozen default-off event bundle | accepted direction, paper-only | after the 2026-05-08 accepted-stack refresh, the current strongest external candidate-pool extension is still the frozen 10-day SEC/Form 4 event bundle; it improves all three canonical windows versus core-only but remains replay-only until shared event adapters and forward replacement-value outcomes exist | exp-20260509-006 |
| Non-generic positive state-surface event add-on | promising replay-only alpha lead | within the frozen event bundle, the best current discriminator is to add bounded paper notional only when PIT state score is positive on a named non-generic state surface; do not retune sources, hold days, or generic score tilts on the same sample | exp-20260507-026, exp-20260509-007 |
| Analyst estimate revision overlay | blocked after data repair | same-event key repair was necessary but insufficient; no three-window candidate touch yet, so revisions remain a forward-ledger question rather than a current ranking field | exp-20260508-006/011 |
| Liquidity-gated 10-K forward watch | accepted measurement adapter | currently the best blocked external candidate-pool direction, but only as an append-only PIT watch until it accumulates real outside-universe candidates and replacement-value outcomes | exp-20260503-011, exp-20260508-011/012 |

## 5. 宸茶瘉浼垨闄嶇骇鐨勬満鍒舵棌

### 5.1 Weak-hold early exit

缁撹锛氫笉瑕佺敤绠€鍗?day-5/day-10 寮卞娍銆丷S lag銆乻ector lag 浣滀负鏃╁崠瑙勫垯銆?

鍘熷洜锛?

- 澶氭暟瑙﹀彂绋€鐤忥紝鏀剁泭鏀瑰杽鏋佸皬銆?
- 瀹规槗鎴柇 delayed winners锛屼緥濡傚急寮€灞€鍚庢仮澶嶇殑澶ц耽瀹躲€?
- sector confirmation 鏈兘鏁戞椿 price-only weak-hold 妯℃澘銆?

闄ら潪鏂板淇″彿鏄湡姝ｆ浜ょ殑 adverse information锛屼緥濡傛柊璐熼潰鏂伴椈銆佽储鎶ユ伓鍖栥€佽繛缁鏃ユ棤娉?reclaim锛屽惁鍒欎笉瑕侀噸璇曞悓鏋勬ā鏉裤€?

Key experiments锛歚exp-20260425-036`, `exp-20260425-037`, `exp-20260425-038`, `exp-20260426-059`銆?

### 5.2 Pullback / leadership / OHLCV-only new entry

缁撹锛氫笉瑕佺户缁彧闈犺繎楂樸€丷S銆乸ullback銆乮nside-day銆乧ompression 绛?OHLCV 褰㈡€佸弽澶嶉€?D 绛栫暐銆?

鍘熷洜锛?

- 涓ユ牸瀹氫箟鏍锋湰澶皯銆?
- 鏀炬澗瀹氫箟鍚庡彉鎴?noisy continuation clutter銆?
- 璁稿 shadow source 鍦ㄤ竴涓獥鍙ｆ湁 forward return锛屼絾璺ㄧ獥鍙ｄ笉绋炽€?

濡傛灉閲嶅惎锛屽繀椤诲姞鍏ユ柊鐨勪笂涓嬫枃鏉ユ簮锛屼緥濡備簨浠躲€乻ector leadership persistence銆乺egime state锛屾垨鍏堣瘉鏄庡畠涓?A+B 鏈変綆閲嶅彔涓旇法绐楀彛 forward return 绋冲畾銆?

Key experiments锛歚exp-20260422-016`, `exp-20260423-001`, `exp-20260426-057`, pullback / VCP / opening-range / gap-and-hold / undercut-reclaim shadow audits銆?

### 5.3 Broad macro defensive overlay

缁撹锛氬畯瑙?defensive 鏂瑰悜涓嶈兘鐢ㄧ畝鍗?broad gate 鎴?gross haircut 鐩存帴涓婄嚎銆?

鍘熷洜锛?

- OR stress trigger 杩囧锛屼細璇激鍋ュ悍绐楀彛銆?
- strict AND trigger 澶█鐤忔垨 vacuous銆?
- defensive / commodity 琛屼负鍙兘瀛樺湪锛屼絾闇€瑕?sleeve routing 鎴栨洿缁嗙姸鎬侊紝涓嶆槸缁熶竴闄嶉闄┿€?

濡傛灉閲嶅惎锛屼紭鍏堝仛 explainability map锛氫粈涔堢姸鎬佷笅 `breakout_long`銆乣trend_long`銆乨efensive exposure 鍚勮嚜搴旇鎷块闄┿€?

Key experiments锛歚exp-20260423-013/014/015/016`, macro defensive v1/v2/budget, cross-asset proxy expansion銆?

### 5.4 C strategy single-field repair

缁撹锛氫笉瑕佸啀鐢ㄥ崟瀛楁 earnings gate 鎴栧皬 checklist 璇曞浘鏁?C 绛栫暐銆?

鍘熷洜锛?

- repaired-data 鍚庝粛鎷栫疮 A+B 鎴栨棤娉曠ǔ瀹氶€氳繃澶氱獥鍙ｃ€?
- 闂鏇村儚浜嬩欢璐ㄩ噺鍒嗙骇鍜?slot opportunity cost锛岃€岄潪鏌愪釜瀛楁缂哄け銆?

濡傛灉閲嶅惎锛屽繀椤昏涔堟湁 LLM 璐㈡姤 grading锛岃涔堟湁鏇村己 post-earnings continuation 鏈哄埗銆?

### 5.5 Entry add-on local threshold tuning

缁撹锛氭櫘閫?strict add-on 浠嶆槸鐮旂┒鍊欓€夛紝浣嗛檮杩戦槇鍊间笉瑕佸啀鎵€?

褰撳墠鍊欓€夛細

- checkpoint day: 2
- unrealized return: `>= +2%`
- RS vs SPY: `> 0`
- add-on size: `25%` original shares
- scheduling: allow schedule, enforce cap / heat on execution day

涓嶈浼樺厛閲嶈瘯锛?

- RS 闃堝€?`0.5% / 1% / 2%`
- absolute unrealized threshold `3% / 4% / 5%`
- day1-to-day2 improvement filter
- checkpoint cap-room prefilter
- positive ticker day2 return confirmation

鍘熷洜锛氳繖浜涢兘鏈ǔ瀹氭敼鍠勬櫘閫?`2% + RS>0 + 25%` 鍊欓€夛紱澶氭暟鍙槸鍑忓皯鏈夋晥 add-ons銆?

Key experiments锛歚exp-20260426-010/011/012/017/035`, `exp-20260427-010/011`銆?

## 6. Promising 浣嗘湭鐢熶骇鍖栨柟鍚?

### 6.1 Entry follow-through add-on

鏍稿績鍙戠幇锛?

- trade-level approximation 鍏堟樉绀?day2 follow-through 鏈夎竟銆?
- real BacktestEngine replay 鍚庝粛涓夌獥鍙ｆ柟鍚戞€т负姝ｃ€?
- 浣嗘墽琛屾棩 cap / heat 浼氬悆鎺夊ぇ閲忕悊璁烘敹鐩婏紝鐪熷疄 effect size 杈冨皬銆?

浠ｈ〃缁撴灉锛?

- no-add-on -> ordinary 25% add-on锛歛ggregate EV delta `+0.0447`锛宎ggregate PnL `+$1,523.89`锛?/3 windows improved銆?
- smaller fractions 10% / 15% 涓嶅 25%銆?
- higher RS / higher unrealized threshold / improvement filter 閮芥病鏈夌ǔ瀹氳儨杩?ordinary candidate銆?

褰撳墠鍐崇瓥锛?

- 淇濈暀 default-off harness銆?
- 涓嶉粯璁や笂绾裤€?
- 涓嬩竴姝ヨ嫢缁х画锛屽繀椤诲鎵?materiality unlock 鎴栨柊 evidence source锛岃€屼笉鏄户缁湰鍦伴槇鍊煎井璋冦€?

鍙爺绌剁殑涓嬩竴姝ワ細

- cap / heat 鏄惁杩囧害闃绘宸茬‘璁?winner 鐨勫姞浠擄紝浣嗚繖灞炰簬 capital allocation 瀹為獙锛屼笉鏄?add-on trigger 寰皟銆?
- forward sample 鎴?paper-trading 瑙傚療鏄惁寮哄寲 materiality銆?
- LLM / news 鏄惁鑳界粰 add-on 鍋氫簨浠剁‘璁わ紝浣嗛渶瑕?replay coverage銆?

### 6.2 LLM soft ranking / event grading

鏍稿績鍙戠幇锛?

- LLM 浠嶆槸绯荤粺鐨勫悎鐞嗕紭鍔挎潵婧愶紝浣嗕笉鏄‖椋庢帶鎵ц鍣ㄣ€?
- 鐩墠鏈€澶ч棶棰樹笉鏄€淟LM 鏈夋病鏈変环鍊尖€濓紝鑰屾槸 replay archive / effective sample 杩樹笉澶熸敮鎾戝綊鍥犮€?

涓嬩竴姝ヨ姹傦細

- 鍙粺璁?production-aligned銆乺anking-eligible 鏍锋湰銆?
- 瀵?LLM 鏀捐 / 闄嶆潈 / veto 鍚庢敹鐩婂仛鍗曠嫭褰掑洜銆?
- 璁?LLM 杈撳嚭缁撴瀯鍖栧瓧娈碉紝渚嬪 event_type銆乪vent_strength銆乺isk_type銆乼ime_sensitivity銆乧onfidence銆乺anking_reason銆?

### 6.3 Meta-allocation / regime routing

鏍稿績鍙戠幇锛?

- `late_strong` 璇存槑 A+B 鍦ㄨ秼鍔垮弸濂芥湡闈炲父寮恒€?
- `mid_weak` 璇存槑绯荤粺鍗充娇璧氶挶锛屼篃鍙兘杈撶粰鎸囨暟锛岄棶棰樹笉鏄崟绾己 signal锛岃€屾槸 allocation / sleeve routing銆?
- `old_thin` 璇存槑寮辩幆澧冧笅 win rate 浣庯紝鍙兘闇€瑕佺姸鎬佽瘑鍒垨椋庨櫓璺敱锛岃€岄潪鏂板灞€閮?entry銆?

鎺ㄨ崘鐮旂┒妗嗘灦锛?

- Market structure锛歜readth銆乪qual-weight vs cap-weight銆乻ector dispersion銆?
- Volatility / correlation锛歳ealized vol銆乮ntraday range銆乧ross-asset pressure銆?
- Flow / positioning proxy锛歡ap-up fade銆乴eader reversal銆乫ake breakout density銆?

涓嶈鐩存帴璺冲埌榛戠 classifier銆傚厛鍋氬皯閲忋€佸彲鍥炴斁銆佸彲瑙ｉ噴鐨?state variables銆?

## 7. 宸叉帴鍙椾絾闇€璋ㄦ厧鐨勭獎瑙勫垯

浠ヤ笅瑙勫垯鎴?cohort 鏇剧粡閫氳繃澶氱獥鍙ｆ垨灞€閮?Gate锛屼絾瀛樺湪杩囨嫙鍚堥闄┿€傚畠浠彲浠ヤ綔涓哄綋鍓?accepted stack 鐨勭粍鎴愭垨鐮旂┒绾跨储锛屼絾涓嶈鏃犻檺澶栨帹锛?

- `Technology trend` 鏇村 target銆?
- `Commodity trend` 鏇村 target銆?
- `single-position cap = 25%`銆?
- 鑻ュ共 residual sector / DTE / near-high pockets銆?

浣跨敤鍘熷垯锛?

- 涓嶆妸绐?pocket 鎵╁ぇ鎴愬叏灞€瑙勫垯銆?
- 涓嶇敤鍗曠獥鍙ｆ紓浜粨鏋滆瘉鏄庡ぇ绫绘満鍒躲€?
- 鑻ユ柊澧炵浉浼?pocket锛屽繀椤昏瘉鏄庡畠涓嶆槸鏃㈡湁 residual mining 鐨勭畝鍗曢噸澶嶃€?

## 8. 澶辫触璁板繂绱㈠紩

涓嬭〃涓嶆槸瀹屾暣鏃ュ織锛屽彧鏄槻姝㈤噸澶嶆€濊矾銆傚畬鏁村弬鏁版煡 `docs/experiment_log.jsonl` 鎴?`docs/experiments/logs/`銆?

| Family | Do not repeat without new evidence | Why |
|---|---|---|
| breakout breadth-only ranking | simple breadth scalar reorder | too weak / often null |
| pullback reclaim | nearby pullback/reclaim OHLCV thresholds | noisy continuation clutter |
| leadership D-strategy | near-high + RS only | strict too sparse, loose dilutes A+B |
| broad stress overlay | OR stress, simple gross haircut | overfires / wrong deployment shape |
| strict weak-tape AND | same two-feature AND as action trigger | often vacuous / insufficient exposure |
| macro defensive gate | simple cross-asset or defensive budget rule | not stable enough |
| weak-hold early exit | day-5/day-10 weak PnL / RS lag | truncates delayed winners |
| sector-confirmed weak exit | weak hold + same-sector lag | effect tiny and sparse |
| add-on RS tightening | global RS thresholds above 0 | removes profitable rotation-tape add-ons |
| add-on stronger unrealized | global thresholds above 2% | reduces realized add-on alpha |
| add-on improvement filter | day2 must improve vs day1 | not better than ordinary add-on |
| C strategy checklist | small earnings quality checklist | cannot overcome slot opportunity cost |

## 9. 涓嬩竴杞疄楠岄槦鍒?

浼樺厛绾?1锛氱‘璁?add-on 鐨?materiality ceiling銆?

- 闂锛氫弗鏍?day2 follow-through add-on 宸茬ǔ瀹氫负姝ｏ紝浣嗙湡瀹炴敹鐩婂皬銆備笅涓€姝ヤ笉鏄槇鍊硷紝鑰屾槸闂€滀负浠€涔?cap/heat 鐣欎笉鍑虹┖闂达紝鏄惁鍊煎緱閲嶅垎閰嶉闄╋紵鈥?
- 鍚堟牸瀹為獙锛歞efault-off capital allocation replay锛屽崟涓€鍙橀噺锛屽彧鏀瑰彉 cap / heat / add-on budget semantics銆?
- 椋庨櫓锛氭斁鏉?cap 鍙兘澧炲姞 concentration 鍜?tail risk锛屽繀椤讳笁绐楀彛瀵规瘮銆?

浼樺厛绾?2锛氬仛 `mid_weak` 鐨?meta-allocation 瑙ｉ噴鍥俱€?

- 闂锛歚mid_weak` 缁濆璧氶挶浣嗚窇杈?SPY/QQQ锛岃鏄?allocation 涓嶅閫傚簲 rotation-heavy bull銆?
- 鍚堟牸瀹為獙锛氬厛鍋?audit / map锛屼笉鐩存帴鏀圭瓥鐣ワ紝杈撳嚭 sleeve銆乻ector銆乥readth銆乿ol銆乫ake-breakout density 鐨勮础鐚垎瑙ｃ€?
- 椋庨櫓锛氬鏋滅洿鎺ヤ笂 classifier锛屽鏄撹繃鎷熷悎銆?

浼樺厛绾?3锛氭瀯閫?LLM event grading replay 鏍锋湰銆?

- 闂锛歀LM ranking 楂?upside锛屼絾鏍锋湰涓嶅銆?
- 鍚堟牸瀹為獙锛氬鍔犵粨鏋勫寲钀界洏鍜?effective attribution锛屼笉鏀瑰彉纭鎺с€?
- 椋庨櫓锛氫笉鑳借 LLM 鍦ㄦ棤褰掑洜鏃舵帴绠′粨浣嶆垨纭?veto銆?

浼樺厛绾?4锛氭柊 universe / new D-strategy 鍙仛 shadow銆?

- 闂锛氬綋鍓?universe 鍙兘闄愬埗 alpha 鎼滅储锛屼絾 snapshots 瀵?outside-production ticker 鏀寔涓嶈冻銆?
- 鍚堟牸瀹為獙锛氬厛楠岃瘉鍊欓€夎鐩栥€侀噸鍙犵巼銆乫orward return銆佹暟鎹彲鐢ㄦ€э紝涓嶆帴鐢熶骇銆?
- 椋庨櫓锛歴hadow forward return 瀹规槗琚垢瀛樿€呭亸宸拰 coverage bias 姹℃煋銆?

## 10. 璇佹嵁绾у埆

| Level | Meaning | Allowed use |
|---|---|---|
| L0 | 鎯虫硶 / 閲戣瀺鐩磋 | 鍙兘鍐?hypothesis |
| L1 | shadow audit 鏈夋柟鍚戞€?| 鍙繘鍏?default-off replay |
| L2 | real backtester 涓夌獥鍙ｆ柟鍚戞€т负姝?| 鍙繚鐣?harness / 缁х画鐮旂┒ |
| L3 | 涓夌獥鍙ｉ€氳繃 Gate 4 涓?effect size 瓒冲 | 鍙€冭檻 production promotion |
| L4 | forward / paper / live 涔熺‘璁?| 鍙彁鍗囦负闀挎湡 accepted doctrine |

褰撳墠澶у鏁版柊澧炴柟鍚戝彧鍒?L1-L2銆備笉瑕佹妸 L1 shadow 褰撴垚鐢熶骇 alpha銆?

## 11. 鏂板疄楠屽啓鍏ヨ鍒?

鏂板瀹為獙涓嶈鎶婂畬鏁存祦姘磋处杩藉姞鍒版湰鏂囨。銆傚彧鍦ㄤ互涓嬫儏鍐典笅鏇存柊鏈枃妗ｏ細

- 涓€涓満鍒舵棌鐨勭姸鎬佹敼鍙樹簡锛屼緥濡?`promising -> accepted`銆乣promising -> rejected`銆乣blocked -> testable`銆?
- 鍑虹幇鏂扮殑闃查噸澶嶈鍒欍€?
- 涓嬩竴杞紭鍏堢骇鍙戠敓鍙樺寲銆?
- 鏈夎冻澶熸硾鍖栦环鍊肩殑鏈哄埗鍚彂銆?

鎺ㄨ崘鍐欐硶锛?

```text
### Mechanism family name

Status: accepted / promising / rejected / blocked / deferred
Core conclusion: one paragraph.
Evidence: key experiment IDs and only the metrics needed to justify the state.
Do not repeat: nearby variants that are now low priority.
Next valid retry requires: concrete new evidence or changed data condition.
```

涓嶈鍐欏叆锛?

- 姣忎釜绐楀彛鐨勫畬鏁?stdout銆?
- 姣忎釜鍙傛暟 sweep 鐨勬墍鏈変腑闂村€笺€?
- 宸茬粡鍦?`experiment_log.jsonl` 閲岀殑 JSON 瀛楁銆?
- 鍙鍗曟瀹為獙鏈夋剰涔夌殑杩囩▼鎬ф帹鐞嗐€?

## 12. 蹇€熷惎鍔ㄦ竻鍗?

姣忚疆寮€濮嬭鏈枃妗ｆ椂锛屽厛鍥炵瓟锛?

1. 鏈疆鏂瑰悜灞炰簬鍝釜 mechanism family锛?
2. 瀹冩槸鍚﹁俯涓簡绗?8 鑺傜殑闃查噸澶嶇鍖猴紵
3. 濡傛灉鍍忔棫鏂瑰悜鐨勫彉浣擄紝鏂拌瘉鎹槸浠€涔堬紵
4. 瀹冩槸 `alpha_search` 杩樻槸瑙ｉ櫎 alpha 鎼滅储闃诲鐨?`measurement_repair`锛?
5. 濡傛灉鎴愬姛锛屼細鏀瑰彉绗?4 鑺傜姸鎬佽〃杩樻槸鍙槸澧炲姞涓€鏉″疄楠屾棩蹇楋紵

鑻ョ 5 鐐圭瓟妗堝彧鏄€滃鍔犱竴鏉″疄楠屾棩蹇椻€濓紝榛樿涓嶈鏀规湰鏂囨。锛屽彧鍐欑粨鏋勫寲瀹為獙璁板綍銆?

### 2026-04-27 mechanism update: Entry follow-through add-on cap headroom

Status: promising, default-off.

Core conclusion: The clean strict day-2 trigger remains `unrealized >= 2%` and `RS vs SPY > 0`; nearby trigger tightening is now low priority. exp-20260427-012 moved the prior shadow-only cap-headroom audit into a real BacktestEngine config hook (`ADDON_MAX_POSITION_PCT`) and found that an add-on-only 35% position cap improved 3/3 fixed windows versus both no-add-on and ordinary 25% add-on.

Evidence: aggregate EV delta was `+0.1458` / PnL `+$4,415.14` versus no-add-on, and `+0.1011` / `+$2,891.25` versus ordinary 25% add-on. Max drawdown increased at most `+0.28 pp`; newly executed add-ons were 4.

Do not repeat: more local add-on trigger threshold tuning (`RS > 0`, day-2 unrealized thresholds, day1/day2 improvement filters).

Next valid retry requires: forward/paper evidence or an explicit production-promotion decision for the 35% add-on-only cap after reviewing concentration risk. Do not generalize this into a higher initial-entry position cap.

### 2026-04-27 mechanism update: Strict follow-through add-on production default

Status: accepted / production default.

Core conclusion: exp-20260427-013 promoted the strict day-2 follow-through add-on to the default backtester configuration with `ADDON_ENABLED=True` and `ADDON_MAX_POSITION_PCT=0.35`. The 25% initial-entry cap remains unchanged; the 35% cap applies only to follow-through add-ons after the existing day-2 `unrealized >= 2%` and `RS vs SPY > 0` trigger.

Evidence: fixed-window default-config replay matched the prior 35% headroom research harness. EV improved in all three windows versus no-add-on baseline: `late_strong 1.5039 -> 1.5855`, `mid_weak 0.4773 -> 0.5218`, `old_thin 0.1310 -> 0.1507`. Aggregate PnL improved by `$4,415.14` / `+6.57%`; max drawdown increased by at most `0.29 pp`.

Do not repeat: local add-on trigger threshold tuning. Keep day-2, `+2%` unrealized, and `RS > 0` as the clean trigger unless new forward evidence appears.

Next valid retry requires: live/paper concentration monitoring, or a genuinely new add-on evidence source. Do not generalize the 35% cap to initial entries or non-follow-through adds.

### 2026-04-27 mechanism update: Global capacity is not meta-allocation

Status: rejected.

Core conclusion: exp-20260427-014 tested whether the accepted A+B+strict-add-on stack was globally capacity constrained by sweeping `MAX_POSITIONS` across 4/5/6/7 on the fixed three-window snapshot set. The result does not support a global slot-count change. Wider capacity helped `mid_weak` PnL but added lower-quality exposure in `late_strong` and `old_thin`; tighter capacity helped only `old_thin` and damaged late/mid.

Evidence: versus the current default 5 slots, `MAX_POSITIONS=6` improved `mid_weak` PnL by `$2,020.42` but regressed `late_strong` EV by `-0.0206`, regressed `old_thin` EV by `-0.0050`, and increased `mid_weak` drawdown by `+1.28 pp`. `MAX_POSITIONS=7` damaged aggregate EV more sharply (`-0.2520` EV sum), while `MAX_POSITIONS=4` regressed two of three windows.

Do not repeat: nearby global `MAX_POSITIONS` scans as a default meta-allocation experiment.

Next valid retry requires: explicit market-state or sleeve-level conditioning that explains when additional slots should be used. The next meta-allocation step should map which sleeve/sector deserves risk in `mid_weak`, not change total portfolio capacity globally.

### 2026-04-27 mechanism update: Scarce-slot sleeve routing

Status: promising, default-off.

Core conclusion: exp-20260427-019 tested a conditional sleeve-routing rule rather than another global capacity change: when only one entry slot remains, defer `breakout_long` entries so the slot is preserved for `trend_long` candidates. This improved `mid_weak` and `old_thin` while leaving `late_strong` unchanged, supporting the exp-20260427-016 audit that scarce-slot trend entries have better marginal slot value than scarce-slot breakouts.

Evidence: EV deltas were `late_strong +0.0000`, `mid_weak +0.0491`, and `old_thin +0.0109`; aggregate PnL delta was `+$867.84`; max drawdown did not increase. The rule deferred 11 breakout candidates across the three windows.

Do not repeat: broad breakout de-risking, global `MAX_POSITIONS` changes, or combining this with add-on trigger tuning.

Next valid retry requires: stronger materiality, forward/paper confirmation, or a production-promotion decision that accepts the modest effect size. Keep it default-off until then.

### 2026-04-27 mechanism update: Scarce-slot threshold widening

Status: rejected.

Core conclusion: exp-20260427-020 tested whether the scarce-slot breakout defer rule should widen from `DEFER_BREAKOUT_WHEN_SLOTS_LTE=1` to `=2`. The wider rule improved `mid_weak` but behaved like broad breakout de-risking in `late_strong`, so the one-slot hook remains the best tested form.

Evidence: `slots_lte_2` produced EV deltas `late_strong -0.3648`, `mid_weak +0.1188`, `old_thin +0.0109`; aggregate EV delta was `-0.2351` and aggregate PnL delta was `-$3,237.82`. It deferred 23 breakout candidates versus 11 for the one-slot form.

Do not repeat: `DEFER_BREAKOUT_WHEN_SLOTS_LTE >= 2` as a threshold-only materiality unlock.

Next valid retry requires: an explicit market-state or sleeve-level discriminator that explains why broader breakout deferral should apply outside `late_strong`.

### 2026-04-27 mechanism update: Scarce-slot regime allowlist

Status: rejected.

Core conclusion: exp-20260427-021 tested whether the one-slot breakout defer hook could be made more robust with a simple market-regime allowlist. It could not. `BULL`-only exactly matched the unconditional one-slot rule because all useful deferrals occurred during BULL regimes, while `NEUTRAL/BEAR`-only never fired.

Evidence: `bull_only_lte_1` matched the exp-20260427-019 result exactly: aggregate EV delta `+0.0600`, PnL delta `+$867.84`, and 11 deferred breakouts. `neutral_bear_lte_1` had zero deferred breakouts and zero metric delta.

Do not repeat: simple `market_regime` allowlists for scarce-slot breakout deferral.

Next valid retry requires: a more specific state discriminator, such as sleeve/sector crowding, breadth, or marginal slot-quality context. Keep the existing one-slot hook default-off.

### 2026-04-27 mechanism update: Scarce-slot same-sector crowding

Status: rejected.

Core conclusion: exp-20260427-022 tested whether the one-slot breakout defer edge comes specifically from avoiding breakout candidates that add to same-sector exposure already held in the portfolio. It did not. The condition reduced the number of deferred breakouts versus the unconditional one-slot hook, but produced no EV improvement in `late_strong` or `mid_weak` and worsened `old_thin` EV/drawdown.

Evidence: EV deltas versus default were `late_strong +0.0000`, `mid_weak +0.0000`, and `old_thin -0.0009`; aggregate PnL rose only `$247.58` while max drawdown increased by `+1.55 pp`. The temporary hook deferred 5 breakouts across the three windows and was rolled back.

Do not repeat: same-sector held-count crowding as the next scarce-slot breakout discriminator.

Next valid retry requires: a different state variable, such as sector breadth, candidate-level rank gap, or explicit marginal slot-quality context. Keep the existing one-slot hook default-off.

### 2026-04-27 mechanism update: Scarce-slot same-day trend substitution

Status: rejected.

Core conclusion: exp-20260427-023 tested whether the one-slot breakout defer edge comes from direct same-day sleeve substitution. It does not. Requiring a same-day `trend_long` candidate before deferring `breakout_long` reduced deferrals from 11 to 3, produced zero EV change versus baseline in all three windows, and gave up the known unconditional one-slot improvement in `mid_weak` and `old_thin`.

Evidence: versus baseline, EV deltas were `late_strong +0.0000`, `mid_weak +0.0000`, and `old_thin +0.0000`; aggregate PnL delta was `$0.00`. Versus the unconditional one-slot hook, EV delta sum was `-0.0600` and PnL delta was `-$867.84`.

Do not repeat: same-day trend availability as the next scarce-slot breakout discriminator, or combinations of it with simple `market_regime` allowlists or same-sector held-count crowding.

Next valid retry requires: a different information source, such as candidate-level rank gap, breadth, or forward/paper evidence. The current evidence says the modest edge is more likely from leaving capacity open for later candidates than from same-day substitution.

### 2026-04-27 mechanism update: Scarce-slot candidate rank gate

Status: rejected.

Core conclusion: exp-20260427-024 tested whether the one-slot breakout defer edge could be made more precise by preserving top-ranked breakouts and only deferring lower-ranked breakout candidates. It could not. Candidate-rank thresholds `rank >= 2` and `rank >= 3` were EV-null versus baseline across all three fixed windows and gave up the known unconditional one-slot benefit.

Evidence: `rank_gte_2_lte_1` deferred only 3 breakouts and produced aggregate EV delta `+0.0000` / PnL delta `$0.00` versus baseline, compared with unconditional one-slot EV delta `+0.0600` / PnL `+$867.84`. `rank_gte_3_lte_1` deferred 0 breakouts and was inert.

Do not repeat: simple candidate-rank thresholds for scarce-slot breakout deferral, or combinations of rank thresholds with same-day trend availability, simple market-regime allowlists, or same-sector held-count crowding.

Next valid retry requires: a genuinely different information source such as breadth, candidate forward-quality context, or forward/paper evidence. The current evidence says the modest one-slot edge is not explained by weak same-day rank.

### 2026-04-27 mechanism update: Scarce-slot simple breadth gate

Status: rejected.

Core conclusion: exp-20260427-025 tested whether the default-off one-slot breakout defer edge could be explained by weak same-day universe breadth above the 50-day SMA. It could not. A strict `breadth <= 55%` condition was inert across all three fixed windows, while `breadth <= 65%` produced no EV improvement in late_strong or mid_weak and regressed old_thin.

Evidence: versus baseline, `breadth_lte_55_lte_1` deferred 0 breakouts and produced aggregate EV delta `+0.0000`. `breadth_lte_65_lte_1` deferred 3 breakouts but produced aggregate EV delta `-0.0134`, aggregate PnL delta `-$501.29`, and max drawdown increase `+0.19 pp`. The already-known unconditional one-slot hook remained best with aggregate EV delta `+0.0600` and PnL delta `+$867.84`.

Do not repeat: simple universe breadth-above-SMA thresholds as the next scarce-slot breakout discriminator.

Next valid retry requires: a genuinely different information source such as candidate forward-quality context, a richer breadth/dispersion map, or forward/paper evidence. Keep the existing one-slot scarce-slot hook default-off.

### 2026-04-27 mechanism update: Global TQS allocation ranking

Status: rejected.

Core conclusion: exp-20260427-026 tested whether the existing enriched `trade_quality_score` could be used as a global same-day allocation ranking key. It could not. Sorting all post-enrichment candidates by TQS regressed EV, PnL, Sharpe, and win rate in all three fixed windows, which means the current native strategy/order structure is carrying useful information that the heuristic TQS does not capture.

Evidence: EV deltas versus default were `late_strong -0.0746`, `mid_weak -0.0324`, and `old_thin -0.0706`; aggregate PnL delta was `-$5,555.30`. The temporary hook was rolled back after the failed Gate 4 check.

Do not repeat: global `trade_quality_score` sorting, confidence-score tie-break variants, or TQS-only allocation ordering as the next ranking experiment.

Next valid retry requires: a new information source or a narrower context that explains why TQS should dominate native ordering. Do not combine TQS sorting with scarce-slot breakout deferral unless a separate audit proves interaction value.

### 2026-04-27 mechanism update: Scarce-slot forward-quality audit

Status: observed-only / mechanism narrowed.

Core conclusion: exp-20260427-027 added measurement-only deferred-event details to the existing default-off one-slot breakout defer hook and measured deferred breakout forward returns. The one-slot hook still improved `mid_weak` and `old_thin` with no `late_strong` effect, but deferred breakouts were not uniformly weak. `mid_weak` deferred candidates were poor over 10/20 trading days; `old_thin` deferred candidates had positive 5/10 day average forward returns.

Evidence: metric deltas matched the known one-slot hook (`late_strong +0.0000`, `mid_weak +0.0491`, `old_thin +0.0109`; aggregate PnL `+$867.84`). Forward-quality audit: `mid_weak` deferred breakout 10d average `-7.81%` with 33.3% win rate; `old_thin` deferred breakout 10d average `+0.71%` with 75.0% win rate.

Do not repeat: same-day candidate-quality explanations that assume deferred breakouts are simply bad. This includes more TQS-only, rank-only, same-day trend availability, same-sector held-count, or simple breadth gates around the one-slot hook.

Next valid retry requires: forward/paper evidence, or a true capacity-timing discriminator that explains why leaving a slot open for later candidates beats taking the current breakout. Keep the one-slot hook default-off.

### 2026-04-27 mechanism update: Scarce-slot default promotion

Status: accepted / production default.

Core conclusion: exp-20260427-028 promoted the simple one-slot scarce-capacity sleeve-routing rule to default: when only one entry slot remains, defer `breakout_long` entries. This is a narrow capital-allocation rule, not broad breakout de-risking. The decision accepts modest but robust effect size because repeated attempts to add same-day discriminators failed, while the simple rule improved two fixed windows and regressed none.

Evidence: versus explicit no-defer baseline, EV deltas were `late_strong +0.0000`, `mid_weak +0.0491`, and `old_thin +0.0109`; aggregate PnL delta was `+$867.84`; max drawdown did not increase in any window and declined in `mid_weak` and `old_thin`. The rule deferred 11 breakout candidates across the three fixed windows.

Do not repeat: same-day scarce-slot explanation searches using simple rank, TQS, same-day trend availability, same-sector held-count, simple market-regime allowlists, or simple breadth thresholds.

Next valid retry requires: forward/paper concentration and opportunity-cost monitoring, or a new information source that explains capacity timing. Do not widen beyond one remaining slot without state-specific evidence.

### 2026-04-27 mechanism update: Extension weak-followthrough exit/ranking

Status: rejected.

Core conclusion: exp-20260428-007 checked whether an extended entry followed by strict short-term failure could become a clean lifecycle alpha. Even the all-three subset (entry day red, next close below entry open, and next-day RS vs SPY negative) was not good enough: it identified 10 losing trades worth `$3,626.04`, but still risked 3 winners worth `$3,828.88`, for a naive net of `-$202.84`.

Evidence: the broader exp-20260427-022 audit was worse (`-$21,607.85` naive net), and the strict subset still had winner collateral in `late_strong` and `mid_weak`. This means short-term OHLCV weakness after an extended entry is not sufficient adverse information by itself.

Do not repeat: nearby extension/weak-followthrough thresholds, entry-day red variants, next-close-below-entry variants, or simple next-day RS penalties as exit/reduce/ranking rules.

Next valid retry requires: an orthogonal adverse-information source such as negative news, earnings deterioration, or forward/paper evidence. Do not turn this into a production early-exit rule from OHLCV follow-through flags alone.

### 2026-04-27 mechanism update: Financials trend wider target

Status: rejected.

Core conclusion: exp-20260427-033 tested whether the accepted selective winner-truncation repair could extend from Technology/Commodities into `trend_long | Financials` with a single 6.0 ATR target. It cannot. The wider target had no late_strong exposure and materially damaged both weaker windows by delaying Financials trend exits and increasing drawdown.

Evidence: versus the current default stack, EV deltas were `late_strong +0.0000`, `mid_weak -0.2062`, and `old_thin -0.1219`; aggregate PnL delta was `-$10,170.05`, and max drawdown increased by up to `+3.54 pp`.

Do not repeat: broad Financials trend target widening or nearby 6.0-style target expansion as a simple extension of the Technology/Commodity target-width wins.

Next valid retry requires: a specific event or state discriminator that explains why wider Financials trend targets would not delay exits in `mid_weak` and `old_thin`. Do not generalize the accepted Technology/Commodity target-width mechanism to Financials.

### 2026-04-27 mechanism update: Second follow-through add-on

Status: rejected for production materiality.

Core conclusion: exp-20260427-035 tested a day-5 second follow-through add-on after the accepted day-2 add-on. The idea is directionally positive and did not regress any fixed window, but the effect size is too small for production promotion under Gate 4.

Evidence: the best tested variant (`day5`, unrealized `>= +5%`, `RS vs SPY > 0`, `35%` original shares, `60%` add-on cap) improved EV in `late_strong` and `mid_weak`, was inert in `old_thin`, and executed 7 second add-ons. Aggregate EV delta was `+0.0655`, aggregate PnL delta was `+$1,658.82`, and max drawdown increased only `+0.01 pp`.

Update 2026-05-01: exp-20260501-022 retested the production-shaped second
add-on path with the existing shared constants (`day5`, unrealized `>= +5%`,
`RS vs SPY > 0`, `15%` original shares, `45%` position cap). It executed only
one second add-on across the three fixed windows, reduced `late_strong` PnL by
`$10.74`, and left `mid_weak` / `old_thin` unchanged.

Do not repeat: nearby second-add-on timing, size, cap, RS, or unrealized
threshold tuning. The next retry needs forward/paper confirmation or a new
independent event/news quality source that increases materiality without
broadening concentration risk.

### 2026-04-27 mechanism update: Same-day sleeve ordering

Status: rejected.

Core conclusion: exp-20260427-036 tested whether same-day allocation should simply rank `trend_long` candidates ahead of `breakout_long` candidates when entry slots are scarce. It failed. The native signal order plus the accepted one-slot breakout defer rule remains better than global trend-first sleeve sorting.

Evidence: versus the current default stack, trend-first ordering regressed EV in `late_strong` (`1.5855 -> 1.5109`) and `mid_weak` (`0.5709 -> 0.5369`), and was inert in `old_thin`. Aggregate EV delta was `-0.1086`; aggregate PnL delta was `-$1,549.13`.

Do not repeat: global same-day trend-first ordering, simple sleeve-priority sorting, or broad breakout de-prioritization as a meta-allocation shortcut.

Next valid retry requires: a new information source or discriminator that explains when `breakout_long` should lose priority without broadly damaging strong or rotation tapes.

### 2026-04-27 mechanism update: Commodity breakout wider target

Status: rejected.

Core conclusion: exp-20260427-037 tested whether the accepted Commodity trend winner-truncation repair could extend to `breakout_long | Commodities` by widening target ATR to 5.0/6.0/7.0. It cannot be promoted. The only non-regressing variant, 5.0 ATR, was too small and only helped `late_strong`; 6.0/7.0 improved `mid_weak` SLV but damaged `late_strong` IAU/GLD by delaying exits and increasing drawdown.

Evidence: 5.0 ATR aggregate EV delta was `+0.0244` and PnL `+$307.94`, below Gate 4 materiality. 6.0 ATR aggregate EV delta was `-0.0313`; 7.0 ATR aggregate EV delta was `-0.0065`; both increased max drawdown by `+1.04 pp`.

Do not repeat: Commodity breakout target-width widening by nearby 5-7 ATR values, or mechanical extension of the accepted Commodity trend target-width rule into Commodity breakouts.

Next valid retry requires: a new event/state discriminator that explains why the `mid_weak` SLV breakout should be allowed to run longer without delaying `late_strong` IAU/GLD exits. Keep Commodity breakout exits on the current production target path.

### 2026-04-28 mechanism update: Commodity trend target-exit re-entry

Status: rejected.

Core conclusion: exp-20260428-002 tested whether accepted `trend_long | Commodities` winners should be re-entered after target exits. The post-target continuation audit looked tempting, but a production-path replay showed the simple same-ticker re-entry rule is inert: 7 scheduled re-entry signals created 0 incremental trades.

Evidence: fixed-window EV/PnL/Sharpe deltas were exactly `0.0000` in `late_strong`, `mid_weak`, and `old_thin`. The rule did not pass through existing slot/sizing/execution constraints, so no Gate 4 criterion passed.

Do not repeat: simple target-exit re-entry based only on `trend_long | Commodities` target exits, or any post-target forward-return audit treated as production evidence.

Next valid retry requires: a different execution semantic, such as explicit target extension before exit or a reserved lifecycle budget, tested as one independent causal variable with the fixed three-window replay.

### 2026-04-28 mechanism update: Commodity trend target extension above 7 ATR

Status: rejected.

Core conclusion: exp-20260428-003 tested the explicit target-extension-before-exit semantic suggested after the inert re-entry replay. Extending `trend_long | Commodities` from the current accepted 7 ATR target to 8 ATR helped `late_strong` and `old_thin`, but it materially damaged the rotation-heavy `mid_weak` window. Wider 9/10 ATR targets damaged `late_strong` severely.

Evidence: best variant 8 ATR produced EV deltas `late_strong +0.1630`, `mid_weak -0.1035`, `old_thin +0.0089`; aggregate PnL delta was only `+$656.83`, while `mid_weak` Sharpe fell `-0.25` and PnL fell `-$2,070.56`. 9/10 ATR variants had aggregate EV deltas below `-0.76`.

Do not repeat: nearby Commodity trend target-width sweeps above 7 ATR, or post-target continuation audits treated as production evidence.

Next valid retry requires: a state or event discriminator that explains when Commodity trend continuation should be held without damaging `mid_weak`; otherwise keep the accepted 7 ATR production target.

### 2026-04-28 mechanism update: Follow-through add-on fraction

Status: accepted / production default.

Core conclusion: exp-20260428-005 tested whether the accepted day-2 follow-through add-on was under-allocating to confirmed winners. Raising only `ADDON_FRACTION_OF_ORIGINAL_SHARES` from `0.25` to `0.50` improved EV in all three fixed windows while leaving entries, exits, add-on trigger thresholds, max add-on position cap, scarce-slot routing, LLM/news replay, and earnings unchanged.

Evidence: versus the 25% baseline, the 50% add-on fraction produced EV deltas `late_strong +0.0640`, `mid_weak +0.0374`, and `old_thin +0.0149`. Aggregate PnL improved by `$3,634.17` / `+5.016%`; max drawdown increased by at most `+0.09 pp`.

Do not repeat: nearby add-on fraction sweeps without forward/paper concentration evidence. This result changes add-on size only; it does not reopen day-2 trigger threshold tuning.

Next valid retry requires: concentration monitoring or a new independent evidence source. Keep `ADDON_CHECKPOINT_DAYS=2`, `ADDON_MIN_UNREALIZED_PCT=0.02`, `ADDON_MIN_RS_VS_SPY=0.0`, and `ADDON_MAX_POSITION_PCT=0.35` unchanged unless new evidence appears.

### 2026-04-28 mechanism update: Follow-through add-on position cap

Status: rejected for production materiality.

Core conclusion: exp-20260428-006 tested whether the newly promoted 50% day-2 add-on was still materially clipped by `ADDON_MAX_POSITION_PCT=0.35`. Raising only the add-on cap to 0.40/0.45/0.50 improved EV in all three fixed windows, but the effect was too small for Gate 4 and saturated at 0.40.

Evidence: best variants all matched at `ADDON_MAX_POSITION_PCT=0.40+`, with EV deltas `late_strong +0.0103`, `mid_weak +0.0162`, and `old_thin +0.0041`. Aggregate PnL delta was only `+$697.26` / `+0.916%`, below the 5% PnL gate and below the EV materiality threshold. Drawdown did not increase.

Do not repeat: nearby add-on cap sweeps above 0.35 as a production-promotion attempt. The cap leak is real but too small in the fixed windows.

Next valid retry requires: forward/paper concentration evidence, or a new independent add-on allocation signal that increases materiality without reopening day-2 trigger threshold tuning.

### 2026-04-28 mechanism update: Adverse next-open entry cancel

Status: accepted / production default.

Core conclusion: exp-20260428-017 tested whether entries that open modestly below signal entry are lower-quality fills rather than bargains. A 2% adverse next-open cancel improved EV in all three fixed windows and passed Gate 4 on aggregate PnL, while 1% was too tight and 3% lost the mid_weak benefit.

Evidence: versus the no-adverse-cancel baseline, `ADVERSE_GAP_CANCEL_PCT=0.02` produced EV deltas `late_strong +0.0718`, `mid_weak +0.1014`, and `old_thin +0.0002`; aggregate PnL delta was `+$4,319.99` / `+5.678%`. The rule cancelled 7 adverse-gap entries across the three fixed windows.

Risk: `mid_weak` max drawdown increased by `+1.40 pp`, so forward monitoring should focus on whether the rule improves PnL by admitting replacement trades while increasing interim drawdown.

Do not repeat: tightening the adverse gap threshold to 1%, or treating 3% as equivalent to 2%. The tested 1% threshold regressed late_strong and mid_weak; 3% preserved late/old but lost the mid_weak materiality.

Next valid retry requires: a genuinely different state discriminator around adverse gaps, or forward evidence that the mid_weak drawdown tradeoff is undesirable. Do not combine this with add-on threshold tuning or LLM/news ranking until each branch has separate evidence.

### 2026-04-28 mechanism update: Upside next-open entry cancel

Status: rejected.

Core conclusion: exp-20260428-021 tested whether the existing `CANCEL_GAP_PCT=0.015` upside next-open cancel was mis-sized. It was not. Tightening to 1% helped `late_strong` only trivially and materially damaged `mid_weak` and `old_thin`; loosening to 2%/3%/5% or disabling the rule admitted lower-quality fills and regressed aggregate EV/PnL.

Evidence: the best nonbaseline variant by aggregate EV was 2%, but it still had aggregate EV delta `-0.1391` and PnL delta `-$4,423.90` versus the current 1.5% baseline. Tightening to 1% had aggregate EV delta `-0.3313` and PnL `-$11,894.16`; disabling the upside cancel had aggregate EV delta `-0.7824` and PnL `-$17,821.97`.

Do not repeat: nearby global `CANCEL_GAP_PCT` sweeps around 1-5%, including disabling the upside gap cancel.

Next valid retry requires: a state or event discriminator explaining when upside gaps are momentum confirmation instead of overextension. Do not combine this with adverse-gap or add-on threshold changes without separate evidence.

### 2026-04-28 mechanism update: Upside-gap sleeve exception

Status: rejected.

Core conclusion: exp-20260428-022 tested whether accepted winner-truncation sleeves could justify an exception to the existing 1.5% upside next-open cancel. They cannot. `trend_long | Technology` improved late_strong EV but reduced aggregate PnL and regressed old_thin; `trend_long | Commodities` damaged late_strong; combining both cohorts was worse.

Evidence: best variant `trend_technology_exception` had EV deltas `late_strong +0.3726`, `mid_weak +0.0000`, and `old_thin -0.0047`, but aggregate PnL delta was `-$1,960.99`. `trend_commodity_exception` had aggregate EV delta `-0.3162` and PnL `-$4,254.55`; combined Technology+Commodity had aggregate PnL `-$6,133.77`.

Do not repeat: Technology/Commodity trend upside-gap cancel exceptions based only on accepted target-width or winner-truncation evidence.

Next valid retry requires: an orthogonal event/state source explaining why a specific upside gap is confirmation, such as fresh positive news, earnings context, or forward/paper evidence. Sector/strategy membership alone is not enough.

### 2026-04-28 mechanism update: Adverse-gap context exceptions

Status: rejected.

Core conclusion: exp-20260428-023 tested whether the newly accepted 2% adverse next-open cancel should have narrow context exceptions. It should not, at least not from simple sector, strategy, full-risk, or TQS predicates. The active exception variants either regressed the strong window or regressed all three fixed windows; the only zero-delta variant was inert because it found no qualifying exceptions.

Evidence: `trend_commodities_exception` allowed 4 late_strong adverse-gap entries and reduced aggregate EV by `-0.2279`, PnL by `-$906.85`, and increased max drawdown by `+1.40 pp`. `full_risk_trend_exception` and `high_tqs_exception` each allowed 7 adverse-gap entries, regressed all three windows, and reduced aggregate PnL by `-$4,715.80`. `breakout_energy_exception` triggered 0 exceptions and is not evidence of edge.

Do not repeat: adverse-gap exceptions based only on sector, strategy, full-risk status, or TQS. Do not weaken `ADVERSE_GAP_CANCEL_PCT=0.02` with a simple context allowlist.

Next valid retry requires: an orthogonal signal that explains why a specific adverse open is recoverable, such as intraday reclaim behavior, fresh positive event context, or forward/paper evidence. Keep the accepted 2% adverse-gap cancel unchanged meanwhile.

### 2026-04-28 mechanism update: Signal-day weak close entry cancel

Status: rejected.

Core conclusion: exp-20260428-024 tested whether A/B signals that failed to
close in the upper part of their own signal-day range should be cancelled at
next open. They should not. Even the loosest tested threshold,
`close_location < 0.50`, regressed EV and PnL in all three fixed windows.

Evidence: versus the current baseline, the best variant had EV deltas
`late_strong -0.4877`, `mid_weak -0.1738`, and `old_thin -0.1367`.
Aggregate PnL fell by `$20,677.68` / `-25.7168%`, with 13 signal-day
close-location cancels across the three windows.

Do not repeat: simple signal-day close-location entry cancels or nearby
0.50-0.70 thresholds as price-only signal-quality filters.

Next valid retry requires: an orthogonal event, intraday reclaim, or
forward/paper signal explaining why a weak signal-day close is harmful in one
context but not another. Do not combine this with gap-cancel threshold changes
without separate evidence.

### 2026-04-28 mechanism update: Initial position cap allocation

Status: accepted / production default.

Core conclusion: exp-20260428-025 tested whether the accepted 50% day-2 add-on
made the old 25% initial position cap too conservative. Raising only
`MAX_POSITION_PCT` to 40% improved EV in all three fixed windows and passed
Gate 4 on aggregate PnL. Lower caps at 15% and 20% damaged all windows; 30% was
directionally positive but missed materiality.

Evidence: versus the 25% baseline, the 40% cap produced EV deltas
`late_strong +0.0626`, `mid_weak +0.0641`, and `old_thin +0.0067`.
Aggregate PnL improved by `$5,602.35` / `+6.9676%`; max drawdown increased by
at most `+0.47 pp`; trade count did not change.

Risk: this is a capital-allocation change, not a new entry edge. It increases
single-name concentration and should be monitored for tail-loss clustering in
forward/paper runs.

Do not repeat: nearby initial-cap sweeps above 40% or below 25% without new
forward concentration evidence. The next valid retry needs an independent
allocation signal rather than simply raising the cap again.

### 2026-04-28 mechanism update: Reduced-risk initial cap

Status: rejected / strict null.

Core conclusion: exp-20260428-026 tested whether non-zero reduced-risk signals
should use a lower initial concentration cap after `MAX_POSITION_PCT` moved to
40%. They should not be changed globally. The tested 20%/25%/30% caps never
bound any reduced-risk position in the fixed windows, so the mechanism is not a
current allocation leak.

Evidence: EV, PnL, Sharpe, drawdown, trade count, and win rate deltas were all
exactly `0.0000` in `late_strong`, `mid_weak`, and `old_thin`; aggregate cap
bind count was `0`.

Do not repeat: nearby reduced-risk initial-cap values or generic "lower cap for
all reduced-risk positions" ideas.

Next valid retry requires: new concentration evidence or a narrower quality
bucket that actually reaches the position cap.

### 2026-04-28 mechanism update: Same-day sector cap

Status: rejected.

Core conclusion: exp-20260428-027 tested whether the global same-day sector cap
should move from `2` to `1` or `3`. Keep it at `2`. Tightening to `1` removed
profitable clustered exposure in all three fixed windows; relaxing to `3` was a
strict null under current slot competition.

Evidence: `MAX_PER_SECTOR=1` EV deltas were `late_strong -0.3724`,
`mid_weak -0.0566`, and `old_thin -0.0545`, with aggregate PnL
`-$14,411.22`. `MAX_PER_SECTOR=3` had aggregate EV/PnL deltas `0.0000`.

Do not repeat: nearby global sector-cap values as a capital-allocation shortcut.

Next valid retry requires: a state- or sleeve-specific sector leadership signal,
not a global cap change.

### 2026-04-28 mechanism update: Portfolio heat budget

Status: rejected.

Core conclusion: exp-20260428-028 tested whether the accepted 40% initial cap
and 50% day-2 add-on made the global `MAX_PORTFOLIO_HEAT=0.08` too tight. It
did not. Raising heat to 10%/12% released two late-strong add-ons and slightly
improved old_thin, but left mid_weak unchanged and missed Gate 4 by a wide
margin; lowering heat to 6% damaged all active windows.

Evidence: best variant `MAX_PORTFOLIO_HEAT=0.10` had EV deltas
`late_strong +0.0244`, `mid_weak +0.0000`, and `old_thin +0.0003`.
Aggregate PnL improved only `$588.01` / `+0.6837%`, with no drawdown, win-rate,
or trade-count improvement. The 12% variant matched 10%, so the effect already
saturated.

Do not repeat: nearby global portfolio-heat sweeps around 6-12% as a simple
materiality unlock for add-ons.

Next valid retry requires: an independent allocation signal or forward/paper
concentration evidence explaining when extra heat should be spent. Do not
combine heat-budget changes with add-on trigger, add-on cap, or initial-cap
changes without separate evidence.

### 2026-04-28 mechanism update: Candidate quality ordering

Status: rejected.

Core conclusion: exp-20260428-029 tested whether same-day slot competition
should globally sort candidates by existing `trade_quality_score` or
`confidence_score` before entry planning. It should not. The native ordering
plus the current breakout-only 52-week-high rerank remains better than a broad
quality-score sort.

Evidence: the best tested nonbaseline variant, `confidence_desc_order`, was
unchanged in `late_strong` but regressed `mid_weak` and `old_thin`; aggregate
EV delta was `-0.1425`, and aggregate PnL fell `$6,212.28` / `-7.2229%`.
`tqs_desc_order` also regressed all three fixed windows, including
`late_strong`.

Do not repeat: simple global candidate ordering by TQS, confidence, or nearby
score-only rank keys as a same-day allocation shortcut.

Next valid retry requires: a state-specific or event-backed ordering
discriminator that explains when the native order should be overridden. Do not
combine ordering changes with cap, heat, gap-cancel, or add-on parameter
changes without separate evidence.

### 2026-04-28 mechanism update: Scarce-slot breakout exceptions

Status: rejected.

Core conclusion: exp-20260428-030 tested whether the accepted one-slot
scarce-slot breakout deferral should allow candidate-level exceptions for
apparently stronger breakouts. It should not, at least not from existing
`trade_quality_score` or 52-week-high proximity fields.

Evidence: the best tested variant, `near_high_breakout_exception`, was
unchanged in `late_strong` and `mid_weak` but regressed `old_thin` by
`EV -0.0448` and PnL `-$2,169.46`. The diagnostic no-deferral variant and
`high_tqs_breakout_exception` also failed Gate 4.

Do not repeat: scarce-slot breakout exceptions based only on TQS,
confidence-adjacent quality, or 52-week proximity.

Next valid retry requires: an orthogonal event/state source that explains why a
specific deferred breakout deserves the last slot. Keep the current one-slot
scarce-slot breakout deferral unchanged.

### 2026-04-28 mechanism update: Second follow-through add-on after cap promotion

Status: rejected.

Core conclusion: exp-20260428-031 retested the prior best day-5 second
follow-through add-on after the production stack changed to a 50% day-2 add-on
and 40% initial cap. The new capital base did not make the second add-on
material. It helped only `mid_weak`, regressed `late_strong`, and was inert in
`old_thin`.

Evidence: versus the current default stack, enabling the day-5 second add-on
with unrealized `>= +5%`, `RS vs SPY > 0`, 35% original shares, and 60% add-on
cap produced EV deltas `late_strong -0.0081`, `mid_weak +0.0418`, and
`old_thin +0.0000`. Aggregate PnL improved only `+$717.99` / `+0.8348%`,
below Gate 4 materiality, with 4 second add-ons executed.

Do not repeat: nearby second-add-on size/cap tuning after the 40% initial cap
promotion. The mechanism remains directionally interesting but too small for
production.

Next valid retry requires: forward/paper evidence or an orthogonal confirmation
source such as event context. Keep `SECOND_ADDON_ENABLED=false` meanwhile.

### 2026-04-28 mechanism update: State-gated breakout deferral

Status: rejected.

Core conclusion: exp-20260428-032 tested whether the accepted one-slot
scarce-slot breakout deferral should only fire when the weaker of SPY/QQQ is
not far above its moving average. It should not be promoted. Relaxing deferral
in stronger index states admitted lower-quality breakouts in the weaker
windows, and the best tested gate still reduced aggregate EV/PnL.

Evidence: the best variant, `DEFER_BREAKOUT_MAX_MIN_INDEX_PCT_FROM_MA=0.08`,
was unchanged in `late_strong` and `mid_weak`, but regressed `old_thin` by
`EV -0.0099` and PnL `-$226.65` aggregate, while increasing max drawdown by
`+1.58 pp`. Looser 0%/3%/5% gates damaged both `mid_weak` and `old_thin`.

Do not repeat: nearby global SPY/QQQ moving-average distance thresholds as the
state gate for scarce-slot breakout deferral.

Next valid retry requires: a more explanatory state source such as breadth,
dispersion, or event-backed breakout confirmation. Keep the current always-on
one-slot breakout deferral unchanged.

### 2026-04-28 mechanism update: Near-stop next-open entry cancel

Status: rejected.

Core conclusion: exp-20260428-033 tested whether entries that open below signal
entry but still above the planned stop should be cancelled when most of the
initial stop distance has already been consumed. This does not improve alpha.
Tight 15%/25% remaining-risk thresholds were inert in all three fixed windows;
looser 35%/50% thresholds only added one active cancel in `late_strong` and
materially damaged that window.

Evidence: best variants 15%/25% had aggregate EV and PnL deltas exactly
`0.0000`. Active variants 35%/50% reduced `late_strong` EV by `-0.2531` and
PnL by `-$4,154.41`, while `mid_weak` and `old_thin` were unchanged.

Do not repeat: nearby near-stop / remaining-risk next-open cancel thresholds as
a standalone entry execution filter.

Next valid retry requires: a new discriminator such as intraday reclaim
behavior, fresh event context, or forward/paper evidence. Keep the accepted
2% adverse-gap cancel unchanged.

### 2026-04-28 mechanism update: Profit-protective stop after early MFE

Status: rejected.

Core conclusion: exp-20260428-034 tested whether positions that first reached
`+3%` MFE should have their stop raised to breakeven, `+1%`, or `+2%`. This is
not a viable lifecycle alpha. It prevented some small losses, but it truncated
far more trend and breakout winners across every fixed window.

Evidence: the best variant, breakeven protection after `+3%` MFE, had EV deltas
`late_strong -1.1759`, `mid_weak -0.5094`, and `old_thin -0.1420`. Aggregate
PnL fell `-$49,004.06` / `-56.9764%`, with 0/3 windows improved and 53 changed
trades.

Do not repeat: simple breakeven / small-profit protective stops after early MFE,
or nearby `0-2%` stop locks after `+3%` MFE.

Next valid retry requires: an orthogonal adverse context such as failed
intraday reclaim, fresh negative event context, or forward evidence that
separates decaying losers from ordinary noisy winners. Do not add generic
profit protection to the accepted stack.

### 2026-04-28 mechanism update: ETF universe expansion

Status: rejected.

Core conclusion: exp-20260428-035 tested whether liquid sector/defensive ETF
proxies already present in the fixed snapshots should become tradeable universe
candidates. Broad ETF expansion and narrower sector/defensive variants did not
pass the fixed-window Gate 4 checks. The best variant, `XLE + USO`, released
large `late_strong` Energy continuation upside but displaced better A+B
opportunities in `mid_weak` and still regressed `old_thin`.

Evidence: `energy_only_etfs` produced EV deltas `late_strong +0.3609`,
`mid_weak -0.2328`, and `old_thin -0.0226`; aggregate PnL improved only
`+$334.72` / `+0.389%`, far below Gate 4 materiality, with 1/3 windows
improved. Broad sector/defensive expansion had positive aggregate EV only
because of `late_strong`, but aggregate PnL was `-$3,232.14`.

Do not repeat: broad sector/defensive ETF additions as a simple tradeable
universe expansion, or single-ETF additions such as XLE/XLP without a state
discriminator.

Next valid retry requires: a state or event discriminator explaining when
Energy/USO continuation deserves scarce slot competition, plus sector mapping
and production watchlist parity before any production promotion.

### 2026-04-29 mechanism update: Global position slot count

Status: rejected.

Core conclusion: exp-20260429-001 tested whether the accepted 40% initial cap
and 50% day-2 add-on changed the right global `MAX_POSITIONS` count. It did
not. The current `MAX_POSITIONS=5` remains the most robust fixed-window setting.
Cutting to 4 slots slightly improved `old_thin` but damaged the stronger
`late_strong` and `mid_weak` windows; raising to 6 or 7 admitted weaker
marginal trades and regressed all three windows.

Evidence: best nonbaseline variant `MAX_POSITIONS=4` had EV deltas
`late_strong -0.0748`, `mid_weak -0.1498`, and `old_thin +0.0069`, with
aggregate PnL delta `-$6,900.39` / `-8.023%`. `MAX_POSITIONS=6` and `7`
regressed all three fixed windows.

Do not repeat: nearby global slot-count sweeps as a capital-allocation shortcut.

Next valid retry requires: a state-specific or sleeve-specific allocation signal.
If slot count is revisited, the variable should be routing which sleeve gets the
scarce slot, not a global portfolio slot count.

### 2026-04-29 mechanism update: Sector-persistence entry source

Status: rejected.

Core conclusion: exp-20260429-002 tested whether sector-relative persistence
candidates should become a new executable entry source. The shadow signal did
not survive real slot, gap-cancel, sizing, add-on, and exit mechanics. It
injected many marginal trades and displaced stronger native A/B opportunities
in every fixed window.

Evidence: enabling `sector_persistence_long` produced EV deltas
`late_strong -1.4585`, `mid_weak -0.6688`, and `old_thin -0.1613`. Aggregate
PnL fell `-$53,807.02` / `-62.5608%`, with 0/3 windows improved and 97
sector-persistence trades added across the three windows.

Do not repeat: promoting sector-relative persistence from shadow forward-return
evidence directly into an entry source, or nearby 20d/60d sector-relative
threshold tuning without an orthogonal discriminator.

Next valid retry requires: a state/event discriminator that explains when a
sector-persistence candidate deserves scarce slot competition, or a different
candidate-pool source with production watchlist parity. Treat simple sector
momentum entries as noise until that evidence exists.

### 2026-04-29 mechanism update: State-gated extra slot

Status: rejected.

Core conclusion: exp-20260429-003 tested whether the rejected global sixth slot
could be rescued by allowing it only when both SPY and QQQ were strongly above
their 200-day moving averages. It should not be promoted. The strictest tested
gate helped the rotation-heavy `mid_weak` window, but still damaged
`late_strong` and `old_thin`; looser gates admitted weak marginal trades.

Evidence: best variant `min(SPY, QQQ) pct-from-200MA >= 10%` had EV deltas
`late_strong -0.0423`, `mid_weak +0.4616`, and `old_thin -0.0322`; aggregate
PnL fell `-$6,031.94` / `-7.0133%`, with only 1/3 windows improved.

Do not repeat: nearby SPY/QQQ pct-from-200MA thresholds as a sixth-slot state
gate, or simple index-distance gates as a capacity unlock.

Next valid retry requires: a genuinely different state source such as breadth,
dispersion, event context, or forward/paper evidence explaining which sleeve
deserves extra capacity. Keep `MAX_POSITIONS=5`.

### 2026-04-29 mechanism update: RS-gated Technology breakout target

Status: rejected.

Core conclusion: exp-20260429-004 tested whether the rejected broad Technology
breakout target-width idea could be rescued by widening targets only for
Technology breakouts with strong `rs_vs_spy`. It cannot be promoted. Candidate
RS gating improved `mid_weak` and aggregate PnL, but the same late-window EV
and Sharpe damage remained, so the variant failed the EV-first multi-window
gate.

Evidence: best variant `rs_vs_spy >= 5%` with a 6 ATR target had EV deltas
`late_strong -0.1994`, `mid_weak +0.0439`, and `old_thin +0.0000`. Aggregate
PnL improved `+$2,491.07` / `+2.8963%`, but aggregate EV fell `-0.1555` and
`late_strong` Sharpe daily fell `-0.57`.

Do not repeat: nearby Technology breakout target widths or simple
`rs_vs_spy` thresholds as the discriminator for wider Technology breakout
targets.

Next valid retry requires: an orthogonal event/state source, such as fresh
positive news, LLM event grading coverage, or forward evidence explaining why a
specific Technology breakout deserves a wider target without degrading the
dominant strong tape.

### 2026-04-29 mechanism update: Sector-sleeve priority ordering

Status: rejected.

Core conclusion: exp-20260429-005 tested whether stable Commodities/Financials
A+B candidates should be mechanically moved earlier in entry planning. They
should not. The best variant, `commodities_first`, left `late_strong` and
`old_thin` unchanged but damaged `mid_weak`; adding Financials priority
further damaged `old_thin`.

Evidence: best variant `commodities_first` had EV deltas
`late_strong +0.0000`, `mid_weak -0.0566`, and `old_thin +0.0000`.
Aggregate PnL fell `-$1,190.49` / `-1.3842%`, trade count rose by 1, and win
rate fell by 2.38 pp in the active window. Financials-priority variants
regressed `old_thin` more sharply.

Do not repeat: simple Commodities/Financials priority ordering as a
meta-allocation shortcut, or nearby sector-priority permutations without a new
state/event discriminator.

Next valid retry requires: breadth, dispersion, event context, or forward
evidence explaining when a sector sleeve deserves earlier slot access. This is
distinct from the already-rejected global sector cap and sector-persistence
entry source, but it reaches the same conclusion: sector labels alone are not a
strong enough allocation signal.

### 2026-04-29 mechanism update: Index-dispersion extra slot

Status: rejected.

Core conclusion: exp-20260429-006 tested whether the rejected sixth slot could
be rescued by using QQQ-vs-SPY 200MA-distance spread as a rotational-tape
discriminator. It should not be promoted. Variants that actually released extra
capacity damaged at least one fixed window; the apparent best EV/Sharpe variant
released zero extra slots and changed no trades or PnL, so it was rejected as a
harness artifact rather than alpha.

Evidence: `qqq_leads_spy_by_2pct` released 20 extra-slot days but regressed
`mid_weak` PnL by `-$3,613.11` and had 2/3 EV windows improved with 1/3
regressed. `balanced_index_spread_lte_2pct` released 23 extra-slot days but
reduced aggregate PnL by `-$1,989.77` and also regressed one window. The
zero-behavior `qqq_leads_spy_by_4pct` showed aggregate EV delta `+1.5402` only
because no trades changed; that is not valid promotion evidence.

Do not repeat: nearby SPY/QQQ leadership-spread thresholds as a sixth-slot
capacity unlock, or any extra-slot experiment that accepts Sharpe/EV movement
without changed trades, PnL, or slot-release counts.

Next valid retry requires: richer breadth/dispersion, event context, or
forward/paper evidence explaining which sleeve deserves extra capacity. A clean
extra-slot harness should also avoid the backtester top-level max-position skip
artifact before using Sharpe as acceptance evidence.

### 2026-04-29 mechanism update: ATR trailing full-exit lifecycle

Status: rejected.

Core conclusion: exp-20260429-009 tested whether current fixed target/stop
exits should be replaced by ATR trailing full exits after a profit trigger.
They should not. All six tested trigger/offset cells reduced EV and PnL in all
three fixed windows.

Evidence: the best variant, `TRAIL_TRIGGER_ATR_MULT=3.0` with
`TRAIL_OFFSET_ATR_MULT=2.0`, had EV deltas `late_strong -0.5018`,
`mid_weak -0.4186`, and `old_thin -0.1673`; aggregate PnL fell
`-$30,150.41`. The worst tested variant fell `-$68,250.09` aggregate PnL.

Do not repeat: broad ATR trailing-stop full exits or nearby trigger/offset
cells as a lifecycle alpha. Also do not use trailing-stop backtest
profitability to justify repeated production partial-reduce advice.

Next valid retry requires: an orthogonal discriminator such as event/news
context, forward evidence, or a state variable that separates decaying winners
from ordinary noisy trends. Any accepted future exit rule must be implemented
as a shared production/backtest policy before promotion.

### 2026-04-29 mechanism update: Trend Commodities near-high risk boost

Status: accepted.

Core conclusion: exp-20260429-013 tested whether the repeat winning sleeve in
`trend_long` Commodities should receive more risk only when the setup is already
within 3% of its 52-week high. This narrow allocation boost passed the fixed
snapshot windows without adding entries, filters, exits, or universe noise.

Evidence: `TREND_COMMODITIES_NEAR_HIGH_RISK_MULTIPLIER=1.5` with
`pct_from_52w_high >= -0.03` moved EV by `late_strong +0.2315`,
`mid_weak +0.0266`, and `old_thin +0.0000`; aggregate PnL improved
`+$7,307.02`. Trade count, win rate, and survival rate were unchanged in all
three windows, so the result came from sizing the same accepted trades.

Do not repeat: broad Commodities risk boosts, deeper pullback thresholds, or
2.0x+ multipliers as simple variants. Wider tests improved aggregate PnL but
increased old_thin exposure to the weaker SLV shape, so the accepted mechanism
is specifically "near-high commodity trend continuation," not "all commodities
deserve more risk."

Next valid retry requires: forward evidence, an event/news discriminator, or a
separate risk-budget metric proving that a wider Commodities sleeve improves
without old_thin regression. Keep any future allocation rule in shared
`portfolio_engine` sizing, not in backtester-only code.

### 2026-04-29 mechanism update: Low-TQS Commodity breakout risk boost

Status: rejected.

Core conclusion: exp-20260429-014 tested whether the already-exempt
`breakout_long + Commodities + low-TQS` pocket should receive 1.5x risk. It
should not be promoted. The effect was directionally positive only in
`late_strong`, inert in `mid_weak` and `old_thin`, and too small to justify a
new sizing branch.

Evidence: the candidate moved EV by `late_strong +0.0398`, `mid_weak +0.0000`,
and `old_thin +0.0000`. Aggregate PnL improved only `+$931.56` / `+0.998%`,
below Gate 4 materiality, while max drawdown rose `+0.46 pp` in the only active
window.

Do not repeat: low-TQS Commodity breakout risk boosts, broad Commodity breakout
boosts, or low-TQS risk boosts without an independent state/event
discriminator.

Next valid retry requires: forward evidence, news/event confirmation, or a
state variable explaining when commodity breakouts deserve more risk. Keep the
current low-TQS Commodities exemption but do not add extra risk.

### 2026-04-29 mechanism update: Trend Financials risk boost

Status: accepted.

Core conclusion: exp-20260429-015 tested whether existing `trend_long +
Financials` candidates deserve a 1.5x risk budget. This passed because it
changed only sizing for already-selected trades, improved the two windows where
the sleeve was active, and left the dominant `late_strong` window unchanged.

Evidence: `TREND_FINANCIALS_RISK_MULTIPLIER=1.5` moved EV by `late_strong
+0.0000`, `mid_weak +0.1143`, and `old_thin +0.0135`; aggregate PnL improved
`+$5,735.09` / `+6.15%`. Trade count, win rate, and survival rate were
unchanged in all three fixed windows.

Do not repeat: Financials sector priority ordering, new Financials entry
sources, or broader Financials risk boosts as simple variants. This accepted
mechanism is specifically "already-selected Financials trend candidates deserve
more risk," not "Financials should get earlier slots."

Next valid retry requires: forward evidence, a stricter state/event
discriminator, or a risk-budget metric proving that a multiplier above 1.5x
does not add tail risk. Keep any future allocation rule in shared
`portfolio_engine` sizing.

### 2026-04-29 mechanism update: Financials near-high risk lift

Status: rejected.

Core conclusion: exp-20260429-016 tested whether the accepted `trend_long +
Financials` 1.5x sizing rule should be lifted to 2.0x when the setup is within
3% of its 52-week high. It should not be promoted. The extra near-high lift was
too small and only improved `old_thin`; it did not move `late_strong` or
`mid_weak`.

Evidence: versus the current accepted stack, the near-high 2.0x variant moved
EV by `late_strong +0.0000`, `mid_weak +0.0000`, and `old_thin +0.0147`.
Aggregate PnL improved only `+$892.55` / `+0.90%`, below Gate 4 materiality.
A stricter pretest that replaced broad Financials 1.5x with only near-high
2.0x regressed `mid_weak` from EV `0.9147` to `0.8004`.

Do not repeat: nearby Financials near-high multiplier thresholds, 2.0x
Financials trend sizing, or simple near-high narrowing of the accepted broad
Financials trend sleeve.

Next valid retry requires: forward evidence, an orthogonal event/state
discriminator, or a risk-budget metric proving material improvement without
damaging `mid_weak`.

### 2026-04-29 mechanism update: Commodity breakout risk boost

Status: rejected for production materiality.

Core conclusion: exp-20260429-017 tested whether already-selected
`breakout_long | Commodities` signals deserve a 1.5x risk budget after the
current three-window audit showed positive late/mid trades and no old-thin
exposure. The direction was positive, but not material enough to justify
another production sizing rule.

Evidence: versus the current accepted stack, the 1.5x boost improved
`late_strong` EV by `+0.0398` and `mid_weak` EV by `+0.0550`, with `old_thin`
unchanged. Aggregate EV delta was only `+0.0948`, just below the `+0.10` Gate
4 threshold, and aggregate PnL improved only `+$2,217.84` / `+2.239%`, below
the `+5%` PnL gate.

Do not repeat: broad Commodity breakout risk-budget boosts at nearby 1.5x
values, or another simple extension of Commodity trend convexity evidence into
Commodity breakouts.

Next valid retry requires: a new state/event discriminator that increases
materiality without reopening rejected Commodity breakout target-width changes
or low-TQS-only boosts.

### 2026-04-29 mechanism update: Shared entry-gate parity

Status: accepted governance.

Core conclusion: exp-20260429-007 moved already-held filtering, same-day sector
caps, and the `BEAR_SHALLOW` post-enrich entry gate into
`production_parity.filter_entry_signal_candidates`. This is not new alpha, but
it closes a real measurement drift vector. Future alpha conclusions should not
depend on duplicated run/backtester gate code.

Evidence: fixed-window metrics were unchanged after the refactor, while both
`quant/run.py` and `quant/backtester.py` now call the same helper and
production persists `entry_filter_audit` for inspection.

Do not repeat: run-only or backtester-only implementations of already-held,
same-day sector, or `BEAR_SHALLOW` entry gating logic.

Next valid retry requires: a new alpha hypothesis that actually changes gate
behavior, or a documented parity gap not already covered by the shared helper.

### 2026-04-29 mechanism update: Shared regime risk sizing parity

Status: accepted governance.

Core conclusion: exp-20260429-008 moved the `NEUTRAL` and `BEAR_SHALLOW`
`risk_pct` overrides into `production_parity.risk_pct_for_market_state`. This
is also not new alpha, but it removes another silent drift path between
production and replay.

Evidence: `BULL`/default, `NEUTRAL 0.75%`, `BEAR_SHALLOW 0.50%`, and
`BEAR_DEEP`/default sizing behavior is now covered by a shared helper and a
focused parity test, with no intended metric movement.

Do not repeat: duplicate adapter arithmetic for regime risk overrides, or
backtester-only sizing interpretations of market state.

Next valid retry requires: a real allocation hypothesis about when risk should
change, not another refactor of already-shared arithmetic.

### 2026-04-29 mechanism update: Trailing partial-reduce replay

Status: measurable but rejected alpha.

Core conclusion: exp-20260429-012 finished the missing parity work for
production trailing partial-reduce advice and added opt-in
`--replay-partial-reduces` support to BacktestEngine. That closes the audit
gap. Once replayed, the mechanism was negative on the fixed windows, so it
should stay off by default and should not be justified by intuition alone.

Evidence: replay-on executed 15 partial reductions and produced aggregate
`expected_value_score` delta `-0.3136` with aggregate PnL delta `-$9,441.76`
versus the current accepted baseline.

Do not repeat: promoting production partial-reduce advice without replay
evidence, or using full trailing-stop exit intuition as a reason to keep
partial reductions alive.

Next valid retry requires: an orthogonal event/state discriminator that can
separate decaying winners from normal trend noise, plus shared production and
backtest policy from the start.

### 2026-04-29 mechanism update: Risk-on unmodified sizing lift

Status: accepted.

Core conclusion: exp-20260429-018 tested whether already-selected `risk_on`
signals with no other active sizing modifier deserve a small risk-budget lift.
They do. The accepted rule is deliberately non-stacking: it does not apply to
existing 1.5x Commodities/Financials boosts or to 0.25x/0x haircut sleeves.

Evidence: `RISK_ON_UNMODIFIED_RISK_MULTIPLIER=1.25` moved EV by
`late_strong +0.1980`, `mid_weak +0.0525`, and `old_thin +0.0144`.
Aggregate PnL improved `+$8,404.99` / `+8.49%`. Trade count, win rate, and
survival rate were unchanged in all three fixed windows; max drawdown rose by
up to `+0.81 pp`, still below the Gate 4 drawdown materiality guardrail.

Do not repeat: simple risk-on leverage above 1.25x, stacking this lift onto
already-boosted sleeves, or using this result to relax low-TQS/sector haircut
rules. This is a plain-inventory risk-budget rule, not a new entry source.

Next valid retry requires: forward evidence, a tail-risk metric showing the
extra drawdown is still compensated, or an orthogonal discriminator that
separates the strongest unmodified risk-on candidates from the rest. Keep any
future change in shared `portfolio_engine` sizing.

### 2026-04-29 mechanism update: Breakout Energy risk boost

Status: rejected.

Core conclusion: exp-20260429-019 tested whether already-selected
`breakout_long + Energy` signals deserved 1.5x risk. The sleeve had visible
late-window continuation, but the effect was too concentrated and too small to
justify another production sizing branch.

Evidence: versus the current accepted stack, the candidate moved EV by
`late_strong +0.0827`, `mid_weak +0.0000`, and `old_thin +0.0000`. Aggregate
PnL improved only `+$2,216.67` / `+2.06%`, below Gate 4 materiality, and
Sharpe did not improve.

Do not repeat: simple `breakout_long + Energy` risk boosts at nearby
multipliers, or using the rejected Energy ETF expansion result as indirect
evidence for native Energy breakout sizing.

Next valid retry requires: a state/event discriminator that proves Energy
breakouts deserve scarce risk budget outside `late_strong`, without adding
universe noise or changing slot priority.

### 2026-04-29 mechanism update: Technology breakout risk boost

Status: rejected alpha.

Core conclusion: exp-20260429-020 tested whether already-selected
`breakout_long + Technology` signals deserved a dedicated 1.5x risk budget
instead of the generic risk-on 1.25x lift. The idea looked plausible from the
trade audit because late_strong and mid_weak Technology breakouts were positive,
but the fixed-window replay showed the extra risk was not worth carrying.
late_strong PnL rose by `$866.07`, but daily Sharpe fell from `4.22` to `4.11`
and EV fell from `2.2134` to `2.1915`. mid_weak added only `$191.59` and
`+0.0048` EV. old_thin lost `$326.18` and EV fell from `0.2113` to `0.2040`.
Aggregate EV declined by `-0.0244`; aggregate PnL improved only `+0.68%`.

Mechanism insight: Technology breakout winners are not a clean sizing sleeve
after the accepted stack. The pocket adds some upside in stronger windows, but
it is Sharpe-dilutive and still exposes the system to old_thin false breakouts.
This also reinforces the earlier Technology breakout target-width rejection:
simple Technology breakout promotion is not enough without a stronger
discriminator.

Do not repeat: nearby `breakout_long + Technology` risk multipliers, or simple
promotion of Technology breakouts based only on sector/strategy membership.
Also do not reuse plain `rs_vs_spy` as the discriminator; that family was
already rejected in the Technology breakout target experiment.

Next valid retry requires: an orthogonal event/state discriminator that
separates MU/AAPL-like winners from DDOG-like old_thin losses without changing
target width, candidate ranking, or global risk-on leverage.

### 2026-04-29 mechanism update: Risk-on score-threshold narrowing

Status: rejected.

Core conclusion: exp-20260429-021 tested whether the accepted non-stacking
`risk_on_unmodified` 1.25x sizing lift should require
`regime_exit_score >= 0.08`. It should not be promoted. The simple score
threshold removed useful low-score risk-on winner exposure and did not improve
trade count, win rate, survival, or drawdown.

Evidence: versus the current accepted stack, the threshold moved EV by
`late_strong -0.0333`, `mid_weak +0.0000`, and `old_thin -0.0197`.
Aggregate PnL fell `-$1,616.20` / `-1.50%`, with 0/3 windows improved and
2/3 windows regressed.

Do not repeat: nearby `regime_exit_score` thresholds as eligibility gates for
the broad `risk_on_unmodified` lift. This is distinct from raising the lift
above 1.25x, which was already discouraged; simple narrowing also damages
winner capture.

Next valid retry requires: a richer state, event, or tail-risk discriminator
that explains why a subset of plain risk-on inventory should lose the accepted
1.25x lift without cutting late_strong and old_thin winners.

### 2026-04-29 mechanism update: Technology trend unmodified risk lift

Status: rejected.

Core conclusion: exp-20260429-022 tested whether otherwise unmodified
`trend_long + Technology` signals deserved a dedicated 1.5x risk budget instead
of the accepted generic `risk_on_unmodified` 1.25x lift. The pocket was
directionally positive but too sparse and too small to justify a new production
sizing branch.

Evidence: versus the current accepted stack, the candidate moved EV by
`late_strong +0.0674`, `mid_weak +0.0000`, and `old_thin +0.0145`.
Aggregate PnL improved `+$1,952.83` / `+1.82%`, below Gate 4 materiality, and
no Sharpe improvement reached `+0.1`.

Do not repeat: nearby `trend_long + Technology` unmodified risk multipliers
without a broader sample or orthogonal discriminator. This is distinct from the
rejected Technology breakout branch, but it reaches the same practical lesson:
simple Technology sleeve promotion is not yet strong enough after the accepted
stack.

Next valid retry requires: evidence that the Technology trend pocket affects
more than isolated winners across the fixed windows, or a state/event
discriminator that increases sample quality without changing entry, ranking,
target width, or global risk-on leverage.

### 2026-04-29 mechanism update: Risk-on add-on fraction

Status: rejected as inert.

Core conclusion: exp-20260429-023 tested whether confirmed day-2 follow-through
positions that originally received the accepted `risk_on_unmodified` 1.25x
sizing lift should receive a larger first add-on fraction. The answer is no
under the current cap stack: raising the sleeve-specific fraction from 50% to
75% changed no executed shares and moved no metrics.

Evidence: fixed-window EV deltas were `late_strong +0.0000`, `mid_weak
+0.0000`, and `old_thin +0.0000`; PnL, drawdown, trade count, win rate,
survival rate, and add-on counts were unchanged in all three windows.

Do not repeat: risk-on add-on fraction increases while `ADDON_MAX_POSITION_PCT`
remains the binding constraint, or sizing-multiplier-specific production add-on
rules without persisted position metadata.

Next valid retry requires: concentration evidence for changing the add-on cap
itself, plus production position metadata that can execute sleeve-specific
add-on rules without drift.

### 2026-04-29 mechanism update: Financials multiplier above 1.5x

Status: rejected on risk-budget quality.

Core conclusion: exp-20260429-024 retested the accepted `trend_long +
Financials` sleeve by sweeping the risk multiplier above 1.5x. The only
material variant, 2.0x, cleared aggregate EV but bought that improvement with
too much mid-window drawdown expansion and a small Sharpe decline.

Evidence: `TREND_FINANCIALS_RISK_MULTIPLIER=2.0` moved EV by `late_strong
+0.0000`, `mid_weak +0.1041`, and `old_thin +0.0146`, but increased
`mid_weak` max drawdown by `+1.36 pp` and reduced `mid_weak` daily Sharpe by
`-0.01`. The 1.75x and 1.9x variants did not clear EV materiality.

Do not repeat: simple Financials trend multipliers above 1.5x, including
nearby 1.75-2.0 sweeps, without a new discriminator that controls the V-like
stop-out risk.

Next valid retry requires: forward evidence or an event/state discriminator
that separates COIN/GS/JPM winners from V stop-outs, plus a tail-risk metric
showing the higher budget does not expand drawdown.

### 2026-04-29 mechanism update: SIGNAL_TARGET partial-reduce replay

Status: rejected.

Core conclusion: exp-20260429-032 tested a replay-only parity hypothesis:
reinterpret the legacy ATR risk target as production-style `SIGNAL_TARGET`
partial trims (next-open sell 33%) instead of same-level full exits. It should
not be promoted. Across all three fixed windows the rule sharply reduced EV,
PnL, and trade completion because the remaining sleeves were left to stop /
end-of-backtest behavior without a compensating later lifecycle rule.

Evidence: the replay executed 15 `SIGNAL_TARGET` partial reductions and
produced aggregate `expected_value_score` delta `-3.0212` with aggregate PnL
delta `-$56,526.39`. Window EV deltas were `late_strong -2.0079`,
`mid_weak -0.8199`, and `old_thin -0.1934`; max drawdown worsened by up to
`+6.85 pp`.

Do not repeat: simple `SIGNAL_TARGET -> partial reduce -> let the rest ride`
replays, or nearby variants that only remove the old full-target exit without
adding a complete downstream lifecycle policy.

Next valid retry requires: a full shared lifecycle design that defines what
happens after the first trim, plus evidence that the broader lifecycle is
beneficial as a single causal variable rather than an isolated trim.

### 2026-04-29 mechanism update: Low-score plain risk-on sizing

Status: accepted as shared production/backtest sizing policy.

Core conclusion: exp-20260429-025 reversed the framing from the rejected
score-threshold experiment. Low `regime_exit_score` inside the already accepted
`risk_on` bucket was not a weakness signal; the affected plain, otherwise
unmodified sleeve contained profitable winners. The accepted rule keeps the
generic `risk_on_unmodified` 1.25x lift, but gives low-score plain risk-on
signals a non-stacking 1.5x budget when `regime_exit_score < 0.10`.

Evidence: fixed-window EV moved `late_strong +0.1183`, `mid_weak +0.0000`,
and `old_thin +0.0172`, for aggregate EV `+0.1355`. Aggregate PnL improved
`+$3,248.54`; trade count, win rate, and survival rate were unchanged in all
three windows. Max drawdown was unchanged in `late_strong` and `mid_weak`, and
rose only `+0.04 pp` in `old_thin`.

Do not repeat: nearby low-score multiplier tweaks, score eligibility gates, or
stacking this lift on top of sector-specific boosts / haircuts without new
forward or tail-risk evidence.

Next valid retry requires: a richer adverse-risk discriminator showing which
low-score risk-on trades are actually tail-risk warnings, or enough forward
sample to justify changing the 1.5x budget.

### 2026-04-29 mechanism update: Mid-score plain risk-on sizing

Status: accepted as shared production/backtest sizing policy, but risk-close.

Core conclusion: exp-20260429-031 extended the accepted plain `risk_on`
allocation family. Otherwise unmodified `risk_on` signals with
`0.10 <= regime_exit_score < 0.20` carried enough positive residual expectancy
to justify a non-stacking 1.6x risk budget instead of the generic 1.25x lift.
This is a capital-allocation rule, not a new entry source.

Evidence: versus the accepted stack after exp-20260429-025, the 1.6x mid-score
rule moved EV by `late_strong +0.1470`, `mid_weak +0.0362`, and `old_thin
-0.0018`. Aggregate PnL improved `+$6,531.45` / `+5.90%`; trade count, win
rate, and survival were unchanged. The risk warning is real: `old_thin` max
drawdown rose by `+0.96 pp`, just below the 1 pp guardrail.

Do not repeat: nearby mid-score risk-on multiplier tuning, broad risk-on
leverage increases, or stacking this lift on top of sector-specific boosts or
haircuts without new forward or tail-risk evidence.

Next valid retry requires: forward evidence, a tail-risk metric showing the
extra `old_thin` drawdown is compensated, or an orthogonal discriminator that
separates the strongest mid-score plain risk-on candidates from the rest.

### 2026-04-29 mechanism update: Post-low-score meta-allocation audit

Status: observed-only.

Core conclusion: exp-20260429-026 audited the accepted stack after the
low-score plain risk-on lift and did not find a production-worthy residual
allocation rule. The strongest cohorts are already accepted
(`trend_commodities_near_high`, `trend_financials`, and low-score plain
`risk_on_unmodified`). The remaining weak pockets are too small and too
localized to justify a new rule without overfitting.

Evidence: fixed-window baseline after exp-20260429-025 was `late_strong EV
2.3317`, `mid_weak EV 0.9672`, and `old_thin EV 0.2285`. The cohort audit found
`trend_commodities_near_high_risk_multiplier_applied` at 7/7 wins and
`+$32,004.78`, `trend_financials_risk_multiplier_applied` at 7 trades and
`+$18,374.95`, and low-score plain risk-on at 7 trades and `+$22,172.67`.
Negative pockets such as `breakout_financials_dte` had only 1-2 affected
trades and sub-$600 observed drag.

Do not repeat: adding zero-risk rules for `breakout_financials_dte`,
`breakout_healthcare_dte`, or Communication Services breakout gap/near-high
overlaps based only on this tiny-sample audit.

Next valid retry requires: forward evidence, event/news confirmation, or a
richer state discriminator that makes one of those pockets material across the
fixed windows. Otherwise the better alpha-search path is a broader
meta-allocation state map rather than another local sizing branch.

### 2026-04-29 mechanism update: Add-on cap to 40%

Status: rejected for production materiality.

Core conclusion: exp-20260429-027 tested whether the accepted strict day-2
follow-through add-on should lift `ADDON_MAX_POSITION_PCT` from 35% to the
existing 40% single-position cap. The direction was positive in all three
fixed windows, but not material enough to promote.

Evidence: versus the current accepted stack, the 40% cap moved EV by
`late_strong +0.0522`, `mid_weak +0.0172`, and `old_thin +0.0051`. Aggregate
PnL improved `+$1,766.97`, with one extra executed add-on in each window and
no drawdown change. This stayed below the +0.10 EV materiality bar and below
the 5% PnL gate.

Do not repeat: nearby global `ADDON_MAX_POSITION_PCT` values around 40%, or
using directionally positive but small add-on cap gains as production evidence.

Next valid retry requires: forward evidence, a concentration/event
discriminator, or tail-risk proof that a higher add-on cap materially improves
winner capture without adding weaker-tape damage.

### 2026-04-29 mechanism update: Second follow-through add-on

Status: rejected as inert.

Core conclusion: exp-20260429-028 tested enabling the existing second add-on
path with day-5, +5% unrealized, RS>0, 15% original shares, and 45% cap. It
should not be promoted. The rule added actions but did not release meaningful
alpha under the current cap/heat stack.

Evidence: EV moved only `late_strong +0.0005`, with `mid_weak` and `old_thin`
unchanged. Aggregate PnL improved only `+$11.37`.

Do not repeat: turning on `SECOND_ADDON_ENABLED` with the existing parameters,
or nearby second-add-on tweaks without a new event/state discriminator and a
complete lifecycle design.

### 2026-04-29 mechanism update: Risk-on unmodified breakout lift

Status: rejected for production materiality.

Core conclusion: exp-20260429-029 tested whether already-selected
`risk_on + breakout_long` signals with no other sizing modifier should receive
the same non-stacking 1.5x risk budget as the accepted low-score plain
`risk_on` sleeve. The direction was positive in the two newer windows but did
not clear materiality and slightly damaged the older tape.

Evidence: versus the accepted stack, the 1.5x breakout subset moved EV by
`late_strong +0.0364`, `mid_weak +0.0291`, and `old_thin -0.0070`.
Aggregate EV improved only `+0.0585`, and aggregate PnL improved only
`+$2,874.52` / `+2.60%`, below Gate 4. `late_strong` daily Sharpe also fell
from `4.28` to `4.17`.

Do not repeat: simple `risk_on_unmodified + breakout_long` 1.5x promotion,
nearby breakout-only unmodified risk multipliers, or using late/mid breakout
attribution alone to justify another production sizing branch.

Next valid retry requires: a richer event/state discriminator that removes
old_thin breakout damage, forward evidence under current cap/heat constraints,
or a tail-risk metric proving the Sharpe dilution is compensated.

### 2026-04-29 mechanism update: Sector-state allocation map

Status: observed only; no production rule promoted.

Core conclusion: exp-20260429-030 audited entry-day sector breadth,
sector 20-day return, sector dispersion, and ticker-vs-sector relative
strength across the fixed three windows. This was an alpha search, not a bug
repair: LLM soft-ranking data was still too thin for a production-aligned
ranking experiment, so the run tested deterministic OHLCV state features
instead.

Evidence: fixed-window metrics stayed unchanged at the accepted baseline:
`late_strong EV 2.3317`, `mid_weak EV 0.9672`, and `old_thin EV 0.2285`.
Across 62 executed trades, `sector_breadth_200 >= 75%` covered 54 trades,
57.4% win rate, and `+$103,141.12`; the lower-breadth buckets were only
7 known trades total and also net positive, so breadth alone is not a useful
filter. Strong sector 20-day return was also broad rather than selective:
`ret20 >= 5%` covered 44 trades, 59.1% win rate, and `+$85,790.18`.

Mechanism insight: the strongest stable state bucket was
`Commodities + breadth_gte_75 + ret20_gte_5` at 9/9 wins and `+$35,243.09`,
but this mostly confirms the already accepted commodity trend allocation
family. The more actionable warning is the opposite: `trend_long +
Technology + breadth_gte_75` had 15 trades, only 33.3% win rate, and much
lower average PnL than Commodities/Financials even in strong sector states.

Do not repeat: simple sector breadth gates, simple sector 20-day return gates,
or using "high breadth" as justification to add broad exposure. These states
mostly describe where the current system already trades.

Next valid retry requires: a production-shared Technology trend discriminator
or lifecycle rule that explains why high-breadth Technology trend entries have
low win rate without killing the existing positive PnL tail. A valid promoted
rule must run through `portfolio_engine`/shared policy or be explicitly listed
as replay-only parity.
### 2026-04-30 mechanism update: Technology trend marginal risk-on de-risking

Status: rejected.

Core conclusion: exp-20260430-002 tested whether `trend_long + Technology`
signals with `0.10 <= regime_exit_score < 0.13` should be cut to 25% risk.
The rule was production-shared during the test, then rolled back. It is not a
valid alpha improvement.

Evidence: versus the accepted stack, the candidate left `late_strong`
unchanged, improved `old_thin` only slightly (`EV +0.0058`, PnL `+$311.48`),
but damaged `mid_weak` (`EV -0.0117`, PnL `-$452.84`). Aggregate EV moved
`-0.0059` and aggregate PnL moved `-$141.36`.

Mechanism insight: simple `regime_exit_score` bands do not separate Technology
trend noise from delayed winners. The tested band included weak TSM/AMD/SNOW
shapes but also useful APP/AAPL-like convex winners, so score-only de-risking
misallocates capital.

Do not repeat: nearby Technology trend marginal-score haircuts or using
`regime_exit_score` alone as the missing Technology trend discriminator.

Next valid retry requires: an orthogonal event/state or lifecycle signal that
can distinguish delayed Technology winners from normal weak trend noise, with
shared production/backtest policy from the start.

### 2026-04-30 mechanism update: Scarce-slot deferral state caps

Status: rejected.

Core conclusion: exp-20260430-003 tested whether the accepted one-slot
`breakout_long` deferral should be restricted by a simple market-extension cap
after the newer sizing stack. It should not. The current unconditional one-slot
form remains the better shared policy.

Evidence: disabling the hook, or requiring `min(SPY, QQQ)` pct-from-200MA to be
`<= 0.0` or `<= 0.05`, left `late_strong` unchanged but damaged the two windows
where the hook matters. `mid_weak` EV fell `1.0034 -> 0.8404` and PnL fell
`$39,346.43 -> $37,523.67`; `old_thin` EV fell `0.2267 -> 0.2028` and PnL fell
`$18,584.08 -> $17,334.50`.

Mechanism insight: the one-slot deferral edge is not explained by a simple
index-extension state. A cap on `min(SPY, QQQ)` distance makes the rule inert in
the windows where preserving slots for later trend candidates has value.

Do not repeat: disabling one-slot breakout deferral, or adding simple
`min(SPY, QQQ)` pct-from-200MA caps to it, without new evidence.

Next valid retry requires: a different production-shared discriminator, such
as candidate forward-quality context or persisted sector-state fields, that
preserves `mid_weak` and `old_thin` benefits without damaging `late_strong`.

### 2026-04-30 mechanism update: Low-score Technology trend haircut release

Status: rejected.

Core conclusion: exp-20260430-004 tested the opposite of the prior Technology
trend score-band haircut: maybe low `regime_exit_score` Technology trend
signals were being over-de-risked by the accepted Technology gap / near-high /
DTE haircuts. The temporary shared `portfolio_engine` patch released those
Technology-specific haircuts when `regime_exit_score < 0.10`, then was rolled
back. This should not be promoted.

Evidence: versus the accepted stack, `late_strong` was unchanged, `mid_weak`
regressed materially (`EV 1.0034 -> 0.8360`, PnL `-$1,346.54`, Sharpe `2.55 ->
2.20`, max drawdown `+0.85 pp`), and `old_thin` PnL rose by `$626.93` while EV
fell (`0.2267 -> 0.2209`) and win rate fell (`40.9% -> 39.1%`). Aggregate EV
moved `-0.1732`; aggregate PnL moved `-$719.61`.

Mechanism insight: low score alone does not prove Technology trend haircuts are
too punitive. The release amplified PLTR/META/MSFT-like stop-outs more than it
recovered AMD/NOW-like delayed winners. This complements exp-20260430-002: both
score-only Technology trend de-risking and score-only haircut release are
invalid discriminators.

Do not repeat: full-risk or risk-on-unmodified releases of low-score Technology
trend haircuts, or any Technology trend haircut release that uses
`regime_exit_score < 0.10` alone as the qualifier.

Next valid retry requires: an orthogonal production-shared event, news, or
lifecycle discriminator that separates delayed Technology winners from ordinary
weak trend noise, plus tail-risk evidence that the release does not expand
`mid_weak` drawdown.

### 2026-04-30 mechanism update: Defensive ETF universe expansion

Status: rejected.

Core conclusion: exp-20260430-005 tested whether defensive rate/dollar ETFs
already present in the fixed OHLCV snapshots (`IEF`, `TLT`, `UUP`) should be
added to the tradeable production watchlist. They should not be promoted as a
simple universe expansion.

Evidence: versus the accepted stack, `late_strong` and `old_thin` were
unchanged on EV, while `mid_weak` improved EV by only `+0.0005` and reduced
PnL by `$440.21`. The only observed defensive trade was a `TLT` target in
`mid_weak`, but it displaced better opportunity under the current slot/heat
stack. Aggregate PnL regressed and no Gate 4 threshold was met.

Mechanism insight: low-volatility defensive targets can still be
opportunity-cost negative when they compete for scarce A/B slots. Adding
defensive ETFs increases candidate supply, not necessarily alpha.

Do not repeat: adding `IEF`/`TLT`/`UUP` as a simple defensive ETF universe
expansion, or treating defensive ETF targets as alpha without opportunity-cost
evidence.

Next valid retry requires: a state discriminator showing when defensive ETF
continuation should compete for scarce slots, or a ranking signal that prevents
low-volatility ETFs from displacing higher-EV A/B candidates.

### 2026-04-30 mechanism update: Zero-share slot prefilter

Status: rejected.

Core conclusion: exp-20260430-006 tested whether candidates already sized to
zero shares should be removed before shared scarce-slot routing and slot
slicing. This looked like a clean slot-allocation alpha, but it should not be
promoted.

Evidence: versus the accepted stack, `late_strong` was unchanged, `mid_weak`
regressed from EV `1.0034` to `0.9429`, and `old_thin` regressed from EV
`0.2267` to `0.1120`. Aggregate PnL fell by `$7,876.12`; no window improved
on EV.

Mechanism insight: zero-share candidates are not merely harmless slot
pollution. In the current ordering stack, preserving them through planning
sometimes blocks worse later candidates; removing them releases lower-quality
trades in weaker tapes.

Do not repeat: dropping zero-share sized candidates before shared entry
planning, or using `no_shares` counts alone as evidence for slot-routing alpha.

Next valid retry requires: candidate forward-quality evidence showing that the
released candidates are better than the blocked candidates, ideally with a
state-specific slot discriminator rather than a blanket pre-filter.

### 2026-04-30 mechanism update: Same-day sector cap sweep

Status: rejected.

Core conclusion: exp-20260430-007 tested whether the shared same-day sector
cap was suppressing existing A/B alpha. It was not. Tightening
`MAX_PER_SECTOR` from `2 -> 1` damaged all three fixed windows, while loosening
it to `3` changed candidate survival but did not improve any executed-trade
metric.

Evidence: `MAX_PER_SECTOR=1` moved aggregate EV by `-0.6565` and aggregate PnL
by `-$19,578.53`, with all three windows regressing. `MAX_PER_SECTOR=3` left
EV, PnL, drawdown, trade count, and win rate unchanged across the fixed
windows; only candidate survival changed.

Mechanism insight: the current same-day sector cap is not the binding alpha
bottleneck. Sector clustering that survives the accepted stack is valuable
enough that tightening removes winners, while loosening does not release
incremental executable alpha under the current slot/heat stack.

Do not repeat: global `MAX_PER_SECTOR=1`, global `MAX_PER_SECTOR=3`, or using
candidate survival-rate improvement alone as evidence for sector-cap alpha.

Next valid retry requires: a state-specific sector crowding discriminator, or a
production-shared ranking signal that chooses among same-sector candidates
rather than changing the global cap.

### 2026-04-30 mechanism update: Sector ETF universe expansion

Status: rejected.

Core conclusion: exp-20260430-008 tested whether sector / commodity ETFs already
available in the fixed OHLCV snapshots (`USO`, `XLE`, `XLP`, `XLU`, `XLV`)
should be added to the tradeable universe as cleaner candidate supply. They
should not be promoted as a simple universe expansion.

Evidence: the full bundle improved `late_strong` EV (`2.4787 -> 3.0879`) but
regressed `mid_weak` (`1.0034 -> 0.5735`) and `old_thin` (`0.2267 -> 0.1996`);
aggregate PnL fell by `$1,059.91`. Narrow variants also failed: `XLE_only`
regressed late/mid, `USO_only` regressed mid/old on EV, and excluding `USO`
still regressed all three EV windows except no old improvement.

Mechanism insight: sector ETFs are not automatically lower-noise replacements
for single-name candidates. `USO` added strong late-tape commodity exposure but
was repeatedly opportunity-cost negative in `mid_weak`, while broad sector ETFs
added slot competition without stable cross-window alpha.

Do not repeat: adding `USO` / `XLE` / `XLP` / `XLU` / `XLV` as a simple
tradeable universe expansion, or treating sector ETFs as safer candidate supply
without a state-specific routing signal.

Next valid retry requires: a state discriminator showing when ETF continuation
should compete for scarce slots, or a ranking signal that explicitly compares
ETF candidates against same-sector single-name candidates.

### 2026-04-30 mechanism update: LLM replay coverage audit

Status: observed-only measurement audit.

Core conclusion: exp-20260430-009 did not change behavior; it refreshed the
current accepted-stack LLM replay coverage picture so soft-ranking work does
not drift back into guesswork.

Evidence: for `2025-10-23 -> 2026-04-21`, the archive now has 10
`llm_prompt_resp` days, 8 `decision_log` days, 16 `quant_signals` days, 7
full-triplet days, and only 3 production-aligned ranking-eligible days
covering 8 presented signals.

Mechanism insight: replay readiness is improving, but the effective LLM sample
is still too thin for a promotion-grade ranking experiment. The bottleneck is
not model intuition; it is ranking-eligible archive density.

Do not repeat: treating raw prompt file count or archive presence alone as
evidence that LLM ranking is ready for alpha promotion.

Next valid retry requires: more production-aligned full-triplet days, or a
coverage push that directly increases ranking-eligible candidate overlap.

### 2026-04-30 mechanism update: Hold-quality oracle loss taxonomy refresh

Status: observed-only.

Core conclusion: exp-20260430-010 refreshed the current accepted-stack
loss-family map before any new lifecycle experiment. The biggest recurring
fixable drag still clusters in failed follow-through and low-MFE stop-out
families, not in broad overnight-gap or wide-stop buckets.

Evidence: the artifact showed `failed_followthrough` as the largest repeated
loss family at 14 losses and `$9,084.88` absolute loss with only `0.32`
winner-collateral, while `low_mfe_stopout` had 9 losses and `$5,712.45` loss
with zero winner-collateral. Overnight-gap and wide-stop families carried much
higher winner collateral and remain poor candidates for direct filters.

Mechanism insight: if lifecycle alpha search resumes, it should start from
follow-through quality or early hold-quality context, not blanket gap/wide-stop
defensiveness.

Do not repeat: broad overnight-gap or wide-stop filters justified only by raw
loss dollars, without collateral accounting.

Next valid retry requires: a production-shared discriminator that targets the
failed-followthrough / low-MFE families while keeping winner collateral low.

### 2026-04-30 mechanism update: Exit advisory replay disclosure

Status: accepted measurement repair.

Core conclusion: production held-position exit advice and backtest price exits
are not the same object. Production computes advisory rules such as
`SIGNAL_TARGET`, profit ladders, and `TIME_STOP`,
then lets the LLM / daily workflow decide whether to issue or preserve
`REDUCE` / `EXIT` actions. The canonical backtest executes full-position
`stop_price` and `target_price` fills, plus only explicitly implemented shared
replay hooks.

Evidence: this repair adds an explicit
`known_biases.exit_policy_unreplayed` result block,
`exit_advisory_shadow_attribution`, and parity docs. It does not change trade
behavior or historical metrics. The anti-repeat evidence remains
`exp-20260429-032`: bare `SIGNAL_TARGET -> 33% trim` replay regressed EV and
PnL in all three fixed windows.

Mechanism insight: exit parity should be closed by shadow attribution and a
complete lifecycle design, not by changing the meaning of `target_price` inside
`backtester.py` alone.

Do not repeat: simple `SIGNAL_TARGET` partial-reduce replays, or any
backtester-only exit lifecycle that production cannot surface through the daily
report / LLM / pending-action path.

Next valid retry requires: enough shadow-attribution sample to identify which
rule families deserve executable replay, followed by a shared policy that both
`run.py` and `backtester.py` can expose.

### 2026-04-30 mechanism update: Approaching hard-stop partial reduce replay

Status: rejected.

Core conclusion: exp-20260430-012 tested the first actionable exit rule exposed
by shadow attribution: first `APPROACHING_HARD_STOP` trigger schedules a
next-open partial reduce using the shared production reduce-percentage helper.
This should not be promoted.

Evidence: the rule lowered max drawdown in all three fixed windows, but EV and
PnL regressed everywhere. EV moved `late_strong 2.4787 -> 1.6378`,
`mid_weak 1.0034 -> 0.6673`, and `old_thin 0.2267 -> 0.1534`; aggregate PnL
fell by `$35,055.21`. The replay executed 9/10/15 approaching-stop partial
reduces across the three windows.

Mechanism insight: `APPROACHING_HARD_STOP` is a noisy warning, not an
executable edge by itself. Many warnings occur during normal early drawdown in
positions that later reach target, so blanket de-risking buys drawdown
improvement by selling profitable convexity.

Do not repeat: first-trigger `APPROACHING_HARD_STOP` partial reduce, full exit,
or similar blanket de-risking variants without a discriminator that separates
true breakdowns from temporary drawdown.

Next valid retry requires: event/news/LLM context or a price-action state that
identifies which approaching-stop warnings deserve action, and must improve EV
rather than only drawdown.

Follow-up: after rejection, `APPROACHING_HARD_STOP` was removed from advisory
rule generation and shared reduce-percentage mapping. It should not appear in
production prompts or future shadow attribution as a standalone rule.

### 2026-04-30 mechanism update: Remove approaching-stop advisory generation

Status: accepted measurement simplification.

Core conclusion: exp-20260430-013 removed `APPROACHING_HARD_STOP` from the
generated advisory exit rule set. Its executable replay was rejected in
exp-20260430-012, and keeping it as a standalone warning adds LLM prompt noise
without demonstrated alpha value.

Evidence: deterministic stop/target backtest metrics are unchanged by
construction and by the late-strong no-drift check: EV remains `2.4787`, PnL
remains `$59,304.19`, and trade count remains `19`. The shared reduce helper
now maps `APPROACHING_HARD_STOP` to `0%` if encountered defensively.

Mechanism insight: a warning that is not actionable should not be generated as
a first-class rule. If a future version wants near-stop context, it needs a
specific event/price-action discriminator rather than a standalone proximity
rule.

Do not repeat: reintroducing `APPROACHING_HARD_STOP` as an independent advisory
or reduce/exit trigger without new LLM archive evidence or a discriminator.

### 2026-04-30 mechanism update: Remove pure trailing-stop advisory generation

Status: accepted measurement simplification.

Core conclusion: exp-20260430-014 disabled pure `TRAILING_STOP` advisory rule
generation from `position_manager.evaluate_exit_signals`. This does not remove
trailing stop risk references: `TRAILING_STOP_PCT`, portfolio heat effective
stops, and `production_trailing_stop_price` remain available for risk context.

Evidence: pure trailing partial-reduce replay was already rejected
(`exp-20260429-011` / `exp-20260429-017`), and shared policy maps pure
`TRAILING_STOP` to `0%` reduce by default. The no-drift fixed-window check
stayed unchanged: EV `2.4787`, PnL `$59,304.19`, 19 trades, and max drawdown
`4.39%`.

Mechanism insight: a rule that is disabled as an action should not keep
appearing as a first-class LLM advisory trigger. Keep the risk level as context,
but do not ask the LLM to infer an action from a rejected standalone signal.

Do not repeat: reintroducing pure `TRAILING_STOP` as an advisory reduce/exit
trigger without new LLM archive evidence or a more specific discriminator.

### 2026-04-30 mechanism update: High-score plain risk-on sizing

Status: rejected as inert.

Core conclusion: exp-20260430-013 tested whether the residual high-score plain
risk-on sleeve (`regime_exit_score >= 0.20`, after accepted low/mid-score
lifts) should move away from the generic 1.25x budget. Variants
1.00x/1.40x/1.50x/1.60x changed no fixed-window trades or metrics.

Evidence: all three fixed windows were identical to baseline: late_strong EV
2.4787 / PnL $59,304.19, mid_weak EV 1.0034 / PnL $39,346.43, old_thin EV
0.2267 / PnL $18,584.08. Aggregate EV delta 0.0 and PnL delta $0.00.

Mechanism insight: the residual high-score plain risk-on scalar is not a
binding alpha lever under current 40% initial cap, heat, and slot constraints.
Candidate-level sizing attribution can show the rule present, but the tested
scalar does not change realized allocations.

Do not repeat: nearby high-score plain risk-on multiplier tweaks or treating
the residual plain sleeve as the next allocation lever without forward/tail-risk
evidence.

Next valid retry requires: an orthogonal event/state discriminator that changes
which candidates get scarce capital, not another scalar budget tweak.

### 2026-04-30 mechanism update: Add-on no-undercut gate

Status: rejected.

Core conclusion: exp-20260430-014 tested whether day-2 follow-through add-ons
should require the position to avoid any intraday undercut of the original
entry price between entry and checkpoint. It should not be promoted. The rule
was temporarily implemented in the shared production/backtest add-on paths,
then rolled back after fixed-window failure.

Evidence: versus the accepted stack, the candidate eliminated all add-on
executions in all three fixed windows. EV moved `late_strong 2.4787 -> 2.4682`,
`mid_weak 1.0034 -> 0.9780`, and `old_thin 0.2267 -> 0.2267`; aggregate PnL
fell by `$2,125.72`.

Mechanism insight: simple intraday entry undercut is too blunt as a
follow-through quality discriminator. It mostly disables the accepted add-on
alpha rather than separating fragile recoveries from normal noisy winners.

Do not repeat: no-entry-undercut add-on gates or nearby intraday-undercut
variants without new evidence that they preserve executed add-ons.

Next valid retry requires: an orthogonal adverse-information source, such as
news/event context or a richer hold-quality state, that targets
failed-followthrough / low-MFE losses without turning off the accepted add-on
mechanism.

### 2026-04-30 mechanism update: Same-sector candidate chooser

Status: rejected.

Core conclusion: exp-20260430-015 tested whether `MAX_PER_SECTOR=2` should
choose retained same-sector candidates by `trade_quality_score` or confidence
instead of native candidate order. It should not be promoted.

Evidence: confidence ordering was inert across all three fixed windows. TQS
ordering left `late_strong` and `old_thin` unchanged, but regressed `mid_weak`
EV `1.0034 -> 0.9429`, PnL `$39,346.43 -> $38,016.04`, and win rate
`52.4% -> 50.0%`. No Gate 4 condition passed.

Mechanism insight: the same-day sector cap is not currently a useful alpha
bottleneck by itself. Simple same-sector score ordering either does nothing or
releases worse slot competition; sector-cap movement is not alpha without
executed-trade improvement.

Do not repeat: simple same-sector TQS or confidence ordering before
`MAX_PER_SECTOR`, or treating sector cap mechanics as the next alpha without a
state/event discriminator.

Next valid retry requires: state-specific sector crowding evidence or
event/news quality context showing that the replacement candidate beats the
dropped candidate after slot and heat constraints.
### 2026-04-30 mechanism update: Breakout deferral quality exception

Status: rejected.

Core conclusion: exp-20260430-016 tested whether the accepted one-slot
`breakout_long` deferral should allow narrow high-quality exceptions for
breakouts with strong `trade_quality_score` and proximity to the 52-week high.
It should not be promoted.

Evidence: both tested variants (`TQS >= 0.90 and pct_from_52w_high >= -3%`,
`TQS >= 0.85 and pct_from_52w_high >= -5%`) produced zero metric movement in
all three fixed windows. Baseline and candidate stayed at `late_strong EV
2.4787`, `mid_weak EV 1.0034`, and `old_thin EV 0.2267`; aggregate PnL delta
was `$0.00`.

Mechanism insight: the breakouts currently blocked by scarce-slot deferral are
not the clean high-quality near-high candidates this rule was meant to rescue.
The bottleneck is not a simple quality exception inside deferral.

Do not repeat: high-TQS near-high breakout exceptions to one-slot deferral, or
treating fewer deferred candidates as alpha without executed-trade movement.

Next valid retry requires: event/news quality context or a candidate
replacement audit proving the allowed breakout beats the displaced trade after
slot, heat, gap-cancel, and add-on effects.

### 2026-04-30 mechanism update: Day-1 weak follow-through partial reduce

Status: rejected.

Core conclusion: exp-20260430-017 tested whether positions that were below
cost and underperforming SPY on day 1 should receive a 50% next-open partial
reduce. The rule was tested through a temporary shared production/backtest
helper, then rolled back after fixed-window failure.

Evidence: versus the accepted stack, the rule executed 17 partial reduces and
regressed EV in all three fixed windows: `late_strong 2.4787 -> 2.4713`,
`mid_weak 1.0034 -> 0.7490`, and `old_thin 0.2267 -> 0.2160`. Aggregate PnL
fell by `$12,673.23`.

Mechanism insight: day-1 below-cost plus negative RS is still too blunt. It
does identify some early weakness, but it sells enough delayed winners and
changes subsequent slot/capital paths enough to overwhelm the saved loss.

Do not repeat: day-1 price-only weak-followthrough partial reduces, or nearby
below-cost / negative-RS de-risking variants without orthogonal adverse
information.

Next valid retry requires: event/news/LLM context or a richer hold-quality
state that separates true failed follow-through from delayed winners before
turning weak early price action into an executable action.

### 2026-04-30 mechanism update: Technology trend near-high multiplier drift

Status: rejected.

Core conclusion: exp-20260430-018 tested whether the accepted
`trend_long` Technology near-high haircut was too punitive. It should not be
promoted or locally retuned. The current 0.25x form remains the better default
until a new discriminator appears.

Evidence: lowering the multiplier to `0.0` badly damaged `mid_weak`
(`EV 1.0034 -> 0.7391`) and `old_thin` (`0.2267 -> 0.1392`). A softer `0.10`
variant also regressed both weak windows. Raising it to `0.50` improved
`mid_weak` and `old_thin` only slightly, but regressed `late_strong`
(`2.4787 -> 2.4711`) and produced only `+0.0038` aggregate EV / `+$948.45`
aggregate PnL, below Gate 4 materiality.

Mechanism insight: the near-high Technology trend pocket is not solved by
nearby multiplier drift. Full bans over-prune delayed winners, while partial
release adds too little edge and slightly damages the dominant strong tape.

Do not repeat: nearby `TREND_TECH_NEAR_HIGH_RISK_MULTIPLIER` values around
`0.10`, `0.25`, or `0.50`, or a full zero-risk near-high Technology trend ban,
without new evidence.

Next valid retry requires: an orthogonal event, news, or lifecycle
discriminator that separates delayed Technology winners from weak near-high
trend noise, and a material aggregate EV improvement rather than tiny
weak-window PnL recovery.

### 2026-04-30 mechanism update: Current-stack second add-on retry

Status: rejected.

Core conclusion: exp-20260430-019 retested the prior best day-5 second
follow-through add-on after the accepted low/mid-score plain risk-on sizing
promotions changed the current capital path. It should not be promoted.

Evidence: the best current-stack retry executed only one second add-on. EV
moved `late_strong 2.4787 -> 2.4779`, while `mid_weak` and `old_thin` were
unchanged at `1.0034` and `0.2267`. Aggregate PnL moved `-$12.73`, so the
qualified retry failed Gate 4.

Mechanism insight: the current accepted stack already captures almost all
available follow-through add-on materiality. A second add-on using only day-5
`>= +5%` unrealized and RS `> 0` no longer releases meaningful alpha.

Do not repeat: day-5 second follow-through add-on variants based only on
unrealized return and RS, or nearby second-add-on fraction/cap tuning on the
current accepted stack.

Next valid retry requires: an orthogonal event, news, or richer lifecycle
quality discriminator that materially increases eligible executions without
expanding concentration risk.

### 2026-04-30 mechanism update: Risk-on Commodities final budget

Status: rejected.

Core conclusion: exp-20260430-020 tested whether the current accepted stack
should raise the final risk budget for `sector == Commodities` only when
`regime_exit_bucket == risk_on`, explicitly excluding the known weak defensive
SLV shape. It should not be promoted.

Evidence: 1.8x and 2.0x variants improved only `late_strong`. The 2.0x variant
lifted `late_strong` EV `2.4787 -> 2.6604` and PnL by `$2,853.32`, but
`mid_weak` and `old_thin` were unchanged. Aggregate EV improved, but the
fixed-window protocol requires majority-window improvement for strategy logic.

Mechanism insight: the commodity sleeve is not necessarily under-allocated
across the whole stack; in `mid_weak` and `old_thin`, the 40% single-position
cap already prevents the tested multiplier from changing realized exposure.
The apparent improvement is a late-strong-only amplification, not a robust
capital-allocation unlock.

Do not repeat: nearby `risk_on` Commodities final multipliers such as 1.8x or
2.0x, or using aggregate EV alone to accept a late-strong-only commodity boost.

Next valid retry requires: cap/headroom evidence that the rule changes realized
shares in at least two fixed windows, or forward evidence that commodity
risk-on exposure remains under-allocated outside the late strong tape.

### 2026-04-30 mechanism update: Trend Technology mid-score state route

Status: rejected.

Core conclusion: exp-20260430-021 tested whether `trend_long` Technology
candidates in the `risk_on` `regime_exit_score` band `[0.10, 0.20)` should
receive an extra risk haircut. This looked like a cleaner state-routing
variant than the rejected near-high / gap / DTE Technology retunes, but it
should not be promoted.

Evidence: the best 0.50x variant only marginally improved `mid_weak` EV
(`1.0034 -> 1.0051`) while damaging `late_strong` (`2.4787 -> 2.2510`) and
`old_thin` (`0.2267 -> 0.1853`). Aggregate PnL fell by `$6,284.02`; stricter
0.25x and 0x variants were worse.

Mechanism insight: regime-exit score alone is not enough to separate fragile
Technology trend entries from delayed winners. The same score band contains
important strong-tape Technology winners, so score-only state routing behaves
like another blunt Technology haircut.

Do not repeat: trend Technology `risk_on` `[0.10, 0.20)` score haircuts, or
nearby score-only Technology state-routing variants without orthogonal
event/news/lifecycle evidence.

Next valid retry requires: a discriminator that preserves late strong
Technology winners while identifying mid-window failed follow-through, ideally
with event/news context or richer hold-quality state rather than score alone.

### 2026-04-30 mechanism update: Breadth-conditioned risk-on boost

Status: rejected.

Core conclusion: exp-20260430-022 tested whether accepted low/mid-score
`risk_on_unmodified` sizing boosts should require healthy 50-day universe
breadth. This should not be promoted.

Evidence: the best variant, `breadth50_min_0_50`, damaged `late_strong` EV
`2.4787 -> 2.3374` and PnL by `$2,151.82`, while `mid_weak` and `old_thin`
were inert. Stricter 0.60 and 0.70 breadth thresholds also hurt weak windows:
0.60 moved `old_thin` EV `0.2267 -> 0.2165`, and 0.70 moved `mid_weak`
`1.0034 -> 0.9715` plus `old_thin` `0.2267 -> 0.2179`.

Mechanism insight: broad 50dma universe breadth is not a useful gate for the
already accepted risk-on plain boost. It removes or reduces exposure to winners
in the dominant strong tape and does not unlock a compensating weak-window
edge. The issue is not "risk-on boost only works when breadth is high"; the
remaining alpha problem still needs a candidate-level, event/news, or richer
lifecycle discriminator.

Do not repeat: requiring broad 50dma breadth before applying accepted
low/mid-score `risk_on_unmodified` boosts, or nearby blunt breadth thresholds
used as overlays on existing risk-on sizing.

Next valid retry requires: evidence that a breadth-derived variable changes
realized exposure in at least two fixed windows without damaging `late_strong`,
or a narrower discriminator that targets a repeated weak-tape failure mode
while preserving accepted strong-tape winners.

### 2026-04-30 mechanism update: Technology sector-leader de-risking

Status: rejected.

Core conclusion: exp-20260430-023 tested whether `trend_long` Technology
signals should receive less risk when Technology sector breadth was high
(`sector_breadth_200 >= 75%`) and the ticker had already outperformed its
sector by at least 3 percentage points over 20 trading days. This should not
be promoted.

Evidence: every tested multiplier regressed all three fixed windows. The best
variant, `0.50x`, moved EV `late_strong 2.4787 -> 2.2502`,
`mid_weak 1.0034 -> 0.9978`, and `old_thin 0.2267 -> 0.1521`; aggregate PnL
fell by `$8,055.31` (`-6.87%`).

Mechanism insight: Technology trend winners are still too dependent on
individual convexity for a sector-relative leadership haircut to work. Even a
candidate-level sector-state discriminator clipped more winner exposure than
it saved; high sector breadth plus ticker leadership is not adverse
information by itself.

Do not repeat: nearby Technology sector-relative 20-day return haircuts,
sector-leader de-risking, or high-breadth Technology trend de-risking without
orthogonal event/news/lifecycle evidence.

Next valid retry requires: a discriminator that separates delayed Technology
winners from fragile leaders using new information, not another relative-return
cutoff around the same sector-state audit.

### 2026-04-30 mechanism update: Earnings and pending-action bias disclosure

Status: accepted measurement repair.

Core conclusion: the backtester disclosure layer was stale in two places. It
still described `earnings_event_long` as `days_to_earnings`-only even though
P-ERN snapshots now provide `eps_estimate` and surprise-history fields when
coverage exists, and it did not expose the current production
`pending_actions.json` ledger as a separate non-replayed gap.

Evidence: this repair does not change trading behavior. It refreshes
`known_biases.earnings_event_long_data_quality` from the actual loaded snapshot
archive, adds `known_biases.pending_action_replay_unreplayed`, and corrects the
LLM attribution note so it no longer implies LLM `position_actions` are
historically replayed.

Mechanism insight: disclosure must distinguish "field absent" from "field
snapshot-backed but coverage-limited." Treating those as the same blind spot
would send future agents back into already-resolved P-ERN work instead of the
real remaining blockers: LLM/news archive density and point-in-time action
ledger snapshots.

Do not repeat: saying Strategy C has no EPS/surprise history without checking
the snapshot coverage fields in `known_biases.earnings_event_long_data_quality`.

### 2026-04-30 mechanism update: Breakout gap-quality subsequence ranking

Status: rejected.

Core conclusion: exp-20260430-025 tested whether the existing `breakout_long`
subsequence should be ranked by setup quality or lower `gap_vulnerability_pct`
instead of the current `pct_from_52w_high` then confidence order. This should
not be promoted.

Evidence: all three tested ranking variants were inert in all three fixed
windows. EV stayed `late_strong 2.4787`, `mid_weak 1.0034`, and `old_thin
0.2267`; aggregate PnL delta was `$0.00`, and trade count / win rate /
drawdown were unchanged.

Mechanism insight: current executed trades are not bottlenecked by these
breakout subsequence sorting keys. The accepted stack's slot, heat, same-sector
cap, and one-slot breakout deferral path mean simple deterministic reordering
inside the breakout subsequence does not change realized allocation.

Do not repeat: nearby breakout subsequence sort keys based only on
`trade_quality_score`, `confidence_score`, `gap_vulnerability_pct`, or
`pct_from_52w_high` without candidate replacement evidence.

Next valid retry requires: event/news context or a candidate replacement audit
showing that the new rank key changes executed trades in at least two fixed
windows after slot, heat, gap-cancel, and add-on effects.

### 2026-04-30 mechanism update: Add-on cap matches initial cap

Status: rejected as positive but immaterial.

Core conclusion: exp-20260430-026 tested `ADDON_MAX_POSITION_PCT` from 35% to
40%, matching the current initial position cap after the accepted stack moved to
40% initial entries and 50% day-2 add-ons. The code change was rolled back
because the improvement did not clear Gate 4 materiality. This was not an
add-on trigger change: checkpoint day, +2% unrealized threshold, RS > 0,
fraction, heat, slots, exits, and ranking stayed fixed.

Evidence: EV and PnL improved in all three fixed windows: late_strong EV
`2.4787 -> 2.5322`, mid_weak `1.0034 -> 1.0152`, old_thin `0.2267 -> 0.2298`.
Aggregate PnL improved by `$1,711.75`; trade count, win rate, survival, and max
drawdown were unchanged. This was only `+1.46%` aggregate PnL, below the +5%
Gate 4 threshold; Sharpe, drawdown, and trade count also failed their materiality
thresholds.

Mechanism insight: after initial entries were allowed to reach 40%, leaving
confirmed winner add-ons capped at 35% may create a small allocation mismatch,
but the measured edge is too small to pay for more concentration. Capacity
alignment alone is not a sufficient alpha lever.

Do not repeat: nearby add-on cap tuning at or above 40%, add-on fraction sweeps,
or second-add-on retries without forward concentration evidence or an orthogonal
event/news/lifecycle discriminator.

### 2026-04-30 mechanism update: Snapshot universe ETF expansion

Status: rejected.

Core conclusion: exp-20260430-027 through exp-20260430-029 tested whether the
next alpha should come from improving the candidate pool rather than tuning
thresholds. The available snapshot extras did not justify production watchlist
expansion. Broad sector ETF expansion regressed all three fixed windows, and
the best energy/oil variants improved only one window while regressing two.

Evidence: the unmapped `add_energy_oil` screen produced aggregate EV delta
`+0.2562` and PnL `+$2,982.31`, but only one EV-positive window and a max
drawdown increase of `+1.13 pp`. With production-like sector mapping, the best
`XLE + USO` variant still improved only one window, regressed two, lost
`$2,040.65`, added seven trades, and lowered win rate by up to `8.9 pp`.
Mapped sector ETFs (`XLE`, `XLV`, `XLP`, `XLU`) regressed all three windows and
lost `$15,440.79`.

Mechanism insight: adding broad ETF candidates is not a clean candidate-pool
upgrade for the current A+B stack. It dilutes scarce slots and changes capital
paths without a stable alpha discriminator. If universe expansion is revisited,
prefer individual names with candidate replacement evidence, not ETF baskets.

Do not repeat: adding XLE/USO, broad sector ETFs, rates/fx ETFs, or snapshot
extras as trading candidates without a new event/news or regime-routing
discriminator.

### 2026-04-30 mechanism update: Market reference ETF pruning

Status: rejected.

Core conclusion: exp-20260430-028 tested whether SPY/QQQ/IWM should remain
context-only instead of tradable. SPY/QQQ pruning was inert, but removing IWM
regressed the accepted stack.

Evidence: removing `IWM` (or `SPY`, `QQQ`, and `IWM` together) moved aggregate
EV by `-0.2809`, PnL by `-$5,582.82` (`-4.76%`), did not improve any EV window,
and lowered win rate by up to `6.55 pp`. Removing only SPY/QQQ moved no fixed
window metrics.

Mechanism insight: IWM is not merely a reference ticker under the current rules;
it occasionally contributes useful tradable exposure. SPY/QQQ are effectively
inert as trade candidates, so removing them does not release alpha.

Do not repeat: pruning IWM from the trading universe without fresh evidence of
IWM trade degradation, or spending another cycle on SPY/QQQ pruning while they
remain metric-inert.

### 2026-04-30 mechanism update: First add-on haircut gate

Status: rejected at audit stage.

Core conclusion: exp-20260430-030 tested whether the accepted day-2
follow-through add-on is leaking capital into positions that the sizing layer
had already de-risked. This was a lifecycle alpha audit, not a bug repair and
not another add-on cap/fraction sweep. No production strategy behavior changed.

Evidence: across the three fixed windows, only 4 trades had executed first
add-ons and only 1 of them had an initial risk haircut. Removing all add-on
share contribution would have reduced approximate PnL by `$1,813.50`
(`-1.55%`). Removing only the haircut-position add-on would have improved
approximate PnL by just `$228.30` (`+0.19%`), with the effect appearing only in
`mid_weak`.

Mechanism insight: the current first add-on leak into de-risked positions is
too sparse to justify a shared production policy. The add-on alpha is mostly
coming from full-risk or boosted winners, so a broad "no add-ons after haircut"
rule would add metadata and policy complexity for de minimis benefit.

Do not repeat: implementing a first-add-on haircut gate, or adding persistence
for initial sizing multipliers solely to support this gate, without full replay
evidence or an orthogonal event/news lifecycle discriminator.

### 2026-04-30 mechanism update: Low-score plain risk-on sizing

Status: rejected as positive but immaterial.

Core conclusion: exp-20260430-031 tested whether otherwise unmodified
`risk_on` signals with `regime_exit_score < 0.10` should receive more than the
current 1.5x risk budget. The best 2.0x variant was directionally positive but
should not be promoted.

Evidence: 2.0x improved `late_strong` EV `2.4787 -> 2.5651` and `old_thin`
EV `0.2267 -> 0.2414`, while `mid_weak` was unchanged. Aggregate EV delta was
`+0.1011`, but this is only `+2.73%` of baseline aggregate EV; aggregate PnL
rose only `$2,223.70` / `+1.90%`, Sharpe improved at most `+0.05`, and no
drawdown/trade-count criterion moved. Gate 4 materiality was not met.

Mechanism insight: low-score plain risk-on exposure is a real positive pocket,
but increasing the scalar is mostly a small amplification of already-captured
winners, not a new robust allocation unlock. The opportunity is too cap-limited
and sparse to justify more concentration.

Do not repeat: nearby low-score plain `risk_on` multiplier tuning such as 1.8x
or 2.0x without forward evidence or an orthogonal candidate-level discriminator.

Next valid retry requires: event/news/lifecycle context that expands or
separates the pocket, rather than another scalar increase.

### 2026-04-30 mechanism update: Gold trend target extension

Status: accepted as shared production/backtest exit policy.

Core conclusion: exp-20260430-032 tested whether the rejected unconditional
Commodity trend 8ATR target could be salvaged by separating GLD/IAU from SLV.
It can. GLD/IAU `trend_long` targets now use 8 ATR, while SLV and all other
Commodity trend targets remain on the accepted 7 ATR path.

Evidence: versus the accepted stack, the rule improved EV in all three fixed
windows: `late_strong 2.4787 -> 2.7000`, `mid_weak 1.0034 -> 1.0221`, and
`old_thin 0.2267 -> 0.2404`. Aggregate PnL improved `+$4,554.88` / `+3.89%`,
drawdown, trade count, and win rate were unchanged, and `late_strong` daily
Sharpe improved by `+0.12`, clearing Gate 4.

Mechanism insight: the Commodity trend continuation edge is not homogeneous.
Gold ETFs continued to benefit from a wider target, while prior wider Commodity
tests were hurt by the SLV path. This is a lifecycle/exit alpha, not a new
entry source and not a risk-budget increase.

Do not repeat: nearby gold target sweeps such as 8.5/9 ATR, extending SLV above
7 ATR, or treating this as evidence for all Commodity breakouts.

Next valid retry requires: forward evidence, event/news confirmation, or a
broader precious-metals state map that explains when non-gold Commodity
continuation should share the wider target.

### 2026-05-01 mechanism update: Broad breakout target extension

Status: rejected.

Core conclusion: exp-20260501-001 tested whether all `breakout_long` winners
should receive wider 5.0ATR or 5.5ATR targets instead of the current
regime-aware target path. This should not be promoted.

Evidence: the best variant, 5.0ATR, raised aggregate PnL by `$2,742.48` but
failed the North Star: EV regressed in two of three fixed windows
(`late_strong 2.7000 -> 2.5483`, `mid_weak 1.0221 -> 0.9634`) and improved only
`old_thin` (`0.2404 -> 0.2497`). 5.5ATR was worse, with aggregate EV delta
`-0.5268` and aggregate PnL delta `-$3,297.83`.

Mechanism insight: breakout winners are not uniformly target-clipped. Giving
the whole breakout sleeve more room increases some dollars but lowers
risk-adjusted quality and damages the mid window, so the current problem is not
a broad breakout target-width shortage.

Do not repeat: broad `breakout_long` target widening to nearby 5.0ATR/5.5ATR,
or using aggregate PnL improvement to override multi-window EV regression.

Next valid retry requires: event/news or lifecycle context that identifies
which specific breakout winners deserve more room without weakening the full
breakout sleeve.

### 2026-05-01 mechanism update: Energy trend target extension

Status: rejected.

Core conclusion: exp-20260501-002 tested whether `trend_long` Energy winners
should receive a wider 5.0ATR or 6.0ATR target instead of the current
regime-aware path. This should not be promoted.

Evidence: both tested variants were identical and damaged the only active
window. `late_strong` EV fell `2.7000 -> 2.3535`, PnL fell by `$4,383.21`,
daily Sharpe fell `4.30 -> 4.03`, and win rate fell by `5.27 pp`. `mid_weak`
and `old_thin` had no Energy trend trades, so the variants were inert there.

Mechanism insight: the current Energy trend sample is not target-clipped in the
same way as GLD/IAU. Widening the target delayed or worsened the late-window
Energy path without providing any cross-window evidence. This is a sparse
sector-specific lifecycle tweak, not a robust alpha unlock.

Do not repeat: Energy trend target-width tuning around 5.0ATR or 6.0ATR, or
treating the gold target extension as evidence that every commodity-adjacent
trend sleeve needs more room.

Next valid retry requires: new event/news or lifecycle evidence showing which
Energy trend positions deserve more room, plus realized exposure in at least
two fixed windows.

### 2026-05-01 mechanism update: Gold trend risk budget

Status: rejected as inert.

Core conclusion: exp-20260501-003 tested whether GLD/IAU `trend_long` signals
should receive a higher non-stacking risk budget after the accepted 8ATR gold
target. This should not be promoted.

Evidence: both 1.8x and 2.0x variants were metric-identical to the 1.5x
baseline in all three fixed windows. EV stayed `late_strong 2.7000`,
`mid_weak 1.0221`, and `old_thin 0.2404`; aggregate PnL delta was `$0.00`.

Mechanism insight: the tested gold trend trades were already constrained by
the position cap, so raising the risk multiplier did not change realized
shares or portfolio outcomes. The next question, if any, is cap/headroom, not
another risk-budget scalar.

Do not repeat: GLD/IAU trend risk multipliers around 1.8x or 2.0x, or broad
Commodity risk-budget increases, without evidence that the change alters
realized shares in at least two fixed windows.

### 2026-05-01 mechanism update: Gold trend position cap

Status: rejected as positive but immaterial.

Core conclusion: exp-20260501-004 tested whether GLD/IAU `trend_long`
positions should use a higher position cap than the global 40% cap. The 50%
variant was directionally positive but should not be promoted.

Evidence: the best 50% cap improved EV and PnL in all three fixed windows:
`late_strong 2.7000 -> 2.7524`, `mid_weak 1.0221 -> 1.0434`, and `old_thin
0.2404 -> 0.2574`. Aggregate PnL improved `+$3,530.21` / `+2.90%`, below the
Gate 4 +5% PnL threshold; aggregate EV rose only `+2.29%`, Sharpe improved at
most `+0.03`, and max drawdown worsened by `+0.14 pp`.

Mechanism insight: GLD/IAU trend concentration has a real positive edge after
the 8ATR target, but the measured lift is not large enough to justify a
gold-specific concentration exception. This is a small amplification of an
already-captured winner path, not a material allocation unlock.

Do not repeat: nearby GLD/IAU trend position-cap tuning such as 45%, 50%, or
higher caps without forward concentration evidence or an orthogonal
event/news/lifecycle discriminator.

### 2026-05-01 mechanism update: Synchronous sector risk-on allocation

Status: rejected as positive but immaterial.

Core conclusion: exp-20260501-007 tested whether otherwise-unmodified `risk_on`
signals should receive a larger total risk budget when their sector is moving
synchronously, defined as 50-day sector breadth >= 75% and 20-day sector return
dispersion <= 5%. This should not be promoted.

Evidence: the best 2.0x variant improved EV in two windows and regressed none,
but the effect was too small: aggregate EV rose only `+0.0373` / `+0.90%` and
aggregate PnL rose only `+$1,205.36` / `+0.93%`. The `mid_weak` window was
unchanged, max drawdown, trade count, and win rate did not improve, and only 11
signals were resized across all three fixed windows.

Mechanism insight: sector synchronization is directionally useful, but mostly
acts as a small amplifier of already-selected plain `risk_on` positions. It
does not release enough capital or improve enough realized trades to justify
adding shared sector breadth/dispersion state to production policy.

Do not repeat: nearby synchronous-sector thresholds such as breadth 70-80%,
dispersion 4-6%, or 1.8x/2.0x total risk multipliers without forward evidence
or an orthogonal event/news/lifecycle discriminator.

### 2026-05-01 mechanism update: AI power / infra individual-name universe expansion

Status: observed positive, deferred.

Core conclusion: `exp-20260501-008` tested the user-supplied AI power,
data-center infra, optical, Bitcoin miner, and storage/semi names as a
candidate-pool expansion. This is different from the rejected ETF expansion
family: it uses individual names tied to AI power/infrastructure beta. The
all-tradeable bundle was economically positive but should not be promoted
blindly because universe expansion remains shadow-only and the win-rate/drawdown
costs need a cleaner discriminator.

Evidence: best variant `add_all_user_tradeable` added
`APLD, BE, CIFR, COHR, CORZ, DBRG, INTC, IREN, LITE, MARA, RIOT, TLN, VST, WULF`
while `CRDO` was already in the universe and CoreWeave had no listed ticker.
Aggregate PnL improved `+$21,384.10` / `+16.50%`; aggregate EV improved
`+0.9398`; EV improved in `late_strong` and `mid_weak` but regressed
`old_thin` by `-0.0500`. Candidate trades contributed `+$14,178.30` across
10 trades. Costs: win rate fell by up to `-5.04 pp` and `late_strong` max
drawdown rose `+1.70 pp`.

Mechanism detail: optical and INTC/storage-semi exposure drove most of the
benefit; data-center infra was negative; Bitcoin miners were inert under the
current A/B rules. Do not conclude the miner theme has no alpha, only that the
current trend/breakout rules did not select those names in the fixed windows.

Next valid step: test a production-parity watchlist/sector-map promotion only
after choosing a non-overfit discriminator, such as theme-level replacement
quality or event/news confirmation. Do not promote the full list solely from
this shadow result.

### 2026-05-01 mechanism update: Minimal AI infra watchlist promotion

Status: rejected despite strong aggregate dollars.

Core conclusion: `exp-20260501-009` tested a minimal production-promotable
subset from the prior AI power / infrastructure universe screen: `BE + INTC`,
plus single-name controls. This was an alpha_search candidate-universe test,
not a signal, sizing, ranking, or exit change. It should not be promoted yet.

Evidence: best variant `add_be_intc` improved aggregate PnL by `+$18,948.85`
/ `+14.62%`, improved EV in `late_strong` and `mid_weak`, and improved PnL in
all three fixed windows. It still failed the multi-window EV gate because
`old_thin` EV regressed `0.2563 -> 0.2466`, driven by a losing BE trade, while
`late_strong` max drawdown rose `+1.65 pp`. `INTC` alone was clean but active
only in `late_strong`; `BE` added real `mid_weak` edge but introduced the
`old_thin` fragility.

Mechanism insight: AI infrastructure individual names remain a real candidate
pool lead, but the current evidence is still too close to single-name path
selection. `INTC` looks like a late-window storage/semi continuation add, while
`BE` is regime-sensitive and needs an old-tape discriminator before production
promotion. Aggregate PnL alone is not enough when EV stability weakens.

Do not repeat: promoting `BE + INTC`, `BE` alone, or `INTC` alone as a raw
watchlist addition without new forward evidence or a production-shared
discriminator that explains when BE should be inactive in old/weak tapes.

Next valid retry requires: a non-overfit theme-level discriminator, event/news
confirmation, or forward sample showing that the BE old_thin failure is not a
repeatable fragility while preserving the mid_weak edge.


### 2026-05-01 mechanism update: AI infra pool robustness audit

Status: rejected for production promotion; retained as research pool.

Core conclusion: `exp-20260501-010` audited the user-supplied AI infrastructure
candidate expansion with leave-one-out, leave-theme-out, and refined-pool
variants. The prior all-name result is real enough to keep researching, but it
does not justify a raw production watchlist addition.

Evidence: best ranked variant `focused_top3_intc_lite_be` produced aggregate PnL delta
`$28,260.55` and aggregate EV delta
`+1.3558`, but the evidence remains
concentrated and sparse. The original all-name bundle's aggregate PnL delta
was `$21,384.10`, split into direct candidate
PnL `$14,178.30` and interaction PnL
`$7,205.80`. That confirms the expansion
changed incumbent ranking/capital competition, not only added clean standalone
new-name alpha.

Mechanism insight: AI infrastructure individual names are a valuable research
source, especially optical/semi/power winners, but current evidence is still
too close to theme beta plus a few winner paths. Bitcoin miners remain inert
under the current A/B rules, and short-history names such as CRWV/SNDK need a
separate scout rather than being mixed into the fixed-window acceptance test.

Do not repeat: promoting the full AI infra list, promoting `BE + INTC`, or
using aggregate PnL alone to override old-window EV fragility, low trade count,
or concentration.

Next valid retry requires: forward evidence, an event/news discriminator, or a
theme-level production rule that explains when the fragile power/infra names
should be inactive while preserving optical/semi upside.

### 2026-05-01 mechanism update: Hold-quality loss taxonomy

Status: observed-only.

Core conclusion: `exp-20260501-011` organized the recent accepted-stack losses
into a reusable hold-quality taxonomy, but the sample is too small to justify a
new rule, filter, or LLM responsibility change.

Evidence: in the latest accepted `late_strong` window, all 4 losses were stop
exits without add-ons, and 3 of the 4 clustered on `2026-01-06`. Metrics were
unchanged because this produced only an audit artifact.

Mechanism insight: the recent losses do not yet show a broad repeated failure
family. The dominant pattern is a single clustered bad day with no winner
collateral, which is useful as a shadow-test seed but not enough for a new
production filter.

Do not repeat: turning this 4-loss sample directly into a new hold-quality
gate, stop rule, or add-on prohibition. A valid retry needs a larger
multi-window failure family or a replayable event/news discriminator.

### 2026-05-01 mechanism update: Post-news continuation shadow audit

Status: observed-only, directionally negative.

Core conclusion: `exp-20260501-012` tested whether post-news continuation is a
clean non-overlapping entry source under the current archived-news coverage. It
is not ready: the visible sample is sparse and economically weak.

Evidence: the `late_strong` audit found 57 candidates, only `10.5%` same-day
overlap with current A/B entries, `fwd10 avg -0.9682%`, and `36.84%` forward
win rate. `mid_weak` and `old_thin` had zero coverage candidates. No strategy
metrics changed because this remained a shadow audit.

Mechanism insight: with current point-in-time news coverage, post-news
continuation is not a credible standalone entry family. The bottleneck is not
just rule design; it is coverage depth plus the lack of a stronger event
discriminator.

Do not repeat: promoting post-news continuation as a raw entry pattern from the
current archive, or retesting nearby price-only continuation templates on the
same sparse sample. A valid retry needs broader coverage or materially better
event typing.

### 2026-05-01 mechanism update: Event-sensitive liquidity universe scout

Status: observed-only, non-promotable.

Core conclusion: `exp-20260501-013` audited a liquidity-filtered
event-sensitive universe, but the current archive and replay setup do not yet
produce promotable out-of-universe candidates.

Evidence: the scout produced zero outside-production candidates, only one fixed
window with archived event coverage, and no slot-aware replay. This was
therefore a research artifact rather than a candidate-universe result.

Mechanism insight: universe scouting without real out-of-universe discoveries
or slot-aware replay does not advance the alpha search. Event-sensitive
expansion is still a valid theme, but only when it creates real replacement
pressure against the accepted stack.

Do not repeat: another event-sensitive universe audit with the same archive
coverage and no slot-aware replay. A valid retry needs either new event
coverage or actual candidate replacement evidence.

### 2026-05-01 mechanism update: LLM replay coverage readiness audit

Status: observed-only, still blocked.

Core conclusion: `exp-20260501-014` confirmed that LLM/event ranking remains a
high-upside direction, but it is still blocked by audit coverage rather than by
alpha falsification.

Evidence: effective attribution remains only 3 days / 8 signals, while
prompt/response archives now contain usable `archive_context` on 7 of the 10
sampled files. Metrics were unchanged because this was a read-only readiness
audit.

Mechanism insight: the system is no longer completely blind on LLM artifacts,
but it is still far from the sample depth needed for ranking-alpha acceptance
or rejection. The next bottleneck is durable replay coverage, not prompt
micro-tuning.

Do not repeat: changing LLM ranking logic, weakening LLM scope, or rerunning
another readiness audit without new archived days. A valid retry needs more
production-aligned replay samples, not another static status check.


### 2026-05-01 mechanism update: AI optical/storage watchlist

Status: rejected.

Core conclusion: `exp-20260501-015` tested whether the cleaner AI infrastructure
optical/storage-semi subset (`INTC + LITE`) could avoid the BE old-tape
fragility seen in the broader pool. It should not be promoted.

Evidence: best variant `add_intc_only_control` produced aggregate PnL delta
`$10,643.51` / `8.21%` and
aggregate EV delta `+0.4869`. It did not
clear the multi-window production gate: EV improved in
`1` windows, regressed in
`0`, and minimum win-rate delta was
`-0.0276`.

Mechanism insight: removing the fragile power names cleans up the old-tape loss
source, but the remaining optical/storage-semi effect is still too
late-window-concentrated for a raw production watchlist addition.

Do not repeat: promoting `INTC + LITE`, `LITE` alone, or `INTC` alone as a raw
watchlist addition without forward evidence or event/news confirmation.

Next valid retry requires: forward evidence, a point-in-time event/news
discriminator, or a broader theme rule that improves at least two fixed windows
without win-rate degradation.


### 2026-05-01 mechanism update: Regime-gated AI infra watchlist

Status: rejected.

Core conclusion: `exp-20260501-016` tested whether the positive-but-fragile AI
infrastructure watchlist lead could be rescued by enabling added `BE` / `INTC`
candidates only in supportive broad-market states. It should not be promoted.

Evidence: best variant `be_intc_bull_positive` produced aggregate PnL delta
`$18,948.85` / `14.62%` and
aggregate EV delta `+0.8562`. Fixed-window
gate status: EV improved in `2` windows, regressed
in `1`, and minimum win-rate delta was
`-0.0276`.

Mechanism insight: a simple broad-tape activation gate is not enough to turn AI
infra names into a production-ready universe addition. The pool still needs
forward evidence or point-in-time event/news confirmation, not another raw
subset or broad BULL-only switch.

Do not repeat: raw `BE + INTC`, raw `INTC`, raw `INTC + LITE`, or simple
BULL/positive-SPY activation gates for these AI infra candidates without new
forward or event/news evidence.

### 2026-05-01 mechanism update: Technology A/B cofire trend preference

Status: rejected.

Core conclusion: `exp-20260501-017` tested whether same-ticker Technology
signals that co-fire `trend_long` and `breakout_long` should prefer the
`trend_long` sleeve, so the accepted Technology wider target can operate. It
should not be promoted.

Evidence: the variant was unchanged in `late_strong` and `old_thin`, but
damaged `mid_weak`: EV `1.2036 -> 0.9078`, PnL `-$8,021.42`, daily Sharpe
`2.58 -> 2.35`, and win rate `52.38% -> 47.62%`. Across the three fixed
windows, aggregate EV fell `-0.2958` and aggregate PnL fell `-6.19%`.

Mechanism insight: the accepted Technology trend wider target does not imply
that every Technology A/B cofire should route to trend. In the active
`mid_weak` sample, suppressing the breakout side changed slot/position paths in
a harmful way, even though the rule looked lifecycle-consistent.

Do not repeat: Technology cofire trend preference, global same-day trend-first,
or using the accepted Technology target extension as a generic reason to
override native A/B dedup. A valid retry needs forward evidence or an
orthogonal event/news discriminator showing which cofires specifically deserve
the trend lifecycle.
### 2026-05-01 mechanism update: TRIP sector metadata allocation path

Status: rejected.

Core conclusion: `exp-20260501-018` tested whether classifying the existing
production-universe ticker `TRIP` as Consumer Discretionary would improve
capital allocation by routing it through sector-aware sizing and event-distance
rules instead of the Unknown/plain risk-on path. It should not be promoted.

Evidence: the three canonical windows were unchanged: `late_strong` EV
`2.7000 -> 2.7000`, `mid_weak` EV `1.2036 -> 1.2036`, and `old_thin` EV
`0.2563 -> 0.2563`; PnL, Sharpe, drawdown, win rate, trade count, and survival
were also unchanged. The code change was rolled back.

Mechanism insight: single-ticker sector metadata cleanup is not automatically
alpha. In this case, the existing accepted rules did not turn the corrected
sector into a different tradable path, so the fixed-window result was
economically inert.

Do not repeat: re-adding `TRIP` to `SECTOR_MAP` as an alpha change without a
broader Unknown-sector distortion audit or a production-shared rule that
actually depends on the corrected sector metadata.

### 2026-05-01 mechanism update: Precious breakout target width

Status: rejected.

Core conclusion: `exp-20260501-019` tested whether the accepted gold/commodity
trend continuation target should extend to `GLD` / `IAU` / `SLV`
`breakout_long` signals. It should not be promoted.

Evidence: the best variant, `precious_breakout_5_5atr`, improved only
`late_strong`: EV `2.7000 -> 2.7990`, PnL `+$1,261.80`, daily Sharpe
`4.30 -> 4.37`. `mid_weak` and `old_thin` were strict nulls, leaving aggregate
EV delta at only `+2.38%` and aggregate PnL delta at `+0.97%`. Wider 6/7 ATR
variants damaged `late_strong` EV and drawdown.

Mechanism insight: accepted trend convexity in gold/commodities does not
automatically transfer to breakout exits. The breakout sleeve either lacks
enough cross-window sample or has a different lifecycle shape from trend.

Do not repeat: nearby precious-metals breakout ATR target sweeps without
forward evidence or event/news context. A valid retry needs a materially
different breakout lifecycle discriminator, not another 5.5/6/7 ATR target.

### 2026-05-01 mechanism update: Financials leader target width

Status: rejected.

Core conclusion: `exp-20260501-020` tested whether the accepted Financials
sector-relative leader discriminator could extend from risk sizing into a
wider trend target. It should not be promoted.

Evidence: best variant `financials_leader_6_0atr` left `late_strong` unchanged
because no Financials leader trades fired there, but damaged both active
windows: `mid_weak` EV `1.2036 -> 0.8260`, PnL `-$7,139.01`, daily Sharpe
`-0.49`; `old_thin` EV `0.2563 -> 0.0750`, PnL `-$10,569.00`, daily Sharpe
`-0.49`, max drawdown `+4.94 pp`. Aggregate EV fell `-0.5589` and aggregate
PnL fell `-13.66%`.

Mechanism insight: Financials sector leadership is useful for entry sizing,
but not for delaying exits. The wider target enlarged or converted losses in
the rotation-heavy and older tapes, so "leader can carry more risk" does not
mean "leader should be held for more ATR."

Do not repeat: Financials leader target-width sweeps around 5-6 ATR, broad
Financials target widening, or using the accepted Financials leader risk budget
as evidence for exit convexity without event/news or forward confirmation.

Next valid retry requires: an orthogonal event/news or lifecycle discriminator
that explains why a specific Financials leader should avoid the delayed-exit
damage seen in `mid_weak` and `old_thin`.

### 2026-05-03 mechanism update: Financials leader position cap

Status: rejected / too small.

Core conclusion: `exp-20260503-050` tested whether the already accepted
Financials sector-leader trend sleeve was constrained by the global 40% initial
position cap. The direction was positive where the sleeve traded, but the effect
size was too small for promotion.

Evidence: best variant `financials_leader_cap_50pct` left `late_strong`
unchanged because no Financials leader trades fired, improved `mid_weak` EV
`+0.0405` / PnL `+$1,332.28`, and improved `old_thin` EV `+0.0163` / PnL
`+$1,069.11`. Aggregate EV improved only `+1.10%` and aggregate PnL only
`+1.52%`, below Gate 4; max drawdown worsened slightly by up to `+0.24 pp`.

Mechanism insight: the accepted Financials leader risk-budget edge is real but
not materially cap-bound after the current accepted stack. More cap scalar
tuning around 45-50% is low-value without new forward concentration evidence.

Do not repeat: nearby Financials sector-leader initial-position cap scalars,
broad Financials cap unlocks, or treating the 2.5x leader risk budget as proof
that this sleeve deserves more concentration.

Next valid retry requires: a materially different lifecycle or event/news
discriminator that explains why the few cap-bound Financials leaders should
carry more concentration than the existing 40% cap allows.

### 2026-05-01 mechanism update: Consumer near-high DTE risk window

Status: rejected.

Core conclusion: `exp-20260501-021` tested whether the accepted Consumer Discretionary near-high trend event-risk haircut should cover a wider DTE window. It should not be promoted.

Evidence: best variant `consumer_near_high_dte_15_90` produced aggregate EV delta `+0.0000` and aggregate PnL delta `$+0.00`, with EV improving in `0` windows and regressing in `0`.

Mechanism insight: Consumer near-high event-distance widening is only useful if it changes realized allocations across multiple windows; otherwise the existing narrow 30-65 DTE pocket remains the cleaner shared sizing rule.

Do not repeat: nearby Consumer near-high DTE window sweeps without event/news confirmation or a broader Consumer loss-family audit.

### 2026-05-01 mechanism update: Healthcare relative laggard risk cap

Status: rejected.

Core conclusion: `exp-20260501-023` tested whether Healthcare signals whose
20-day return lagged the equal-weight Healthcare sector 20-day return should
receive a lower total risk cap. It should not be promoted.

Evidence: best variant `healthcare_laggard_0x` produced aggregate EV delta
`+0.0000` and aggregate PnL delta `$+0.00`, with EV improving in `0` windows
and regressing in `0`. The partial `0.25x` variant damaged `late_strong`
because it reduced a Healthcare winner while still missing the mid/old
Healthcare losers.

Mechanism insight: sector-relative Healthcare laggard status did not identify
the residual Healthcare loss family. This is not evidence for a broader
Healthcare ban; it is evidence that the remaining Healthcare losses require a
different context source, likely event/news or a larger multi-window failure
family.

Do not repeat: Healthcare sector-relative laggard 0x/0.25x caps, or nearby
Healthcare relative-strength scalar variants, without forward evidence or an
orthogonal event/news discriminator.

### 2026-05-01 mechanism update: Liquid proxy ETF universe expansion

Status: rejected.

Core conclusion: `exp-20260501-025` tested whether already-snapshotted liquid
proxy ETFs could improve candidate-pool quality without fetching new data or
adding noisy single-name themes. It should not be promoted.

Evidence: best variant `all_liquid_proxy_etfs` added `XLE`, `XLV`, `XLP`,
`XLU`, `USO`, `IEF`, `TLT`, and `UUP`. It improved `late_strong` sharply
(`EV +0.7335`, PnL `+$10,700.99`, Sharpe daily `+0.34`) but regressed both
weaker validation windows: `mid_weak` EV `-0.3080` / PnL `-$11,099.59` and
`old_thin` EV `-0.0237` / PnL `-$530.79`. Aggregate PnL fell `-$929.39`, EV
improved in only 1/3 windows, and win rate worsened in every window.

Mechanism insight: liquid ETF proxies can amplify strong-tape trend capture,
but they do not solve the weak/rotational window. In the current A/B rules they
mostly add slot competition and defensive-looking trades without stable
replacement value.

Do not repeat: raw sector/rate/defensive ETF bundle additions, or nearby
`XLE`/`XLV`/`XLP`/`XLU`/`USO`/`IEF`/`TLT`/`UUP` candidate-pool tests, without
forward evidence, event/news confirmation, or slot-aware replacement evidence
that specifically fixes the mid/old-window damage.

### 2026-05-01 mechanism update: Trend Technology leader risk recovery

Status: rejected.

Core conclusion: `exp-20260501-026` tested whether trend Technology signals
already reduced by accepted Technology risk pockets should recover risk budget
when their 20-day return exceeded the equal-weight Technology sector 20-day
return. It should not be promoted.

Evidence: best variant `tech_leader_recovery_0_50x` resized 24 candidate
signals across the three fixed windows and regressed every window: aggregate
EV delta `-0.2497`, aggregate PnL delta `-$4,812.94`, `late_strong` PnL
`-$903.89`, `mid_weak` PnL `-$2,812.69`, and `old_thin` PnL `-$1,096.36`.
The 0.75x variant was worse with aggregate PnL `-$7,127.73`.

Mechanism insight: the rejected Technology sector-leader de-risking result does
not imply the inverse rule is useful. Sector-relative Technology leadership is
still too blunt to override the accepted lifecycle/gap/DTE haircuts; it changes
slot and sizing paths in a way that damages all tapes.

Do not repeat: Technology sector-relative leader risk recovery around
0.5x/0.75x/1.0x, or using relative-return leadership alone to loosen accepted
Technology haircuts. A valid retry needs event/news or richer lifecycle
evidence that separates delayed winners from fragile leaders.

### 2026-05-01 mechanism update: Risk-on SPY-relative leader lookback

Status: rejected.

Core conclusion: `exp-20260501-028` tested whether the accepted
otherwise-unmodified `risk_on` SPY-relative leader allocation should use a
shorter 10-day relative-strength lookback instead of the current 20-day
lookback. It should not be promoted.

Evidence: the 10-day variant was bit-identical across the three canonical
windows: aggregate EV delta `+0.0000`, aggregate PnL delta `$+0.00`, no Sharpe,
drawdown, win-rate, trade-count, or survival-rate movement.

Mechanism insight: the accepted SPY-relative leader allocation already captures
the active fixed-window inventory; simply changing the momentum observation
horizon does not create a new production-relevant allocation path.

Do not repeat: nearby SPY-relative lookback sweeps such as 5/10/15/30 trading
days, or using another plain ticker-vs-SPY horizon as the only discriminator.
A valid retry needs event/news or richer lifecycle context, not another
relative-strength lookback.

### 2026-05-01 mechanism update: Risk-on SPY-relative leader lifecycle split

Status: rejected.

Core conclusion: `exp-20260501-031` tested whether the accepted
otherwise-unmodified `risk_on` SPY-relative leader allocation should split by
signal lifecycle. It should not be promoted.

Evidence: breakout-leader amplification to 2.25x added raw aggregate PnL
`+$1,147.01`, but EV fell `-0.0142` and EV regressed in 2/3 windows. The 2.5x
variant was worse with EV `-0.0405` and higher drawdown. Trend-leader
de-risking to 1.5x lowered `old_thin` drawdown by 1.35 pp, but aggregate EV
fell `-0.1359` and PnL fell `-$4,108.66`; 1.25x damaged EV and PnL further.

Mechanism insight: lifecycle alone is not enough to improve the accepted
SPY-relative leader rule. Breakout leaders can add raw PnL while worsening risk
efficiency, and trend leader de-risking cuts convex winners more than it removes
losses.

Do not repeat: breakout-leader multipliers above 2.0, trend-leader de-risking
around 1.25x/1.5x, or lifecycle-only splits of the accepted SPY-relative
leader allocation. A valid retry needs event/news or richer lifecycle evidence
that improves EV, not just raw PnL or drawdown.

### 2026-05-02 mechanism update: Risk-on breadth-confirmed leader allocation

Status: rejected.

Core conclusion: `exp-20260502-001` tested whether the accepted plain
`risk_on` SPY-relative leader boost should require IWM-vs-SPY breadth
confirmation. It should not be promoted.

Evidence: best variant `breadth_confirmed_2_0x_else_1_6x` regressed all three
canonical windows: aggregate EV delta `-0.1694`, aggregate PnL delta
`-$3,350.98`, and EV/PnL improved in `0/3` windows. The more aggressive
`2.25x` confirmed variant also failed.

Mechanism insight: small-cap breadth confirmation is not a useful refinement
for the accepted SPY-relative leader allocation in the current stack. The
existing SPY-relative rule appears to be capturing selected cap-weight
leadership rather than a broad-market breadth condition.

Do not repeat: nearby IWM/SPY breadth scalars, or de-risking SPY-relative
leaders solely because IWM lags SPY, without forward evidence or a richer
dispersion/event discriminator.

### 2026-05-02 mechanism update: Risk-on sector-confirmed leader allocation

Status: rejected.

Core conclusion: `exp-20260502-002` tested whether the accepted plain
`risk_on` SPY-relative leader boost should require same-sector 20-day
equal-weight return to also beat SPY. It should not be promoted.

Evidence: best variant `sector_confirmed_2_0x_else_1_6x` produced aggregate EV
delta `-0.0794` and aggregate PnL delta `-$3,180.49`. `old_thin` improved only
slightly (`EV +0.0038`, PnL `+$123.47`), `mid_weak` was unchanged, and
`late_strong` regressed (`EV -0.0832`, PnL `-$3,303.96`) despite a small
drawdown improvement.

Mechanism insight: sector synchronization is too blunt for refining the
accepted SPY-relative leader sleeve. The accepted rule appears to capture
selected ticker leadership that can remain valuable even without equal-weight
sector confirmation; cutting unconfirmed leaders mostly removed late-window
convexity.

Do not repeat: nearby sector-confirmed SPY leader scalars, same-sector
confirmation as a hard requirement for risk-on leaders, or sector-vs-SPY
threshold sweeps without event/news or richer dispersion context.


### 2026-05-02 mechanism update: Event-guarded AI infra pool

Status: rejected.

Core conclusion: `exp-20260502-003` tested whether AI infrastructure candidates
should be eligible only when the existing earnings-distance field shows more
than 20 trading days to earnings. This was an event-risk qualification policy,
not another raw AI infra promotion or broad BULL-state switch.

Evidence: best variant `optical_storage_event_guarded` produced aggregate EV delta
`-0.0478` and aggregate PnL delta
`$-744.80` / `-0.53%`;
EV improved in `0` windows and regressed in
`2`.

Mechanism insight: raw AI infra expansion still needs forward/event evidence.
The earnings-distance guard alone is not enough unless it clears the fixed-window
Gate 4 policy and can be shared by production and backtest.

Do not repeat: raw AI infra core-pool promotion, simple BULL-only activation, or
nearby event-distance guard thresholds without new forward or event/news evidence.

### 2026-05-02 mechanism update: State-conditioned entry cluster cap

Status: rejected.

Core conclusion: `exp-20260502-004` tested whether same-day new-entry clusters
should be capped at two entries when broad index state is weak. It should not be
promoted.

Evidence: both variants, `cap2_when_min_index_below_0` and
`cap2_when_min_index_below_2pct`, were bit-identical to baseline across the
three canonical windows. Aggregate EV delta was `+0.0000`, aggregate PnL delta
was `$+0.00`, and the cap triggered `0` times.

Mechanism insight: the 2026-01-06 loss cluster is not evidence that a weak-index
same-day entry cap is a live bottleneck in the current accepted stack. Existing
slot, sector, heat, and entry gates already prevent this proposed condition from
changing realized exposure.

Do not repeat: same-day entry-cluster caps based only on
`min(SPY pct-from-MA, QQQ pct-from-MA)` thresholds near `0%` / `2%`, or using
the 2026-01-06 cluster as a standalone reason for a production filter. A valid
retry needs forward evidence or an orthogonal event/news discriminator.

### 2026-05-02 mechanism update: Commodity breakout leader risk budget

Status: rejected.

Core conclusion: `exp-20260502-005` tested whether otherwise-unmodified
`risk_on` Commodity `breakout_long` signals that already qualify as
SPY-relative leaders should receive more total risk. It should not be promoted.

Evidence: both 3.0x and 4.0x variants resized the intended candidates, but the
three canonical windows were bit-identical: aggregate EV delta `+0.0000` and
aggregate PnL delta `$+0.00`. The selected GLD/IAU/SLV-style breakout leaders
were already constrained by the 40% single-position cap, so higher risk budget
could not express in realized trades.

Mechanism insight: this commodity breakout sleeve is capacity-capped, not
risk-budget-capped. Do not retry nearby commodity breakout leader risk
multipliers; the bottleneck is position concentration, not the nominal risk
scalar.

Do not repeat: commodity breakout leader risk multipliers around 3x/4x, or
using this result as evidence for precious-metals breakout target widening.

### 2026-05-02 mechanism update: Commodity breakout leader position cap

Status: rejected, positive but below Gate 4.

Core conclusion: `exp-20260502-006` tested whether the capacity-capped
Commodity `breakout_long` SPY-relative leader sleeve should receive a higher
single-position cap. It should not be promoted.

Evidence: best variant `commodity_breakout_leader_cap_60pct` improved
`late_strong` EV by `+0.1521` / PnL `+$3,358.14` and `mid_weak` EV by
`+0.0860` / PnL `+$1,996.49`, with `old_thin` unchanged. Aggregate EV improved
`+0.2381` (`+5.31%`) and aggregate PnL improved `+$5,354.63` (`+3.87%`), but
this missed Gate 4's `>10%` EV or `>5%` PnL thresholds. The main cost was
`late_strong` max drawdown rising `+0.96 pp`, close to the 1 pp guardrail.

Mechanism insight: the sleeve has real positive directionality, but the
incremental edge is not large enough to justify weakening the accepted 40%
single-position cap. A larger cap might clear raw PnL but would likely do so by
adding concentration and drawdown, not by discovering a new robust alpha.

Do not repeat: nearby commodity breakout leader cap levels such as 50%/60% or
larger concentration unlocks without forward evidence, event/news
confirmation, or a lifecycle discriminator that reduces the drawdown cost.

### 2026-05-02 mechanism update: LLM decision-outcome join readiness

Status: observed-only.

Core conclusion: `exp-20260502-007` produced a read-only join manifest between
production-aligned LLM ranking samples and replay trade outcomes. It did not
change strategy behavior, but it made the current blocker explicit.

Evidence: only `1` of the current `8` effective LLM candidate rows could be
scored against replay trades. Metrics were unchanged by construction.

Mechanism insight: the next LLM soft-ranking experiment is still blocked by
outcome attribution sparsity, not by lack of new prompt ideas. Do not treat
dated replay coverage as equivalent to usable ranking-alpha sample.

Do not repeat: another LLM ranking prompt iteration before more
production-aligned outcome-join coverage exists.

### 2026-05-02 mechanism update: Liquid recent-listing shadow universe

Status: observed-only.

Core conclusion: `exp-20260502-008` shadow-audited a liquid recent-listing
cohort (`APP`, `COIN`, `CRDO`, `DDOG`, `PLTR`, `SNOW`). It is not
production-ready.

Evidence: candidate count was `0/9/6` across the three windows, same-day A/B
overlap was `0/6/3` with weighted overlap `60%`, and forward returns across
the `15` candidates were negative on 5/10/20-day horizons (`-2.31%`, `-2.23%`,
`-4.12%`). Outside-production constituent coverage remained `0`.

Mechanism insight: recent-listing momentum is not blocked by liquidity in the
current snapshots; it is blocked by source validity, overlap, and poor forward
quality. This should stay a scout artifact, not a raw watchlist promotion.

Do not repeat: this recent-listing cohort as a direct production universe
addition without a true PIT source and slot-aware replacement replay.

### 2026-05-02 mechanism update: Scarce-slot routing and MFE giveback audit

Status: rejected / observed-only mixed audit.

Core conclusion: `exp-20260502-009` tested a point-in-time scarce-slot strong
candidate insertion replay and paired it with an observation-only MFE giveback
audit. The insertion rule should not be promoted.

Evidence: aggregate EV fell `-0.1076` and aggregate PnL fell `-$6,599.57`.
`mid_weak` improved (`EV +0.0601`, `PnL +$3,505.29`), but `old_thin`
regressed sharply (`EV -0.1677`, `PnL -$10,104.86`). The accompanying audit
showed `12` old-thin losses that first had positive MFE, with total
giveback `+$21,831.29` before turning into realized losers.

Mechanism insight: weak-window slot pressure is real, but a generic
leadership-score replacement rule is not the right fix. The reusable takeaway
is the audit: future lifecycle work should explain which positive-MFE losers
deserved protection without replaying the same broad slot swap idea.

Do not repeat: generic scarce-slot replacement using PIT leadership score alone
or another nearby slot-swap replay without a stricter event/news or lifecycle
discriminator.

### 2026-05-02 mechanism update: Fresh positive clean-news intensity scout

Status: observed-only.

Core conclusion: `exp-20260502-010` shadow-audited a fresh multi-headline
positive clean-news intensity mechanism. It is not production-ready.

Evidence: the scout found `23` candidates, all inside `late_strong`, with `0`
same-day A/B overlap. Short-horizon quality was mixed: `5d avg +1.21%`
(`55.6%` win rate), but `10d avg -0.49%` (`30.8%`) and `20d avg -1.89%`
(`27.3%`). Scarce-slot comparison count was `1` and negative.

Mechanism insight: fresh clean-news intensity may create attention, but without
better persistence or replayable ranking context it does not yet clear the bar
for a new sleeve. This is a scout for future event-grading work, not evidence
for raw news-only promotion.

Do not repeat: a raw clean-news intensity sleeve without stronger persistence,
replacement evidence, or LLM/event-grading context.

### 2026-05-02 mechanism update: Wide-stop SPY-relative leader risk

Status: rejected.

Core conclusion: `exp-20260502-013` tested whether otherwise-unmodified
`risk_on` SPY-relative leaders with wide initial stop distance (`initial_risk_pct
>= 6%`) should receive more total risk. It should not be promoted.

Evidence: the best variant, `wide_stop_06_total_3_0x`, added aggregate PnL
`+$7,191.72` / `+5.19%`, but EV fell `-0.0452` / `-1.01%`. `late_strong`
regressed on EV (`-0.1044`) and Sharpe (`-0.36`) while max drawdown increased
`+1.41 pp`; `old_thin` improved (`EV +0.0592`, PnL `+$3,508.86`), and
`mid_weak` was unchanged.

Mechanism insight: wide-stop SPY leaders can add raw dollars, but the gain is
mostly paid for with lower risk efficiency and worse strong-window drawdown. In
the current stack, initial stop width alone is not enough to separate convex
leaders from fragile high-volatility exposure.

Do not repeat: nearby wide-stop SPY-relative leader thresholds such as 5-7%, or
2.5x/3.0x total-risk variants, without forward evidence or an orthogonal
event/news/lifecycle discriminator.

### 2026-05-02 mechanism update: MFE-giveback SMA protective exit

Status: rejected.

Core conclusion: `exp-20260502-014` tested whether a path-aware protective exit
should sell after meaningful MFE, large giveback, and a close below the 5-day
SMA. It should not be promoted.

Evidence: best variant `mfe_07_giveback_50_sma5` regressed aggregate EV by
`-0.5726` (`-12.78%`) and aggregate PnL by `-$15,834.98` (`-11.43%`). It
improved only `old_thin` slightly (`EV +0.0089`, PnL `+$713.73`) while
damaging `late_strong` (`EV -0.3849`, PnL `-$8,930.71`) and `mid_weak`
(`EV -0.1966`, PnL `-$7,618.00`). Across 9 triggers it improved losers by
`+$4,312.33` but truncated 6 winners by `-$20,147.31`.

Mechanism insight: price-path giveback protection still cuts convex winners
more than it saves failed trades, even when it is narrower than the rejected
simple breakeven stop. The old-thin MFE-giveback family is real, but OHLCV-only
path weakness is not enough to identify which winners deserve protection.

Do not repeat: nearby MFE thresholds around 5-7%, giveback thresholds around
50-60%, or SMA5 breakdown variants as executable exits. A valid retry needs an
orthogonal event/news or lifecycle discriminator that explains winner
collateral before touching production exit policy.

### 2026-05-02 mechanism update: SPY leader absolute-momentum floor

Status: rejected.

Core conclusion: `exp-20260502-015` tested whether otherwise-unmodified
`risk_on` SPY-relative leaders should keep the accepted 2.0x risk budget only
when their own 20-day return was positive or at least +5%. It should not be
promoted.

Evidence: `positive_20d_else_1_25x` and `positive_20d_else_1_50x` were
bit-identical across all three canonical windows. The stricter
`five_pct_20d_else_1_25x` variant regressed aggregate EV by `-0.0047` and PnL
by `-$182.72`, with no Gate 4 criterion passed.

Mechanism insight: the accepted SPY-relative leader sleeve is not carrying a
live weak-absolute-momentum leak in the fixed-window inventory. A simple
absolute 20-day return floor either does not bind or cuts a small amount of
useful exposure.

Do not repeat: nearby absolute 20-day return floors for SPY-relative leaders
such as `>0%`, `>3%`, or `>5%`, or fallback multipliers around `1.25x/1.5x`,
without forward evidence or an orthogonal event/news/lifecycle discriminator.

### 2026-05-02 mechanism update: SPY leader sector whitelist

Status: rejected.

Core conclusion: `exp-20260502-016` tested whether otherwise-unmodified
`risk_on` SPY-relative leaders should keep the accepted 2.0x risk budget only
inside a sector whitelist, with non-whitelisted leader sectors falling back to
1.5x total risk. It should not be promoted.

Evidence: best variant `persistent_sector_else_1_5x` improved EV in `mid_weak`
and `old_thin` only marginally, but damaged `late_strong` enough that aggregate
EV fell `-0.1907` (`-4.25%`) and aggregate PnL fell `-$3,251.64` (`-2.35%`).
The old-thin drawdown improvement is not enough to override the north-star EV
regression.

Mechanism insight: the accepted SPY-relative leader sleeve still needs selected
one-window convex contributors; a static sector whitelist mostly cuts late-tape
convexity rather than removing a robust weak-window leak. Sector membership
alone is too blunt as the next discriminator.

Do not repeat: nearby SPY-relative leader sector whitelists, sector blacklists,
or fallback multipliers around 1.5x without forward evidence or an orthogonal
event/news/lifecycle discriminator.

### 2026-05-02 mechanism update: Trend-only SPY leader non-core fallback

Status: rejected / observed-positive below Gate 4.

Core conclusion: `exp-20260502-017` tested whether the accepted 2.0x
SPY-relative leader budget should stay broad for `breakout_long` but fall back
for `trend_long` leaders outside repeat-positive trend sectors. This was a
sleeve-specific attempt to avoid repeating the rejected all-sleeve sector
whitelist.

Evidence: best variant `trend_noncore_else_1_00x` improved `late_strong` EV by
`+0.0495`, left `mid_weak` unchanged, and improved `old_thin` EV by `+0.0406`.
Aggregate EV rose only `+0.0901` (`+2.01%`) and aggregate PnL rose `$2,391.56`
(`+1.73%`), below Gate 4 materiality; Sharpe improved at most `+0.08`.

Mechanism insight: non-core `trend_long` SPY leaders are a plausible leakage
source, but the fixed-window effect is too small and sparse for production
promotion. The right next step is forward evidence or a stronger lifecycle/event
discriminator, not another nearby fallback multiplier.

Do not repeat: trend-only SPY leader non-core fallback values around
`1.0x/1.25x/1.5x`, or simple non-core sector blacklists, without new forward
evidence or an orthogonal event/news/lifecycle discriminator.
### 2026-05-02 mechanism update: Breakout extreme range risk haircut

Status: rejected.

Core conclusion: `exp-20260502-018` tested whether `breakout_long` signals
with signal-day `daily_range_vs_atr` at or above 2.5x/3.0x should receive a
simple risk haircut. It should not be promoted.

Evidence: best variant `range_2_5_atr_0_25x` improved only `mid_weak`
(`EV +0.0140`, PnL `+$355.10`) and was unchanged in `late_strong` and
`old_thin`. Aggregate EV delta was only `+0.0031` pct of baseline and
aggregate PnL delta was only `+0.26%`, below Gate 4. Exposure was also thin:
only three eligible signals across the fixed three-window set.

Mechanism insight: signal-day range extension is not a strong standalone
breakout exhaustion discriminator in the current stack. The tiny positive
mid-window movement is not enough to justify a production sizing rule, and the
absence of exposure in the other two windows makes nearby threshold tuning
mostly curve-fitting.

Do not repeat: global `breakout_long` daily-range-vs-ATR haircuts around
2.5x/3.0x or simple 0.25x/0.50x multipliers. A valid retry needs a richer
condition such as event/news confirmation or hold-path attribution that
separates true exhaustion from institutional breakout demand.

### 2026-05-02 mechanism update: Narrow proxy ETF candidate pool

Status: rejected.

Core conclusion: `exp-20260502-019` tested whether the failed broad liquid proxy
ETF expansion could be rescued by excluding the known `USO` / `XLP` drag and
using a narrower already-snapshotted proxy set (`XLE`, `XLV`, `TLT`, optionally
`IEF`). It should not be promoted.

Evidence: the best variant `energy_healthcare_rate` regressed aggregate EV by
`-0.2795` (`-6.24%`) and aggregate PnL by `-$4,705.58` (`-3.40%`). It added
late-window raw PnL (`+$3,817.39`) but lowered late-window EV (`-0.0403`) and
Sharpe (`-0.28`), while `mid_weak` regressed sharply (`EV -0.2392`, PnL
`-$8,522.97`). `old_thin` was unchanged.

Mechanism insight: the proxy ETF idea is not failing only because of `USO` or
`XLP`. Even the cleaner energy/healthcare/rate proxy subset disrupts slot
competition and risk efficiency in the fixed windows. Added proxy trades can
make money in a strong tape while still lowering EV once displaced core
opportunities, win rate, drawdown, and Sharpe are counted.

Do not repeat: nearby proxy ETF subsets such as `XLE`/`XLV`, adding `TLT`/`IEF`,
or another hand-selected liquid proxy bundle without forward evidence, event
context, or a production-ready regime route that explains when proxy exposure
should replace core single-name exposure.

### 2026-05-02 mechanism update: Trend mid-stop risk haircut

Status: rejected.

Core conclusion: `exp-20260502-020` tested whether `trend_long` signals with
initial stop distance in the 5%-7% band should receive a simple risk haircut.
It should not be promoted.

Evidence: the best variant, `mid_stop_5_7pct_0_25x`, improved `old_thin` EV by
`+0.0979`, PnL by `+$3,200.00`, Sharpe by `+0.23`, and max drawdown by
`-2.03 pp`, but it regressed `mid_weak` EV by `-0.0121` and PnL by `-$475.60`;
`late_strong` was unchanged. Aggregate EV improved only `+0.0858` (`+1.91%`)
and aggregate PnL improved `+$2,724.40` (`+1.97%`), below Gate 4, with EV
improvement in only 1/3 windows.

Mechanism insight: the old-thin 5%-7% trend stop pocket is real, but stop width
alone is not a stable production discriminator. The same haircut trims useful
mid-window exposure, while the profitable `>=7%` trend bucket confirms this is
not a monotonic "wide stop is bad" rule.

Do not repeat: nearby 5%-7% trend initial-risk haircuts, simple trend stop-width
haircuts, or attempts to rescue this with adjacent 0.25x/0.50x multipliers. A
valid retry needs event/news context or a lifecycle discriminator that separates
fragile wide stops from convex winners.

### 2026-05-02 mechanism update: SPY-relative leader follow-through add-on cap

Status: accepted.

Core conclusion: `exp-20260502-022` tested whether the already accepted
SPY-relative leader sleeve was still cap-constrained after entry. Raising only
the first day-2 follow-through add-on cap from the global 35% add-on cap to 60%
passed the canonical three-window Gate 4 check versus the `exp-20260502-021`
stack: aggregate PnL improved `+$9,346.49` (`+6.28%`), aggregate EV improved
`+0.3536` (`+7.33%`), and EV improved in all three windows.

Keep this narrow: the rule applies only to the first follow-through add-on for
positions that qualified as SPY-relative leaders at entry. It does not change
entries, exits, candidate ordering, global add-on triggers, or non-leader
add-on capacity.

Cost: `mid_weak` max drawdown rose from `7.99%` to `8.79%`. This is acceptable
under the current Gate 4 and convergence caps, but it makes further nearby cap
expansion a concentration-risk experiment rather than a default next step.

Do not repeat: SPY-relative leader add-on caps above 60%, broader add-on cap
unlocks, or second-add-on variants without forward/tail evidence or an
orthogonal event/news discriminator.

### 2026-05-02 mechanism update: SPY-relative leader target floor

Status: rejected.

Core conclusion: `exp-20260502-023` tested whether 20-day SPY-relative leaders
were still being lifecycle-clipped by the current regime-aware target width.
Simple 5.0 ATR and 6.0 ATR target floors should not be promoted.

Evidence: the best variant, `spy_leader_target_floor_5_0atr`, regressed EV in
all three canonical windows. Aggregate EV fell `-1.0872` (`-20.99%`) and
aggregate PnL fell `-$17,855.57` (`-11.28%`). `late_strong` gained only
`+$205.55` raw PnL while Sharpe dropped `-0.55`; `mid_weak` lost `-$11,393.85`;
`old_thin` lost `-$6,667.27` and max drawdown rose `+6.59 pp`. The 6.0 ATR
floor was worse.

Mechanism insight: the accepted SPY-relative leader sleeve is not simply
target-clipped. Its current edge comes from sizing, cap, and first add-on
capacity working with the existing exit profile. A blunt wider target reduces
risk efficiency and lets weak-window leaders give back too much.

Do not repeat: nearby SPY-relative leader target floors around 5-6 ATR or
simple leader-wide target extension. A valid retry needs event/news or
lifecycle evidence that separates leaders deserving more room from leaders
whose current target should remain intact.

### 2026-05-02 mechanism update: Portfolio heat capacity

Status: rejected, positive but below Gate 4.

Core conclusion: `exp-20260502-025` tested whether the accepted SPY-relative
leader initial-cap and first-add-on cap increases exposed `MAX_PORTFOLIO_HEAT`
as the next binding capacity constraint. Raising the global heat cap from 8%
to 9%, 10%, or 12% should not be promoted.

Evidence: the best variant, `heat_cap_12pct`, improved EV and PnL in all three
canonical windows, but the effect was too small for Gate 4: aggregate EV
improved `+0.1318` (`+2.55%`) and aggregate PnL improved `+$3,924.94`
(`+2.48%`). Sharpe moved only `-0.01`, `+0.04`, and `+0.02` across the three
windows, trade count and win rate did not change, and the improvement came from
three extra add-on increments rather than a clear new entry opportunity.

Mechanism insight: the global heat cap is directionally a real capacity
constraint after the accepted leader-cap changes, but the unlocked exposure is
not material enough to justify weakening a hard portfolio risk limit. This is
a forward-observation candidate, not a production change.

Do not repeat: nearby global heat caps around 9-12% without forward
concentration evidence or a narrower production-shared capacity discriminator.
Do not pair heat-cap changes with entry, add-on, or target changes in the same
experiment.

### 2026-05-02 mechanism update: SPY leader upside-gap exception

Status: rejected, no exposure.

Core conclusion: `exp-20260502-026` tested whether the accepted SPY-relative
leader sizing state could serve as the orthogonal discriminator needed to relax
the existing 1.5% upside gap cancel. It should not be promoted.

Evidence: the variant had zero eligible exceptions in all three canonical
windows. Metrics were bit-identical: aggregate EV delta `+0.0000`, aggregate
PnL delta `$+0.00`, and no trade-count, win-rate, drawdown, or survival change.

Mechanism insight: this is not currently an actionable fixed-window alpha
surface. The gap-cancel leak visible in skip audits is not explained by the
accepted SPY-relative leader sizing state.

Do not repeat: SPY-relative leader upside-gap exceptions without forward
evidence of nonzero exposure, and do not rerun global `CANCEL_GAP_PCT` sweeps
around 1-5%. A valid retry needs event/news confirmation or another
production-visible discriminator with actual exposure.

### 2026-05-02 mechanism update: Initial-risk 5-6% sizing haircut

Status: rejected.

Core conclusion: `exp-20260502-027` tested whether the current accepted stack's
5-6% initial stop-distance bucket should receive a simple sizing haircut. It
should not be promoted.

Evidence: the best variant, `risk_5_6pct_0x`, improved only `old_thin`
(`EV +0.1337`, PnL `+$4,306.58`, max drawdown `-1.37 pp`) but regressed
`late_strong` (`EV -0.0339`, PnL `-$424.80`) and `mid_weak` (`EV -0.0097`,
PnL `-$579.33`). Aggregate EV improved only `+0.0901` (`+1.74%`) and aggregate
PnL only `+$3,302.45` (`+2.09%`), below Gate 4 and unstable across windows.

Mechanism insight: the weak 5-6% bucket was mostly an old-thin protection
surface, not a robust cross-window alpha lever. Stop-width-only sizing remains
too blunt: it can help the weakest tape but slightly damages healthier tapes.

Do not repeat: nearby initial-risk-only haircuts around 5-6% or adjacent
stop-width buckets. A valid retry needs an orthogonal event/news, lifecycle, or
position-state discriminator that explains why a 5-6% risk trade deserves less
capital without cutting healthy-window exposure.

### 2026-05-03 mechanism update: Trend Industrials reactivation

Status: rejected.

Core conclusion: `exp-20260503-001` tested whether the old 0x
`trend_long` Industrials risk sleeve had become too conservative after the
accepted SPY-relative leader, position-cap, and first-add-on allocation stack.
It should not be reactivated.

Evidence: the best variant, `trend_industrials_0_25x`, regressed aggregate EV
by `-0.5512` (`-10.64%`) and aggregate PnL by `-$24,554.15` (`-15.52%`).
It helped only `late_strong` slightly (`EV +0.0078`, PnL `+$183.43`) while
damaging `mid_weak` (`EV -0.2941`, PnL `-$8,938.75`) and `old_thin`
(`EV -0.2649`, PnL `-$15,798.83`). The sleeve added 10 trend Industrials
trades across the fixed windows, but aggregate trend-Industrials PnL was
negative (`-$1,200.55`) and the collateral damage to existing slot/risk
allocation was much larger.

Mechanism insight: the 0x trend Industrials haircut is still doing useful
capital protection in the current accepted stack. The issue is not that this
old zero-risk sleeve has been made obsolete by later leader/add-on allocation
changes.

Do not repeat: nearby trend Industrials reactivation multipliers such as
0.25x/0.50x/1.0x without forward evidence, event/news context, or a new
lifecycle discriminator that explains why this sleeve would behave differently.

### 2026-05-03 mechanism update: Earnings + SEC surprise round 1

Status: observed-only, schema-ready but coverage-blocked.

Core conclusion: `exp-20260503-002` successfully landed the first replayable
`earnings + SEC filings + surprise` event-shock schema, but the current free
local archives are still too sparse to validate whether this direction creates
executable alpha. This should not be promoted yet, and it should not be read as
"earnings/SEC alpha was disproven."

Evidence: hypothesis A (`post_earnings_confirmed_drift`) saw only 1 earnings
event day in `late_strong` and 0 in the other two canonical windows, producing
0 confirmed candidates and no forward-return sample. Hypothesis B
(`guidance_and_filing_severity_filter`) joined 61 accepted-stack baseline
trades but found 0 SEC-backed trade contexts. Hypothesis C
(`quality_of_surprise_discriminator`) produced 0 usable quality cohorts across
all three windows.

Mechanism insight: the blocker is now clearer than before. The first missing
piece is archive density for daily earnings/news snapshots; the second is
SEC-item-to-ticker mapping quality. Until those two are improved, nearby
earnings threshold tweaks, confirmation tweaks, or filing-severity variants
would mostly be measuring archive sparsity rather than alpha quality.

Do not repeat: rerunning nearby earnings/SEC surprise variants on the same thin
archive and interpreting null exposure as a no-go verdict on the whole
direction. A valid retry first needs denser point-in-time archives and better
SEC symbol joins, then the same round-1 schema can be rerun before any second
round replay promotion.

### 2026-05-03 mechanism update: Low-TQS breakout reactivation

Status: rejected.

Core conclusion: `exp-20260503-003` tested whether the non-commodity low-TQS
breakout 0x sleeve had become too conservative after the accepted SPY-relative
leader, position-cap, and first-add-on allocation stack. It should not be
reactivated.

Evidence: the best variant, `low_tqs_breakout_0_10x`, regressed aggregate EV
from `5.1785` to `4.9420` and aggregate PnL from `$158,257.48` to
`$147,409.01` (`-$10,848.47`, `-6.86%`). Higher 0.25x and 0.50x restorations
were worse. The reactivation added 5 trades, but win rate fell in both active
windows and EV improved in 0/3 windows.

Mechanism insight: the low-TQS non-commodity breakout haircut is still doing
useful quality protection in the current accepted stack. Added trades are not
hidden alpha; they mostly dilute the high-quality breakout sleeve.

Do not repeat: nearby non-commodity low-TQS breakout multipliers such as
0.10x/0.25x/0.50x without forward evidence, event/news context, or a stronger
quality discriminator that separates true low-TQS recoveries from the
late/mid-window drag.

### 2026-05-03 mechanism update: SEC feed coverage audit

Status: observed-only measurement repair.

Core conclusion: `exp-20260503-004` confirms the immediate blocker behind the
new earnings/SEC surprise branch is not subtle filing ranking logic. It is much
more basic: the current local archives contain zero persisted SEC source items,
so the SEC half of the branch has effectively been running on an empty sample.

Evidence: across 30 archived `news_*`, 30 `clean_news_*`, and 30
`clean_trade_news_*` files, `source == "sec"` appeared 0 times. Historical
archive coverage also had 0 `news_source_stats_*` diagnostics files, so prior
runs could tell us that SEC context was absent, but not whether the SEC feeds
returned 0 entries, were blocked, or failed before parse.

Mechanism insight: before retrying any SEC filing severity, 8-K item-type, or
guidance-via-SEC ranking experiments, the pipeline must first become
source-observable. This round adds SEC-specific request headers plus forward
`news_source_stats_YYYYMMDD.json` diagnostics so future runs can distinguish:
`sec feed fetched zero entries` vs `sec feed errored` vs `sec items arrived but
did not map to tickers`.

Do not repeat: rerunning SEC-context alpha variants on the pre-diagnostics
archives, or interpreting zero SEC joins as evidence that SEC alpha is weak. A
valid retry first needs forward pipeline runs with the new source diagnostics
and at least some nonzero SEC coverage or explicit fetch-failure evidence.

### 2026-05-03 mechanism update: SEC CIK-to-ticker mapping

Status: observed-only measurement repair; blocker materially reduced.

Core conclusion: `exp-20260503-005` confirms that live SEC Atom feeds can now be
turned into ticker-tagged event rows using the SEC title CIK plus a local
`company_tickers` cache. This moves the SEC branch from "zero persisted sample"
to "mapping layer works; wait for forward archives before ranking tests."

Evidence: across the latest 300 live SEC rows (`8-K`, `10-Q`, `10-K`), 300 had
parsed CIKs and 284 mapped to tickers (`94.67%`). After disabling generic ticker
extraction for SEC titles, current production-universe overlap is 1 real row
(`TSLA` `10-K/A`): nonzero, but too sparse for a ranking conclusion. Feed-level
mapping is `8-K 95/100`, `10-Q 91/100`, and `10-K 98/100`.

Mechanism insight: the old null SEC join was not an alpha result. It was an
attribution plumbing problem: SEC filings had issuer CIKs, but the pipeline did
not structure CIK/company fields or join them to tickers. The next test should
use forward archives created after this mapping layer, because old archives
cannot be made point-in-time ticker-tagged without separate SEC raw replay.

Do not repeat: SEC filing-context ranking on archives predating the CIK mapping
patch, or SEC title text ticker extraction that treats company suffixes such as
`/MA/` or `Corp. V` as symbols. A valid retry needs multiple forward
`news_YYYYMMDD.json` archives with `source == "sec"` rows carrying `sec_cik`,
`sec_company_name`, and ticker tags; if production-universe overlap remains
thin, route the idea through a filing-driven shadow universe scout rather than
production entry changes.

### 2026-05-03 mechanism update: Filing-driven shadow universe scout

Status: replay-candidate for a discriminated second-round replay; not
production-ready.

Core conclusion: `exp-20260503-006` tested whether the newly working SEC CIK
mapping could seed a filing-driven shadow universe outside the current
production watchlist. Broad SEC filing continuation is not strong enough, but
the scout found enough non-current-universe, price-covered history to justify a
second-round replay focused on filing/liquidity discrimination.

Evidence: the latest archive produced `284` mapped SEC filing rows across `279`
unique tickers, but only `1` row overlapped the current production universe.
The historical submission expansion built `992` filing events across `100`
tickers; `876` had price coverage and `787` had valid 10-day forward excess
returns. Overall 10-day excess return was negative (`-1.22%`, win rate
`46.5%`), so `SEC filing => buy` is not the mechanism. The useful branches were
more selective: `10-K` had positive 10-day excess (`+0.88%` on `92` samples),
`ADV $5m-$20m` had `+2.94%` on `114` samples, and `ADV >= $20m` had `+0.14%`
on `310` samples. Low-liquidity filings were clearly bad (`-3.81%` on `347`
samples).

Mechanism insight: the current production universe is too narrow for SEC filing
research, but broad outside-universe filings are not automatically alpha. The
next replay should test a liquidity-gated 10-K / high-ADV filing scout and
explicitly exclude or down-rank low-liquidity filings before any watchlist
expansion proposal.

Do not repeat: broad filing-type promotion, low-liquidity filing inclusion, or
production universe expansion directly from this scout. A valid retry is a
second-round replay that locks the discovered discriminators (`10-K`, `ADV >=
$5m`, current-universe overlap accounting) and measures whether those candidates
can beat same-day A/B scarce-slot alternatives.

### 2026-05-03 mechanism update: Semicap equipment watchlist scout

Status: rejected.

Core conclusion: `exp-20260503-007` tested a bounded candidate-universe
expansion using liquid semiconductor equipment / compute supplier names
(`QCOM`, `AMAT`, `ASML`). It should not be promoted.

Evidence: the corrected comparison used canonical base snapshots for baseline
and augmented snapshots only for variants. Baseline matched the accepted stack:
EV `3.4191 / 1.4415 / 0.3179` across `late_strong`, `mid_weak`, and
`old_thin`. The full basket added raw aggregate PnL `+$2,585.79`, but EV fell
`-0.4881`, win rate dropped as much as `-9.38 pp`, max drawdown worsened by
`+2.01 pp`, and EV improved in `0/3` windows. The best non-inert control
(`QCOM`) also regressed EV (`-0.1810`) and PnL (`-$2,228.91`).

Mechanism insight: adding large liquid semiconductor-adjacent names is still
not automatically a candidate-pool upgrade. The current A/B engine can create
extra trades from the theme, but the added exposure lowers risk-adjusted quality
and does not solve a repeat replacement bottleneck.

Do not repeat: raw `QCOM` / `AMAT` / `ASML` watchlist promotion or nearby
semiconductor-equipment large-cap universe additions without event/news
confirmation, forward pilot evidence, or slot-aware replacement proof.

### 2026-05-03 mechanism update: Pullback relative-strength EOD rank

Status: observed-only, not promoted.

Core conclusion: `exp-20260503-008` tested an EOD cross-sectional rank where
strong 60-day relative strength is boosted when the last 5 days have pulled
back. The pullback composite is directionally positive, but it does not dominate
the simpler 60-day momentum control and has materially higher turnover.

Evidence: after 35 bps cost across the three canonical non-overlapping windows,
`pullback_rs_60_5` averaged positive 5/10/20/60-day top-minus-bottom spreads,
but the 60-day momentum control had stronger average rank IC and spread at the
20/60-day horizons with lower turnover. The pullback rank also concentrates the
top bucket heavily in Technology and uses the repo's current snapshot universe,
so it remains survivorship-biased.

Mechanism insight: the current data supports a broad medium-term relative
strength rank more than a short-term pullback overlay. A pullback term may still
be useful as a tie-breaker or slot-aware entry timing feature, but it should not
replace pure relative strength without a point-in-time historical universe and
sector/liquidity-neutral validation.

Do not repeat: promoting `z_ret_60d - z_ret_5d` directly into production from
current snapshots, or treating the positive long-horizon spread as sufficient
without addressing Technology concentration, survivorship bias, and slot-aware
A/B integration.

### 2026-05-03 mechanism update: Repeated ATR trailing full-exit profile

Status: rejected; also flagged as a near-repeat.

Core conclusion: `exp-20260503-009` retested a full-position ATR trailing exit
after a profit trigger. This was a mistake to prioritize because the
2026-04-29 ATR trailing full-exit mechanism update had already rejected the
same family. The new data confirms the old guardrail rather than opening a new
branch.

Evidence: the best variant was `TRAIL_TRIGGER_ATR_MULT=3.0` with
`TRAIL_OFFSET_ATR_MULT=2.0`. It regressed EV in all three canonical windows:
`late_strong -1.0969`, `mid_weak -0.8005`, and `old_thin -0.2669`. Aggregate
EV fell `-2.1643` (`-41.79%`) and aggregate PnL fell `-$60,296.29`
(`-38.10%`). The only partial benefit was mid-window drawdown improvement, but
the main objective and PnL both collapsed.

Mechanism insight: full-position ATR trailing still cuts the accepted fixed
target winners more than it saves giveback. The failure is not a narrow
parameter miss; the entire simple trigger/offset family lacks a discriminator
that can separate trend exhaustion from normal volatility.

Do not repeat: nearby full-position ATR trailing trigger/offset sweeps. A valid
retry requires an orthogonal event/news or position-state discriminator and, if
positive, a shared production/backtest lifecycle policy.

### 2026-05-03 mechanism update: Medium-term RS slot ranking

Status: rejected.

Core conclusion: `exp-20260503-010` tested whether already survived, already
sized candidates should be sorted before slot slicing by medium-term
ticker-vs-SPY relative strength and trade quality. It should not be promoted.

Evidence: the best tested variant was `tqs_then_rs20`, but it regressed EV in
all three canonical windows: `late_strong -0.1479`, `mid_weak -0.0653`, and
`old_thin -0.1549`. Aggregate EV fell `-0.3681`; aggregate PnL fell
`-$11,883.15` (`-7.51%`). Pure `rs20_then_tqs` and
`spy_leader_rs20_then_tqs` were worse, cutting `late_strong` EV from `3.4191`
to `2.5688`.

Mechanism insight: broad medium-term relative strength can rank future returns
in an observed-only cross-sectional study, but using it as a global slot-order
overlay damages the accepted A/B engine. The accepted confidence/breakout order
is already carrying information that a simple RS overlay overwrites.

Do not repeat: global pre-slot sorting by `ticker_ret20_minus_spy_pct`,
`spy_relative_leader`, or `trade_quality_score` alone. A valid retry must be
scope-limited to a narrower collision class, such as same-day slot-sliced pairs
or sector-neutral replacements, and must remain production/backtest shared if
accepted.

### 2026-05-03 mechanism update: Liquidity-gated 10-K filing scout

Status: replay-candidate, shadow-only.

Core conclusion: `exp-20260503-011` locked the second-round SEC filing
discriminators from `exp-20260503-006`: outside-current-universe `10-K`
filings with 20-day ADV >= `$5M`. This is a real research lead, but not a
production universe promotion.

Evidence: the locked cohort produced `354` candidates, `103` of which landed
inside the three canonical windows. The 10-day excess-return distribution was
positive (`+0.38%` average, `+0.43%` median, `53.39%` win rate), and the
same-day core-trade conflict proxy was positive in `6/7` matched cases with
average replacement edge `+2.48%`. The evidence is still static/shadow:
historical CIKs were seeded from the latest SEC archive, not from a
point-in-time universe ledger.

Mechanism insight: liquidity gating removed the worst low-ADV filing noise and
made 10-K filings worth forward observation. The next valid step is a PIT or
forward replay that freezes eligibility and same-day alternatives before entry.
Static SEC shadow evidence can nominate research/pilot candidates, but it
cannot insert tickers into core or trade-enabled status.

Do not repeat: broad filing promotion, low-liquidity filing inclusion, or
direct watchlist expansion from static SEC backfills. A valid retry needs
forward `news_YYYYMMDD.json` SEC archives with ticker tags and an append-only
universe eligibility path, then replacement-value measurement versus same-day
A/B alternatives.

### 2026-05-03 mechanism update: Slot-sliced collision ranking

Status: rejected.

Core conclusion: `exp-20260503-012` tested the valid narrow retry requested by
`exp-20260503-010`: apply TQS / 20-day relative-strength ranking only on days
where survived candidates were actually `slot_sliced`. It should not be
promoted.

Evidence: the best variant, `collision_conf_then_tqs_rs20`, was unchanged in
`late_strong` but regressed `mid_weak` and `old_thin`. Aggregate EV fell
`-0.2209` (`-4.27%`) and aggregate PnL fell `-$10,490.40` (`-6.63%`), with EV
improving in `0/3` windows. The more aggressive `collision_rs20_then_tqs`
variant was worse (`EV -1.0712`, PnL `-$25,823.58`).

Mechanism insight: the accepted signal order is not just a crude global sort;
even inside scarce-slot collision days, simple TQS / RS replacements damage
the current A/B engine. The failure is no longer only "global ranking was too
broad"; this narrower collision surface also lacks a useful discriminator.

Do not repeat: TQS / RS slot-collision ranking without a new, case-specific
reason tied to the exact losing collision set. Any future positive ranking
variant must be implemented as shared production/backtest policy before it can
affect live entries.

### 2026-05-03 mechanism update: Duplicate static universe scout guardrail

Status: rejected in planning; guardrail strengthened.

Core conclusion: `exp-20260503-013` correctly stopped a same-family universe /
D-strategy shadow scout before it became another low-information static rerun.
With no new point-in-time eligibility ledger, no fresh forward SEC/news
archives, and no closed pilot replacement-value evidence after
`exp-20260503-011`, rerunning another static outside-production cohort would
only repeat the same measurement defect.

Evidence: this run intentionally produced no strategy or backtester delta.
Baseline remained the accepted stack at `EV 3.4191 / 1.4415 / 0.3179` across
`late_strong`, `mid_weak`, and `old_thin`, and `after_metrics` were explicitly
`0.0` because the experiment was rejected before execution. The blocked retry
was already covered by nearby evidence from `exp-20260502-008`,
`exp-20260503-006`, `exp-20260503-007`, and especially the positive-but-still-
shadow `exp-20260503-011` liquidity-gated `10-K` scout.

Mechanism insight: the correct next step for new-universe SEC/filer ideas is
not another static pool. It is forward/PIT evidence capture: append-only
eligibility state, forward SEC ticker-tagged archives, and frozen same-day
replacement-value logging. Until those exist, "one more static scout" is not
alpha search; it is duplicate measurement noise.

Do not repeat: new static universe / D-strategy cohort scouts without new PIT
eligibility evidence, forward archives, or replacement-value logs created after
the prior same-family scout. A valid retry first needs the forward observability
path that `exp-20260503-011` and `exp-20260503-013` now jointly require.

### 2026-05-03 mechanism update: Non-leader follow-through add-ons

Status: rejected / zero-impact.

Core conclusion: `exp-20260503-014` tested whether the accepted day-2
follow-through add-on was only worth keeping for SPY-relative leaders by
setting the normal non-leader `ADDON_MAX_POSITION_PCT` to `0.0` while leaving
the accepted SPY-relative leader add-on cap at `60%`. It should not be
promoted.

Evidence: the variant was bit-identical across all three canonical windows:
EV delta `+0.0000`, aggregate PnL delta `$+0.00`, no Sharpe, drawdown,
win-rate, trade-count, or survival change. The reason was exposure, not a
hidden tradeoff: baseline executed first add-ons were all SPY-relative leaders
(`late_strong 4`, `mid_weak 4`, `old_thin 2`) and there were `0` executed
non-leader first add-ons to remove.

Mechanism insight: the current accepted stack has already concentrated
effective add-on exposure inside the SPY-relative leader sleeve. Generic
non-leader add-on disablement is now a vacuous surface in the fixed windows.

Do not repeat: `ADDON_MAX_POSITION_PCT=0` or generic non-leader first-add-on
disablement without new lifecycle attribution showing actual non-leader add-on
exposure. A valid retry needs event/news context or a narrower non-leader
quality discriminator with nonzero executions, and any positive result must
remain shared between production and backtest paths.

### 2026-05-03 mechanism update: Vol-adjusted SPY leader gate

Status: rejected.

Core conclusion: `exp-20260503-047` tested an ATR-normalized quality gate for
the accepted SPY-relative leader sleeve: require 20-day ticker-vs-SPY excess
return divided by ticker ATR% to clear a minimum threshold before granting
leader risk/cap/add-on treatment. It should not be promoted.

Evidence: the best variant, `vol_adj_ge_1_00atr`, reduced aggregate EV from
`5.1785` to `5.1073` and aggregate PnL from `$158,257.48` to `$156,916.19`
across the three canonical windows. `late_strong` was unchanged, `mid_weak`
regressed by `EV -0.0849` and `PnL -$1,818.12`, while `old_thin` improved only
modestly by `EV +0.0137`, `PnL +$476.83`, and `drawdown -0.82pp`. Higher
thresholds worsened `late_strong`, so the apparent old-window risk benefit did
not generalize.

Mechanism insight: the accepted SPY-relative leader sleeve is not simply too
permissive on volatility-adjusted excess return. Demoting marginal
vol-adjusted leaders can remove some older-window risk, but it also cuts useful
mid-window add-on / leader exposure. Together with `exp-20260503-046`, this
shows that nearby leader qualification thresholds are no longer the strongest
alpha surface.

Do not repeat: raw percentage margin or ATR-normalized SPY-relative leader
qualification gates without event/news confirmation, forward tail-risk
evidence, or another orthogonal discriminator. Any positive retry must be
implemented as shared production/backtest policy before promotion.

### 2026-05-03 mechanism update: SEC filing reaction drift

Status: rejected.

Core conclusion: `exp-20260503-051` tested whether PIT-safe SEC filing event
days with a first EOD excess reaction of at least `+2%` versus SPY identify
post-reaction drift. They do not. This was a real alpha-search attempt using
the new SEC public-PIT filing backbone from `exp-20260503-050`, not another
coverage audit.

Evidence: the positive reaction cohort had enough sample (`138` valid `10d`
observations), but aggregate `10d` excess return was negative (`-0.81%`
average, `-0.48%` median, `46.38%` win rate). The window profile was unstable:
`late_strong` was materially negative (`-3.18%` average `10d` excess), while
`mid_weak` and `old_thin` were only modestly positive. Same-day core
replacement proxy was worse: `122` valid comparisons averaged `-4.24%`
replacement value with only `33.61%` positive.

Mechanism insight: SEC public filing coverage is no longer the immediate
blocker for this narrow test. The blocker is mechanism quality: raw post-filing
price reaction is too noisy and often worse than the accepted A/B stack's
same-day opportunities. SEC may still be useful, but it needs richer filing
semantics such as 8-K item text, XBRL surprise fields, or forward production
SEC archives rather than nearby reaction thresholds.

Do not repeat: fixed raw SEC filing reaction gates around `+2%` or nearby
threshold sweeps. A valid retry needs a different discriminator and, if it can
affect ranking or entries, a shared production/backtest event feature before
promotion.

### 2026-05-03 mechanism update: Large Form 4 standalone event sleeve

Status: shadow-promising; not production-promoted.

Core conclusion: `exp-20260503-052` tested the remaining Form 4 branch after
near-entry accepted-trade overlap (`exp-20260503-048`) and entry-skip oracle
replacement overlap (`exp-20260503-049`) were too sparse. Form 4 still looks
interesting, but not as a current A/B overlay. The promising discriminator is a
standalone external-event source: `meaningful_purchase_v1` with total insider
purchase value at least `$500k`.

Evidence: the fixed 10-trading-day shadow replay kept core before/after
metrics unchanged (`EV 3.4191 / 1.4415 / 0.3179`) and measured event outcomes
separately. The `$500k` meaningful-purchase cohort had `13` valid events,
average net return `+5.75%`, average excess versus SPY `+4.76%`, and positive
10-day excess in all three canonical windows. Window details were:
`late_strong` `4/4` valid with `+4.84%` average excess, `mid_weak` `8/10`
valid with `+5.27%`, and `old_thin` `1/3` valid with `+0.33%`.

Mechanism insight: Form 4 buying is too sparse to explain the accepted A/B
trade set or the known top skipped opportunities, but large real-money insider
buys may be a useful candidate-source scout. The old-window sample is only one
valid event, so this is not enough to add core entries or a production ranking
rule. The next valid step is a default-off forward/pilot event queue with
frozen same-day alternatives and closed outcome attribution.

Do not repeat: Form 4 near-entry overlay joins or entry-skip oracle overlap
joins without a materially broader sample. Do not directly promote `$500k`
Form 4 purchases into core entries from this shadow result. A valid promotion
must first add a shared production/backtest event feature or pilot queue, then
show forward replacement value and closed trade outcomes.

### 2026-05-03 mechanism update: Form 4 owner-role discriminator

Status: rejected.

Core conclusion: `exp-20260503-053` tested whether simple owner-role filters improve the
shadow-promising `meaningful_purchase_v1 >= $500k` Form 4 standalone event
source. They should not be promoted or repeatedly swept.

Evidence: the best role-only variant was `ge500k_not_ceo_cfo_or_president`. It
improved average 10-day excess by only
`+0.15 pp` versus
the plain >=$500k branch while cutting valid events by
`-4`. The old_thin
window still had only one valid event, so the apparent role lift does not solve
the main sample-stability problem.

Mechanism insight: Form 4 remains more promising as a forward standalone event
queue than as another static role-threshold sweep. The simple distinction
between director, officer, CEO/CFO/president, single-owner, and cluster buying
does not add enough information on top of purchase value.

Do not repeat: simple Form 4 owner-role filters around the `$500k` meaningful
purchase branch without materially broader transaction history or live forward
pilot evidence. A valid next step remains a default-off forward/pilot event
queue with frozen same-day alternatives and shared production/backtest event
policy before promotion.

### 2026-05-04 mechanism update: Form 4 forward event queue

Status: accepted as default-off observation, not promoted to strategy entries.

Core conclusion: `exp-20260504-001` implemented the valid next step after the
shadow-promising `$500k` Form 4 branch. Large `meaningful_purchase_v1` insider
purchase event-days are now surfaced through a production-visible forward queue
that is explicitly disabled for trading and freezes same-day alternatives for
future replacement-value attribution.

Evidence: the three canonical fixed-window backtests were rerun with no core
metric movement because the queue does not alter entries, ranking, sizing,
exits, or orders: `late_strong` EV `3.4191`, `mid_weak` EV `1.4415`, and
`old_thin` EV `0.3179`. The production smoke check returned `enabled=false`,
`candidate_count=0` for `2026-05-04`, source status `loaded`, and
`alters_orders=false`.

Mechanism insight: this avoids the two failed Form 4 patterns: it is not a
near-entry overlap join, and it is not another owner-role threshold sweep. It
turns the sparse but positive branch into a measurable candidate-source scout.
The alpha claim is still pending forward samples; this only fixes the
production observability path needed to gather them without changing strategy
behavior.

Do not repeat: do not directly promote `$500k` Form 4 events into core entries
from historical shadow evidence alone, and do not run more simple role/value
threshold sweeps until the default-off queue has forward replacement-value
outcomes. A valid promotion needs enough closed queue samples plus a shared
backtest/production event-sleeve policy.

### 2026-05-04 mechanism update: Earnings SEC price-reaction packet

Status: observed-only / not promoted.

Core conclusion: `exp-20260504-002` tested the first complete free-source
event packet for `earnings + PIT-safe SEC filing + first price reaction`.
Adding nearby SEC results-filing context does not by itself rescue the
earnings line, and positive reaction after a results 8-K is not a stable
ranking signal in the currently covered window.

Evidence: the covered late window produced `92` raw inferred earnings events,
deduped to `76` event packets after collapsing same SEC shock/accession
duplicates. Of those, `72` were price-covered, `65` were results 8-K events,
and `21` were primary packets defined as `results_8k + positive first excess
reaction`. The primary packet had `20` valid 10-day outcomes with average
excess `-1.83%` and win rate `30.00%`. The stronger
`results_8k + >=2% first excess reaction` branch had `12` valid 10-day
outcomes with average excess `-1.69%`. When packet entries conflicted with
same-day accepted A/B trades, the 10-day replacement-value proxy averaged
`-9.87%`, with only `2/22` positive replacement samples.

Mechanism insight: the next earnings retry should not be another nearby
reaction-threshold sweep. The missing edge is probably richer event grading
such as XBRL fundamentals, analyst revisions, or LLM financial-statement
semantics, plus older PIT earnings coverage for non-overlapping windows.

Do not repeat: raw `results_8k + positive reaction` gates, nearby +/- reaction
threshold tuning, or simple SEC-context checklists as a C-strategy revival.
A valid retry needs new information content, not another price-confirmation
variant on the same covered sample.

### 2026-05-04 mechanism update: SEC Companyfacts financial-quality grading

Status: observed-only / not promoted.

Core conclusion: `exp-20260504-004` filled the prior XBRL/companyfacts data
gap with `17,109` normalized SEC Companyfacts rows and tested a simple
financial-quality score across 10-Q/10-K financial filing events. The data gap
is now materially repaired, but the simple score is not a promotion-quality
ranking signal.

Evidence: the replay matched `292` financial filing events to Companyfacts
accessions and covered `218` with prices across all three canonical windows:
`72` old_thin, `71` mid_weak, and `75` late_strong. The `high_quality` bucket
had `135` events and `131` valid 10-day outcomes, with average 10-day excess
`+0.45%`, median `-0.28%`, and win rate `48.09%`. It was positive in
`late_strong` and `old_thin`, but negative in `mid_weak`. More importantly, the
supposedly adverse `warning_quality` bucket had stronger 10-day excess
(`+1.65%`, win rate `52.27%`) and stronger 20-day excess (`+2.42%`), so the
simple score is not monotonic.

Mechanism insight: Companyfacts is now available as a replayable PIT-ish field
layer, but naive financial-statement point scoring should not be promoted or
swept. The next valid retry needs new information content: LLM filing-text
grading, analyst revisions, or a cleaner earnings-release same-quarter XBRL
extraction, not point-weight tuning.

Do not repeat: nearby score weights or simple high/positive/warning bucket
thresholds on this same Companyfacts grade. If this direction continues, use
Companyfacts as structured context for LLM or analyst-revision joined grading,
not as a standalone checklist.

### 2026-05-04 mechanism update: SEC filing-text language packets

Status: observed-only / not promoted.

Core conclusion: `exp-20260504-007` added a replayable SEC filing-text layer
for 8-K Item 2.02 events and tested a fixed keyword language proxy. The text
data gap is materially repaired, but simple positive-language scoring is not an
alpha. The useful discovery is that adverse/negative language may be a
candidate for LLM semantic grading, not a direct keyword rule.

Evidence: the text backfill covered `306/306` Item 2.02 filings, fetched
`1,224` archive documents, and produced `12,024,232` extracted text characters.
The shadow replay evaluated `302` events and price-covered `232` across all
three windows: `80` old_thin, `74` mid_weak, and `78` late_strong. The primary
`earnings_release_text + positive_language` branch had `65` events and `62`
valid 10-day outcomes, with average 10-day excess `-1.27%` and win rate
`40.32%`. The broad `positive_language` bucket was also negative at 10 days
(`-1.19%`, win rate `42.42%`). In contrast, the `negative_language` bucket had
`32` events, `29` valid 10-day outcomes, average 10-day excess `+3.22%`, win
rate `58.62%`, and average 20-day excess `+4.93%`.

Mechanism insight: simple positive language is often already priced, stale, or
too generic. The promising branch is not "buy negative words"; it is a possible
post-shock recovery / conservative-disclosure / bad-news-already-discounted
mechanism that needs LLM context to distinguish real deterioration from
absorbed or overreacted bad news.

Do not repeat: positive-language keyword scoring, nearby phrase-list tuning, or
promotion of negative-language keywords as a direct entry rule. A valid retry
should freeze the filing-text packet schema and ask an LLM to grade whether the
filing describes recoverable pressure, guidance reset, transient headwind, or
true fundamental deterioration, then compare LLM grades against this keyword
baseline and raw price reaction.

### 2026-05-04 mechanism update: SEC negative-language reaction absorption

Status: shadow-promising / not promoted.

Core conclusion: `exp-20260504-008` tested the next discriminated branch after
the fixed SEC filing-text packet found `negative_language` was unexpectedly
positive. The edge is not simple nonnegative-reaction "bad news absorbed."
Within `negative_language`, events with first public-PIT reaction below SPY had
the stronger forward profile.

Evidence: across the three canonical windows, `negative_language +
reaction_excess_return < 0` produced `16` events and `14` valid 10-day
outcomes with average 10-day excess `+5.73%`, win rate `64.29%`, and average
20-day excess `+6.46%`. The branch was positive in all three windows:
`late_strong +8.99%`, `mid_weak +6.55%`, and `old_thin +0.64%` average 10-day
excess. The nonnegative-reaction control had the same `16` events but only
`+0.88%` average 10-day excess.

Mechanism insight: the useful filing-text direction is closer to "negative
disclosure plus measured selloff creates recoverable-pressure drift" than to
"positive words are good" or "the market ignored bad words." This should be
fed into an LLM/event-sleeve grader, not promoted as a keyword rule.

Do not repeat: direct `negative_language` entry promotion, phrase-list tuning,
or nearby reaction-threshold sweeps. A valid retry should freeze this packet as
structured input and test whether LLM grading can separate recoverable
pressure, guidance reset, transient headwind, and true deterioration, with
shared production/backtest event policy before any live entry effect.

### 2026-05-04 mechanism update: SEC negative-reaction event sleeve

Status: shadow-promising / not promoted.

Core conclusion: `exp-20260504-010` froze the `exp-20260504-008` packet
(`8-K Item 2.02 + negative_language + first reaction excess < 0`) and tested
it as a standalone deterministic event sleeve with transaction costs,
capacity, fixed 10/20 trading-day exits, and daily equity accounting. The
packet survived this stricter portfolio-level replay, but it is still not a
production entry rule because it has not been tested for scarce-slot
replacement value against A/B candidates.

Evidence: the fixed packet produced `16` candidate events across the three
canonical windows (`4` old_thin, `7` mid_weak, `5` late_strong). The primary
`10d_max1` sleeve took `13` trades, skipped `3` for slot capacity, returned
`+99.99%` on standalone sleeve equity, Sharpe daily `1.4757`, max drawdown
`10.37%`, and win rate `84.62%`. The `10d_max2` variant took all `16` events
with Sharpe daily `1.6232`, max drawdown `5.30%`, and win rate `87.50%`.
The result is not clean enough for promotion because one `LITE` trade
contributed `69.10%` of primary total PnL.

Mechanism insight: the SEC text/reaction branch is now stronger than a pure
shadow statistic: as a small event sleeve it appears monetizable after costs.
The likely edge remains "recoverable pressure after adverse disclosure and
measured first-day selloff," not positive filing text and not simple bad-news
absorption. The next alpha step should measure whether this packet adds value
when it competes with existing accepted/skipped A/B candidates.

Do not repeat: keyword phrase tuning, nearby reaction-threshold sweeps, or
direct core-slot promotion. A valid retry is a replacement-value replay versus
same-day A/B candidates, then a default-off forward queue with shared
production/backtest packet policy if replacement value remains positive.

### 2026-05-04 mechanism update: SEC negative-reaction replacement value

Status: replacement-inconclusive / not promoted.

Core conclusion: `exp-20260504-011` froze the `exp-20260504-010` packet and
tested whether it has enough scarce-slot replacement value versus same-day A/B
accepted candidates and occupied-slot proxies. The packet is still
standalone-positive, but it should not be promoted into core entries or ranking.

Evidence: all `16/16` packet events had 10-trading-day outcomes. Aggregate net
10-day return was `+5.71%`, average net excess versus SPY was `+4.74%`, and
net win rate was `87.50%`. But direct same-day accepted A/B replacement evidence
was only `2` samples, averaging `+1.91 pp` versus accepted alternatives with a
`50.00%` positive rate. Active-slot proxy evidence was broader (`13` samples)
but only mildly positive: average `+0.99 pp`, median `+0.50 pp`, and `53.85%`
positive. Old-thin remained weak versus active slots (`-4.19 pp` average).

Mechanism insight: SEC negative disclosure plus measured first-day selloff
continues to look like a plausible standalone event source, not a proven core
slot competitor. The strongest interpretation is still a default-off forward
event queue / LLM-grading candidate, where replacement value can be accumulated
with frozen same-day alternatives. It is not enough evidence for direct
production entries or A/B rank promotion.

Do not repeat: direct core-slot promotion of this packet, keyword phrase tuning,
or nearby reaction-threshold sweeps. A valid retry needs either a shared
default-off production/backtest SEC event queue with forward replacement-value
attribution, or richer LLM semantic grading that separates recoverable pressure
from true deterioration before any live entry effect.

### 2026-05-04 mechanism update: SEC default-off forward queue

Status: default-off observation ready / not promoted to trading.

Core conclusion: `exp-20260504-012` moved the frozen SEC
`negative_language + reaction_excess_return < 0` packet into a shared
production-visible queue policy, but kept it default-off and observe-only. This
is the right next step after replacement value was inconclusive: accumulate
forward replacement-value samples without changing orders, sizing, ranking, or
core A/B entries.

Evidence: the shared queue policy replayed `16/16` exp-20260504-010 historical
packets exactly, with `0` missing and `0` extra replayed candidates. The
production smoke for `2026-05-04` loaded the SEC filing-text source
successfully, found `0` same-day rows/candidates, and reported
`alters_orders=false`, `alters_candidate_ranking=false`,
`alters_sizing=false`, and `enabled=false`.

Mechanism insight: the SEC packet has now crossed from "interesting replay" to
"safe to observe forward," but not to "safe to trade." The queue's job is to
freeze same-day A/B/cash alternatives so future closed outcomes can answer the
replacement-value question with out-of-sample evidence.

Do not repeat: another replacement-value replay on the same frozen historical
sample, keyword phrase tuning, or core-slot promotion. A valid retry now needs
new forward queue samples, or an LLM semantic grader layered on the same frozen
queue schema and measured against later realized replacement value.

### 2026-05-04 mechanism update: SEC reaction Companyfacts context

Status: rejected / not promoted.

Core conclusion: `exp-20260504-014` tested whether structured SEC Companyfacts
context can separate recoverable negative SEC reactions from true fundamental
deterioration inside the frozen `negative_language + reaction_excess_return < 0`
packet. It does not help with the current data shape.

Evidence: all `16/16` packet events joined only to latest-prior Companyfacts;
`0/16` had same-accession Companyfacts available at the SEC 8-K event date. The
full packet still averaged `+5.7338%` 10-day excess return over SPY across `14`
valid outcomes, but the fixed buckets were not promotion-quality:
`pressure_but_not_terminal` had `11` valid 10-day outcomes with only `+2.9264%`
average excess and `54.55%` positive rate, while `fundamental_pressure` had just
`3` valid 10-day outcomes, `+16.0275%` average excess, and was dominated by the
same `LITE` rebound concentration already seen in the sleeve replay.

Mechanism insight: latest-prior Companyfacts is too stale to grade an 8-K
earnings-reaction packet. It can document the issuer's background condition, but
it does not identify whether the specific sold-off disclosure is recoverable or
terminal. The correct next information source is same-accession/same-day
earnings XBRL, analyst revisions, or an LLM semantic grader on the frozen queue
schema with forward replacement-value outcomes.

Do not repeat: Companyfacts stale-background buckets, nearby severe-flag counts,
or simple pressure/not-terminal labels on this same SEC reaction packet. A valid
retry requires PIT-safe same-accession or same-day earnings XBRL at the reaction
date, or forward LLM semantic grading measured against frozen alternatives.

### 2026-05-04 mechanism update: SEC leadership-change negative reaction

Status: shadow-promising / not promoted.

Core conclusion: `exp-20260504-015` found a separate SEC event-context branch:
8-K leadership-change filings with a first public excess reaction of at most
`-2%` rebounded over the next 10 trading days across all three canonical
windows. This is not the same as the rejected broad positive SEC reaction gate,
and it is not the Item 2.02 negative-language queue.

Evidence: the primary branch had `25` event rows, `23` valid 10-day outcomes,
`19` unique tickers, average 10-day excess return `+3.8135%`, median
`+2.2373%`, and `60.87%` positive rate. Window averages were positive in
`3/3` windows: `late_strong +5.0878%`, `mid_weak +4.1842%`, and
`old_thin +1.2573%`. Ticker concentration was acceptable for a shadow packet:
top count ticker `UNH` represented `13.04%` of valid outcomes and the top
absolute contribution share was `26.0371%`.

Mechanism insight: leadership-change selloffs may represent temporary
uncertainty absorption rather than fundamental deterioration. The branch is
worth forward observation or later queue integration, but it is not yet a
production entry/ranking/sizing rule because replacement value against same-day
A/B alternatives has not been tested.

Do not repeat: nearby negative-reaction thresholds, direct core promotion, or
single-window tuning of the leadership-change branch. A valid next step is a
default-off forward queue/replacement-value harness that freezes same-day A/B
alternatives without changing orders, or an LLM semantic grader that separates
routine governance transitions from genuine management-disruption risk.

### 2026-05-04 mechanism update: Forward queue attribution readiness

Status: measurement-blocked / not promoted.

Core conclusion: `exp-20260504-017` clarified the next gating condition for the
new default-off event queues. Form 4 forward attribution is structurally ready
to accumulate paper evidence, but the SEC queue family still lacks a persistent
paper/outcome ledger, so it is not yet ready for promotion tests.

Evidence: the audit found a live `data/form4_event_sleeve_paper_state.json`
contract for the Form 4 queue, while the SEC queues had no analogous
persistent paper/outcome state. Core three-window metrics remained unchanged
(`late_strong` EV `3.4191`, `mid_weak` EV `1.4415`, `old_thin` EV `0.3179`)
because this was a read-only measurement check.

Mechanism insight: default-off queue policy is not enough by itself. Before
SEC event sleeves or LLM grading on top of them can be judged fairly, the repo
must freeze same-day alternatives and realized outcomes in a persistent forward
ledger, not only in ephemeral queue evaluation.

Do not repeat: replay the same SEC queue promotion debate without first adding
the missing persistent SEC paper/outcome ledger. A valid next step is to make
SEC queue attribution as durable as the Form 4 paper state, then let forward
samples accumulate.

### 2026-05-04 mechanism update: SEC leadership-change shadow universe

Status: shadow-promising / not promoted.

Core conclusion: `exp-20260504-018` showed that the frozen
leadership-change-negative-reaction branch from `exp-20260504-015` is also a
clean candidate-source scout at the universe level. It is liquid, mostly inside
the current tradable universe, and has low same-day A/B overlap, but it still
needs replacement-value or forward-queue evidence before any production
expansion.

Evidence: the shadow universe had `25` candidate events across `19` tickers,
with `23` valid 10-day outcomes, `88%` overlap with the current universe, only
`3` same-day A/B overlaps (`12%`), and all `25` candidates above
`$20M` 20-day average dollar volume. Core A/B metrics stayed unchanged because
the scout was observe-only.

Mechanism insight: this branch is stronger as a frozen candidate-source scout
than as a direct core-entry proposal. The useful property is not just positive
forward return; it is that the branch is liquid, covered, and not simply
relabeling the current A/B inventory.

Do not repeat: direct universe promotion, nearby reaction-threshold tuning, or
single-window rescoring of this branch. A valid next step is a default-off
forward queue or replacement-value harness with frozen same-day alternatives.

### 2026-05-04 mechanism update: SEC agreement/debt event packet

Status: rejected / not promoted.

Core conclusion: `exp-20260504-019` tested a separate PIT-safe SEC 8-K packet
around agreement/debt disclosures and found no stable multi-window edge. This
branch should not take priority over the stronger leadership-change or
negative-language reaction families.

Evidence: the primary packet produced `39` events with `38` valid 10-day
samples, average 10-day excess versus SPY `-0.8619%`, and win rate `39.47%`.
`mid_weak` was positive, but both `late_strong` and `old_thin` were negative,
so the branch failed the required cross-window consistency test.

Mechanism insight: not every structured SEC filing family is worth turning into
an event sleeve. Agreement/debt disclosures currently look more like noisy
context than a portable standalone alpha source.

Do not repeat: nearby agreement/debt threshold sweeps, direct queue promotion,
or another standalone packet rerun on the same frozen sample. A valid retry
needs materially new information content or a different event semantics family,
not more tuning of this packet.

### 2026-05-04 mechanism update: SEC other-filing mild negative reaction

Status: shadow-promising / not promoted.

Core conclusion: `exp-20260504-022` tested a residual SEC 8-K branch outside
the already-tested earnings/results, agreement/debt, leadership-change, and
FD/other-event packets. The fixed branch `other_sec_filing +
negative_excess_0_to_minus_2pct` was positive across all three canonical
windows, but it is still too broad and slot-thin for production promotion.

Evidence: the primary branch had `22` event rows, `20` valid 10-day outcomes,
`17` unique tickers, average 10-day excess versus SPY `+2.5478%`, median
`+2.4522%`, and `55.00%` positive rate. Window averages were positive in
`3/3` windows: `late_strong +0.0089%`, `mid_weak +2.3445%`, and
`old_thin +4.5589%`. The same-day A/B replacement proxy was weak:
`4` same-day overlaps, only `2` valid replacement samples, both negative,
with average replacement value `-9.7802%`.

Mechanism insight: the residual branch is likely a candidate-source scout,
not a core slot competitor yet. Its forms are all 8-Ks, mostly item `5.07`
and `5.03` with `9.01` exhibits, suggesting governance/shareholder-meeting or
charter-change context rather than a generic SEC reaction rule.

Do not repeat: nearby mild/strong reaction threshold tuning or direct
production entry/ranking promotion from this sample. A valid next step is
semantic decomposition of the residual 8-K item mix or a default-off forward
queue that freezes same-day alternatives before measuring replacement value.

### 2026-05-04 mechanism update: Macro ETF candidate-pool expansion

Status: rejected / not promoted.

Core conclusion: `exp-20260504-028` tested whether adding liquid macro / sector
ETFs already present in the canonical OHLCV snapshots could improve the
production candidate pool without relying on LLM soft-ranking data. The answer
is no for a ticker-list-only expansion.

Evidence: the broad `macro_all` basket (`TLT`, `IEF`, `UUP`, `USO`, `XLE`,
`XLP`, `XLU`, `XLV`) improved `late_strong` EV from `3.4191` to `4.0952`, but
regressed `mid_weak` EV from `1.4415` to `1.0990` and `old_thin` EV from
`0.3179` to `0.2448`; aggregate PnL fell `$4,862.05`, and late-window drawdown
rose by `+1.41 pp`. Narrowing to `XLE` alone still failed: `late_strong` PnL
rose, but `mid_weak` PnL fell `$9,633.07`, aggregate EV fell `-0.1642`, and
late-window Sharpe/drawdown worsened.

Mechanism insight: macro ETF instruments can create late-window winners, but
the current A/B signal stack does not know when ETF rotation is a high-quality
candidate versus a weaker-tape distraction. Candidate-pool expansion by ticker
list alone is not enough; it needs a macro-regime or event discriminator.

Do not repeat: broad macro ETF watchlist additions, `XLE`-only production
promotion, or nearby ticker-list-only ETF basket scans on the same snapshots.
A valid retry needs forward evidence or a production-shared macro-regime
allocator that explains when these instruments should compete for scarce slots.

### 2026-05-04 mechanism update: Form 4 satellite overlay

Status: positive sample / not promoted.

Core conclusion: `exp-20260504-034` tested the strongest currently available
Form 4 path: keep the A/B core unchanged and add the frozen meaningful-purchase
queue as a separate `10k` notional, one-position satellite overlay. It improved
EV in all three canonical windows, but the lift was not material enough to add
live capital or production complexity.

Evidence: aggregate EV rose from `5.1785` to `5.4218` (`+4.70%`) and aggregate
PnL rose `$4,658.62` (`+2.94%`). Window EV deltas were `late_strong +0.1223`,
`mid_weak +0.1209`, and `old_thin +0.0001`. No window reached the `>10%` EV or
`>5%` PnL materiality bar; the only hard Gate 4 pass was `mid_weak`
Sharpe-daily `+0.11`, and trade-count/win-rate passed in only `2/3` windows.

Mechanism insight: Form 4 meaningful purchases remain real signal candidates,
but the current sample is a small overlay, not a production capital-allocation
answer. The right interpretation is "continue forward observation", not
"promote to live orders" and not "retune the insider threshold".

Do not repeat: Form 4 overlay promotion, purchase-value threshold sweeps, or
owner-role filters on the same frozen sample. A valid retry needs either a
larger closed forward paper-sleeve sample, a higher-capacity event
discriminator, or a shared trade-enabled sleeve adapter followed by the same
three-window parity check.

### 2026-05-04 mechanism update: Default-off event overlay bundle

Status: promising replay-only / not promoted to live orders.

Core conclusion: `exp-20260504-049` tested the strongest currently available
alpha direction after core A/B, macro ETF, AI infra, LLM soft-ranking, and
single-source event paths: combine the already-frozen default-off Form 4,
SEC negative-reaction, and SEC governance/procedural event queues as independent
`$10k` satellite overlays while leaving core A/B unchanged. This is not a
threshold sweep and not a direct production promotion.

Evidence: the bundle improved all three canonical windows: `late_strong`
EV `3.4191 -> 4.0085` and PnL `+$8,351.28`, `mid_weak` EV
`1.4415 -> 2.0246` and PnL `+$10,294.85`, and `old_thin` EV
`0.3179 -> 0.3516` and PnL `+$1,404.66`. Aggregate EV rose `+1.2062`
(`+23.29%`) and aggregate PnL rose `+$20,050.79` (`+12.67%`), with no
EV-regressed window.

Mechanism insight: the next high-priority alpha path is external event
satellite allocation, not another A/B threshold, ranking, macro ETF, or simple
LLM prompt tweak. The positive result is still replay-only because it combines
sparse event families. Before live capital, the system needs a single shared
default-off event-sleeve paper ledger that freezes source, candidate,
same-day A/B alternatives, and realized outcomes.

Do not repeat: retuning event thresholds, keyword lists, Form 4 purchase values,
owner roles, or single-source overlay promotion on the same frozen sample.
A valid next step is a production/backtest shared event-sleeve paper adapter
for the frozen bundle, followed by forward replacement-value observation.

### 2026-05-04 mechanism update: Event bundle forward attribution

Status: accepted observe-only / production-visible but default-off.

Core conclusion: `exp-20260504-053` did not retune the event bundle from
`exp-20260504-049` and did not promote it to live orders. It added a shared
default-off aggregate attribution layer over the existing Form 4, SEC
negative-reaction, and SEC governance/procedural paper sleeves so the daily
production path can observe the bundle as one candidate alpha surface.

Evidence: focused tests passed (`24 passed` across the event sleeve bundle and
source event-sleeve tests). All three canonical core backtests were unchanged:
`late_strong` EV `3.4191`, `mid_weak` EV `1.4415`, and `old_thin` EV `0.3179`;
Sharpe daily, drawdown, PnL, win rate, trade count, and survival rate also
matched baseline.

Mechanism insight: the external event bundle is still the best current alpha
direction, but the next unit of work is forward paper replacement-value
observation, not another frozen-sample threshold, notional, holding-period,
capacity, keyword, or single-source promotion sweep.

Do not repeat: direct live promotion or same-sample retuning of the bundle
before closed forward paper outcomes exist. A valid next step needs daily
pipeline runs that close paper outcomes and freeze same-day cash/core
alternatives, followed by a separate shared trade-enabled adapter only if the
forward attribution supports it.

### 2026-05-04 mechanism update: BEAR_SHALLOW base risk budget

Status: rejected / not promoted.

Core conclusion: `exp-20260504-036` tested whether shallow-bear entries were
worth keeping but at a smaller base risk budget. Variants changed only the
`BEAR_SHALLOW` risk override (`0.50%` baseline versus `0.375%`, `0.25%`, and
`0.75%`) while leaving universe, entries, exits, ranking, add-ons, caps, LLM,
news, and earnings data unchanged.

Evidence: the best variant was `0.25%`. Aggregate EV rose from `5.1785` to
`5.1851` (`+0.13%`) and aggregate PnL rose `$321.79` (`+0.20%`). `late_strong`
and `mid_weak` were unchanged; only `old_thin` improved, from EV `0.3179` to
`0.3245` and PnL `$24,642.07` to `$24,963.86`. No window passed the material
Gate 4 bars for EV, PnL, Sharpe, drawdown, or trade-count-with-win-rate.

Mechanism insight: BEAR_SHALLOW sizing is not a meaningful alpha surface on
the current frozen snapshots. Lowering risk trims a tiny weak-window loss
pocket, but the trade set is too small and too localized to justify another
shared policy parameter or parity test.

Do not repeat: nearby `BEAR_SHALLOW` base-risk values in the `0.25%` to
`0.75%` range on the same snapshots. A valid retry needs either forward
bear-tape evidence, a new discriminator that changes which shallow-bear trades
deserve risk, or a broader regime allocation hypothesis that is not just this
single risk_pct override again.

### 2026-05-04 mechanism update: SEC governance/procedural overlay

Status: accepted_requires_followup / not live-promoted.

Core conclusion: `exp-20260504-039` tested a fixed semantic allowlist from the
residual SEC 8-K branch as a separate `10k` notional, one-position satellite
overlay. The tested cells were `shareholder_vote + mild negative reaction`,
`charter_or_securities_change + mild positive reaction`, and `exhibit_only`
with mild positive or mild negative reaction. This is an event-sleeve candidate
source, not a core A/B slot replacement and not a production order change.

Evidence: aggregate EV rose from `5.1785` to `5.6080` (`+8.29%`) and aggregate
PnL rose from `$158,257.48` to `$166,452.07` (`+$8,194.59`, `+5.18%`). EV
improved in all three canonical windows with no EV regression:
`late_strong +0.1554`, `mid_weak +0.2435`, and `old_thin +0.0306`. The sleeve
selected `13` trades from `24` candidates, generated `$7,333.02` event PnL,
had a `61.54%` event win rate, and top absolute trade concentration was `TRIP`
at `24.14%` of absolute event PnL. The main cost is that `old_thin` max
drawdown worsened from `8.05%` to `8.89%`, still inside the guardrail.

Mechanism insight: the useful residual SEC branch is not generic "other filing"
and not another reaction-threshold surface. It looks more like temporary
uncertainty around governance/procedural disclosures where the market reaction
is mild enough for 10-day absorption/drift. The next value step is execution
parity and forward replacement-value measurement, not another static
threshold/notional/cap sweep.

Do not repeat: nearby reaction buckets, holding periods, event notionals,
one-position capacity variants, or direct production promotion on the same
frozen sample. A valid next step is a shared default-off trade-enabled event
sleeve adapter plus a persistent SEC paper/outcome ledger that freezes same-day
A/B and cash alternatives before any live capital is considered.

### 2026-05-04 mechanism update: SEC governance forward ledger

Status: accepted observe-only / production-visible but default-off.

Core conclusion: `exp-20260504-044` did not retune the SEC governance/procedural
alpha. It implemented the allowed follow-up from `exp-20260504-039`: a shared
default-off daily queue plus paper outcome ledger for the fixed governance /
procedural cells. This converts the alpha from experiment-only evidence into a
forward-measurable production artifact without changing orders, ranking,
sizing, signal generation, exits, or default core backtests.

Evidence: focused tests passed (`12 passed` across `quant/test_sec_event_queue.py`
and `quant/test_sec_event_sleeve.py`). All three canonical core backtests were
unchanged after the queue/ledger integration: `late_strong` EV `3.4191`,
`mid_weak` EV `1.4415`, and `old_thin` EV `0.3179`; PnL, Sharpe daily,
drawdown, win rate, trade count, and survival rate also matched baseline.

Mechanism insight: the highest-value current work is not another same-sample
SEC threshold/cap/notional sweep. The blocker was production observation and
replacement-value attribution for the already-positive governance/procedural
event sleeve. The right next step is to accumulate closed forward paper
outcomes and same-day alternatives, then decide whether a trade-enabled shared
adapter is justified.

Do not repeat: live promotion, reaction-bucket sweeps, holding-period sweeps,
notional sweeps, or capacity sweeps before forward paper outcomes exist. A
valid retry needs closed paper outcomes and replacement-value evidence, not
another frozen-sample optimization.

### 2026-05-04 mechanism update: Energy pair-confirmed macro ETF

Status: rejected.

Core conclusion: `exp-20260504-045` tested the valid retry condition left by
`exp-20260504-028`: macro ETF expansion must have a regime discriminator.
Requiring XLE and USO to both be above their 200-day averages with positive
10d/20d momentum did not clear the three-window materiality gate.

Evidence: best variant `xle_uso_pair_confirmed` moved aggregate EV by
`0.96` and aggregate PnL by
`$1665.95`. EV improved in
`1` windows and regressed in
`2` windows.

Do not repeat: nearby XLE/USO pair-confirmation thresholds, XLE-only list
promotion, or broad macro ETF baskets on the same frozen snapshots.

Next valid retry requires: new macro/event evidence that explains when energy
ETFs deserve scarce slots, not another ticker-list or local momentum gate.

### 2026-05-05 mechanism update: Event bundle FD/Other source composition

Status: positive marginal sample / rejected for promotion.

Core conclusion: `exp-20260505-004` tested whether the already-frozen
FD/Other Event negative-reaction sleeve from `exp-20260504-037` should become a
fourth independent source in the replay-only external event bundle from
`exp-20260504-049`. It improved EV and PnL in all three canonical windows, but
the marginal lift versus the existing three-source bundle was too small to add
another production-visible source.

Evidence: baseline three-source bundle EV sum was `6.3847`; adding FD/Other
raised it to `6.6309` (`+3.86%`). Aggregate PnL rose `$5,134.16` (`+2.88%`).
Window EV deltas were `late_strong +0.1279`, `mid_weak +0.0839`, and
`old_thin +0.0344`. FD/Other contributed `12` trades and positive PnL in all
windows, but no aggregate EV/PnL, Sharpe, or drawdown materiality gate passed.
The trade-count gate was treated as diagnostic only because adding a satellite
source mechanically increases trade count.

Mechanism insight: FD/Other negative-reaction SEC events are probably real but
not currently high-capacity enough to justify bundle complexity. The next
event-bundle work should not be another source-composition, notional, holding
period, or capacity sweep on the same frozen samples. The valid next step is
closed forward paper evidence from the existing three-source bundle, or a
materially richer event discriminator that changes event quality rather than
just adding another sparse positive source.

Do not repeat: adding FD/Other as a fourth bundle source, nearby FD reaction
thresholds, FD notional/capacity/holding-period sweeps, or direct FD production
observation on the same frozen sample. A valid retry needs closed forward
paper outcomes, a larger PIT-safe FD event sample, or structured semantics that
explain which FD/Other events deserve scarce satellite complexity.

### 2026-05-05 mechanism update: Active-position sector cap

Status: rejected.

Core conclusion: `exp-20260505-006` tested whether same-day entry sector caps
should also count already-open positions in each sector. The intuition was that
existing sector crowding might be using scarce new-entry slots too aggressively,
but the stricter cap removed useful clustered exposure.

Evidence: aggregate EV fell `-0.7323`
(`-14.14%`) and aggregate PnL fell
`$-18,734.19` (`-11.84%`).
`late_strong` and `mid_weak` both regressed; `old_thin` was unchanged.

Mechanism insight: the accepted stack still benefits from some sector clustering
after positions are already open. Sector crowding is not a portable alpha
discriminator by itself; treating concentration reduction as alpha damages
capital deployment.

Do not repeat: active-position sector-cap counting, stricter existing-sector
entry filters, or nearby sector-crowding rules without candidate-level
replacement evidence showing that the skipped clustered trade is worse than the
admitted alternative.

### 2026-05-05 mechanism update: Breakout above-200MA hard gate

Status: rejected.

Core conclusion: treating above_200ma as a hard Strategy B gate was redundant
on the canonical snapshots. The replay dropped zero actual breakout candidates
in all three windows, so this is a no-op alpha surface rather than a useful
quality discriminator.

Evidence: aggregate EV delta `+0.0000`
(`+0.00%`) and aggregate PnL delta
`$0.00` (`+0.00%`).
EV improved in `0` windows and regressed in
`0` windows.

Do not repeat: breakout above_200ma hard gates, nearby moving-average hard
gates, or extra trend-state gates for Strategy B unless candidate audits first
show that the gate would actually touch current signals.

### 2026-05-05 mechanism update: SEC leadership forward harness

Status: accepted as default-off observation harness.

Core conclusion: `exp-20260505-008` moved the shadow-positive 8-K Item 5.02
leadership-change negative-reaction branch into production-visible forward
paper tracking. This is not a promoted trading rule. It freezes same-day
candidates and core alternatives, then tracks paper-only 10-session outcomes
for replacement-value measurement.

Evidence: the production-equivalent core order path did not drift in any
canonical window. EV stayed `3.4191`, `1.4415`, and `0.3179` for
`late_strong`, `mid_weak`, and `old_thin`; aggregate PnL delta was `$0.00`.
Focused SEC queue/sleeve tests passed.

Mechanism insight: event alphas with good shadow evidence should now progress
through closed forward paper replacement-value evidence, not another frozen
sample source-composition or threshold sweep. Leadership-change selloffs are a
separate SEC uncertainty-absorption branch and should not be folded into the
existing three-source event overlay bundle until forward outcomes justify the
added source complexity.

Do not repeat: direct leadership-event trade promotion, reaction-threshold
retuning, notional/capacity sweeps, or event-bundle insertion before closed
forward paper outcomes show positive replacement value versus frozen
alternatives.

### 2026-05-05 mechanism update: Fresh OHLCV historical-attention expansion

Status: rejected for core promotion.

Core conclusion: `exp-20260505-009` tested whether the user's broader
historical attention list should be turned into a larger candidate universe by
backfilling fresh OHLCV and letting the existing A/B/C stack trade it. This
was not a small threshold tweak. It was a direct candidate-pool expansion, and
it failed across all three canonical windows.

Evidence: aggregate EV fell from `5.0936` to `2.6582` (`-47.81%`) and
aggregate PnL fell from `$157,015.83` to `$105,929.65` (`-$51,086.18`,
`-32.54%`). Every window regressed: `late_strong` EV `3.3342 -> 2.2844`,
`mid_weak` EV `1.4415 -> 0.3428`, and `old_thin` EV `0.3179 -> 0.0310`.
Max drawdown worsened in all three windows, with the largest damage in
`old_thin` (`8.05% -> 15.28%`). Trade count rose by `58` across the windows,
but win rate fell materially and the added symbols consumed slot capacity
without adding enough quality.

Mechanism insight: "more liquid, tradeable names with fresh OHLCV" is not an
alpha thesis by itself. The accepted stack still depends on disciplined
candidate selection. Expanding the universe with attention-list names adds
noise faster than it adds edge unless a smaller, mechanism-grounded sub-basket
can prove stable replacement value.

Do not repeat: broad historical-attention-list universe expansion, fresh-OHLCV
watchlist enlargement, or complexity-increasing candidate-pool growth on the
same rationale. A valid retry needs governance evidence for a much smaller
sub-basket with stable cross-window contribution, plus a clear mechanism for
why those names should win scarce slots against the accepted core universe.


## Recent mechanism insights
- `exp-20260506-016` (rejected): Conditional extra sixth core slot for
  slot-sliced SPY-relative leaders was tested as scarce-slot allocation, not a
  global capacity scan. Best `spy_leader_extra_slot_scarce_only` changed no
  `late_strong` or `mid_weak` trades and damaged `old_thin`: aggregate EV
  delta `-0.1677` (`-3.2384%`), PnL delta `$-9,158.81` (`-5.7873%`), win-rate
  delta min `-6.13 pp`. Do not retry generic MAX_POSITIONS, nearby sixth-slot,
  or sliced-SPY-leader slot unlock variants without explicit slot-collision PnL
  attribution or forward evidence that sliced leaders outperform entered
  candidates.
- `exp-20260506-007` (rejected): Post-add-on weakness reduce tested a day-3
  loss of SPY-relative follow-through plus negative post-add-on return as an
  add-on-sleeve trim. Aggregate EV delta was `-0.0016` and PnL delta was
  `$-1,191.20`; only `1/3` windows improved and only two trims executed. Do
  not retry nearby post-add-on day-count, RS-vs-SPY, or negative-return
  threshold variants without a larger touched cohort and an orthogonal
  lifecycle quality discriminator.
- exp-20260506-006: default-target SPY-relative leader target-width rejected; best `spy_leader_default_target_5_0atr` had aggregate EV delta `-1.0872` and PnL delta `$-17855.57` across the canonical three windows. Do not repeat nearby SPY-leader target widths without new forward or event/news evidence.
- `exp-20260505-015` (rejected): Consumer Discretionary trend target-width replay tested 5.0ATR/5.5ATR targets for `trend_long | Consumer Discretionary`. Best `consumer_trend_target_5_5atr` aggregate EV delta 0.0497 (0.96%), PnL delta $2183.69. Do not retry nearby Consumer trend target widths without a new event/state lifecycle discriminator or forward evidence.

- `exp-20260505-013` (rejected): Commodity breadth+momentum sector-state boost tested total 2.0x/2.5x risk for `trend_long | Commodities`. Best `commodity_state_total_2_5x` aggregate EV delta 0.2217 (4.28%), PnL delta $3397.04. Do not retry nearby Commodity state risk multipliers without a new non-price discriminator or forward evidence.

- `exp-20260505-012` (rejected): Compound severe-haircut skip was tested by zero-sizing signals with multiple existing 0.25x risk tags. Best `compound_2plus_025x_skip` aggregate EV delta 0.1883 (3.64%), PnL delta $-4063.71. Do not retry nearby severe-tag count thresholds without candidate-level replacement evidence.

- `exp-20260505-011` (rejected): Narrow consumer digital platform sub-basket `HOOD, RBLX, SOFI` was replayed after the broad historical-watchlist expansion failed. Aggregate EV delta 0.0557 (1.09%), PnL delta $8024.56. Do not promote directly to the core universe; a valid next step is universe-governance or default-off pilot treatment with forward replacement-value attribution.

- `exp-20260510-012` (accepted): RS20 entry-state shared sizing promoted the replay-only `exp-20260510-010` lead into shared `risk_engine.py` / `portfolio_engine.py` policy. The accepted 1.10x cap-aware post-sizing top-up improved aggregate EV `+0.2259` (`+3.74%`) and PnL `+$6,364.03` (`+3.58%`) with 3/3 EV-positive windows, unchanged trade count, unchanged survival, and max drawdown worsening capped at `+0.62 pp`. Stronger 1.25x and 1.50x variants were rejected for mid-window drawdown. Do not retry nearby RS20 scalars without forward attribution or a new discriminator.

- `exp-20260510-011` (rejected): Single-name AI connectivity candidate `MRVL` was replayed as the narrowest possible follow-up to the broad attention-list failure, using the three fixed windows and the existing `exp-20260505-009` fresh OHLCV snapshots because canonical snapshots do not contain MRVL. Aggregate EV delta was `-0.1356` (`-2.28%`) and PnL delta was `$-1,499.77`, with all three windows regressing despite `5` MRVL trades adding `$789.88` standalone PnL. Do not retry MRVL-only static universe promotion; any valid AI-infra candidate-pool retry needs point-in-time selection or live pilot replacement-value evidence.


- `exp-20260505-010` (rejected): Form 4 sale-pressure de-risk was tested on the three canonical windows. Best `sale_pressure_0_25x` aggregate EV delta -0.1203 (-2.32%), PnL delta $-8321.39. Do not retry simple sale-pressure veto/de-risk variants without a larger touched cohort or a new discriminator such as cluster selling, CEO/CFO-only selling, or adverse post-sale price reaction.


### 2026-05-05 mechanism update: Breakout DTE residual zero-risk

Core conclusion: exp-20260505-016 tested whether the already-haircut
Financials/Healthcare breakout event-proximity sleeve should move from 0.25x
risk to 0x. It was a deterministic alpha search, not an LLM or production
parity repair.

Evidence: aggregate EV delta was `-0.2938`
(`-0.056735`) and aggregate PnL delta was
`$-5548.11` (`-0.035057`).
Window EV improved/regressed counts were `0` /
`2`.

Do not repeat: nearby Financials/Healthcare breakout DTE zero-risk, 0.1x, or
0.5x scalar retries without new forward evidence or a richer event-quality
discriminator.


### 2026-05-05 mechanism update: Financials leader add-on cap

Status: rejected.

Core conclusion: `exp-20260505-017` tested whether accepted `trend_long`
Financials sector leaders should receive a higher first follow-through add-on
cap after passing the existing day-2 checkpoint. This was a lifecycle
allocation test, not a Financials multiplier, initial-cap, target-width,
universe, LLM, or event-threshold retry.

Evidence: best variant `financials_leader_addon_cap_60pct` moved aggregate EV by
`0.0` (`0.0`)
and aggregate PnL by `$0.0`
(`0.0`). Window EV improved/regressed counts
were `0` / `0`.

Do not repeat: nearby Financials leader add-on cap levels without forward
evidence or a richer post-entry quality discriminator.
### exp-20260505-018 breakout slot ranking
- Decision: rejected.
- Best variant: `breakout_rank_rs_then_52w`.
- Aggregate EV delta: -0.1157 (-0.022342).
- Aggregate PnL delta: -2403.87 (-0.01519).
- Mechanism insight: breakout-only collision ranking is allowed only when it demonstrates multi-window replacement value; nearby RS/confidence subsequence orders should not be retried without a fresh collision audit.

### exp-20260505-019 regime-qualified trend mid-stop haircut
- Decision: rejected/no-op.
- Best variant: `defensive_5_7pct_0_25x`.
- Aggregate EV delta: 0.0 (0.0).
- Aggregate PnL delta: 0.0 (0.0).
- Mechanism insight: adding a regime-exit bucket discriminator to the rejected 5%-7% trend initial-risk haircut did not touch any accepted-stack trades in the three canonical windows. Do not retry nearby trend 5%-7% stop-width haircuts with simple `balanced`/`defensive` buckets; a valid retry needs a different lifecycle or event/news discriminator that actually has candidate coverage.

### exp-20260505-020 consumer platform governance gate
- Decision: rejected.
- Best variant by aggregate EV: `risk_on_only`.
- Aggregate EV delta: 0.0557 (0.010935).
- Aggregate PnL delta: 8024.56 (0.051107).
- Stability check: EV improved/regressed windows were 1 / 2 for the best aggregate variant. The only variant with two improving windows, `risk_on_score_ge_0_10`, still regressed `late_strong` and only added 0.0081 aggregate EV.
- Mechanism insight: HOOD/RBLX/SOFI remain a forward-governance candidate, not a core universe addition. Simple `risk_on`, SPY-leader, score, or TQS gates do not stabilize the basket enough for promotion. A valid retry needs forward replacement-value evidence or a different ex-ante basket mechanism, not another same-sample gate.

### exp-20260506-005 financials leader target width
- Decision: rejected.
- Best variant: `financials_leader_target_5_5atr`.
- Aggregate EV delta: -0.6039 (-11.66%).
- Aggregate PnL delta: -$17,207.66 (-10.87%).
- Stability check: EV improved/regressed windows were 0 / 2; `late_strong` was unchanged because the touched cohort was absent, while `mid_weak` and `old_thin` both regressed.
- Mechanism insight: the accepted Financials sector-leader discriminator is valid for sizing, but it does not justify wider target exits. The broad Financials target-width failure was not rescued by narrowing to sector-relative leaders.
- Do not repeat: nearby Financials sector-leader target widths, or "let Financials leaders run" target changes, without new event/news evidence or forward lifecycle attribution.


### exp-20260506-011 time-stop days sweep
- Decision: rejected/no-op.
- Tested `TIME_STOP_DAYS` 30/45/60 across the canonical windows; all metrics were identical and `time_stop` exits were 0.
- Mechanism insight: the accepted stack exits before this lifecycle surface is reached. Do not retry nearby time-stop values without a trade-duration cohort where the rule would actually fire.


### 2026-05-06 mechanism update: Crypto-beta regime-guarded pool

Status: rejected.

Core conclusion: `exp-20260506-012` tested whether a narrow crypto-beta
candidate pool (`MSTR`, `IBIT`, `BITB`) should be eligible only when `IBIT`
is above its 200-day average and has positive 20-day momentum. This was a
state-gated candidate-pool alpha search, not broad watchlist growth, LLM
ranking, short-pressure tuning, or an external-event bundle sweep.

Evidence: best variant `btc_etfs_guarded` produced aggregate EV delta
`-0.0849` and aggregate PnL delta
`$-1,241.65` / `-0.77%`;
EV improved in `0` windows and regressed in
`1`. Added crypto-beta trade PnL was
`$0.00` across `0`
trades.

Mechanism insight: BTC-tape confirmation is a valid way to avoid raw noisy
crypto ticker growth, but it still must clear the same three-window Gate 4 and
shared-policy parity rules before production promotion.

Do not repeat: raw crypto-beta watchlist promotion, nearby `IBIT` momentum
guard thresholds, or adding leveraged/inverse crypto proxies without forward
evidence or a materially different external-asset state source.

### 2026-05-06 mechanism update: SEC guidance-raise selloff recovery

Status: rejected.

Core conclusion: `exp-20260506-013` tested a fixed Item 2.02 SEC event packet:
explicit guidance-raise language, no guidance-cut hit, and a non-positive
first tradeable-day SPY-relative reaction, entered on the next open as a
10-day, 10k-notional replay-only sleeve. This was an alpha search on SEC event
timing, not an LLM ranking change, broad positive-language retune, or
candidate-pool expansion.

Evidence: aggregate EV delta was `-0.0503` (`-0.9713%`) even though aggregate
PnL rose by `$467.97` (`0.2957%`). EV improved in `2` windows but regressed in
`late_strong`, and `0/3` windows cleared material EV/PnL Gate 4. Qualified
sample size was `9` events across `ISRG`, `META`, `MSFT`, `PLTR`, and `UNH`.

Mechanism insight: a weak first reaction after explicit guidance raises is not
a stable underreaction sleeve on the current sample. The small mid/old-window
P&L lift is not enough to offset EV regression in the strongest accepted-stack
window.

Do not repeat: nearby SEC guidance-raise weak-reaction sleeves, same-sample
reaction-threshold variants, or simple guidance-raise phrase-list tuning
without new forward samples or an orthogonal event-quality discriminator.

### 2026-05-06 mechanism update: high-dispersion trend de-risk

Experiment: `exp-20260506-029`

Decision: `rejected`.

Finding: High-sector-dispersion trend de-risking did not pass Gate 4. The best variant `trend_high_dispersion_0_00x` changed aggregate EV by -0.4713 and PnL by -30013.99; it does not justify a new state-aware trend sizing branch.

Do not repeat: nearby trend-only high-sector-dispersion multipliers using the same 8% dispersion threshold unless a new discriminator or forward evidence explains why the touched trades should differ.

### 2026-05-07 mechanism update: recent SEC filing breakout risk

Experiment: `exp-20260507-003`

Decision: `rejected`.

Finding: Recent PIT-safe SEC filing confirmation for `breakout_long` candidates
did not pass the three-window Gate 4 standard as a sizing alpha. The best
variant (`recent_sec_breakout_1_25x`) improved aggregate EV by `+0.1344`
(`+2.39%`) and aggregate PnL by `$4,708.21` (`+2.81%`), but EV improved in
only one window, regressed in one window, and was unchanged in the old thin
window. Wider multipliers lifted nominal PnL while degrading EV stability and
drawdown.

Mechanism insight: "any SEC filing in the last 20 trading days" is too broad
to justify breakout risk expansion. It captures some strong late-window winners
but also touches weak mid-window trades, so the filing-recency feature needs a
richer event-quality discriminator before it can support allocation.

Do not repeat: nearby recent-SEC breakout risk multipliers, wider lookbacks, or
larger scalar-only variants on the same broad filing-recency definition. A valid
retry needs event content quality, source/type specificity, or forward evidence,
not another simple recency scalar.

### 2026-05-07 mechanism update: mid-dispersion fragility guard

Experiment: `exp-20260507-009`

Decision: `rejected`.

Finding: Removing the accepted mid-sector-dispersion `trend_long` allocation
boost from already-fragile sizing sleeves did not create material alpha. The
best variant, `no_multi_fragility_stack`, improved aggregate EV by only
`+0.0008` and aggregate PnL by `$44.49`; the broader tech/any-fragility guards
regressed aggregate EV and PnL. No production policy was changed.

Do not repeat: nearby mid-dispersion fragility stacking guards, haircut-count
variants, or "do not stack positive boost on existing haircut" variants on the
accepted mid-dispersion trend rule without new forward evidence or a materially
different discriminator.

### 2026-05-07 mechanism update: broad-breadth conviction trend risk

Experiment: `exp-20260507-010`

Decision: `rejected`.

Finding: A cleaner version of the rejected broad-breadth trend risk boost did
not clear Gate 4. The tested qualifier required broad 200-day universe
participation plus at least three existing positive accepted sizing multipliers
and zero accepted haircuts. Best variant `conviction_breadth_trend_1_50x`
improved aggregate EV by only `+0.0348` (`+0.62%`) and aggregate PnL by
`$858.13` (`+0.51%`). EV improved in only `1/3` fixed windows. The 1.5x and
2.0x variants were equivalent because the touched trades were constrained by
existing position caps.

Mechanism insight: broad 200-day participation still looks like a descriptive
state feature, not a promotion-ready allocation surface. Adding an accepted
conviction qualifier removed the risk damage from `exp-20260507-007`, but it
also removed most of the economic lift. Scarce capital is already largely
allocated to these high-conviction winners by the existing stack.

Do not repeat: nearby broad-breadth conviction multipliers, 3-positive-stack
variants, or cap-insensitive broad-breadth trend risk boosts without new
forward evidence or an orthogonal event/news/state discriminator that changes
which high-conviction trades have remaining sizing headroom.


### 2026-05-07 mechanism update: earnings sleeve revalidation

Experiment: `exp-20260507-011`

Decision: `rejected`.

Finding: Re-enabling `earnings_event_long` after P-ERN snapshot backfill did
not pass the canonical three-window Gate 4 standard. EV regressed in all three
windows; aggregate EV delta was `-2.0504`
and aggregate PnL delta was `$-38828.27`.

Mechanism insight: P-ERN snapshot coverage fixes the prior measurement blocker,
but the current C-sleeve rule is still not a production-ready alpha source. It
adds low-win-rate earnings trades and displaces stronger A/B capital.

Do not repeat: simply adding `earnings_event_long` back to
`ENABLED_STRATEGIES`, or nearby C-sleeve enablement without a stronger
event-quality discriminator such as directional guidance, same-accession facts,
or closed forward event evidence.

### 2026-05-07 mechanism update: state-surface conviction prune

Experiment: `exp-20260507-017`

Decision: `rejected`.

Finding: Removing `balanced_state_leadership` from the replay-only
state-surface satellite did not improve the full-surface result. The pruned
variant still improved the core baseline by aggregate EV `+0.2855` and PnL
`+$24,777.48`, but it regressed `late_strong` EV by `-0.4772`, improved only
`2/3` windows, and underperformed the full `exp-20260507-016` replay by
`-0.9774` EV and `-$11,315.31` PnL.

Mechanism insight: the balanced surface looks noisy in contribution tables, but
removing it breaks late-window robustness and weakens the overall satellite.
Surface-level pruning based only on one replay's realized contribution is too
coarse; the full state-surface package remains the better replay-only lead.

Do not repeat: nearby state-surface surface-subset pruning, balanced-only
removal, or simple surface allowlist variants without a new ex-ante quality
feature. A valid next step is a default-off shared production/backtest paper
adapter for the full surface, not another same-sample surface subset sweep.

### 2026-05-07 mechanism update: satellite shared-capacity allocation

Experiment: `exp-20260507-019`

Decision: `rejected`.

Finding: Combining the two strongest replay-positive default-off surfaces under
one max-3 active satellite budget did not beat the event-only baseline. The
shared-cap stack remained strong versus core (`+1.4069` aggregate EV,
`+$37,774.25` PnL, EV improved in all three windows), but the correct marginal
baseline is the full event bundle. Versus event-only, aggregate PnL improved
`+$21,498.59`, but `late_strong` EV regressed `-0.3226` and Sharpe fell
`-0.36`; EV improved in only `2/3` windows.

Mechanism insight: state-surface is not automatically complementary to the
event bundle just because both are positive versus core. In the strongest
window, adding state-surface idle-capacity trades diluted event-only risk
quality. The separate event and state-surface paper sleeves should continue
collecting forward outcomes independently; a combined meta-satellite adapter
needs new forward evidence, not another same-sample capacity or priority tweak.

Do not repeat: nearby event+state-surface shared-cap variants, event-vs-state
priority flips, max-active satellite cap sweeps, or "state fills event idle
slots" retries without closed forward paper outcomes or a new ex-ante
complementarity discriminator.

### 2026-05-07 mechanism update: FD/Other item 8.01 semantics

Experiment: `exp-20260507-020`

Decision: `rejected_positive_immaterial`.

Finding: A structured SEC item-code discriminator inside the FD/Other
negative-reaction sleeve was directionally positive but still below Gate 4
materiality. Requiring item `8.01` and excluding item `7.01` improved EV in all
three fixed windows with no EV regression: aggregate EV delta `+0.3276`
(`+5.82%`) and aggregate PnL delta `$+7,720.27` (`+4.61%`). The event sleeve
selected `10` trades, generated `$+6,836.77` event PnL, and had `80.0%` event
win rate. Versus the full FD/Other source, the filter removed losing selected
`LITE` and `COIN` item-7.01 trades, improving source event PnL by `$+1,702.60`,
but the total lift still missed the `>10%` EV and `>5%` PnL acceptance bars.

Mechanism insight: item-code semantics are a better FD/Other quality direction
than source-composition or threshold retuning, but this sample is still too
sparse and too small to justify another production-visible event source. The
right interpretation is "keep observing this semantic cut", not "promote item
8.01 FD/Other into the event bundle".

Do not repeat: nearby FD/Other item-code filters such as excluding only item
`7.01`, requiring `8.01+9.01`, or small semantic allowlist tweaks on the same
frozen samples without closed forward paper outcomes or a materially larger
PIT-safe FD/Other event sample.

### 2026-05-07 mechanism update: event pre-entry relative momentum

Experiment: `exp-20260507-022`

Decision: `rejected`.

Finding: Tilting default-off event-bundle notional toward trades with stronger
PIT-safe 5-trading-day pre-entry return versus SPY did not beat the full frozen
event bundle. The best variant, `preentry_rs_2pct_150_050`, remained attractive
versus core (`+1.2486` aggregate EV and `+$20,425.91` PnL), but the correct
marginal baseline is the existing full event bundle. Versus full bundle it
added only `+0.2689` aggregate EV (`+4.14%`) and `+$4,155.39` PnL (`+2.28%`),
with `mid_weak` regressing by `-0.0056` EV and `-$181.81` PnL.

Mechanism insight: simple PIT-safe pre-entry relative momentum is a descriptive
event-quality feature, not a promotion-ready allocation rule. It helps
`late_strong` and `old_thin`, but the small `mid_weak` regression and sub-Gate
4 materiality show that the full event bundle remains the stronger replay
surface.

Do not repeat: nearby 5-day pre-entry relative-strength scalar tilts, sign
gates, or +2pp threshold variants on the same frozen event-bundle sample
without forward event replacement-value evidence or a materially different
event-quality discriminator.

### 2026-05-07 mechanism update: event pre-entry price structure

Experiment: `exp-20260507-024`

Decision: `rejected`.

Finding: Medium-term PIT-safe price-structure confirmation did not improve the
frozen default-off event bundle robustly. The best variant,
`price_structure_150_050`, tilted event notional toward rows where the ticker's
pre-entry close was above SMA50 and SMA20 was above SMA50. It improved
aggregate EV by `+1.3100` and aggregate PnL by `+$45,759.05` versus the full
bundle, but the correct Gate 4 standard is multi-window stability: `late_strong`
regressed by `-1.1027` EV and `-$5,254.62` PnL, so the result improved only
`2/3` windows and failed the zero-regression requirement.

Mechanism insight: medium-term trend structure is a powerful event-quality
descriptor in weaker windows, but it appears to remove or underweight too much
late-window event upside. This is not a production alpha, and the full frozen
event bundle remains the better replay-only surface while forward paper
outcomes accumulate.

Do not repeat: nearby SMA20/SMA50 event price-structure tilts, SMA confirmation
skips, or small scalar variants on the same frozen event-bundle sample without
closed forward event outcomes or a materially different event-quality
discriminator that explains the late-window failure.

### 2026-05-07 mechanism update: far-from-earnings entry-state risk

Experiment: `exp-20260507-033`

Decision: `rejected`.

Finding: Rewarding accepted A/B trades tagged `pre_earnings_46_plus` with a
cap-aware risk add-on was directionally positive, but not stable enough for
promotion. The best variant, `far_earnings_1_50x_cap_aware`, added `+$8,678.54`
proxy PnL (`+5.23%`) and `+0.3173` aggregate proxy EV (`+3.91%`), but it
regressed the `mid_weak` window by `-$245.77` and `-0.0214` EV. It also worsened
max drawdown by `+1.05pp` in `old_thin`, just beyond the Gate 4 drawdown limit.

Mechanism insight: being far from the next earnings date is a useful descriptive
entry-state tag, but it is not a standalone sizing alpha. The effect appears to
mostly reward already-strong mature winners while adding drawdown in the older
thin window and failing the zero-regression requirement.

Do not repeat: nearby `pre_earnings_46_plus` risk multipliers, cap-only variants,
or small distance-from-earnings threshold tweaks on the same three frozen
windows without forward evidence or a materially different event-quality
discriminator.

### 2026-05-08 mechanism update: Commodity near-high risk scalar

Experiment: `exp-20260508-003`

Decision: `rejected`.

Finding: Raising the accepted `trend_long + Commodities + pct_from_52w_high >= -0.03`
risk multiplier from `1.5x` to `2.0x` did not clear Gate 4. It improved only
`late_strong` (`EV +0.0657`, PnL `+$1,110.16`) while `mid_weak` and `old_thin`
were unchanged because the extra risk budget was mostly absorbed by position
caps and existing allocation constraints. Aggregate EV improved only `+1.19%`
and aggregate PnL only `+0.67%`.

Mechanism insight: the Commodity near-high sleeve is still high quality, but
the next raw risk-budget increment is not the current bottleneck. More scalar
tuning on this sleeve is unlikely to matter without new evidence that cap room,
heat, macro state, or event context can unlock additional return without
repeating the rejected heat/add-on-cap families.

Do not repeat: nearby `1.75x`, `2.0x`, or `2.5x` Commodity near-high risk
multipliers on the same fixed snapshots. A valid retry needs a materially new
capacity or ex-ante context discriminator, not another scalar-only replay.

### 2026-05-08 mechanism update: Platform RS20 entry-state replay

Experiments: `exp-20260507-034`, `exp-20260507-035`

Decision: `rejected / observed-only underpowered`.

Finding: Platform `rs20_leader` is a useful oracle tag but not a production entry rule. The hard no-backfill entry gate skipped only 4 candidates, improved aggregate EV only `+2.84%`, reduced PnL by `$1,925.31`, and had NFLX concentration `77.58%` of positive contribution. The complementary missed-candidate fixed-notional sleeve audit showed `+$7,971.93` on 6 missed candidates, but APP contributed `87.76%` of positive PnL and late_strong lost money.

Mechanism insight: RS20 leadership describes where platform upside can appear, but the tradable edge is currently dominated by too few names and too few missed entries. Treat it as an oracle/forward attribution feature, not a hard entry gate, risk scalar, or sleeve.

Do not repeat: nearby platform RS20 thresholds (`0pp`, `3pp`, `4pp`, `5pp`), same-day refill variants, or platform-RS20 missed-candidate sleeve promotion on the same frozen sample. A valid retry needs forward paper evidence, at least 8 missed candidates, lower single-ticker concentration, or an orthogonal event/news/earnings-quality discriminator.

### 2026-05-08 mechanism update: event state-score floor

Experiment: `exp-20260508-005`

Decision: `rejected`.

Finding: Tightening the current non-generic positive state-surface event add-on
by requiring a higher PIT state score did not clear the correct marginal
baseline. The best stricter variant, `non_generic_score_gt_050_2x`, improved
EV in all three fixed windows versus the current `score > 0` add-on, but only
by `+0.0796` aggregate EV (`+1.12%`) and `+$1,569.68` aggregate PnL (`+0.82%`).
It remained strongly positive versus the full frozen event bundle, but the
current paper rule had already captured most of that edge.

Mechanism insight: the non-generic state-surface event add-on is still the
right event-quality direction, but extra score-floor precision is not the
current bottleneck. Requiring `state_score > 0.50` mostly removes weak-positive
event rows without creating enough marginal return to justify another rule.

Do not repeat: nearby event state-score floors such as `>0.25`, `>0.50`,
`>0.75`, or `>1.00` on the same frozen event sample. A valid retry needs closed
forward event replacement-value evidence or a materially different event-quality
feature, not another small score threshold.

### 2026-05-08 mechanism update: Platform RS20 no-gap missed feature

Experiment: `exp-20260508-007`

Decision: `observed_only_underpowered`.

Finding: On the six missed platform `rs20_leader` candidates from
`exp-20260507-035`, the existing `no_gap_up_3pct` state split was directionally
clean but too small. No-gap rows were `3/3` winners with `+$10,353.51` fixed
notional PnL and `34.95%` average return; the complement `gap_up_3pct` rows were
`0/3` winners with `-$2,381.58` PnL. The observed gate still failed because the
matched sample had only 3 candidates and APP contributed `87.76%` of positive
PnL.

Mechanism insight: For missed platform RS20 candidates, the apparent edge is
not "RS20 strength" alone. It is closer to "RS20 strength without signal-day
gap chase." This is a strong forward-watch hypothesis, but not a tradable sleeve
or entry rule on the frozen sample.

Do not repeat: no-gap platform RS20 missed-candidate sleeve promotion, hard
gap-up skips, or same-day refill variants on this same six-row sample. A valid
retry needs at least 8 no-gap missed candidates, lower single-ticker
concentration, or a genuinely orthogonal event/news/earnings-quality
discriminator.

### 2026-05-08 mechanism update: Platform RS20 no-gap forward watch

Experiment: `exp-20260508-008`

Decision: `accepted_measurement_adapter`.

Finding: The platform RS20 no-gap hypothesis was moved from frozen-sample
analysis into a default-off forward watch. `run.py` now records platform-pool
missed entry candidates from `scarce_slot_breakout_deferred` and `slot_sliced`
when they are RS20 leaders without a signal-day `gap_up_3pct`; the report
renders them as observe-only and the ledger dedupes daily rows. This does not
alter signal generation, ranking, sizing, exits, slots, or orders.

Mechanism insight: The correct response to the clean-but-underpowered no-gap
split is sample accumulation, not another same-sample rule. Future promotion
requires closed forward outcomes, at least 8 no-gap missed candidates, and
single-ticker positive contribution at or below `50%`.

Do not repeat: additional same-sample platform RS20/no-gap sweeps before the
forward ledger has enough closed outcomes.

### 2026-05-08 mechanism update: SMA20 reclaim missed-candidate sleeve

Experiment: `exp-20260508-010`

Decision: `rejected`.

Finding: Existing A/B candidates tagged `sma20_reclaim` but missed by the core
entry path did not show replacement value as a fixed-notional 20-day sleeve.
Across the canonical three windows, the audit found 8 missed candidates, total
PnL `-$1,710.86`, win rate `37.5%`, and only 1/3 positive windows. The only
positive window was `mid_weak` with `+$365.22`; `late_strong` lost `-$2,040.69`
and `old_thin` lost `-$35.39`. Positive contribution was still too concentrated
at `57.07%`.

Mechanism insight: Narrowing pullback/reclaim logic to existing missed
candidates did not rescue the rejected broad pullback/reclaim family. SMA20
reclaim remains descriptive state context, not a default-off sleeve or entry
permission signal.

Do not repeat: broad pullback/reclaim promotion, SMA20 reclaim missed-candidate
sleeves, or nearby reclaim-entry variants on the same frozen samples. A valid
retry needs a materially different discriminator or closed forward missed-entry
evidence.

### 2026-05-08 mechanism update: Analyst estimate revision readiness

Experiments: `exp-20260508-006`, `exp-20260508-011`

Decision: `data-gap repaired, alpha still blocked`.

Finding: repairing `next_earnings_date` from PIT `days_to_earnings` was useful
infrastructure, not proof of alpha. `exp-20260508-006` repaired same-event
identity well enough to produce forward-ledger rows (`41` rows with
`next_earnings_date`, `39` with a prior same-event snapshot, `GS` and `LITE`
matched in the smoke check), but the three-window readiness audit in
`exp-20260508-011` still found zero candidate touches and revision steps only
inside `late_strong` (`37` total). `mid_weak` and `old_thin` still have zero
usable non-event-day revision steps.

Mechanism insight: "schema repaired" is not the same as "ranking field ready."
Do not promote analyst estimate revisions as an A/B ranking or veto input until
the data exists across multiple windows and actually touches candidate dates.

Do not repeat: nearby revision-lookback tweaks, nearby DTE gates, or replaying
the same historical estimate snapshots as if they were already a stable
three-window PIT revision ledger.

Next valid retry requires: 30-60 forward trading days of append-only revision
ledgers with same-event identity, real candidate touches across at least two
regimes, and replacement-value evidence that tagged names beat the default
same-day A/B alternatives.

### 2026-05-08 mechanism update: Liquidity-gated 10-K forward watch

Experiments: `exp-20260508-011`, `exp-20260508-012`

Decision: `accepted measurement adapter, not promoted alpha`.

Finding: among the currently blocked external-alpha directions, liquidity-gated
outside-universe 10-K scouts remain the best next candidate-pool lead, but the
right action was to freeze forward evidence instead of promoting a rule.
`exp-20260508-011` kept 10-K ahead of analyst revisions because old/late
windows showed positive 10-day excess and same-day replacement proxy, but
`mid_weak` had only one negative row. `exp-20260508-012` then created the
append-only PIT watch, and the first five PIT-safe 10-K rows produced zero
eligible candidates because all observed rows were amendment-excluded
`TSLA 10-K/A`.

Mechanism insight: the right next step for 10-K alpha is not threshold tuning,
SEC universe expansion, or replay promotion. It is sample accumulation with
frozen same-day alternatives and closed forward replacement-value outcomes.

Do not repeat: same-sample 10-K promotion attempts, broad SEC filing universe
expansion, or static threshold retunes before the forward watch has real
outside-universe eligible candidates.

Next valid retry requires: append-only PIT 10-K eligibility rows with actual
outside-universe candidates, frozen same-day A/B alternatives before entry, and
closed 5/10/20-day replacement-value outcomes across at least two regimes.

### 2026-05-08 mechanism update: SLV precious-metals target state

Experiment: `exp-20260508-016`

Decision: `rejected`.

Finding: Retrying SLV trend target widening with a pre-registered
precious-metals state discriminator did not clear the canonical three-window
gate. The best variant, `slv_ret20_gt_gld_ret20`, retargeted SLV from 7 ATR to
8 ATR when SLV 20-day momentum led GLD. It improved `late_strong` only
slightly (`EV +0.0576`, `PnL +$910.47`), damaged `mid_weak` materially
(`EV -0.3248`, `PnL -$7,625.95`, `Sharpe -0.24`), and had no effect in
`old_thin`. The stricter 2pp spread and both-positive variants produced the
same rejection pattern.

Mechanism insight: SLV leadership over GLD is not enough to explain when
silver trend continuation deserves the gold-like 8 ATR target. The old
commodity lesson still holds: gold ETF convexity is robust enough for the wider
target, while SLV target extension remains regime-fragile and can consume slots
long enough to hurt replacement value.

Do not repeat: SLV 7-to-8 ATR target variants based only on SLV-vs-GLD 20-day
relative momentum, positive precious-metals momentum, or nearby spread
thresholds on the same frozen samples. A valid retry needs a materially
different silver-specific lifecycle signal, such as forward evidence that SLV
target misses beat same-day alternatives after accounting for slot occupancy.

### 2026-05-08 mechanism update: Add-on heat ceiling

Experiment: `exp-20260508-017`

Decision: `rejected_for_production_policy`.

Finding: Removing the portfolio-heat cap only from add-on execution, while
leaving entry heat gating and all add-on trigger/fraction/position-cap logic
unchanged, improved EV in all three canonical windows: `late_strong +0.3239`,
`mid_weak +0.0717`, and `old_thin +0.0224`. Aggregate PnL improved
`+$10,328.98` (`+6.17%`), and scheduled add-ons moved from `11/18` executed to
`18/18` executed. The replay still passed per-window Gate 4 only in
`late_strong`, and the change is not production-safe because it weakens a hard
portfolio risk cap.

Mechanism insight: day-2 follow-through add-ons still have positive marginal
expectancy after the accepted stack, but raw heat-cap relaxation is the wrong
implementation surface. The alpha surface is capital reservation or an
add-on-specific spending discriminator, not another global heat-cap sweep or
add-on trigger retune.

Do not repeat: raw add-on heat-cap removal or nearby heat-cap increases as a
production policy. A valid retry must keep the hard portfolio risk cap intact
and test a shared production/backtest add-on reserve or state-specific
discriminator that decides when confirmed-winner heat is worth spending.

### 2026-05-08 mechanism update: Add-on execution priority

Experiment: `exp-20260508-018`

Decision: `rejected_no_effect`.

Finding: Sorting same-day scheduled follow-through add-ons by checkpoint
`rs_vs_spy`, `unrealized_pct`, and SPY-relative leader status before sequential
heat allocation produced no metric changes in any canonical window. EV, PnL,
Sharpe, drawdown, trade count, win rate, and survival all stayed exactly flat:
`late_strong 3.7435`, `mid_weak 1.5478`, and `old_thin 0.3359` EV before and
after.

Mechanism insight: the add-on heat bottleneck from `exp-20260508-017` is not a
same-day ordering problem. Missed add-ons usually had zero available heat room
before ordering mattered, so a priority key cannot unlock the positive shadow
capacity.

Do not repeat: nearby same-day add-on ordering keys on the same fixed windows.
A valid retry needs a real hard-cap-preserving reserve, lifecycle-staged
sizing, or an ex-ante discriminator that changes budget availability, not just
which queued add-on is processed first.

### 2026-05-08 mechanism update: Same-sector cap quality replacement

Experiment: `exp-20260508-020`

Decision: `rejected`.

Finding: Replacing the current input-order same-day sector cap with a local
quality selector inside each sector collision did not improve the fixed-window
stack. The variant kept the top same-sector candidates by
`trade_quality_score`, then `confidence_score`, then `pct_from_52w_high`, while
preserving global order for kept candidates and leaving `MAX_PER_SECTOR`,
sizing, exits, add-ons, scarce-slot routing, LLM/news, and the universe
unchanged. It was inert in `late_strong` and `old_thin`, but regressed
`mid_weak`: EV `1.5478 -> 1.4800`, PnL `$57,542.74 -> $56,062.37`, and win rate
`52.38% -> 50.00%`.

Mechanism insight: Same-sector cap collisions are not a hidden TQS/confidence
misallocation surface in the accepted stack. The current sector cap should
remain order-preserving unless a genuinely new event/news replacement signal
shows that the skipped clustered trade is worse than the admitted alternative.

Do not repeat: nearby sector-cap quality keys, confidence keys, TQS-only local
replacement, or same-sector near-high replacement on the same fixed windows.

Next valid retry requires: candidate-level replacement evidence from an
orthogonal source, preferably event/news context, not another deterministic
quality-key permutation.


### 2026-05-08 mechanism update: Adverse-gap reclaim delayed entry

Experiment: `exp-20260508-022`

Decision: `rejected`.

Finding: A delayed-entry satellite for adverse-gap-cancelled A/B candidates
with same-day reclaim evidence did not clear the three-window Gate 4 standard.
Best variant `intraday_reclaim_next_open` changed aggregate EV by
`-0.0411` and aggregate PnL by
`$153.08` across
`2` satellite trades.

Mechanism insight: reclaim behavior is a valid orthogonal information source
relative to rejected raw gap-cancel bypasses, but this replay is not strong
enough for production promotion. Keep the accepted 2% adverse-gap cancel
unchanged.

Do not repeat: adverse-gap delayed-entry sleeves based only on same-day high or
close reclaim of the original signal entry. A valid retry needs richer
intraday structure, fresh event/news confirmation, or forward paper evidence
that reclaimed adverse-gap candidates beat same-day alternatives.

### 2026-05-08 mechanism update: Add-on execution memory

Experiment: `exp-20260508-027`

Decision: `accepted_measurement_adapter`.

Finding: Production already had code-decided day-2 follow-through add-ons, but
the pending-action ledger only tracked `REDUCE` and `EXIT`. A missed or
conservatively skipped `ADD` could disappear after the checkpoint day even
though recent add-on attribution showed confirmed-winner exposure still has
positive marginal value. The adapter now records `add_on_trades` as pending
`ADD` actions and repeats them until `open_positions` share count reconciles.

Mechanism insight: the immediate production gap was execution memory, not
another add-on trigger. This preserves already-decided add-on intent without
relaxing heat caps, changing add-on fractions, or expanding the checkpoint
window.

Do not repeat: using this finding as justification for raw heat-cap increases,
same-day add-on ordering keys, volume confirmation filters, or wider add-on
windows. The next valid step is a separate intended-share/top-up replay for
conservative entries.

### 2026-05-08 mechanism update: Form 4 cluster satellite

Experiment: `exp-20260508-028`

Decision: `rejected`.

Finding: PIT-safe clustered Form 4 meaningful open-market purchases were
directionally positive as a standalone satellite, but too sparse and
concentrated for production promotion. Across the fixed three-window protocol,
aggregate EV improved by `0.2193` (`+3.63%`) and aggregate PnL improved by
`$3,640.82` (`+2.05%`). `late_strong` and `mid_weak` improved, while
`old_thin` was unchanged. The sleeve selected only `3` event trades, and the
largest single-ticker positive contribution was `55.64%`.

Mechanism insight: clustered insider buying remains a real forward-watch
signal, but this frozen historical sample is not broad enough to justify a live
strategy sleeve. The right next step is forward paper accumulation or a larger
PIT event archive, not threshold retuning.

Do not repeat: Form 4 cluster satellite promotion, nearby cluster-window tweaks,
owner-role filters, or purchase-value threshold sweeps on this same frozen
sample. A valid retry needs at least `8` selected cluster events, lower
single-ticker concentration, or closed forward paper sleeve outcomes.

### 2026-05-08 mechanism update: Conservative-entry top-up metadata

Experiment: `exp-20260508-029`

Decision: `accepted_measurement_adapter`.

Finding: The live portfolio cannot currently tell whether several non-legacy
positions were filled at the original intended size or bought conservatively.
The current audit found `0/4` non-legacy positions with intended-share metadata:
`MSFT`, `SNXX`, `UNH`, and `AMZN` are missing `original_shares` /
`intended_shares` / equivalent fields. Without this, production follow-through
logic falls back to current shares and can silently treat an underfilled entry
as a complete position.

Mechanism insight: The next add-on improvement is not a new trigger or wider
checkpoint window. It is an intent-metadata repair: record the original signal
share count separately from current broker shares, then test a conservative
entry top-up replay. Production now uses intended-share metadata when present
and surfaces missing metadata in the LLM preflight audit.

Do not repeat: add-on heat-cap relaxation, same-day add-on ordering keys,
volume confirmation filters, or attempts to infer intended entry size from
current shares. A valid retry needs trustworthy `original_shares` or
`intended_shares` populated for the live positions or a frozen historical entry
ledger that preserves original signal size.

### 2026-05-08 mechanism update: Staged entry top-up replay

Experiment: `exp-20260508-034`

Decision: `rejected`.

Finding: A direct conservative-entry lifecycle replay tested buying only
`50%` or `75%` of each accepted A/B signal initially while preserving the
original computed share count for the existing day-2 follow-through add-on.
This was a true alpha-search capital-allocation test, not a logging repair.

The best variant was `initial_75pct`. It reduced max drawdown in all three
canonical windows, but EV and PnL regressed in all three windows:
aggregate EV fell from `6.0452` to `4.7171` (`-21.97%`), and aggregate PnL
fell by `$38,883.33` (`-21.88%`). `initial_50pct` was worse.

Mechanism insight: the current accepted entries already need full initial
exposure; the day-2 follow-through add-on is not enough to recover the upside
lost by staging every entry. Drawdown reduction alone is not sufficient under
the EV-first north-star rule.

Do not repeat: nearby `50%` to `75%` staged-entry fractions, blanket
conservative initial buys, or "buy small then top up all confirmed winners"
without a new ex-ante discriminator identifying which entries should be staged.
A valid retry must be selective, shared by production and backtest before
promotion, and must improve EV/PnL rather than only lowering drawdown.

### 2026-05-08 mechanism update: Early-adverse no-reclaim exit

Experiment: `exp-20260508-035`

Decision: `rejected`.

Finding: A stricter lifecycle exit for already-open A/B trades that suffered
at least `-3%` early MAE and failed to reach `+2%` MFE within the first three
trading days did not survive replay. It improved `old_thin` (`EV +0.1029`,
PnL `+$1,846.58`) but damaged `late_strong` badly (`EV -1.4869`, PnL
`-$15,539.57`) and was inert in `mid_weak`. Aggregate proxy EV fell
`-1.3840` (`-15.88%`) and aggregate PnL fell `-$13,692.99` (`-7.71%`).

Mechanism insight: even requiring both material early adversity and lack of
early reclaim still cuts valuable late-window shakeouts. The biggest positive
delta came from one old-window loser (`TRIP`), while the rule truncated large
`MU` and `SLV` winners. The refreshed hold-quality taxonomy is useful for
diagnosis, but this price-path-only exit trigger is not a production alpha.

Do not repeat: nearby three-day early-adverse/no-reclaim exit thresholds such
as `2-4` confirmation days, `-2%` to `-4%` MAE, or `+1%` to `+3%` early MFE
on the same samples. A valid retry needs an orthogonal event/news/market-state
discriminator that separates true failed holds from bullish shakeouts, and any
positive version must be implemented as shared production/backtest lifecycle
policy before promotion.

### 2026-05-09 mechanism update: Add-on entry heat reserve

Experiment: `exp-20260509-004`

Decision: `rejected`.

Finding: A hard-cap-preserving add-on reserve was tested by lowering only the
new-entry heat admission threshold while leaving the portfolio hard heat cap and
add-on cap calculation at the unchanged `8%` ceiling. The sweep covered
`0.5pp`, `1.0pp`, `1.5pp`, and `2.0pp` reserves across the three canonical
windows.

The best variant, `reserve_0_5pct_heat`, was inert: aggregate EV stayed
`6.0452`, aggregate PnL stayed `$177,676.93`, and all three windows were
unchanged. Larger reserves did not unlock add-on value; `1.5pp` and `2.0pp`
regressed `old_thin` by `-0.0872` EV and `-$4,759.83` PnL while leaving the
other windows unchanged.

Mechanism insight: the add-on heat bottleneck identified in `exp-20260508-017`
is not solved by reserving generic entry heat. The capital shortfall is not
caused by new entries arriving in the narrow heat band just below the cap; it
requires a real add-on-specific value discriminator or forward replacement
evidence.

Do not repeat: nearby generic entry-heat reserve thresholds, especially
`0.5pp` through `2.0pp`, as an add-on capital allocation fix. A valid retry
needs a state-specific add-on value discriminator, not another generic reserve.

### 2026-05-09 mechanism update: Non-generic event state add-on current stack

Experiment: `exp-20260509-007`

Decision: `promising_replay_only_non_generic_event_state_addon`.

Finding: after the current core stack and full event bundle were refreshed,
the prior non-generic state-surface add-on remained the best event-bundle
allocation lead. The tested single variable was a 2.0x paper-notional add-on
only for event rows with positive PIT state score on a non-generic state
surface; event sources, thresholds, hold days, core A/B behavior, LLM/news,
sizing, exits, and orders stayed unchanged.

Relative to the full event bundle, EV improved in all three canonical windows:
`late_strong +0.3209`, `mid_weak +0.2703`, and `old_thin +0.0293`. Aggregate
EV improved `+0.6205` (`+8.80%`) and aggregate PnL improved `+$10,040.02`
(`+5.18%`), clearing Gate 4 via PnL materiality with zero EV regressions.
Relative to core-only, aggregate EV improved `+1.6292` (`+26.95%`) and PnL
improved `+$26,343.86` (`+14.83%`).

Mechanism insight: the strongest current alpha surface is not another core
threshold, slot, source-pruning, or generic heat-reserve tweak. It is event
candidate-pool allocation: let the frozen default-off event bundle stand, then
spend extra paper notional only when an orthogonal PIT state surface says the
event ticker is on a named, non-generic opportunity surface.

Do not repeat: nearby event source subsets, same-sample event overlap filters,
hold-day/notional retunes, or broad positive-vs-nonpositive state-score tilts
as separate experiments. The current lead is specifically the non-generic
positive state-surface add-on, and it remains paper-only.

Next valid retry requires: closed forward paper replacement-value outcomes or
an explicit shared trade-enabled event adapter with run/backtester parity tests.
Until then, do not route this to live/default orders even though the historical
three-window evidence is positive.

### 2026-05-09 mechanism update: State-surface current-stack revalidation

Experiment: `exp-20260509-010`

Decision: `promising_replay_only_current_stack`.

Finding: the frozen state-surface satellite sleeve remains positive after the
accepted-stack refresh. The tested single variable was the existing bounded
paper sleeve: top-three non-overlapping production-universe state-surface
candidates, next-open entry, 20-trading-day hold, and at most three active
paper positions. Core A/B behavior, event bundle, LLM/news, sizing, exits,
add-ons, pilot sleeves, and production orders stayed unchanged.

Relative to current core-only, EV improved in all three canonical windows:
`late_strong +0.0592`, `mid_weak +0.7622`, and `old_thin +0.4921`.
Aggregate EV improved `+1.3135` (`+21.73%`) and aggregate PnL improved
`+$36,120.97` (`+20.33%`). Single-ticker positive contribution was `31.34%`,
inside the concentration guard. The tradeoff is that `late_strong` Sharpe fell
`-0.17` and max drawdown rose `+0.27 pp`, so this is not a clean production
promotion signal.

Mechanism insight: state-surface candidate-pool extension is still a real
paper alpha family and is the strongest non-event candidate-pool lead after
LLM ranking, earnings/revisions, gap/reclaim, staged entry, and add-on reserve
surfaces were blocked or rejected. However, by the north-star EV score the
non-generic event state add-on from `exp-20260509-007` remains the stronger
current replay lead versus core (`EV +1.6292` versus `+1.3135`). Treat
state-surface as a parallel paper sleeve candidate, not a reason to demote the
event-bundle lead.

Do not repeat: rerunning the same full state-surface current-stack replay,
dropping `balanced_state_leadership` again, or sweeping nearby top-N,
max-active-position, hold-day, and notional parameters on the same frozen
sample. A valid retry needs either closed forward paper replacement-value
outcomes, a shared run/backtester trade adapter with parity tests, or an
orthogonal discriminator that explains the `late_strong` Sharpe/drawdown
tradeoff without retuning the sleeve mechanics.

### 2026-05-09 mechanism update: Event-state plus state-surface stack

Experiment: `exp-20260509-012`

Decision: `promising_replay_only_additive_stack_risk_flag`.

Finding: the two strongest frozen paper sleeves are additive in aggregate, but
not clean enough for production promotion. The tested single variable was to
add the frozen state-surface satellite sleeve from `exp-20260509-010` on top of
the frozen non-generic event state add-on from `exp-20260509-007`. Event source
definitions, state-surface parameters, core A/B behavior, LLM/news, sizing,
exits, and production orders stayed unchanged.

Against the event-state add-on baseline, aggregate EV improved from `7.6744`
to `9.0131` (`+1.3387`, `+17.44%`) and aggregate PnL improved from
`$204,020.79` to `$239,230.09` (`+$35,209.30`, `+17.26%`). PnL improved in all
three canonical windows and EV improved in two of three:
`mid_weak +0.8605`, `old_thin +0.5061`, but `late_strong -0.0279`.

Mechanism insight: candidate-pool extension alpha can stack across event-state
and state-surface sleeves, especially in weaker/older windows where the state
surface adds replacement value. The risk is that the same stack adds marginal
Pnl in the strongest tape while lowering Sharpe (`late_strong -0.22`) and
raising drawdown (`+0.88 pp`), so it is not a clean live-capital instruction.

Do not repeat: simple sleeve stacking, event-source retunes, state-surface
top-N/hold/notional sweeps, or core-overlap exclusions on the same frozen
sample. A valid next step needs closed forward paper replacement-value evidence
or an orthogonal risk discriminator that fixes the `late_strong` Sharpe/drawdown
tradeoff without reintroducing a rejected overlap or parameter sweep.

Production note: this remains replay-only/default-off. No live/default order
path changed. Any trade-enabled version requires a shared `run.py` /
`backtester.py` adapter, parity tests, and forward closed outcomes.

### 2026-05-09 mechanism update: State-surface sector complement

Experiment: `exp-20260509-013`

Decision: `rejected_full_stack_replacement`.

Finding: a sector-complement gate did not beat the full event-state plus
state-surface stack. The tested single variable was to keep the frozen
event-state add-on and frozen state-surface sleeve unchanged, but skip
state-surface candidates whose sector was already represented by an active core
A/B trade on the candidate entry date.

Against event-state-only, the gated stack was still positive: aggregate EV
improved from `7.6744` to `8.5325` (`+0.8581`, `+11.18%`) and aggregate PnL
improved by `$19,785.40` (`+9.70%`), with EV and PnL up in all three canonical
windows. That is not the correct marginal baseline, because the experiment was
trying to replace the stronger full stack from `exp-20260509-012`. Against the
full stack, aggregate EV regressed by `-0.4806` (`-5.33%`) and aggregate PnL by
`-$15,423.90` (`-6.45%`). The gate improved `late_strong` EV by `+0.0858` and
reduced late drawdown by `0.95 pp`, but it damaged `mid_weak` and `old_thin`,
especially by skipping old-window Technology continuation winners.

Mechanism insight: same-sector complementarity is directionally useful as a
late-risk explanation, but it is too blunt as an allocation rule. In older and
weaker windows, the state-surface sleeve's replacement value often comes from
same-sector continuation while the core is already carrying that sector. A
sector crowding gate therefore fixes the wrong part of the stack and gives up
too much north-star EV.

Do not repeat: state-surface same-sector active-core exclusion, sector-crowding
variants, or broader "make state-surface orthogonal to core sectors" gates on
the same frozen samples. A valid retry needs a more granular event/news or
trade-lifecycle discriminator that preserves old-window continuation winners
while addressing the late-window Sharpe/drawdown tradeoff.

### 2026-05-09 mechanism update: State-surface benchmark momentum gate

Experiment: `exp-20260509-014`

Decision: `promising_replay_only_benchmark_momentum_gate`.

Finding: a broad-market momentum participation gate is the strongest current
risk discriminator for the event-state plus state-surface stack, but it is
still replay-only. The tested single variable was to keep the frozen
event-state add-on and frozen state-surface sleeve unchanged, then allow
state-surface entries only after a 20-trading-day core warm-up when
`max(SPY_20d_return, QQQ_20d_return) > 0`.

Against event-state-only, the momentum-gated stack improved EV in all three
canonical windows: `late_strong +0.9826`, `mid_weak +0.6817`, and
`old_thin +0.3705`. Aggregate EV improved from `7.6744` to `9.7092`
(`+2.0348`, `+26.51%`) and aggregate PnL improved by `$39,729.22`
(`+19.47%`).

Against the ungated full stack from `exp-20260509-012`, aggregate EV improved
by `+0.6961` (`+7.72%`) and aggregate PnL by `$4,519.92` (`+1.89%`). The gate
fixes the original late-window risk: `late_strong` EV `+1.0105`, Sharpe
`+0.55`, and max drawdown `-0.80 pp` versus the full stack. It is not a clean
full-stack replacement because it gives back EV in `mid_weak` (`-0.1788`) and
`old_thin` (`-0.1356`) versus the ungated full stack.

Mechanism insight: the state-surface sleeve's late risk is better explained by
broad benchmark momentum / sleeve warm-up state than by sector complementarity
or ticker overlap. A zero-line SPY/QQQ momentum gate preserves the additive
stack in strong benchmark tape while cutting cold-start and negative-tape
state-surface exposure. The cost is missed early-window leaders, so promotion
requires forward evidence that the late-risk reduction is worth the mid/old
opportunity cost.

Do not repeat: broad surface subsets, balanced-surface pruning, sector
complement gates, top-N/hold/notional retunes, or benchmark-momentum threshold
sweeps on the same frozen samples. A valid next step is either forward paper
validation of this exact gate or implementation of the exact gate in a shared
default-off run/backtester adapter with parity tests and blocked-reason
attribution. Do not route live/default orders from this replay-only result.

### 2026-05-09 mechanism update: State-surface benchmark plus core momentum gate

Experiment: `exp-20260509-015`

Decision: `rejected`.

Finding: adding accepted-core 20-day equity momentum confirmation on top of the
benchmark-momentum participation gate did not improve the current best
state-surface stack. The tested single variable was to keep the frozen
event-state add-on, frozen state-surface sleeve, and exp-20260509-014 benchmark
zero-line gate unchanged, but additionally require
`core_trailing_return_20d > 0` before allowing state-surface entries.

Against event-state-only, the variant was still positive: aggregate EV improved
from `7.6744` to `9.6406` (`+1.9662`, `+25.62%`) and aggregate PnL improved by
`$32,434.84` (`+15.90%`), with EV up in all three windows. That is not the
correct marginal baseline. Against the ungated full stack from
`exp-20260509-012`, aggregate EV improved only `+0.6275` (`+6.96%`) while PnL
regressed by `-$2,774.46` (`-1.16%`). It improved `late_strong` and `mid_weak`,
but damaged `old_thin` heavily (`EV -0.4141`, PnL `-$13,543.98`).

Mechanism insight: accepted-core trailing equity momentum is too lagging as a
state-surface participation filter. It correctly preserves late-window risk
control, but it removes old-window recovery and continuation exposure that the
state-surface sleeve is supposed to find. The broader benchmark momentum gate
from `exp-20260509-014` remains the stronger participation discriminator.

Do not repeat: adding core-equity trailing-return sign gates to the
state-surface sleeve, nearby core-equity lookback variants, or "strategy health"
confirmation filters on the same frozen samples. A valid retry needs a more
forward-looking state/event/news discriminator, not another lagging internal
equity-curve gate.

### 2026-05-09 mechanism update: State-surface benchmark gate shared adapter

Experiment: `exp-20260509-016`

Decision: `accepted_production_alignment_default_off`.

Finding: the benchmark-momentum gate from `exp-20260509-014` is still the
strongest current state-surface participation lead, but it needed a shared
production-visible adapter before any further promotion could be trusted. This
run implemented the exact zero-line `max(SPY_20d_return, QQQ_20d_return) > 0`
gate in `state_surface_sleeve.py` for the default-off paper queue and exposed
allow/block reasons in the production snapshot. It did not change live orders,
core A/B signals, sizing, exits, or LLM/news replay.

Three canonical core backtests intentionally stayed unchanged because the
adapter is paper-only: `late_strong` EV `4.0674`, `mid_weak` EV `1.6195`, and
`old_thin` EV `0.3583`. Focused parity tests now cover both allowed and blocked
benchmark states and assert `alters_orders=false`.

Mechanism insight: the next state-surface work should treat the benchmark gate
as the current default participation hypothesis, not as another threshold to
sweep. The useful new data from here is forward replacement value under
allow/block attribution: whether blocked paper candidates would have hurt and
whether allowed paper candidates beat cash/core alternatives.

Do not repeat: benchmark threshold tuning, core-equity momentum confirmation,
or live-order promotion from replay-only evidence. A valid next step is forward
paper attribution on this exact shared gate, or a separate alpha source that
does not depend on the state-surface data bottleneck.

### 2026-05-10 mechanism update: TRIP sector taxonomy

Experiment: `exp-20260510-015`

Decision: `accepted_shared_policy_small`.

Finding: TRIP was falling through shared sector enrichment as `Unknown`. Mapping
it to Consumer Discretionary improved aggregate EV from `6.2711` to `6.2882`
(`+0.0171`, `+0.27%`) and aggregate PnL from `$184,040.96` to `$184,444.42`
(`+$403.46`, `+0.22%`) across the three canonical windows. Trade count,
signals generated, and signals survived were unchanged; max drawdown did not
worsen, and `old_thin` drawdown improved by `1.00 pp`.

History check: this deliberately revisits the rejected `exp-20260501-018`
TRIP mapping only because the rejection's retry condition is now satisfied.
That older stack showed no metric movement. The current accepted stack has
shared sector-dispersion enrichment / allocation behavior that consumes sector
metadata, and the new artifact records `12` changed existing trades.

Mechanism insight: real taxonomy gaps can leak alpha through shared
sector-aware allocation and sector-dispersion enrichment even when no new
threshold or ticker is added. The effect is small and valid only because the
classification is production-real and the policy is shared by production and
backtest paths.

Do not repeat: single-ticker sector-label mining, especially from losing trades,
on the same frozen samples. A valid taxonomy follow-up must start from a real
production universe classification gap and pass the same three-window
no-regression check. Any new sector-aware allocation rule remains a separate
single-variable alpha experiment.

### 2026-05-10 mechanism update: Effective slot accounting scout

Experiment: `exp-20260510-018`

Decision: `rejected`.

Finding: raw slot scarcity is a real execution bottleneck, but the historical
replacement-value evidence is not clean enough to justify changing core slot
accounting yet. The tested single variable was observed-only fixed-notional
20-trading-day replacement value for candidates that already survived the
current entry path but were blocked by `slot_sliced` or
`scarce_slot_breakout_deferred`. Global `MAX_POSITIONS`, heat, sizing, ranking,
signals, exits, LLM/news, add-ons, and production orders stayed unchanged.

All slot-missed rows: count `25`, PnL
`$8330.63`, win rate `0.4`, positive windows
`1`, single-ticker positive share
`0.4652`. First missed row per day:
count `16`, PnL `$6934.96`. Pure one-extra
slot rows (`slot_sliced` only): count `6`, PnL
`$2568.43`. Breakout rows that require effective slots above
the one-slot defer threshold: count `10`, PnL
`$4366.53`.

Mechanism insight: the user's 2026-05-08 MU case is structurally important
because heat allowed new risk while raw slot count blocked the core entry plan.
However, because `DEFER_BREAKOUT_WHEN_SLOTS_LTE=1` is active, a breakout does
not become executable merely by creating one nominal slot; the effective slot
accounting policy would need to release enough capacity for `available_slots >
1` or explicitly change scarce-slot breakout routing, which is a separate
causal variable.

Do not repeat: global `MAX_POSITIONS` sweeps, simple sixth-slot gates, or
nearby scarce-slot threshold retunes. A valid retry needs a shared effective
slot accounting design that is exposure/risk based, production-visible in
`run.py`, and evaluated by full portfolio replay with drawdown and tail-risk
impact.

### 2026-05-10 mechanism update: Dust slot pre-plan filter

Experiment: `exp-20260510-022`

Decision: `rejected`.

Finding: dust-sized whole-share signals were removed before scarce slot planning to test whether accepted risk haircuts should also imply lower slot priority. The best variant `drop_one_or_two_share_sized_signals` produced aggregate EV delta `-0.0510` and PnL delta `$-2,173.70` across the canonical windows. EV improved/regressed windows: `2` / `1`.

Mechanism insight: whole-share dust status alone is not enough to promote a new slot-routing rule unless it clears Gate 4. Do not retry nearby 1-3 share dust filters on this frozen sample without replacement-value evidence or a distinct execution-cost model.

### 2026-05-10 mechanism update: SEC T+1 event drift surface

Experiment: `exp-20260510-023`

Decision: `observed_only_paper_watch_candidate`.

Finding: the new non-OHLCV SEC backtest snapshots are complete enough to run a
three-window shadow event-surface audit, but the simple positive T+1
excess-drift label is not yet production alpha by itself. Aggregate shadow
candidates: `393`; valid 10d forward rows:
`363`; positive 10d-average windows:
`2/3`; aggregate 10d average return:
`0.012219` with win rate `0.5179`.

Mechanism insight: this is the right shape for the next event/oracle work:
start from public-PIT event availability, measure post-event continuation, and
only then decide whether an event candidate deserves forward paper routing.
Do not turn this into another PEAD threshold sweep; the current run changed no
reaction-magnitude threshold, volume rule, hold length, ranking rule, or live
adapter.

### 2026-05-10 mechanism update: SEC financial-report T+1 drift slice

Experiment: `exp-20260510-024`

Decision: `observed_only_forward_paper_queue_candidate`.

Finding: narrowing the broader SEC T+1 event-drift surface to financial-report
events (`earnings_8k` plus `periodic_report`) materially cleaned up stability:
`184` valid 10d rows, 10d average return
`0.022332`, 10d win rate
`0.538`, and positive
10d average return in `3/3` windows.

Mechanism insight: for the event/oracle stack, the next production-visible work
should be a default-off forward paper queue for this exact deterministic label.
Do not promote same-sample SEC event trades directly, and do not retry broad
PEAD reaction-magnitude, volume, or fixed-hold sweeps.

### 2026-05-10 mechanism update: SEC financial-report T+1 forward queue

Experiment: `exp-20260510-025`

Decision: `accepted_for_forward_observation`.

Finding: the strongest open SEC event/oracle lead from `exp-20260510-024` was
moved into a production-visible, default-off paper queue and sleeve:
`SEC_FINANCIAL_REPORT_T1_DRIFT_FORWARD_QUEUE` and
`SEC_FINANCIAL_REPORT_T1_DRIFT_EVENT_SLEEVE_PAPER`. The frozen qualification
rule is financial-report event family (`earnings_8k` or `periodic_report`) plus
positive ticker T+1 close-to-close return that also beats SPY on T+1. The queue
freezes next-session paper entries, tracks open/closed paper state, and reports
P&L attribution without emitting orders, changing core ranking, changing core
sizing, or consuming core slots.

Evidence: the focused queue/sleeve/report tests passed (`22 passed`). The
canonical three-window core backtests stayed unchanged versus the accepted
baseline: `late_strong` EV `4.2340`, `mid_weak` EV `1.6689`, and `old_thin` EV
`0.3853`; aggregate EV and PnL deltas were both `0`. Survival stayed
`80.39%`, `79.25%`, and `91.67%`.

Mechanism insight: this is the correct production-safe expression of the SEC
financial-report T+1 drift alpha for now: collect forward replacement-value
outcomes before any live/default trade adapter. It deliberately bypasses the
LLM soft-ranking bottleneck because the deterministic event/price-response
surface already has a cleaner same-sample lead.

Do not repeat: same-sample SEC financial-report T+1 threshold retunes,
event-family micro-slices, hold-day retunes, or live promotion from the frozen
historical sample. The next evidence must be closed forward paper outcomes:
direct P&L, cash-relative P&L, core replacement value, and same-theme
replacement value.

### 2026-05-10 mechanism update: SEC financial-report non-platform queue

Experiment: `exp-20260510-027`

Decision: `accepted_default_off_forward_queue_refinement`.

Finding: the accepted financial-report positive T+1 excess drift queue improves
when `platform_pool` is excluded: source 10d average return
`0.022332` across
`184` valid rows versus non-platform
10d average return `0.027636`
across `157` valid rows. The
excluded platform_pool slice averaged
`-0.008507` over 10d.

Mechanism insight: keep collecting this SEC queue as default-off paper, but
freeze the deterministic candidate pool to non-platform financial-report events
before spending forward observation budget on closed replacement value.

### 2026-05-11 mechanism update: Space catalyst static-pool replay

Experiment: `exp-20260511-002`

Decision: `rejected_static_pool_alpha`.

Finding: adding the `SPACE_CATALYST_SHADOW` operating equities (`RKLB`, `ASTS`,
`LUNR`, `PL`, `RDW`, `BKSY`, `IRDM`, `VSAT`, `GSAT`, `SATS`) to deterministic
snapshot copies was strongly positive in raw static replay but not acceptable as
production alpha. Aggregate EV improved `+2.3036` and aggregate PnL improved
`+$64,577.73`, with EV up in all three canonical windows. The added space
trades themselves contributed `25` trades, `+$79,995.67`, and `52%` win rate.

Rejection basis: the result is selected with 2026-05-10 knowledge, not
point-in-time trade permission, and it worsened old-window drawdown from
`8.15%` to `11.71%` (`+3.56 pp`). Late-window Sharpe also fell despite positive
PnL. This is too much tail-risk drift for direct core or live-pilot promotion.

Mechanism insight: the space catalyst pool is a real alpha lead, but it should
stay in observe-only / forward-shadow mode. The right next evidence is
event-dated replacement value under the existing zero-live-slot sleeve, not a
static core universe promotion, live slot enablement, nearby ticker mining, or
SpaceX/UAP headline-only trade rule.

### 2026-05-11 mechanism update: Space catalyst shadow surface

Experiment: `exp-20260511-003`

Decision: `accepted_default_off_forward_observation_surface`.

Finding: the rejected static-pool lead from `exp-20260511-002` is now expressed
as a shared, production-visible shadow surface instead of a trading rule. The
daily path exposes `SPACE_CATALYST_SHADOW` records, theme segments, LLM event
fields, stop rules, and promotion gates in universe/report outputs while
keeping live slots at `0`.

Evidence: focused tests passed (`17 passed`) and the canonical core metrics
stayed unchanged in all three windows: `late_strong EV 4.2340`, `mid_weak EV
1.6689`, and `old_thin EV 0.3853`. Orders, signal generation, ranking, sizing,
filters, exits, add-ons, and LLM hard-risk boundaries did not change.

Mechanism insight: this is the valid next form of space catalyst alpha
research: collect forward direct PnL, cash-relative PnL, core replacement
value, same-theme replacement value, and risk-adjusted replacement value before
any pilot/live promotion.

Do not repeat: static space catalyst pool promotion, adjacent space ticker
mining, or SpaceX/UAP headline-only entry rules on these frozen samples. A
trade-enabled retry requires closed forward evidence, explicit nonzero pilot
slots, shared run/backtest policy, and parity tests.

### 2026-05-11 mechanism update: All-signal 52-week proximity ranking

Experiment: `exp-20260511-004`

Decision: `rejected`.

Finding: extending the existing breakout-only `pct_from_52w_high` re-ranking
to all same-day entry candidates degraded the canonical three-window result.
Aggregate EV fell from `6.2882` to `5.5140` (`-0.7742`) and aggregate PnL fell
from `$184,444.42` to `$157,746.80` (`-$26,697.62`). No window improved EV.

Mechanism insight: 52-week-high proximity remains useful as a breakout
subsequence ordering feature, but it should not become a global scarce-slot
ranking key. The broader stack appears to need strategy-specific ordering
because all-signal proximity over-prioritizes near-high candidates that the
current filter/risk mix intentionally balances against other entry types.

Do not repeat: global all-signal 52-week proximity ordering or nearby global
near-high slot retunes. A valid retry needs a narrower event-conditioned or
replacement-value-backed ranking feature implemented in shared production and
backtest policy if positive.

### 2026-05-11 mechanism update: SEC financial-report core priority

Experiment: `exp-20260511-005`

Decision: `rejected`.

Finding: prioritizing already-survived core A/B candidates that carried the
frozen non-platform SEC financial-report positive T+1 excess-drift label did
not improve the canonical three-window stack. Aggregate EV delta was
`-0.1340` and aggregate PnL delta
was `$-7,773.91`.

Mechanism insight: the SEC financial-report T+1 surface remains a useful
default-off forward queue, but the current same-sample event tag is not enough
to override native core entry-planning order. Keep collecting closed forward
replacement value before promoting the tag into core ranking, sizing, or live
orders.

Do not repeat: SEC financial-report T+1 core-priority ranking, nearby active
hold-day priority variants, or promotion of the frozen SEC queue tag into core
slot ordering on these same windows without closed forward replacement-value
evidence or a genuinely new semantic event-quality field.

### 2026-05-11 mechanism update: same-day sector cluster risk

Experiment: `exp-20260511-006`

Decision: `rejected_replay_only`.

Finding: applying a 0.5x initial-risk follower haircut to the second and later
same-day, same-sector `risk_on` core entry did not clear the canonical
three-window gate. Aggregate EV delta was
`-0.0089` and aggregate PnL delta was
`$-817.86`.

Mechanism insight: same-day sector clustering is a real risk-allocation
surface, but this simple follower haircut is too blunt for the accepted stack.
Do not promote or repeat this exact 0.5x same-sector risk-on follower rule
without a new ex-ante quality discriminator that separates crowded winners
from crowded tail-loss clusters.

### 2026-05-10 mechanism update: SEC financial-report RS20 slice

Experiment: `exp-20260510-029`

Decision: `observed_only_stronger_oracle_feature_candidate`.

Finding: adding the already accepted RS20 leader state to the SEC
financial-report + positive T+1 excess-drift label lifted 10d average return
from `0.022332` to
`0.034878` with
`83` valid rows, win rate
`0.5904`, and positive
10d-average return in
`3/3`
windows. The diagnostic non-platform intersection was stronger at
`0.045087`, but it is a second
variable and needs its own pre-registered follow-up before becoming a rule.

Mechanism insight: the stronger event/oracle candidate is not platform-specific
and not a new RS20 sizing scalar; it is a public-PIT financial-report event
whose price already confirms RS20 leadership. The next production-visible step
should collect forward paper outcomes for this exact deterministic label.

### 2026-05-11 mechanism update: SEC non-platform RS20 slice

Experiment: `exp-20260511-007`

Decision: `observed_only_rejected_concentration`.

Finding: excluding `platform_pool` from the SEC financial-report T+1 drift plus
RS20 leader label lifted 10d average return from
`0.034878` to
`0.045087` with
`67` valid rows and win rate
`0.5821`. However the
slice failed the concentration guard: max single-ticker positive PnL share was
`0.375` versus the 0.35 cap.

Mechanism insight: the stronger-looking same-sample slice is not clean enough
to become a new rule. Keep RS20 as an attribution dimension on the default-off
SEC queue and wait for closed forward replacement value before any further
SEC cohort slicing.
