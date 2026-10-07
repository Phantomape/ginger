# exp-20260906-008: broker history date-range paging

Engineering acceptance only. The full 730-day lookback is unchanged; no signal,
ranking, sizing, exit or trading permission changes belong to this experiment.

The frozen before artifact records real history_deals/history_orders failures:
the installed broker rejects query spans longer than 360 days. The collector had
sent the entire two-year range in one call. The SDK treats date endpoints as
inclusive, so the repair uses consecutive <=360-date intervals with no overlap
or gap and retains per-segment manifests. Failed segments cannot be masked by a
later successful segment. Current observations remain final and fees are queried
once per order using existing batching and rate-limit handling.

## Verification

- Synthetic regressions reproduce the range limit and test exact date coverage,
  boundaries, partial/error aggregation, current-over-history priority and cancel.
- A -> B -> A snapshots now append the final observed version without double
  counting economic deals or fees. Old committed captures and same-capture replay
  append zero rows and cannot roll back current state.
- Three additional regressions first failed, then passed for interrupted state
  writes after manifest commit, missing/stale state recovery and stale replay /
  same-collection snapshot conflict rejection. Only the latest capture may
  rebuild derived state; all raw plans must remain empty.
- Final focused suite: **92 passed**. Frozen real-capture verification passes.
- Six real history requests succeed across 2024-09-06..2025-08-31,
  2025-09-01..2026-08-26 and 2026-08-27..2026-09-06.
- Captured 698 fills, 740 orders and 658 order-fee observations. Final desired
  normalized facts match both isolated and canonical ledgers with zero differences.
- Eight existing JSONL prefixes preserved exactly. Committed real capture replay
  adds zero rows; two performance calls agree and do not write raw bytes.

The initial live capture and canonical append preceded the later independent
A -> B -> A review finding. Initial proof and code hashes are retained rather
than relabeled. The revisions reused that private capture, froze final code, and
verified final-fact equality, zero append and unchanged raw bytes. They made no
new broker request and did not rewrite source history.

## Result and limits

History freshness is restored to 2026-09-06T17:01:19.296539Z. All three economic
query statuses are now ok. There are 105 lifecycle groups carrying a close event:
103 pass the full checks, while two have incomplete/invalid quantity paths and
remain excluded. The same evaluated subset has gross trading PnL -USD 14,172.0262,
order fees USD 540.84 and net trading PnL after order fees **-USD 14,712.8662**.
Gross minus fees equals net on precisely the same cohort. The amount did not
improve; the collector now works and reports its limitations honestly.

Open mark-to-market, financing, borrow costs, dividends, FX, cash transfers,
unknown baselines and unsupported instruments are excluded. No strategy/order
lineage exists, so this is neither Ginger-attributed profit nor whole-account
return. No backtest, Sharpe or economic improvement is claimed. trade_enabled=false.
No order, unlock, position refresh or operator-state mutation occurred.

Frozen before: `data/experiments/exp-20260906-008/before.json`.
Final proof: `data/experiments/exp-20260906-008/final_after.json`.
Revision proof: `data/experiments/exp-20260906-008/version_projection_revision/`.
Reproduction: `.venv/Scripts/python.exe -B quant/experiments/exp_20260906_008_broker_history_date_range_paging.py --verify-existing-capture`.

Reopen only for a demonstrated new collection/version/recovery defect, not to
shorten history, exclude losses or convert this repair into an alpha claim.
