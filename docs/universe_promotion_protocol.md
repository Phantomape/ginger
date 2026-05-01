# Universe Promotion Protocol

This protocol separates ticker discovery from trading permission. The goal is
to let the system expand its opportunity set with real-money learning while
preserving point-in-time auditability and production/backtest parity.

## Core Principles

1. The current watchlist is not ground truth. It is one universe version.
2. New and old tickers use the same lifecycle, including demotion.
3. Static pool backtests can generate hypotheses, but cannot grant production
   status by themselves.
4. Every universe state change must be reconstructable from an append-only
   event ledger.
5. Pilot trades must freeze counterfactuals before entry, not after outcome.
6. Promotion is based on risk-adjusted replacement value, not raw PnL alone.

## States

| State | Meaning | Can trade? |
| --- | --- | --- |
| `research` | Observable candidate. Signals and shadow trades may be logged. | No |
| `pilot` | Real-money exploratory sleeve with strict risk limits. | Yes, limited |
| `limited_production` | Can compete with core names under tighter caps. | Yes, limited |
| `core` | Standard production universe member. | Yes |
| `specialist` | Requires a separate rule/risk profile, such as miners, IPOs, or short-history event names. | Only through specialist policy |
| `quarantine` | Frozen after a risk/event/failure trigger. | No new entries |
| `retired` | Removed from active consideration. | No |

`specialist` is not just a label. A specialist ticker must not be judged by the
same sample-count, volatility, event-risk, or promotion standards as a mature
core ticker.

## Point-In-Time Dates

Each registry record must distinguish:

| Field | Meaning |
| --- | --- |
| `discovered_as_of` | Date the ticker entered human/system awareness. |
| `eligible_as_of` | Date it became eligible for research signals. |
| `first_trade_allowed_as_of` | First date real or quasi-real capital may be used. |
| `status_effective_as_of` | Date the current status became effective. |
| `decision_as_of` | Date the decision was made with then-available information. |
| `data_available_as_of` | Date the input data supporting the decision was available. |

Backtests must never treat a ticker as eligible before the relevant as-of date.
The append-only event ledger is the source of truth for reconstructing the
universe on any historical day.

## Files

| File | Role |
| --- | --- |
| `data/universe_registry.json` | Current universe state snapshot. |
| `data/universe_events.jsonl` | Append-only universe event ledger. |
| `quant/universe_manager.py` | Point-in-time replay, validation, and hashing helpers. |
| `quant/candidate_competition_logger.py` | Pre-trade counterfactual snapshot, outcome logging, and replacement-value rollups. |
| `quant/pilot_sleeve.py` | Shared real-money pilot sleeve policy, risk scalar application, slot limits, and snapshot construction. |
| `quant/performance_engine.py` | Appends closed pilot outcomes when trade metadata carries the frozen decision id. |

The registry is convenient for current operations. The ledger is what prevents
future information leakage.

## Backtest Modes

| Mode | Valid Use |
| --- | --- |
| `static_pool_backtest` | Hypothesis generation only. Answers: "If this pool had existed, would the strategy have found anything?" |
| `walk_forward_universe_backtest` | Formal historical evidence. Replays discovery, eligibility, status changes, promotion, quarantine, and retirement using point-in-time data. |
| `live_pilot_attribution` | Forward evidence for short-history, new-theme, and event-sensitive names. |

Production promotion requires either walk-forward evidence or live pilot
evidence. Static pool results alone are not enough.

As of 2026-05-01, `INTC`, `LITE`, and `BE` are trade-enabled only through
`AI_INFRA_PILOT`. They are not core universe members and must not be evaluated
as if static-pool historical evidence alone promoted them.

## Pilot Risk Limits

Pilot size is governed by risk contribution first, capital second:

| Limit | Default Guardrail |
| --- | --- |
| Sleeve max capital | 10-15% of account capital |
| Sleeve max risk contribution | 5-8% of total portfolio risk |
| Single pilot ticker risk contribution | 2-3% |
| Event-sensitive ticker risk contribution | 1-2% |

Registry records therefore include both `max_capital_scalar` and
`max_risk_scalar`. High-beta or event-sensitive tickers may have modest capital
but must still have lower risk contribution.

## Counterfactual Snapshot

A pilot decision must freeze its counterfactual before entry:

```json
{
  "decision_id": "pilot-20260501-lite-001",
  "timestamp": "2026-05-01T09:25:00-07:00",
  "sleeve": "AI_INFRA_PILOT",
  "pilot_ticker": "LITE",
  "action": "BUY",
  "protocol_version": "universe_protocol_v1.0",
  "ranking_snapshot": [
    {"ticker": "LITE", "score": 0.76, "status": "pilot"},
    {"ticker": "AMD", "score": 0.71, "status": "core"}
  ],
  "counterfactuals": [
    {"type": "primary_displaced_candidate", "ticker": "AMD", "shadow_weight": 0.5},
    {"type": "cash_baseline", "ticker": "CASH", "shadow_weight": 0.5}
  ],
  "risk_snapshot": {
    "pilot_expected_vol": 0.034,
    "replacement_expected_vol": 0.028,
    "theme_exposure_before": 0.14,
    "theme_exposure_after": 0.18
  }
}
```

Outcomes are later appended against the same `decision_id`. The counterfactual
must not be edited after the result is known.

## Promotion Tests

`pilot -> limited_production` is only an initial live sanity check. It requires:

1. Direct pilot PnL > 0.
2. Replacement value > 0.
3. Risk-adjusted replacement value > 0.
4. Max drawdown inside sleeve limit.
5. No single trade explains more than 60-70% of total profit.
6. Theme beta does not explain most of the return.
7. No unresolved event-risk violation.
8. Live slippage inside expected range.

`limited_production -> core` requires broader evidence:

- At least 30 closed trades, or
- At least 60 active signal days, or
- At least 90 live observation days,
- plus exposure across at least two market regimes.

## Kill Switches

| Kill Switch | Action |
| --- | --- |
| Pilot sleeve drawdown > limit | Pause new pilot entries. |
| Three consecutive losing pilot trades with negative replacement value | Demote affected ticker to `research` or `quarantine`. |
| Theme-level replacement value negative for N trades | Freeze the theme pilot. |
| Correlation with core positions spikes above limit | Reduce pilot scalar or freeze theme. |
| Event calendar violation | Freeze ticker until reviewed. |

Manual overrides are allowed, but must be ledgered with `expires_at`. No
open-ended override should become a permanent hidden rule.
