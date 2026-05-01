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

The first rollout does not:

- promote AI infrastructure names into `filter.WATCHLIST`;
- change `quant/run.py` trade recommendations;
- change position sizing, exits, add-ons, or ranking;
- make `INTC`, `LITE`, or `BE` eligible for live orders by itself;
- use static pool backtests as production evidence.

Any later change that lets pilot names place real trades must be explicit and
must include production/backtest parity checks.

## Current Foundation

Already added:

| File | Role |
| --- | --- |
| `docs/universe_promotion_protocol.md` | Lifecycle, PIT, promotion, kill-switch rules. |
| `data/universe_registry.json` | Current registry snapshot. |
| `data/universe_events.jsonl` | Append-only universe event ledger. |
| `quant/universe_manager.py` | Replay, validation, and hashing helpers. |
| `quant/candidate_competition_logger.py` | Pre-trade counterfactual and outcome logger. |
| `quant/test_universe_manager.py` | Tests for PIT replay, eligibility gates, and counterfactual logging. |

Current AI infrastructure metadata:

| Bucket | Tickers | Current Meaning |
| --- | --- | --- |
| Pilot metadata | `INTC`, `LITE`, `BE` | Not production-wired; eligible by ledger only from `2026-05-06` if future adapters consume it. |
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

Status: initial adapter implemented.

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

- Daily run can print or save universe state. Pending production report wiring.
- Backtester can disclose universe governance state. Pending read-only metadata wiring.
- Existing canonical backtest metrics remain unchanged because adapter is not
  consumed by signal generation.
- Unit tests prove read-only adapter does not include pilot names in core
  trading lists. Completed.

### Phase 2: Shadow Signal Attribution

Purpose: generate and record signals for non-core names without letting them
compete for production slots.

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
- If event/calendar/risk data is missing, pilot entry is blocked.
- Backtest and production share the same pilot sleeve policy before activation.

### Phase 5: Limited Live Pilot

Purpose: buy real evidence without allowing a new theme to take over the core
strategy.

Activation requirements:

- Phase 1-4 tests pass.
- Counterfactual snapshot is active.
- Event guard is active.
- Daily report includes pilot PnL and replacement value fields.
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

## First Implementation Slice

The next code step should be Phase 1 only:

1. Add `quant/universe_adapter.py`.
2. Read `universe_manager.records_as_of`.
3. Return segmented universe state.
4. Add tests proving `pilot` names are visible but not in the core trade list.
5. Optionally add a read-only CLI/report field.

Stop before Phase 2 unless Phase 1 verifies that canonical trading behavior is
unchanged.

## Gate Before Real Pilot Trading

No real pilot trade should be enabled until all are true:

- point-in-time adapter is used by production and backtest;
- shadow reports are being generated;
- counterfactual snapshots are written before entry;
- pilot sleeve risk limits are active;
- event guard blocks missing event data;
- daily report shows direct PnL, replacement PnL, and risk-adjusted replacement value;
- user explicitly approves enabling the pilot sleeve.

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

Proceed with Phase 1: read-only universe adapter. Do not yet modify the daily
trading universe, watchlist, or order recommendation path.
