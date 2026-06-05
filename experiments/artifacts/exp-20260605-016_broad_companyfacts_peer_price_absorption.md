# exp-20260605-016 Broad Companyfacts Peer Price Absorption

- Trial family: `broad_companyfacts_peer_price_absorption_candidate_pool`
- Changed variable: `broad_companyfacts_peer_price_absorption_candidate_source_v1`
- Decision: `rejected_broad_companyfacts_peer_price_absorption_candidate_pool`
- Aggregate EV delta: +0.2859
- Aggregate PnL delta: $+6,770.51
- Target trades: 192
- Production impact: `replay_only_no_live_adapter`

## Hypothesis

Broad Companyfacts filing events with positive realized growth and recent peer price absorption may add cleaner default-off paper candidates than same-industry growth confirmation.

## Gate 1-4

| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 80 | $1,164.46 | 5.1628 | 5.1832 | +0.0204 | $+1,808.80 | +0.0001 |
| mid_weak | 81 | $4,845.79 | 2.1402 | 2.4263 | +0.2861 | $+5,556.81 | -0.0011 |
| old_thin | 31 | $-787.19 | 0.5911 | 0.5705 | -0.0206 | $-595.10 | +0.0079 |

## Candidate Audit

```json
{
  "candidate_rows_before_daily_top1_by_window": {
    "late_strong": 513,
    "mid_weak": 320,
    "old_thin": 66
  },
  "growth_ticker_count": 1274,
  "industry_group_count": 136,
  "min_peer_confirmations": 1,
  "peer_absorption_rule": {
    "lookback_days": 45,
    "min_age_days": 5,
    "min_close_location": 0.55,
    "min_excess_spy": 0.0,
    "min_return": 0.02
  },
  "peer_confirmation_lookback_days": 45,
  "peer_rejected_by_window": {
    "late_strong": 15264,
    "mid_weak": 11577,
    "old_thin": 6162
  },
  "raw_candidate_count": 192,
  "same_ticker_cooldown_days": 30,
  "sector_coverage": {
    "cache_generated_at": "2026-05-27T05:25:19Z",
    "ok_share": 0.856846,
    "rule_version": "yfinance_gics_proxy_sector_v1",
    "sector_counts": {
      "Basic Materials": 66,
      "Communication Services": 47,
      "Consumer Cyclical": 162,
      "Consumer Defensive": 61,
      "Energy": 79,
      "Financial Services": 176,
      "Healthcare": 140,
      "Industrials": 189,
      "Real Estate": 64,
      "Technology": 213,
      "Utilities": 42
    },
    "sector_unique_count": 11,
    "source": "yfinance.Ticker.info.sector",
    "status_counts": {
      "fetch_error": 207,
      "missing_info": 0,
      "missing_ticker": 0,
      "ok": 1239
    },
    "status_shares": {
      "fetch_error": 0.143154,
      "missing_info": 0.0,
      "missing_ticker": 0.0,
      "ok": 0.856846
    },
    "tickers_requested": 1446,
    "tickers_unique": 1446,
    "unresolved_sample": [
      "FETH",
      "GDXU",
      "PSLV",
      "SLV",
      "SSNC",
      "T",
      "TFC",
      "THG",
      "TKO",
      "TNDM",
      "TNL",
      "TRMB",
      "TSN",
      "UCO",
      "UHS",
      "ULTA",
      "USFD",
      "UVXY",
      "VAL",
      "VNT",
      "WFRD",
      "WGS",
      "WTRG",
      "WYNN",
      "YUMC"
    ]
  },
  "selected_by_window": {
    "late_strong": 80,
    "mid_weak": 81,
    "old_thin": 31
  },
  "warehouse_frame_count": 1446
}
```

## Gate 4

- `passed`: `False`
- `status`: `rejected`
- `decision`: `rejected_broad_companyfacts_peer_price_absorption_candidate_pool`
- `failed_reasons`: `['window_ev_regression', 'window_pnl_regression']`
- `windows_ev_regressed`: `['old_thin']`
- `windows_pnl_regressed`: `['old_thin']`
- `drawdown_guard`: `<= 0.005`
- `target_trade_count_min`: `20`
- `target_window_count_min`: `3`
- `single_ticker_positive_share_guard`: `<= 0.5`
- `positive_pnl_hhi_guard`: `<= 0.3`
- `requires_parity_before_promotion`: `True`
- `production_parity_note`: `This runner changes no production code. A positive result would require a separate shared default-off Companyfacts peer-price absorption adapter, daily production exposure of the same filed-date-safe growth, industry, and OHLCV peer absorption fields, warehouse/snapshot replay parity, and focused tests before any report queue, paper ledger, candidate priority, or order surface could change.`

## Production / Backtest Parity

This runner changes no production code. A positive result would require a separate shared default-off Companyfacts peer-price absorption adapter, daily production exposure of the same filed-date-safe growth, industry, and OHLCV peer absorption fields, warehouse/snapshot replay parity, and focused tests before any report queue, paper ledger, candidate priority, or order surface could change.

## Reproducibility

.\.venv\Scripts\python.exe -B quant\experiments\exp_20260605_016_broad_companyfacts_peer_price_absorption.py

No JavaScript was used.
