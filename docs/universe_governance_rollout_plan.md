# Universe Governance Rollout Plan

This document turns the universe promotion protocol into an implementation
sequence. It is deliberately separate from `universe_promotion_protocol.md`:
the protocol defines the rules; this plan defines how to wire those rules into
the trading system without accidentally changing live behavior too early.

## Objective

Build a system that can expand the ticker universe, trade new opportunities
with bounded real risk, and produce point-in-time attribution showing whether a
new ticker was worth the slot it consumed.

The end goal is profit, not endless observation. The control principle is:

```text
new ticker risk can go live only after the system can say:
  when the ticker became eligible,
  why it became eligible,
  what it would replace,
  what risk budget it consumes,
  and how its realized outcome compares with that frozen counterfactual.
```

## Design Thesis

The current watchlist is not a permanent truth source. It is only the current
version of the opportunity set. New and old tickers should therefore be managed
by the same lifecycle:

```text
research -> pilot -> limited_production -> core
                  -> quarantine -> retired
specialist is a parallel state for names that need separate rules.
```

Ticker selection becomes a governed alpha surface, not a manually edited list.

## Non-Goals

The first rollout still does not:

- promote AI infrastructure names into `filter.WATCHLIST`;
- make `INTC`, `LITE`, or `BE` core candidates;
- change core position sizing, exits, add-ons, or ranking;
- use static pool backtests as production evidence.

`INTC`, `LITE`, and `BE` are now eligible only through the bounded
`AI_INFRA_PILOT` sleeve. This is a real-money pilot path, not a core universe
promotion.

## Current Foundation

Already added:

| File | Role |
| --- | --- |
| `docs/universe_promotion_protocol.md` | Lifecycle, PIT, promotion, kill-switch rules. |
| `data/universe_registry.json` | Current registry snapshot. |
| `data/universe_events.jsonl` | Append-only universe event ledger. |
| `quant/universe_manager.py` | Replay, validation, and hashing helpers. |
| `quant/candidate_competition_logger.py` | Pre-trade counterfactual, outcome logger, and replacement-value rollup. |
| `quant/test_universe_manager.py` | Tests for PIT replay, eligibility gates, and counterfactual logging. |
| `quant/pilot_sleeve.py` | Shared real-money pilot sleeve policy and pre-trade snapshot builder. |
| `quant/test_pilot_sleeve.py` | Tests for trade-date gating, pilot scalars, slot limits, and snapshots. |

Current AI infrastructure metadata:

| Bucket | Tickers | Current Meaning |
| --- | --- | --- |
| Trade-enabled pilot | `INTC`, `LITE`, `BE` | Daily run can generate separate `AI_INFRA_PILOT` signals from `2026-05-01`; not core. |
| Research | `COHR`, `APLD` | Signal/shadow candidates only. |
| Specialist | `SNDK`, `CRWV`, `CORZ`, `IREN`, `CIFR`, `WULF`, `RIOT`, `MARA` | Need short-history or BTC/HPC specialist handling. |
| Quarantine | `DBRG`, `TLN`, `VST` | Do not trade until a distinct rule explains the prior failure mode. |

## Rollout Phases

### Phase 0: Governance Foundation

Status: completed.

Acceptance:

- Registry validates with zero issues.
- Ledger can replay point-in-time ticker eligibility.
- `first_trade_allowed_as_of` blocks pilot names before their allowed date.
- Counterfactual logger refuses missing counterfactuals.
- No production path consumes the registry yet.

Verification:

```powershell
.\.venv\Scripts\python.exe -m pytest quant\test_universe_manager.py -q
```

### Phase 1: Read-Only Universe Adapter

Purpose: let production and backtest code inspect the same point-in-time
universe state without using it to place trades.

Status: completed and consumed by daily run governance output.

Implement:

- `quant/universe_adapter.py` (added)
- A function returning segmented universes:
  - `core`
  - `pilot`
  - `limited_production`
  - `research`
  - `specialist`
  - `quarantine`
  - `retired`
