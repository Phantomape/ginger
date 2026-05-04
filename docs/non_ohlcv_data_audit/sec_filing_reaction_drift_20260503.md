# SEC Filing Reaction Drift Shadow Replay

- experiment_id: `exp-20260503-051`
- generated_at: `2026-05-03`
- lane: `alpha_search`
- production_impact: `shadow_only_no_strategy_logic_changed`

## Hypothesis

PIT-safe SEC filing event-days with a first EOD excess reaction of at least
`+2%` versus SPY may identify post-reaction drift that can later confirm or
rank existing A/B candidates.

## Test Design

- Event unit: `ticker + usable_trade_date`, grouping same-day SEC filings.
- Reaction day: first trading day on or after `usable_trade_date`.
- Entry timing: next trading-day open after reaction close.
- Horizons: `5d`, `10d`, `20d`.
- Canonical windows:
  - `late_strong`: `2025-10-23 -> 2026-04-21`
  - `mid_weak`: `2025-04-23 -> 2025-10-22`
  - `old_thin`: `2024-10-02 -> 2025-04-22`

## Coverage

- SEC event groups: `1,090`
- Evaluated window event groups: `1,083`
- Price-covered groups: `739`
- Price coverage: `68.24%`
- Positive reaction groups: `150`
- Positive reaction valid `10d` groups: `138`

## Result

The fixed positive-reaction cohort failed the aggregate alpha test:

- `10d` excess return count: `138`
- `10d` average excess return: `-0.81%`
- `10d` median excess return: `-0.48%`
- `10d` excess win rate: `46.38%`

Window detail for positive reactions:

| Window | Count | 10d Avg Excess | 10d Win Rate |
|---|---:|---:|---:|
| `late_strong` | 50 | `-3.18%` | `30.00%` |
| `mid_weak` | 47 | `+0.24%` | `59.57%` |
| `old_thin` | 41 | `+0.88%` | `51.22%` |

Same-day core replacement proxy was also negative:

- valid replacement proxy count: `122`
- average replacement value: `-4.24%`
- median replacement value: `-3.60%`
- positive replacement rate: `33.61%`

## Decision

Rejected. This was not blocked by sample size: the positive-reaction cohort had
enough valid `10d` observations. The simple `+2%` SEC filing reaction
discriminator did not produce stable multi-window drift and was materially
negative versus same-day core alternatives.

## Do Not Repeat

Do not retry nearby raw SEC reaction thresholds without richer filing semantics
such as 8-K item text, XBRL surprise fields, or forward production SEC archives.
If this branch returns, it should be scoped to a shared production/backtest
event feature before affecting candidate ranking.
