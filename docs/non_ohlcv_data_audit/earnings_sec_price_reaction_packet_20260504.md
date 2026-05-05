# Earnings + SEC filing + price reaction packet audit

- Experiment: `exp-20260504-002`
- Status: `observed_only_not_promoted`
- Covered window: `2025-10-23 -> 2026-04-21`
- Production impact: shadow-only; no strategy logic changed.

## Headline

The covered event packet did not clear a promotion-quality drift bar, or the sample is too thin after requiring nearby results 8-K context and positive reaction.

## Coverage

- Raw inferred earnings events: `92`
- Deduped event packets: `76`
- Price-covered events: `72`
- Nearby SEC packet events: `66`
- Results 8-K events: `65`
- Primary packet events: `21`
- Primary valid 10d outcomes: `20`
- Current EPS surprise inferred: `69`

## Primary Packet

| Cohort | Events | 10d excess avg | 10d win | 20d excess avg | 20d win |
|---|---:|---:|---:|---:|---:|
| results_8k + positive reaction | 21 | -1.83% | 30.00% | 1.33% | 35.00% |

## By SEC Packet Type

| Cohort | Events | 10d excess avg | 10d win | 20d excess avg | 20d win |
|---|---:|---:|---:|---:|---:|
| no_nearby_sec | 6 | 1.25% | 80.00% | -3.01% | 40.00% |
| periodic_10q_10k | 1 | -27.45% | 0.00% | -24.65% | 0.00% |
| results_8k | 65 | -0.43% | 43.55% | 0.51% | 32.26% |

## By Reaction Bucket

| Cohort | Events | 10d excess avg | 10d win | 20d excess avg | 20d win |
|---|---:|---:|---:|---:|---:|
| negative_excess_0_to_minus_2pct | 21 | 0.71% | 57.14% | -0.05% | 33.33% |
| negative_excess_le_minus_2pct | 26 | -0.11% | 47.83% | -1.00% | 26.09% |
| positive_excess_0_to_2pct | 10 | -1.46% | 44.44% | 0.05% | 33.33% |
| positive_excess_ge_2pct | 15 | -3.14% | 26.67% | 1.03% | 40.00% |

## Gate / Caveat

- Gate 4 is intentionally not passed because this is not a promoted strategy change.
- Mid/old windows are blocked by missing PIT earnings snapshots, so this cannot yet support production ranking.
- The SEC side is public-availability PIT via EDGAR `accepted_at`; it does not prove local production observation.

## Next Action

Do not tune nearby reaction thresholds. The next valid retry needs older PIT earnings coverage, XBRL fundamentals, or LLM financial-statement grading.
