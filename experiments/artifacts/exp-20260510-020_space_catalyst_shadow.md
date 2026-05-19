# exp-20260510-020 Space Catalyst Shadow Sleeve

Status: observed_only.

## Hypothesis

SpaceX IPO attention, UAP disclosure attention, government space contracts, and
satellite connectivity milestones may create event-driven replacement value
across a public space proxy basket.

## Scope

Single causal variable: add a `SPACE_CATALYST_SHADOW` research/quarantine
candidate pool and zero-live-slot sleeve policy. This does not change core
universe membership, entry filters, exits, ranking, sizing, live pilot slots, or
LLM hard-risk authority.

## Seed Pool

Research: `RKLB`, `ASTS`, `LUNR`, `HAWK`, `PL`, `RDW`, `BKSY`, `IRDM`, `VSAT`,
`GSAT`, `SATS`, `ARKX`, `UFO`.

Quarantine: `SPCE`.

Segments:

- `launch_lunar`: `LUNR`, `RKLB`
- `satellite_connectivity`: `ASTS`, `GSAT`, `IRDM`, `SATS`, `VSAT`
- `space_data_defense`: `BKSY`, `HAWK`, `PL`, `RDW`
- `theme_beta_benchmark`: `ARKX`, `UFO`
- `quarantine_meme`: `SPCE`

## News Basis

- UAP/UFO disclosure attention is real but not cash-flow evidence:
  `https://www.war.gov/News/Releases/Release/Article/4480582/department-of-war-releases-unidentified-anomalous-phenomena-files-in-historic-t/`
- SpaceX IPO attention is the stronger catalyst, but there is still no public
  SpaceX ticker or public S-1 in the SEC feed:
  `https://www.investing.com/news/stock-market-news/spacex-to-pursue-2026-ipo-raising-above-30-billion-bloomberg-news-reports-4399323`
  and `https://data.sec.gov/submissions/CIK0001181412.json`
- Public proxy fundamentals/catalysts checked for `RKLB`, `ASTS`, and `LUNR`:
  `https://www.globenewswire.com/news-release/2026/05/07/3290563/0/en/rocket-lab-announces-first-quarter-2026-financial-results-surpasses-all-guidance-metrics-including-revenue-margin-and-adjusted-ebitda-posts-record-200m-quarterly-revenue-and-over-2.html`,
  `https://www.nasdaq.com/press-release/fcc-grants-ast-spacemobile-commercial-authority-deliver-direct-device-cellular`,
  `https://investors.intuitivemachines.com/news-releases/news-release-details/intuitive-machines-expands-lunar-surface-operations-1804-million`.

## Validation

Core no-drift check used the same fixed windows from `docs/backtesting.md` via a
no-save `BacktestEngine` harness with `include_pilot_sleeve=True` to avoid
overwriting the dirty shared `data/backtest_results_20260510.json` artifact.

| Window | EV | Sharpe daily | PnL | Max DD | Trades | Survival | Pilot entries |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | 4.2340 | 4.50 | $94,086.91 | 5.48% | 19 | 80.39% | 0 |
| `mid_weak` | 1.6689 | 2.70 | $61,813.40 | 9.41% | 21 | 79.25% | 0 |
| `old_thin` | 0.3853 | 1.35 | $28,544.11 | 8.15% | 22 | 91.67% | 0 |

Registry validation: `0` issues. Targeted tests:
`quant/test_pilot_sleeve.py` and `quant/test_space_catalyst_sleeve.py` passed
`15/15`.

## Decision

Keep as observed-only. Promotion requires at least 30 active signal days or 10
closed/resolved decisions with direct PnL > 0, replacement value > 0,
risk-adjusted replacement value > 0, and no single ticker contributing more
than 70% of positive value.
