# exp-20260530-002: SEC 8-K event-family forward-drift (hardened)

**Read-only.** No entries/exits/ranking/sizing/orders.

Verdict: {'5.02': 'fragile', '8.01': 'robust'}

## fwd 5d (non-overlap n=442)

### Item 5.02
- pooled: n=110 (34 tickers) mean=1.07% t=2.12
- sub-period lifts: [-0.15, 1.36, 2.46]
- drop top ticker (AVGO): mean=0.85% t=1.81 (n=108)
- first-event-per-ticker: mean=0.14% t=0.43 (n=34)

### Item 8.01
- pooled: n=80 (31 tickers) mean=-0.71% t=-1.52
- sub-period lifts: [-1.25, -0.87, -0.97]
- drop top ticker (UNH): mean=-0.45% t=-1.13 (n=77)
- first-event-per-ticker: mean=-1.42% t=-1.53 (n=31)

## fwd 10d (non-overlap n=380)

### Item 5.02
- pooled: n=89 (34 tickers) mean=2.17% t=1.83
- sub-period lifts: [0.53, 0.88, 2.91]
- drop top ticker (INTC): mean=1.81% t=1.5 (n=84)
- first-event-per-ticker: mean=0.81% t=0.39 (n=34)

### Item 8.01
- pooled: n=64 (26 tickers) mean=-0.72% t=-2.12
- sub-period lifts: [-0.77, -1.56, -2.91]
- drop top ticker (XOM): mean=-0.41% t=-1.74 (n=61)
- first-event-per-ticker: mean=-1.5% t=-2.38 (n=26)

## Caveats

- departure/appointment text split BLOCKED offline (6/158 Item-5.02 filings carry usable body text); needs EDGAR 8-K Item 5.02 body fetch
- single 18-month large-cap (~38 ticker) sample, no transaction costs
- multiple testing: family-wise bar is |t|~3, focal cells are ~2.1