- Metadata:
  - `registry_hash`
  - `event_ledger_hash`
  - `protocol_version`
  - `as_of`
- Read-only report field in daily output/backtest known-bias metadata.

Strict non-impact rule:

```text
Phase 1 must not alter the universe passed into signal generation,
candidate ranking, sizing, or order advice.
```

Acceptance:

- Daily run can print or save universe state. Completed via
  `data/universe_state_YYYYMMDD.json` and `quant_signals_YYYYMMDD.json`
  `universe_governance`.
- Backtester can disclose universe governance state. Pending read-only metadata wiring.
- Existing canonical backtest metrics remain unchanged because adapter is not
  consumed by signal generation.
- Unit tests prove read-only adapter does not include pilot names in core
  trading lists. Completed.

### Phase 2: Shadow Signal Attribution

Purpose: generate and record signals for non-core names without letting them
compete for production slots.

Status: partially superseded for `INTC`/`LITE`/`BE` by the pilot sleeve. Still
needed for `research` and `specialist` names.

Implement:

- A shadow signal path for `pilot/research/specialist` tickers.
- `blocked_reason` for every non-core signal:
  - `research_only`
  - `pilot_not_enabled`
  - `specialist_policy_missing`
  - `quarantine`
  - `first_trade_date_not_reached`
- Shadow forward-return tracking for 5/10/20 trading days.

Outputs:

- `data/daily_universe_shadow_YYYYMMDD.json`
- Per-ticker signal counts, rank snapshots, and blocked reasons.

Acceptance:

- Production recommendations remain unchanged.
- Shadow report shows whether each non-core ticker had a signal.
- Each shadow signal has a status and a point-in-time registry hash.

### Phase 3: Competition Attribution Snapshot

Purpose: before any pilot trade is allowed, freeze what it would replace.

Status: initial implementation completed through `quant/pilot_sleeve.py` and
`quant/candidate_competition_logger.py`.

Implement:

- Ranking snapshot across core + pilot candidates.
- Counterfactual selection policy:
  - primary displaced candidate;
  - cash baseline;
  - optional same-theme alternative;
  - optional top-3 displaced basket.
- Write to append-only decision log before entry.

Hard gate:

```text
No pilot order can be considered valid unless the pre-trade
counterfactual snapshot has already been written successfully.
```

Acceptance:

- `decision_id` is stable and unique.
- Snapshot includes `registry_hash`, `strategy_version`, and `risk_model_version`.
- Snapshot cannot be reconstructed after the trade; it must exist before entry.

### Phase 4: Pilot Sleeve Sizer

Purpose: allow small real-money pilot trades with risk contribution limits.

Status: initial implementation completed for daily production output.

Implement:

- `AI_INFRA_PILOT` sleeve configuration.
- Max sleeve capital and risk contribution.
- Per-ticker `max_capital_scalar` and `max_risk_scalar`.
- Event-sensitive haircut.
- Theme exposure cap.
- Correlation shock guard.
- Kill switches from protocol.

Initial policy:

| Name | Default |
| --- | --- |
| Pilot sleeve max capital | 10-15% |
| Pilot sleeve max risk contribution | 5-8% |
| Single pilot ticker max risk contribution | 2-3% |
| Event-sensitive ticker max risk contribution | 1-2% |
| Max concurrent AI infra pilot positions | 1 |

Acceptance:

- Pilot sizing is computed separately from core sizing.
- Pilot recommendation includes sleeve and risk contribution fields.
- If event/calendar/risk data blocks the underlying signal, pilot entry is not
  generated.
- Production calls the shared pilot sleeve policy before activation.
- Canonical historical backtests remain core-only under point-in-time rules
  because the pilot trade date is `2026-05-01`; static pilot-pool experiments
  remain hypothesis evidence, not promotion proof.

### Phase 5: Limited Live Pilot

Purpose: buy real evidence without allowing a new theme to take over the core
strategy.

Status: activated for a bounded first sleeve after explicit user approval on
2026-05-01.

Activation requirements:

