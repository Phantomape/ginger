# exp-20260531-017 full_universe_alpha_score_component_forward_return

- timestamp: 2026-05-31T16:17:15Z
- decision: `observed_only_component_edge_without_clean_ladder`
- strategy impact: none; read-only attribution only
- baseline: accepted core aggregate EV `7.8941`, PnL `$234,850.99`
- windows: `late_strong`, `mid_weak`, `old_thin` from `docs/backtesting.md`

## Component Readout

| Component | Status | 5d Q5-Q1 | Monotonic | Positive windows | Min bucket obs | Unique scores |
|---|---|---:|---:|---:|---:|---:|
| trend | no_component_edge | 0.0002 | False | 1/3 | 710 | 10 |
| relative_strength | top_bottom_edge_without_clean_ladder | 0.0081 | False | 2/3 | 710 | 2460 |
| expectation_revision | insufficient_component_bucket_coverage | -0.0065 | False | 1/3 | 710 | 1 |
| post_earnings_drift | insufficient_component_bucket_coverage | -0.0065 | False | 1/3 | 710 | 1 |
| theme_participation | inverted_component_ladder | -0.0053 | False | 1/3 | 710 | 8 |
| breadth_alignment | top_bottom_edge_without_clean_ladder | 0.0090 | False | 3/3 | 710 | 69 |

## Interpretation

This experiment decomposes an existing ranking surface. It does not add a new information source and does not justify any production ranking, sizing, entry, exit, LLM prompt, paper sleeve, or order change by itself.
