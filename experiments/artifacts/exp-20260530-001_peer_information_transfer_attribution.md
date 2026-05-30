# exp-20260530-001: intra-sector peer information-transfer attribution

**Read-only / observe-only.** Does not touch entries, exits, ranking, sizing, orders, paper sleeves, or LLM.

Universe: 42 tickers, 4 sectors (Communication Services, Financial Services, Industrials, Technology), 207 shock events.

## Pooled, non-overlapping forward sampling (excess vs SPY)

### fwd 5d  (n=1998 after non-overlap)

| bucket | n | mean excess % | hit % | t vs none |
|---|---:|---:|---:|---:|
| strong_pos | 397 | +1.12 | 59 | 1.03 |
| pos | 55 | +1.37 | 54 | 0.66 |
| none | 1237 | +0.70 | 52 | 0.0 |
| neg | 92 | +0.06 | 50 | -0.98 |
| strong_neg | 217 | +1.32 | 53 | 0.99 |

### fwd 10d  (n=999 after non-overlap)

| bucket | n | mean excess % | hit % | t vs none |
|---|---:|---:|---:|---:|
| strong_pos | 230 | +3.07 | 60 | 2.82 |
| pos | 29 | +4.28 | 62 | 1.27 |
| none | 613 | +0.94 | 50 | 0.0 |
| neg | 50 | +1.79 | 50 | 0.54 |
| strong_neg | 77 | +2.34 | 54 | 1.01 |

## Temporal sign-consistency of the `pos` bucket

- fwd 5d: positive lift in 2/3 sub-periods (lifts [3.06, 0.481, -2.587])
- fwd 10d: positive lift in 2/3 sub-periods (lifts [6.885, 1.783, -3.988])

## Caveats

- universe is ~56 tech-heavy names across 4 sectors; possible AI-theme co-movement not removed by SPY-excess alone
- shocks are gap+volume proxies, not a true earnings calendar
- no transaction costs
- sub-period bucket samples are thin after non-overlap sampling
