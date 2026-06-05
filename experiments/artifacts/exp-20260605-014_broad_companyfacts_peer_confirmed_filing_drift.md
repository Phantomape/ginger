# exp-20260605-014 Broad Companyfacts Peer-Confirmed Filing Drift

- Trial family: `broad_companyfacts_peer_confirmed_filing_drift_candidate_pool`
- Changed variable: `broad_companyfacts_peer_confirmed_filing_drift_candidate_source_v1`
- Decision: `positive_replay_lead_not_promoted_requires_shared_adapter`
- Aggregate EV delta: +0.2992
- Aggregate PnL delta: $+11,207.33
- Target trades: 253
- Production impact: `replay_only_no_live_adapter`

## Hypothesis

Broad Companyfacts filing events with recent same-industry dual-growth confirmation can add cleaner default-off paper candidates than standalone broad dual-growth relative strength.

## Gate 1-4

| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 106 | $3,544.93 | 5.1628 | 5.1752 | +0.0124 | $+4,695.53 | +0.0026 |
| mid_weak | 100 | $5,077.71 | 2.1402 | 2.4163 | +0.2761 | $+5,788.73 | -0.0017 |
| old_thin | 47 | $754.09 | 0.5911 | 0.6018 | +0.0107 | $+723.07 | +0.0000 |

## Candidate Audit

```json
{
  "candidate_rows_before_daily_top1_by_window": {
    "late_strong": 1019,
    "mid_weak": 542,
    "old_thin": 92
  },
  "growth_ticker_count": 1274,
  "industry_group_count": 136,
  "min_peer_confirmations": 1,
  "peer_confirmation_lookback_days": 45,
  "peer_rejected_by_window": {
    "late_strong": 7843,
    "mid_weak": 7243,
    "old_thin": 4689
  },
  "raw_candidate_count": 253,
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
      "DIA",
      "IBIT",
      "SGOL",
      "SPY",
      "SSNC",
      "SWK",
      "SYK",
      "TAL",
      "TGT",
      "TKR",
      "TMO",
      "TNDM",
      "TSN",
      "TXN",
      "TXNM",
      "UAA",
      "UMBF",
      "UTHR",
      "V",
      "VLY",
      "VNT",
      "WMG",
      "WMS",
      "WPM",
      "XPO"
    ]
  },
  "selected_by_window": {
    "late_strong": 106,
    "mid_weak": 100,
    "old_thin": 47
  },
  "warehouse_frame_count": 1446
}
```

## Gate 4

- `passed`: `True`
- `status`: `accepted`
- `decision`: `positive_replay_lead_not_promoted_requires_shared_adapter`
- `failed_reasons`: `[]`
- `windows_ev_regressed`: `[]`
- `windows_pnl_regressed`: `[]`
- `drawdown_guard`: `<= 0.005`
- `target_trade_count_min`: `20`
- `target_window_count_min`: `3`
- `single_ticker_positive_share_guard`: `<= 0.5`
- `positive_pnl_hhi_guard`: `<= 0.3`
- `requires_parity_before_promotion`: `True`
- `production_parity_note`: `This runner changes no production code. A positive result would require a separate shared default-off Companyfacts peer-confirmation adapter, daily production exposure of the same filed-date-safe growth and industry fields, warehouse/snapshot replay parity, and focused tests before any report queue, paper ledger, candidate priority, or order surface could change.`

## Production / Backtest Parity

This runner changes no production code. A positive result would require a separate shared default-off Companyfacts peer-confirmation adapter, daily production exposure of the same filed-date-safe growth and industry fields, warehouse/snapshot replay parity, and focused tests before any report queue, paper ledger, candidate priority, or order surface could change.

## Reproducibility

.\.venv\Scripts\python.exe -B quant\experiments\exp_20260605_014_broad_companyfacts_peer_confirmed_filing_drift.py

No JavaScript was used.
