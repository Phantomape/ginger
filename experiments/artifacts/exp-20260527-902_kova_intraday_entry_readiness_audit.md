# exp-20260527-902 Kova Intraday Entry Readiness Audit

Decision: `data_gap_intraday_entry_rows_unavailable`.

The local Kova intraday sidecar does not have PIT 15m/60m bars for the accepted VCP top-2 trade dates. Do not run or promote an intraday Kova entry rule until the sidecar contains real bars.

## Sidecar

- Intraday files: `2`.
- Intraday rows: `62`.
- Status counts: `{'skipped': 62}`.
- Reason counts: `{'refresh_intraday_false_or_missing_ALPHA_VANTAGE_API_KEY': 62}`.

## Trade Coverage

- Source trades: `117`.
- Fully covered 15m+60m signal-date trades: `0`.
- Covered windows: `[]`.

| coverage status | trades |
|---|---:|
| skipped_only_no_intraday_bars | 117 |

## Gate 4

No strategy promotion was possible because this is a data-readiness audit.

```json
{
  "decision_evidence": {
    "covered_trade_count": 0,
    "covered_trade_count_min": 20,
    "covered_window_count": 0,
    "covered_window_count_min": 2,
    "covered_windows": [],
    "readiness_gate_passed": false
  },
  "passed": false,
  "promotion_grade": false,
  "reason": "Data readiness audit only; no strategy rule was tested.",
  "strategy_replacement_tested": false
}
```

## Repro

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260527_902_kova_intraday_entry_readiness_audit.py
```