- Phase 1-4 tests pass.
- Counterfactual snapshot is active.
- Event guard is active.
- Daily report includes pilot PnL and replacement value fields. Completed.
- User explicitly approves enabling pilot trading.

Initial eligible names:

- `INTC`
- `LITE`
- `BE` with specialist-like risk scalar and stronger event guard

These names are not special truths. They are simply the first candidates with
enough evidence to justify bounded forward exploration.

### Phase 6: Promotion Engine

Purpose: automate weekly status review while preserving manual override audit.

Metrics:

- direct pilot PnL;
- replacement value;
- risk-adjusted replacement value;
- drawdown contribution;
- slippage vs expected;
- single-trade profit concentration;
- theme beta attribution;
- active signal days;
- closed trade count;
- regime coverage.

Promotion:

```text
pilot -> limited_production:
  passed initial live sanity check

limited_production -> core:
  enough sample, regime coverage, and replacement value stability
```

Demotion:

```text
negative replacement value + drawdown breach -> quarantine
theme-level failure -> freeze theme
manual override without expires_at -> invalid
```

## Backtesting Upgrade Path

The system should support three evidence tiers:

| Mode | Purpose | Production Eligibility |
| --- | --- | --- |
| Static pool | Hypothesis generator | No |
| Point-in-time replay | Formal historical evidence | Possible |
| Live pilot attribution | Forward evidence | Possible |

For dynamic universe experiments, the accepted backtest must replay:

- ticker discovery;
- eligibility;
- status changes;
- first trade allowed date;
- quarantine/retirement;
- promotion rules;
- counterfactual selection policy.

The system must not backfill a ticker into the past just because it is known
today.

## Production/Backtest Parity Rules

Any logic affecting these must be shared or explicitly disclosed:

- universe membership;
- pilot eligibility;
- counterfactual selection;
- sleeve sizing;
- event guard;
- theme exposure cap;
- kill switch;
- promotion/demotion.

Backtester-only pilot logic is not acceptable production evidence unless it is
documented as replay-only measurement.

## Implemented Slice

Completed:

1. Added `quant/universe_adapter.py`.
2. Added `quant/pilot_sleeve.py`.
3. Wired `quant/run.py` to download pilot OHLCV, compute pilot features, run
   the standard signal chain, apply pilot risk scalars, and emit
   `pilot_signals`.
4. Added pre-trade counterfactual snapshots before executable pilot entries.
5. Kept pilot signals out of core `signals` so core watchlist behavior remains
   separated.
6. Added closed-outcome attribution and daily replacement-value rollups through
   `candidate_competition_logger`, `performance_engine`, `run.py`, and
   `report_generator`.

Next implementation slice should add Phase 6 weekly promotion review output once
forward pilot decisions exist. Until then, the system should accumulate
decision snapshots, closed outcomes, and replacement-value coverage.

## Gate Before Real Pilot Trading

Real pilot trading is enabled only for `INTC`, `LITE`, and `BE` while the
following remain true:

- point-in-time adapter is used by production;
- counterfactual snapshots are written before entry;
- pilot sleeve risk limits are active;
- pilot recommendations remain separate from core recommendations;
- outcome attribution is active before any promotion to `limited_production`;
- user approval is required for any wider pilot list.

## Key Risks

| Risk | Control |
| --- | --- |
| Future information leakage | Append-only ledger + point-in-time replay. |
| New ticker overfitting | Static backtest cannot promote by itself. |
| Hidden manual bias | Overrides require `expires_at` and ledger entries. |
| False diversification | Theme/correlation exposure reporting. |
| Raw PnL illusion | Replacement value and risk-adjusted replacement value. |
| Over-governance | Phase gates; no production change without explicit adapter tests. |

## Current Recommendation

Run the daily pipeline normally. If `INTC`, `LITE`, or `BE` produces a valid
signal, it appears under `pilot_signals` with `AI_INFRA_PILOT` metadata and a
pre-trade decision hash. Do not move any pilot name into `core` until live
replacement-value attribution supports promotion. Closed pilot outcomes now roll
up into `pilot_attribution` in `quant_signals_YYYYMMDD.json` and the daily
report.
