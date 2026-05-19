# exp-20260507-027 Core Platform Cap-Aware Risk Replay

Decision: `rejected`
Best variant: `core_platform_1_50x_cap_aware`

## Hypothesis

Core platform trades may not need special entries or exits, but may deserve more capital only when the existing position cap leaves headroom after the baseline system has already selected them.

## Baseline

| EV sum | PnL sum | Trades |
|---:|---:|---:|
| 5.6272 | 167347.95 | 62 |

## Aggregate Replay

| Variant | EV delta | PnL delta | Windows EV +/- | Touched | Changed | DD worsening | Single ticker share | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| core_platform_1_25x_cap_aware | 0.0748 | 2506.91 | 2/0 | 11 | 8 | 0.0112 | 0.9171 | FAIL |
| core_platform_1_50x_cap_aware | 0.1675 | 4830.37 | 2/0 | 11 | 9 | 0.0097 | 0.9605 | FAIL |

## Guardrails

- Replay only; no production path changed.
- Single causal variable: core platform risk multiplier.
- Position-cap headroom is enforced from proxy equity at entry.
- Entries, ranking, exits, add-ons, universe, LLM/news, and earnings are locked.
- This is not a consumer-platform universe promotion, entry timing retry, or runner-exit retry.

## Rejection Reason

Best variant `core_platform_1_50x_cap_aware` failed the pre-registered proxy gate: EV delta 0.1675 (0.020275), windows improved/regressed 2/0, changed trades 9 of 11 touched, max DD worsening 0.0097, single ticker positive share 0.9605.
