# 20260503_0305 pullback_rs_eod

- experiment_id: `exp-20260503-008`
- lane: `alpha_search`
- category: `cross_sectional_ranking`
- decision: `observed_promising_not_promoted`
- run_time_utc: `2026-05-03T03:05:00.649083+00:00`

## Alpha Hypothesis
Strong 60-day relative strength combined with a short 5-day pullback can rank better than pure momentum or pure reversal for EOD 5/10/20/60-day holding horizons.

## Mechanism Insight Check
This does not retry rejected low-TQS breakout, Financials target-width, semicap watchlist, or SEC/earnings sparse-archive variants. It is a standalone OHLCV cross-sectional ranking probe.

## Outputs
- `D:\Github\ginger\experiments\pullback_rs_eod\results.csv`
- `D:\Github\ginger\experiments\pullback_rs_eod\rank_ic_by_date.csv`
- `D:\Github\ginger\experiments\pullback_rs_eod\notes.md`
- `D:\Github\ginger\experiments\pullback_rs_eod\config.yaml`

## Coverage
{
  "late_strong": {
    "liquid_count": 41,
    "sectors": {
      "Communication Services": 3,
      "Consumer Discretionary": 4,
      "Energy": 2,
      "Financials": 5,
      "Healthcare": 4,
      "Industrials": 4,
      "Technology": 16,
      "Unknown": 4
    },
    "ticker_count": 42
  },
  "mid_weak": {
    "liquid_count": 38,
    "sectors": {
      "Communication Services": 3,
      "Consumer Discretionary": 4,
      "Energy": 2,
      "Financials": 5,
      "Healthcare": 4,
      "Industrials": 4,
      "Technology": 15,
      "Unknown": 1
    },
    "ticker_count": 38
  },
  "old_thin": {
    "liquid_count": 38,
    "sectors": {
      "Communication Services": 3,
      "Consumer Discretionary": 4,
      "Energy": 2,
      "Financials": 5,
      "Healthcare": 4,
      "Industrials": 4,
      "Technology": 15,
      "Unknown": 1
    },
    "ticker_count": 38
  }
}

## Result Summary at 35 bps
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

## Decision Rationale
Primary variant is directionally promising, but this is a standalone cross-sectional study with survivorship-biased current snapshots and no production slot-aware integration yet.
