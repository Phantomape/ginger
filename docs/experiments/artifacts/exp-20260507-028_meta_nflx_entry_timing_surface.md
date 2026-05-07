# exp-20260507-028 META/NFLX Entry Timing Surface

Decision: `observed_only`
Surface status: `promising_surface_not_promoted`

## Hypothesis

META/NFLX entry quality may depend on ex-ante platform lifecycle states such as orderly pullback, breakout, post-earnings drift, relative strength, and trend structure. The goal is to discover which states deserve a later candidate-level replay, not to change production entries now.

## Scope

- Seeds: META, NFLX
- Peers: GOOG, AMZN, SPOT, DIS, APP
- Decision price: current close; hypothetical entry: next open.
- This is observed-only and uses overlapping daily rows.

## Best Seed Timing Tags

| Tag | Count | Score | 20d ret | 40d ret | 20d excess SPY | 40d excess SPY | Windows + |
|---|---:|---:|---:|---:|---:|---:|---:|
| pre_earnings_0_7 | 86 | 0.078445 | 0.030116 | 0.062916 | 0.014345 | 0.05302 | 2/3 |
| pre_earnings_46_plus | 87 | 0.059693 | 0.02252 | 0.030761 | 0.024879 | 0.043845 | 2/3 |
| gap_up_3pct | 16 | 0.058125 | 0.028819 | 0.050608 | 0.02221 | 0.032217 | 2/3 |
| pre_earnings_runup_0_14 | 67 | 0.035749 | 0.028546 | 0.033079 | 0.012703 | 0.025955 | 1/3 |
| sma20_reclaim | 41 | 0.034147 | 0.016783 | 0.044379 | 0.008457 | 0.031896 | 1/3 |

## META And NFLX Reads

### META

| Tag | Count | Score | 20d ret | 40d ret | 20d excess SPY | Windows + |
|---|---:|---:|---:|---:|---:|---:|
| pre_earnings_8_21 | 91 | 0.084351 | 0.064681 | 0.025514 | 0.050086 | 3/3 |
| sma20_reclaim | 23 | 0.067548 | 0.021962 | 0.059422 | 0.010087 | 2/3 |
| below_sma50 | 153 | 0.05755 | 0.004843 | 0.075315 | 0.004077 | 3/3 |
| pre_earnings_22_45 | 138 | 0.025926 | -0.020951 | 0.08478 | -0.025325 | 1/3 |
| orderly_pullback_3_8_above_sma50 | 78 | 0.0243 | 0.032314 | 0.027146 | 0.01367 | 2/3 |

### NFLX

| Tag | Count | Score | 20d ret | 40d ret | 20d excess SPY | Windows + |
|---|---:|---:|---:|---:|---:|---:|
| post_earnings_drift_1_10 | 19 | 0.340961 | 0.129302 | 0.187256 | 0.084351 | 2/2 |
| pre_earnings_0_7 | 47 | 0.161848 | 0.044635 | 0.106509 | 0.025205 | 1/3 |
| rs60_leader | 226 | 0.094205 | 0.03962 | 0.063316 | 0.031697 | 2/3 |
| near_252d_high | 118 | 0.090767 | 0.037631 | 0.067859 | 0.024478 | 1/2 |
| post_earnings_1_5 | 20 | 0.08553 | 0.059741 | 0.05745 | 0.042333 | 2/3 |

## Decision Read

At least one seed-level tag beat all-days on 20d return and showed positive excess in at least two windows.

Next action: `pre_register_candidate_level_entry_timing_replay`

## Guardrails

- No production path changed.
- No ticker-specific privilege is promoted from this audit.
- No LLM, news, exit, sizing, ranking, or universe logic changed.
- Any next strategy replay must be candidate-level and pre-registered.
