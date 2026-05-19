# exp-20260510-025 SEC financial-report T+1 forward queue

## Hypothesis

SEC financial-report events (`earnings_8k`, `periodic_report`) that beat SPY on T+1 may have forward replacement value if frozen for next-session paper entry.

This follows `exp-20260510-024`, which found the financial-report + positive T+1 excess slice was the strongest SEC filing drift lead. This run did not use LLM soft-ranking because that path remains sample-limited.

## Change

Added a default-off forward queue and paper sleeve:

- `SEC_FINANCIAL_REPORT_T1_DRIFT_FORWARD_QUEUE`
- `SEC_FINANCIAL_REPORT_T1_DRIFT_EVENT_SLEEVE_PAPER`

Qualification rule:

```text
event_family in earnings_8k, periodic_report
AND ticker T+1 close-to-close return > 0
AND ticker T+1 close-to-close return > SPY T+1 return
```

The queue/sleeve is observe-only: no orders, no core ranking, no sizing, no slot use.

## Gate 4

Canonical three-window fixed-snapshot backtests stayed unchanged versus the accepted core baseline:

| Window | EV | PnL | Return | Max DD | Trades | Survival |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | 4.2340 | $94,086.91 | 94.09% | 5.48% | 19 | 80.39% |
| mid_weak | 1.6689 | $61,813.40 | 61.81% | 9.41% | 21 | 79.25% |
| old_thin | 0.3853 | $28,544.11 | 28.54% | 8.15% | 22 | 91.67% |

Aggregate EV delta: `0.0000`. Aggregate PnL delta: `$0.00`.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest quant\test_sec_event_queue.py quant\test_sec_financial_report_event_sleeve.py
.\.venv\Scripts\python.exe quant\backtester.py --start 2025-10-23 --end 2026-04-21 --ohlcv-snapshot data\ohlcv_snapshot_20251023_20260421.json
.\.venv\Scripts\python.exe quant\backtester.py --start 2025-04-23 --end 2025-10-22 --ohlcv-snapshot data\ohlcv_snapshot_20250423_20251022.json
.\.venv\Scripts\python.exe quant\backtester.py --start 2024-10-02 --end 2025-04-22 --ohlcv-snapshot data\ohlcv_snapshot_20241002_20250422.json
```

Result: `22 passed`; all three core windows unchanged.

## Production impact

```text
production_impact:
  shared_policy_changed: true
  backtester_adapter_changed: false
  run_adapter_changed: true
  replay_only: false
  parity_test_added: true
  alters_signal_generation: false
  alters_candidate_ranking: false
  alters_sizing: false
  alters_orders: false
```

Decision: accepted for forward observation only. Promotion requires closed paper replacement-value evidence and a shared trade adapter.
