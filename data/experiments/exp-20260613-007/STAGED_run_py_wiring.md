# exp-20260613-007 — deferred run.py wiring (do after exp-20260612-009 lands)

`run.py` and `kova_data_sidecar.py` were held by the concurrently-claimed
exp-20260612-009 during this experiment, so the daily wiring was intentionally
deferred to avoid a two-agent edit collision. The ingestion modules
(`sec13f_universe_map.py`, `sec13f_ingest.py`) are complete, tested, and have
already produced real data. Only the daily trigger remains.

## What to add to run.py

In the broad-market block (near where the broad universe feed is loaded /
`broad_market_candidate_universe` is resolved — the exp-20260612-002 region),
add an idempotent daily call. 13F is quarterly: this is a no-op on ~246/250
trading days and only re-parses when a new SEC filing window is released
(~4x/year, around mid-Feb/May/Aug/Nov).

```python
# exp-20260613-007: refresh universe-scoped 13F institutional holdings.
if not _env_flag("SEC13F_INGEST_DISABLED"):
    try:
        from sec13f_ingest import ingest_universe_13f

        sec13f_summary = ingest_universe_13f(
            universe=broad_market_candidate_universe.get("tickers") or [],
            as_of=today_iso,
        )
        log.info(
            "SEC 13F holdings: status=%s window=%s coverage=%s/%s (%.0f%%)",
            sec13f_summary.get("status"),
            sec13f_summary.get("window_label"),
            sec13f_summary.get("universe_covered_count"),
            sec13f_summary.get("universe_size"),
            sec13f_summary.get("universe_coverage_pct") or 0.0,
        )
    except Exception as sec13f_error:
        log.warning("SEC 13F holdings ingestion failed: %s", sec13f_error)
```

Notes:
- Default `head_check=_default_head_check` does one HEAD request to absorb
  publish lag near a window boundary; on the no-op days it still short-circuits
  on the existing `holdings_<window>.json` before any parse.
- The first run after a new window appears downloads ~100MB and parses ~3M rows
  (tens of seconds); steady-state daily cost is one HEAD request.
- Optional follow-up: retire the kova `sec13f_ownership_*` skipped-placeholder
  stream (or point it at this real artifact) — that lives in
  `kova_data_sidecar.py`, also in exp-20260612-009's scope.
```
