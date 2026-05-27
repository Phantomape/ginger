# exp-20260526-037 Kova Unavailable Feature Readiness Audit

## Decision

`observed_only_data_gap_kova_unavailable_features`. No strategy change, order change, rank change, sizing change, or exit change is allowed from this audit.

## Readiness Matrix

| Idea | Status | Why not tested as alpha now | Next unblocker |
|---|---|---|---|
| intraday_precision_entry_15m_60m | `blocked_no_pit_intraday_ohlcv` | The repository has daily OHLCV snapshots for the canonical windows, but no PIT 15m/60m bar archive was found. Daily bars cannot replay Kova's intraday precision entry without lookahead or invented fills. | Add PIT intraday OHLCV snapshots with vendor/as-of timestamps and a replay fill policy before testing intraday pivot timing. |
| canslim_fundamental_growth | `partial_non_ohlcv_not_canslim_complete` | Earnings snapshots and estimate-revision ledgers exist, but they are not a complete PIT CAN SLIM fundamental surface and should not be substituted for explicit growth fields. | Create a forward-audited fundamental-growth sidecar with same-as-of identity before using CAN SLIM-style filters or ranking. |
| rs_rating_or_leader_laggard | `proxy_only_no_ibd_rs_rating` | The codebase has relative-strength proxies, but no explicit PIT RS Rating. A proxy can be a separate hypothesis, not the same Kova field. | Define a Ginger-native relative-strength proxy with its own frozen baseline, or ingest an audited RS Rating source if available. |
| institutional_ownership_13f_accumulation | `blocked_no_pit_13f_ownership_surface` | No usable PIT 13F/institutional ownership surface was found. Using today's ownership data for historical signals would be lookahead. | Build a vendor/as-of 13F ownership sidecar and only then test institutional sponsorship as metadata or ranking. |
| pyramid_addon_sequence | `requires_separate_lifecycle_replay` | Pyramiding is a capital-allocation/lifecycle policy, not a candidate metadata bucket. It would change sizing, heat, and fill path and must be tested as one causal add-on policy against the accepted core stack. | Only revisit with a new ex-ante add-on quality discriminator and a full real replay; do not mine frozen VCP winners for a pyramid rule. |
| stop_under_higher_low_r_multiple | `partial_requires_exit_and_risk_policy_replay` | Daily OHLCV can approximate a prior higher low, and R diagnostics exist, but using that level as a stop or sizing denominator changes exits and risk allocation. That is outside the accepted VCP paper metadata sleeve. | Define a single VCP-specific exit/risk replay with explicit stop timing, gap handling, and R denominator before testing this as alpha. |

## Gate Notes

- Gate 1: reused the accepted VCP rank-notional source only as context.
- Gate 2: daily OHLCV is present; missing or incomplete non-daily surfaces are the result.
- Gate 3: no survival impact because no filter is added.
- Gate 4: promotion is disallowed; this is a readiness/data-gap artifact.

## Reproduction

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260526_037_kova_unavailable_feature_readiness_audit.py
```
