# Research Queue Guardrails

Last updated: 2026-06-01.

This file turns the current Ginger research review into an operator-facing anti-repeat checklist. It does **not** change entries, exits, rankings, sizing, orders, LLM prompts, or live capital. It exists to keep new agents from spending another cycle on nearby variants that already failed on the current frozen evidence.

Use it with `docs/alpha-optimization-playbook.md`, `docs/current_state.md`, `docs/backtesting.md`, and `docs/experiment_log.jsonl` before reserving a new experiment ID.

## Three immediate queue changes

1. **Freeze nearby retries on the current frozen windows.** Do not run another threshold, top-N, scalar, lifecycle, or pattern-name variant when the prior evidence already says the family is frozen. A retry needs new PIT data, forward rows, exact replacement value, or a pre-registered richer field.
2. **Prioritize forward maturation.** The best current surfaces are default-off paper sleeves, not more historical retunes. The next useful work is closed forward outcomes, cash/core displacement replacement value, adjacent-rank comparison, concentration, kill-gates, and activation blockers.
3. **Require a new information source for new alpha.** A proposed alpha test should add a new production-visible PIT field, a stronger relation graph, or exact same-day displacement value. Renaming an OHLCV pattern, retuning a score weight, or adding a one-line scalar is not enough.

## Hard-freeze / guarded directions

| Direction | Current stance | Do not do next | Valid continuation |
|---|---|---|---|
| PEAD / expectation / pre-earnings | Frozen on current sample | 5d PEAD retries, imminent-earnings top-N/threshold/revision/hold/exit variants | Multi-season PIT estimate coverage, >=20 usable candidates per season, pre-registered 10d or richer expectation-quality fields |
| Full-universe `alpha_score` | Read-only triage, not routing | Raw top-1/top-N sleeve, component gates, score-weight tuning, filled-trade-only attribution | Same-day displacement replacement value, cost-adjusted rank deltas, new PIT non-OHLCV component |
| Kova / VCP / CANSLIM | Accepted VCP paper anchor, but live activation blocked | Pocket-pivot/base/MA/stop/pyramid/QQQ/top-N/rank-notional retunes on frozen VCP rows | Nonzero forward candidates, closed replacement value, candidate-feed readiness, PIT intraday/13F/CAN SLIM coverage |
| SEC event recurrence / simple catalyst cuts | Same-ticker recurrence and simple freshness/diversity are rejected | Same-family bursts, first/follow-on, cross-family transitions, simple catalyst freshness/source diversity | Characteristic-similarity peers, source overlap, theme propagation, SEC/news semantic direction with retrieval traces |
| State-surface scalar/profile tuning | Strict >10% aggregate EV gate | Same-family profile/notional/capital tweak with small paper-only improvement | >10% aggregate EV, or measurement repair, or activation/replacement-value evidence |
| Fundamental Growth RS / VBB / FINRA paper sleeves | Promising but default-off | Frozen-sample threshold/scalar/top-N/cooldown retunes | Forward rows, replacement value, concentration, activation blockers |

## Preferred next work

1. Roll up forward evidence for `FUNDAMENTAL_GROWTH_RS_PAPER`, `VOLUME_BREADTH_BREAKOUT_PAPER`, `FINRA_IWM_CONFIRMED_PAPER`, QQQ-confirmed VCP, and broad-market paper.
2. Add exact same-day displacement attribution before proposing any `alpha_score` top-N candidate pool.
3. Build stronger event relations: characteristic-similarity peer transfer, source overlap, theme propagation, or SEC/news semantic direction with audited retrieval traces.
4. Repair empty candidate feeds that block activation, especially VCP or SEC sleeves with `0` forward candidates.
5. Add friction-aware fields before allocation changes: cost/liquidity, borrow availability/utilization, fill delay, and exchange-specific execution semantics.

## OKX / crypto boundary

If Ginger adds an OKX or crypto route, treat it first as a measurement and execution-parity project, not as a direct alpha transplant. OKX v5 provides REST and WebSocket APIs; trading rate limits are shared across REST and WebSocket order-management channels, and place-order endpoints are rate-limited per User ID + instrument/instrument-family. Any OKX work must therefore start with replayable market-data snapshots, rate-limit throttling, request timeout handling, order-state reconciliation, and demo/paper parity before a trade-enabled sleeve.

## Required preflight command

Before reserving an experiment ID for a new alpha proposal, run or mentally apply:

```powershell
.\.venv\Scripts\python.exe -B scripts\research_preflight.py `
  --hypothesis "<one-sentence hypothesis>" `
  --mechanism-family "<trial family>" `
  --changed-variable "<single causal variable>"
```

If the script returns `blocked_nearby_repeat`, do not proceed unless the ticket explicitly names the new evidence that overrides the freeze.
