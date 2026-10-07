# Frozen plan: news-propagation pair sleeve grace-period clock must follow the authorized price sources, not the session anchor

Frozen 2026-10-07 (UTC) before reservation. Lane: root production_maintenance / measurement_repair.

## Defect (identity-only evidence, no PnL field read)

- Machine was off from ~2026-09-26 to 2026-10-06 17:35 local (LastBootUpTime); `quant/run.py` catch-up started 17:39:22 local (00:39:22Z 10-07).
- `news_propagation_pair_paper_sleeve.run()` executed at 2026-10-07T00:56:01.77Z (state.json updated_at, run log 17:56:01) and appended two `unsettleable` outcomes:
  - basket `news-first-seen-39644ff3bf36cb2bdb66` (decision 2026-09-13, entry 2026-09-14, exit 2026-09-25): short leg AIOT + INSG reported missing "in every authorized price source through the grace period". This basket was the FIRST acceptance-countable basket (admitted after exp-20260913-007; admission_priceability passed on sessions 09-04..09-11 via the massive fallback).
  - basket `news-first-seen-356b2f544aa1cd7ff44a` (decision 2026-09-07, pre-amendment): legs ABIT / BMHL / GTIJF genuinely have no bars (ABIT, GTIJF absent from massive; BMHL 5 bars) -> correct.
- AIOT and INSG have 0 rows in `data/warehouse/warehouse_main_hot.sqlite` (not in the 1320-ticker hot universe) and 11/11 bars 2026-09-11..2026-09-25 in `massive_history.daily_bars` as of now.
- `massive_history.fetch_checkpoint`: grouped:2026-09-24 complete 2026-09-26T03:08Z (last pre-outage pass); grouped:2026-09-25 complete 2026-10-07T00:56:40.50Z; grouped:2026-09-28 00:56:51Z ... grouped:2026-10-05 00:57:52Z. So at settlement time massive ended at 2026-09-24: the exit bar (09-25) arrived 39 seconds AFTER the terminalization.
- Session anchor SPY is in the 56-ticker core `primary_batch` (refreshed 17:50:27 local, hot max 2026-10-06), so `calendar` in `settle_pair_basket` already had 7 sessions after the exit; `len(calendar)-1-exit_index >= UNSETTLEABLE_GRACE_SESSIONS (5)` held and the missing leg was terminalized.
- Step order in run.py: pair sleeve (run.py:550, inside the non-OHLCV snapshot stage) runs BEFORE `_run_massive_ohlcv_grouped_catchup` (run.py:4561). On a normal day massive lags one session and the 5-session grace absorbs it; after a 7-session outage the anchor jumped 7 sessions in one pass while massive still lagged -> grace "elapsed" on the anchor clock while the leg's own source had not yet reached the exit session.

## Root cause (single causal variable)

`settle_pair_basket` measures the exp-20260913-007 grace period on the session anchor's calendar (SPY hot frame) instead of on the authorized price sources' own coverage. The frozen rule says a leg is unsettleable only when its bar is "missing in every authorized price source through the grace period"; a source that has not yet published the grace-window sessions cannot have been consulted "through the grace period".

## Fix (minimal, forward-only)

1. `load_pair_bars` records `bars["__source_last_sessions__"] = {"warehouse_anchor": <anchor_last>, "massive": <MAX(trade_date) in daily_bars or None>}` (one extra read-only query; nothing else changes).
2. `settle_pair_basket`: when legs are missing and the anchor calendar reaches the grace session `calendar[exit_index + 5]`, terminalize as `unsettleable` ONLY IF the massive source has also reached that session (`massive_last >= grace_session`). Otherwise return the ordinary `missing_leg_bars:<tickers>` blocker (basket stays pending). Bars mappings without `__source_last_sessions__` (unit-test fixtures, replay callers) keep the legacy anchor-only behaviour byte-for-byte.
3. New unit test: anchor calendar 7 sessions past exit + leg missing: massive_last before the grace session -> blocker; massive_last at/after the grace session -> unsettleable terminal row (same shape as today).

Locked: hold 10 / 45bp / $1000; admission priceability v1; grace length 5; acceptance contract (>=20 baskets / >=10 dates / halves / <=40%); run.py step order; ledger bytes (append-only; the false `unsettleable` row for basket 39644ff3 is NOT rewritten or re-settled under this ID - user decision, recorded in the receipt); readiness records; massive/hot warehouses.

## Acceptance rule

Accepted only if: (a) new test passes and all existing `quant/test_news_propagation_pair_paper_sleeve.py` + `quant/test_run_daily_wiring.py` + `quant/test_news_propagation_pair_forward_observer.py` tests pass unchanged; (b) read-only replay of the frozen 09-13 decision with bars where massive rows are pruned to <= 2026-09-24 (the settlement-time state) returns the `missing_leg_bars:AIOT,INSG` blocker under the fixed code (bug reproduced: current code returns `unsettleable`); (c) the same replay with today's full bars returns `outcome_status == settled` under both current and fixed code (only the status is read; no PnL value is printed or persisted); (d) ledger.jsonl and state.json sha256 unchanged.

Budget: <=1 measurement_repair ID, <=60 wall minutes from reservation, 0 external spend, 0 outcome/PnL fields read.
Predicted failure modes: massive_db_absent_in_some_caller_so_legacy_path_keeps_anchor_clock; grouped_catchup_403_on_latest_session_delays_terminalization_by_one_day; hot_tier_only_ticker_with_lagging_frame_not_covered_by_massive_clock; run_py_step_order_still_settles_massive_legs_one_day_late.
