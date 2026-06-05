# exp-20260605-015 Broad Companyfacts Peer-Confirmed Adapter

- Trial family: `broad_companyfacts_peer_confirmed_filing_drift_adapter`
- Changed variable: `broad_companyfacts_peer_confirmed_filing_drift_shared_adapter_v1`
- Decision: `rejected_default_off_broad_companyfacts_peer_confirmed_adapter`
- Aggregate EV delta: +0.4864
- Aggregate PnL delta: $+12,793.51
- Target trades: 296
- Production impact: `shared_adapter_candidate_not_promoted`

## Hypothesis

Promoting the positive broad Companyfacts peer-confirmed filing-drift lead into a shared default-off adapter preserves the three-window replacement-value edge while making forward production paper evidence auditable.

## Gate 1-4

| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 106 | $3,544.93 | 5.1628 | 5.1752 | +0.0124 | $+4,695.53 | +0.0026 |
| mid_weak | 116 | $11,863.50 | 2.1402 | 2.7029 | +0.5627 | $+11,094.40 | -0.0075 |
| old_thin | 74 | $-2,080.38 | 0.5911 | 0.5024 | -0.0887 | $-2,996.42 | +0.0181 |

## Candidate Audit

```json
{
  "candidate_rows_before_daily_top1_by_window": {
    "late_strong": 1102,
    "mid_weak": 982,
    "old_thin": 274
  },
  "growth_ticker_count": 1274,
  "min_peer_confirmations": 1,
  "peer_confirmation_lookback_days": 45,
  "peer_rejected_by_window": {
    "late_strong": 7843,
    "mid_weak": 8420,
    "old_thin": 6984
  },
  "raw_candidate_count": 296,
  "same_ticker_cooldown_days": 30,
  "selected_by_window": {
    "late_strong": 106,
    "mid_weak": 116,
    "old_thin": 74
  },
  "warehouse_frame_count": 1446
}
```

## Production / Backtest Parity

The production-realistic replay calls quant/companyfacts_peer_confirmed_filing_drift_paper_sleeve.py, but the candidate adapter is not wired into quant/run.py, daily reports, watchlists, or order surfaces because Gate 4 failed.

## Failure Diagnosis

The positive exp-20260605-014 lead was not promoted because the production-realistic shared helper applies same-ticker cooldowns chronologically. The earlier replay iterated canonical windows in reverse chronology, so later-window selections could suppress older-window candidates; production cannot reproduce that behavior. With chronological cooldown semantics, old_thin regressed and drawdown drift exceeded the guard.

## Gate 4

- `passed`: `False`
- `status`: `rejected`
- `decision`: `rejected_default_off_broad_companyfacts_peer_confirmed_adapter`
- `failed_reasons`: `['window_ev_regression', 'window_pnl_regression', 'drawdown_drift_too_high']`
- `windows_ev_regressed`: `['old_thin']`
- `windows_pnl_regressed`: `['old_thin']`
- `drawdown_guard`: `<= 0.005`
- `target_trade_count_min`: `20`
- `target_window_count_min`: `3`
- `single_ticker_positive_share_guard`: `<= 0.5`
- `positive_pnl_hhi_guard`: `<= 0.3`
- `requires_parity_before_promotion`: `True`
- `parity_test_added`: `True`
- `shared_adapter_module`: `quant/companyfacts_peer_confirmed_filing_drift_paper_sleeve.py`
- `promotion_allowed`: `False`
- `production_parity_note`: `The production-realistic replay calls quant/companyfacts_peer_confirmed_filing_drift_paper_sleeve.py, but the candidate adapter is not wired into quant/run.py, daily reports, watchlists, or order surfaces because Gate 4 failed.`

## Reproducibility

.\.venv\Scripts\python.exe -B quant\experiments\exp_20260605_015_broad_companyfacts_peer_confirmed_adapter.py

No JavaScript was used.
