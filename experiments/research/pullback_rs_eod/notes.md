# pullback_rs_eod

## Hypothesis
Rank liquid US equities higher when 60-day cross-sectional momentum remains strong but the last 5 trading days have pulled back.

## Data Fields
- `Date`, `Close`, `Volume` from existing OHLCV snapshots
- Derived features: `ret_5d`, `ret_20d`, `ret_60d`, `adv20`, `vol20`
- Labels: forward close-to-close returns at 5/10/20/60 trading days

## Guardrails
- Point-in-time features use only data available through the signal date.
- Forward returns are labels only, never inputs.
- Current repo snapshots are current-universe biased; no promotion from this artifact alone.
- No production rules, thresholds, LLM prompts, or risk policy changed.

## Decision
`observed_promising_not_promoted` - Primary variant is directionally promising, but this is a standalone cross-sectional study with survivorship-biased current snapshots and no production slot-aware integration yet.

## Best 35 bps rows
| variant          |   horizon |   rank_ic_mean |   top_bottom_spread_mean |   top_bucket_return_mean |   turnover_mean |   top_bottom_hit_rate |
|:-----------------|----------:|---------------:|-------------------------:|-------------------------:|----------------:|----------------------:|
| momentum_60      |        60 |      0.145449  |               0.248109   |                0.261092  |        0.106379 |              0.759349 |
| pullback_rs_60_5 |        60 |      0.0437373 |               0.152012   |                0.202028  |        0.296171 |              0.698873 |
| momentum_60      |        20 |      0.0773947 |               0.0538123  |                0.0604773 |        0.119617 |              0.64988  |
| pullback_rs_60_5 |        20 |      0.0407377 |               0.048922   |                0.059488  |        0.300513 |              0.618561 |
| pullback_rs_60_5 |        10 |      0.0366563 |               0.0217913  |                0.0272267 |        0.293847 |              0.544357 |
| momentum_60      |        10 |      0.0549017 |               0.0176107  |                0.0253663 |        0.120224 |              0.559984 |
| momentum_60      |         5 |      0.038939  |               0.00841767 |                0.011192  |        0.120236 |              0.577635 |
| pullback_rs_60_5 |         5 |      0.0273383 |               0.00784033 |                0.0113597 |        0.296871 |              0.530326 |
