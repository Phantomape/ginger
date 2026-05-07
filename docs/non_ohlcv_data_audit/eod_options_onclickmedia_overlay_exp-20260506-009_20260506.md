# exp-20260506-009 EOD Options Overlay

Decision: `rejected_for_promotion`

## Hypothesis

EOD options structure may add overlay information to existing Ginger candidate
days. The tested idea was deliberately non-standalone: call OI structure might
identify better continuation candidates, while put-skew or put/call structure
might identify weaker candidates.

## Why This Was Eligible

This did not repeat the earlier no-data options audits. `exp-20260506-003`
created a local OnClickMedia adapter and real option-chain rows, so this run
could join option structure to the three canonical backtest candidate days.

This was also not an LLM soft-ranking retry, not a universe expansion, and not a
core threshold change.

## Three-Window Core Baseline

The overlay was shadow-only. Core production-equivalent metrics stayed at the
accepted baseline:

| Window | EV | SharpeD | PnL | Max DD | Win rate | Trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | 3.4191 | 4.35 | 78600.33 | 5.41% | 78.95% | 19 |
| `mid_weak` | 1.4415 | 2.62 | 55015.08 | 8.79% | 52.38% | 21 |
| `old_thin` | 0.3179 | 1.29 | 24642.07 | 8.05% | 40.91% | 22 |

## Shadow Result

Candidate coverage was high: `135 / 138` candidate rows had options coverage
(`97.83%`), with `13,484` normalized option rows.

| Metric | Aggregate | late_strong | mid_weak | old_thin |
| --- | ---: | ---: | ---: | ---: |
| call support minus no-call 20d return | -0.0082 | -0.0213 | +0.0769 | -0.0577 |
| downside risk minus no-downside 20d return | -0.0377 | -0.0941 | -0.1208 | +0.0617 |

Slot-conflict value was also negative for both tags:

- `call_structure_support`: average 20d replacement value `-0.1132`
- `downside_structure_risk`: average 20d replacement value `-0.1365`

## Decision

Do not promote an options overlay into production ranking, sizing, gating, or
orders.

The simple call-support tag is not bullish on aggregate. The downside-risk tag
is directionally negative in `late_strong` and `mid_weak`, but it reverses in
`old_thin`, so it is not stable enough for a production rule.

## PIT Caveat

Historical OnClickMedia backfill rows do not expose vendor publication/as-of
metadata. They remain `pit_safe = false`. This source can support forward
paper attribution and shadow research, but not historical promotion evidence by
itself.

## Anti-Repeat Rule

Do not retry naive call-OI support, put/call OI, or 25-delta skew thresholds on
the same historical OnClickMedia backfill. A valid retry needs forward
PIT-safe rows with closed outcomes, or a materially richer feature set such as
IV rank, IV-vs-realized, earnings IV flags, and vendor-asof metadata.

