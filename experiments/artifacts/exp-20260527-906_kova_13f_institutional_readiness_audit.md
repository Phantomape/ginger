# exp-20260527-906 Kova 13F Institutional Readiness Audit

Decision: `data_gap_13f_institutional_rows_unavailable`.

The local Kova SEC 13F sidecar does not have enough PIT ticker-mapped current and prior ownership rows for the accepted VCP top-2 trade dates. Do not run or promote an institutional sponsorship rule until those rows exist.

## Sidecar

- Institutional files: `2`.
- Institutional rows: `62`.
- Usable PIT rows: `0`.
- Status counts: `{'skipped': 62}`.
- Reason counts: `{'no_sec13f_zip_or_year_quarter_supplied': 62}`.
- Ticker mapping counts: `{}`.

## Trade Coverage

- Source trades: `117`.
- Current+prior covered trades: `0`.
- Covered windows: `[]`.

| coverage status | trades |
|---|---:|
| skipped_only_no_sec13f_zip | 117 |

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
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260527_906_kova_13f_institutional_readiness_audit.py
```
