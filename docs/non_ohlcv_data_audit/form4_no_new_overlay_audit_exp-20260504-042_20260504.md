# Form 4 No-New-Evidence Overlay Audit

- experiment_id: `exp-20260504-042`
- timestamp: `2026-05-04T17:23:36+00:00`
- decision: `shadow_only_no_new_evidence`
- production_impact: `observed_only_no_production_change`

## Hypothesis

Meaningful open-market insider buying may confirm or supplement existing A/B opportunities, but this run only checks whether fresh PIT-safe Form 4 evidence exists beyond the frozen queue.

## Historical Check

- Prior Form 4 audits/replays already exist: `exp-20260503-017`, `exp-20260503-052`, `exp-20260503-053`, `exp-20260504-001`, `exp-20260504-006`, and `exp-20260504-034`.
- Playbook guardrail: do not repeat threshold sweeps, owner-role filters, overlay promotion, or live-order promotion on the same frozen sample.
- This run is not a replay or promotion; it records that no new local Form 4 evidence is available today.

## Data Availability

- transaction rows: `27879`
- filings seen: `6558`
- PIT-safe rows: `27879`
- open-market purchase rows: `131`
- max filing date in local file: `2026-05-01`
- max usable trade date in local file: `2026-05-04`
- usable 2026-05-04 open-market purchase rows: `0`
- forward queue candidates as of 2026-05-04: `0`
- paper state pending/open/closed: `0` / `0` / `0`

## Baseline Metrics

| Window | EV | Return | Sharpe daily | Max DD | Win rate | Trades | Generated | Survived | Survival | vs SPY | vs QQQ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 0.786 | 4.35 | 0.0541 | 0.7895 | 19 | 51 | 41 | 0.8039 | 0.7319 | 0.728 |
| mid_weak | 1.4415 | 0.5502 | 2.62 | 0.0879 | 0.5238 | 21 | 53 | 42 | 0.7925 | 0.2958 | 0.2151 |
| old_thin | 0.3179 | 0.2464 | 1.29 | 0.0805 | 0.4091 | 22 | 60 | 55 | 0.9167 | 0.3137 | 0.3213 |

## Shadow Metrics

Frozen `meaningful_purchase_v1 >= $500k` events, using existing Form 4 transaction rows and OHLCV snapshots. 90d counts are lower because later events lack a full 90-trading-day lookahead.

| Horizon | Count | Avg return | Median return | Win rate | Avg excess vs SPY | Excess win rate |
|---|---:|---:|---:|---:|---:|---:|
| 10d | 13 | 6.100954% | 5.5287% | 0.846154 | 4.759438% | 0.846154 |
| 20d | 13 | 6.577192% | 3.5561% | 0.692308 | 5.017823% | 0.692308 |
| 60d | 12 | 14.512325% | 10.7083% | 0.666667 | 10.791208% | 0.583333 |
| 90d | 11 | 18.923209% | 14.417% | 0.636364 | 10.865118% | 0.545455 |

## Slot Value

- historical queue candidates: `17`
- priced candidates: `13`
- same-day accepted conflicts: `2`
- replacement vs accepted avg SPY excess: `-2.194575` pp
- interpretation: slot replacement evidence remains too thin; satellite overlay was positive but below materiality.

## Decision

`shadow_only_no_new_evidence`. Continue default-off observation; do not promote to production, do not sweep thresholds, and do not retest owner-role filters on the frozen sample.
