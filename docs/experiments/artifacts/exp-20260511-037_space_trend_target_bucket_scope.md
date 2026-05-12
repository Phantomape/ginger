# exp-20260511-037 Space trend target bucket scope

Decision: `rejected_space_trend_target_scope`.

Hypothesis: the accepted 5 ATR Space trend target might belong only to the
higher-convexity official-catalyst buckets, while PL/BKSY data-vendor trend
signals might be better left on the shared regime target.

Result versus the accepted `exp-20260511-032` Space stack:

| Variant | Aggregate EV delta | Aggregate PnL delta | Windows improved | Gate |
| --- | ---: | ---: | ---: | --- |
| `exclude_data_vendor_trend` | -0.0270 | -$1,098.59 | 0/3 | fail |
| `launch_connectivity_only` | -0.0775 | -$3,164.86 | 0/3 | fail |
| `launch_connectivity_plus_rdw` | -0.0270 | -$1,098.59 | 0/3 | fail |

Mechanism insight: the accepted Space 5 ATR trend target should remain broad
across official-catalyst trend signals. Simple bucket narrowing to remove
data-vendor or RDW trend exposure does not add alpha on the frozen three-window
sample.

Anti-repeat: do not retry nearby Space trend-target bucket-scope narrowing on
the same frozen snapshots. The next valid Space exit refinement needs closed
forward replacement-value evidence by catalyst bucket or a genuinely new
ex-ante catalyst-quality field.

Artifact: `data/experiments/exp-20260511-037/space_trend_target_bucket_scope.json`.
