# exp-20260906-001: Broker trading PnL visibility

Decision: accepted engineering measurement repair only. No alpha, strategy qualification or trading change.

The locked downstream check was daily report and quant-signals visibility of broker-backed PnL. The old code and latest existing daily outputs did not contain this measurement. The repaired output statements now both consume the same immutable aggregate, with incomplete facts shown explicitly. Historical daily reports were not rewritten.

Before: `data/experiments/exp-20260906-001/before.json`. Frozen inputs and code: `data/experiments/exp-20260906-001/source_contract.json`. After: `data/experiments/exp-20260906-001/after.json`.

The source and code freeze preceded the first outcome read. Source as of: 2026-09-06T03:02:15.736022Z. Broker event times remain broker-local with unspecified timezone.

| Same evaluated cohort | USD |
|---|---:|
| Gross trading PnL | -14,172.0262 |
| Latest reported order fees, once per order | 540.84 |
| Net trading PnL after order fees | -14,712.8662 |

Coverage: 68 committed collections; 732 latest effective fills; 1 cancelled latest deal excluded. 103 fully covered closed lifecycles were evaluated; 0 closed lifecycle failed cost/identity coverage. 13 open/unclosed lifecycles and 182 unknown-baseline fills are outside the sum. 2376 rows belonging to uncommitted collections are invisible. These counts describe different units and must not be added together. Status: `partial`.

All 103 accepted closed lifecycles have their fees; missing fees never become zero. Gross and net use exactly the same cohort. The 182 unknown-baseline fills also fail the zero-baseline prefix check; these are overlapping reason counts, not 364 different fills. Two repeated calls returned identical summaries and all 10 frozen source files retained their exact hashes. All offline production output checks passed and synthetic signals remained unchanged. The companion core/ledger/reporting regression suite passed 55 tests in the root task.

These are account-level trading observations and cannot be attributed to Ginger decisions. Financing, stock borrowing charges, dividends, open-position MTM, FX, capital flows and pre-window activity are excluded. This is not account return, strategy return, Sharpe, TWR or replacement value. `economic_progress=false`, `alpha_changed=false`, `trade_enabled=false`.

Reproduce offline: `.\.venv\Scripts\python.exe -B quant\experiments\exp_20260906_001_broker_performance_reporting.py`. The runner rejects changed frozen inputs; later daily snapshots use the normal read-only helper, not a silent revision of this experiment.

The repair is accepted because the measurement becomes visible and reconciles, regardless of its profit sign. The negative observed value is preserved without tuning any trade rule to it. Forbidden retry: slicing this account history into profitable symbol/sector/date buckets and calling them alpha. Reopen only for a new demonstrated accounting defect or independently frozen decision-to-order lineage that permits attribution.
