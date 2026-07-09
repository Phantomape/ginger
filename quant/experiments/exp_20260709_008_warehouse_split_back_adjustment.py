"""exp-20260709-008: warehouse OHLCV split back-adjustment (measurement_repair).

Hypothesis / blocker: the warehouse freezes stored OHLCV rows
(``update_existing=False`` on every daily write path), so a stock split that
occurs after a ticker's rows were written leaves the stored history at the
pre-split scale while later auto-adjusted vendor fetches insert
post-split-scale rows next to it. The discontinuity is permanent and corrupts
returns/ATR/drawdown for every consumer of ``ohlcv_overlay``.

Confirmed instances (vendor split calendar cross-checked via yfinance):

    KLAC 10:1  effective 2026-06-12, stale rows <= 2026-04-24 (666 cold)
    CRWD  4:1  effective 2026-07-02, stale rows <= 2026-06-29 (701 cold + 26 hot)
    DD   1:3 R effective 2026-06-24, stale rows <= 2026-06-22 (700 cold + 21 hot)
    MLI   2:1  effective 2026-07-01, stale rows <= 2026-06-26 (700 cold + 25 hot)

Repair (single measurement surface): back-adjust all stored rows at or before
each boundary by the round split divisor (OHLC / divisor, volume * divisor) in
BOTH tiers via ``quant/ohlcv_split_repair.py``, recorded in the
``split_adjustments`` ledger table (idempotent: re-runs return
``already_applied`` and can never double-divide). Plus a standing write-path
guard in ``quant/ohlcv_warehouse_refresh.py`` that compares fetched overlap
days against stored closes and auto-repairs future splits at insert time.

This runner is the reproduction/verification harness: it re-runs the overlay
scan, (re-)applies the four adjustments, re-scans, and writes the artifact.
Safe to re-run any time; it mutates the warehouse only if a listed adjustment
has not been applied yet.

Repro:
    .\.venv\Scripts\python.exe -B quant\experiments\exp_20260709_008_warehouse_split_back_adjustment.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "quant"))

from quant.ohlcv_split_repair import (  # noqa: E402
    back_adjust_ticker,
    list_adjustments,
    scan_overlay_discontinuities,
)
from quant.ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH, connect_overlay_reader  # noqa: E402

EXPERIMENT_ID = "exp-20260709-008"
ARTIFACT_PATH = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / "exp_20260709_008_warehouse_split_back_adjustment.json"
)

# (ticker, last stored date at the OLD scale, price divisor, vendor evidence)
REPAIRS = [
    ("KLAC", "2026-04-24", 10.0, "10:1 forward split effective 2026-06-12 (yfinance splits)"),
    ("CRWD", "2026-06-29", 4.0, "4:1 forward split effective 2026-07-02 (yfinance splits)"),
    ("DD", "2026-06-22", 1.0 / 3.0, "1-for-3 reverse split effective 2026-06-24 (yfinance splits)"),
    ("MLI", "2026-06-26", 2.0, "2:1 forward split effective 2026-07-01 (yfinance splits)"),
]

# Boundary continuity windows checked after repair: (ticker, start, end).
VERIFY_WINDOWS = [
    ("KLAC", "2026-04-20", "2026-05-01"),
    ("CRWD", "2026-06-24", "2026-07-03"),
    ("DD", "2026-06-17", "2026-06-26"),
    ("MLI", "2026-06-23", "2026-07-02"),
]

# Consumer blast radius established 2026-07-09 (read-only audit; see the
# experiment log for the full table). Recorded here so the artifact is
# self-contained.
CONTAMINATION_AUDIT = {
    "default_on_live_paths_affected": False,
    "notes": [
        "Core live signals price off yfinance directly (data_layer.get_ohlcv*), "
        "not the warehouse; run.py warehouse block declares alters_signal_generation/"
        "ranking/sizing/orders = False.",
        "KLAC/CRWD/DD/MLI are NOT in the core traded universe (quant/filter.py "
        "_BASE_WATCHLIST); KLAC+CRWD are in the PEAD broad universe, all four are "
        "in the broad ingest universe.",
    ],
    "contaminated_artifacts": [
        {
            "path": "data/kova/rs_proxy/rs_proxy_YYYYMMDD.jsonl",
            "detail": "default-ON alternative-data accumulation (non-order); KLAC "
            "rows contaminated 20260612-20260708, CRWD 20260702-20260708, DD "
            "20260623-20260708, MLI 20260701-20260708; files regenerate daily from "
            "the repaired warehouse going forward",
        },
        {
            "path": "data/non_ohlcv/news_event_exposure_observations/rows.jsonl",
            "detail": "default-off observer; KLAC/CRWD exposure rows written on/after "
            "2026-06-12 / 2026-07-02 used corrupt series",
        },
    ],
    "contaminated_experiments": [
        {
            "experiment": "exp-20260622-025",
            "detail": "factor_residual_idiosyncratic_leadership_post_repair: broad "
            "ohlcv_overlay read spanning KLAC 2026-04-24 boundary, ran 2026-06-22",
        },
        {
            "experiment": "exp-20260702-017",
            "detail": "ipo_theme_propagation: frames 2024-09-02..2026-07-02 spanning "
            "KLAC+CRWD boundaries; KLAC/CRWD theme-peer rows in propagation_rows.jsonl",
        },
        {
            "experiment": "exp-20260702-018",
            "detail": "sec_425_merger_theme_peer_propagation: same window; 14 "
            "KLAC/CRWD rows in propagation_rows.jsonl",
        },
    ],
    "clean_paths_checked": [
        "core watchlist experiments (exp-20260628-015, exp-20260629-008): core-50 "
        "universe, no affected tickers",
        "exp-20260627-017: frozen 20260604 baseline, windows end pre-split",
        "exp-20260702-023 / exp-20260703-009: no affected tickers in artifacts",
        "options/exit-lifecycle readers: closed core/options positions only",
        "forward_replacement_value comparators (SPY/QQQ) unaffected",
        "DD/MLI absent from PEAD broad universe and both propagation artifacts",
    ],
}


def _boundary_windows() -> list[dict[str, object]]:
    conn = connect_overlay_reader(DEFAULT_WAREHOUSE_PATH)
    out: list[dict[str, object]] = []
    try:
        for ticker, start, end in VERIFY_WINDOWS:
            rows = conn.execute(
                "SELECT date, close FROM ohlcv_overlay "
                "WHERE ticker = ? AND date BETWEEN ? AND ? ORDER BY date",
                (ticker, start, end),
            ).fetchall()
            closes = [(str(day), round(float(close), 4)) for day, close in rows]
            max_move = 0.0
            for (_d1, c1), (_d2, c2) in zip(closes, closes[1:]):
                if c1 > 0:
                    max_move = max(max_move, abs(c2 / c1 - 1.0))
            out.append(
                {
                    "ticker": ticker,
                    "window": [start, end],
                    "closes": closes,
                    "max_abs_day_move": round(max_move, 4),
                    "continuous": max_move < 0.30,
                }
            )
    finally:
        conn.close()
    return out


def main() -> int:
    # Scan state at this run's start. On the original 2026-07-09 run the four
    # discontinuities were captured to scan_before.json BEFORE any repair; on
    # re-runs the live scan is already clean, so prefer the preserved capture
    # as the canonical before-state.
    run_start_scan = scan_overlay_discontinuities(DEFAULT_WAREHOUSE_PATH)
    before_scan = run_start_scan
    before_capture = ARTIFACT_PATH.parent / "scan_before.json"
    if before_capture.exists():
        try:
            captured = json.loads(before_capture.read_text(encoding="utf-8-sig"))
            before_scan = captured.get("hits", before_scan)
        except (json.JSONDecodeError, OSError):
            pass
    apply_results = []
    for ticker, boundary, divisor, note in REPAIRS:
        apply_results.append(
            back_adjust_ticker(
                DEFAULT_WAREHOUSE_PATH,
                ticker,
                boundary,
                divisor,
                detected_from="exp-20260709-008 runner",
                experiment=EXPERIMENT_ID,
                note=note,
            )
        )
    after_scan = scan_overlay_discontinuities(DEFAULT_WAREHOUSE_PATH)
    windows = _boundary_windows()

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "lane": "measurement_repair",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "decision_variable": "warehouse OHLCV split-adjustment consistency "
        "(ohlcv_overlay continuity across split boundaries)",
        "before": {
            "scan_hits": before_scan,
            "scan_hit_count": len(before_scan),
            "scan_hits_at_run_start": len(run_start_scan),
            "before_capture_file": "data/experiments/exp-20260709-008/scan_before.json",
        },
        "repairs_requested": [
            {"ticker": t, "boundary_date": b, "price_divisor": d, "note": n}
            for t, b, d, n in REPAIRS
        ],
        "apply_results": apply_results,
        "after": {
            "scan_hits": after_scan,
            "scan_hit_count": len(after_scan),
            "boundary_windows": windows,
        },
        "adjustment_ledger": list_adjustments(DEFAULT_WAREHOUSE_PATH),
        "contamination_audit": CONTAMINATION_AUDIT,
        "guard": {
            "module": "quant/ohlcv_split_repair.py",
            "wired_into": "quant/ohlcv_warehouse_refresh.py refresh_warehouse_ohlcv "
            "(repair_splits=True default; events in summary['split_discontinuities'])",
            "tests": [
                "quant/test_ohlcv_split_repair.py",
                "quant/test_ohlcv_warehouse_refresh.py::"
                "test_refresh_split_guard_repairs_stale_history",
            ],
        },
        "verdict": {
            "repaired": all(
                r.get("status") in ("applied", "already_applied") for r in apply_results
            ),
            "after_scan_clean": len(after_scan) == 0,
            "all_boundaries_continuous": all(w["continuous"] for w in windows),
        },
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "artifact": str(ARTIFACT_PATH.relative_to(REPO_ROOT)),
                "before_hits": len(before_scan),
                "after_hits": len(after_scan),
                "apply_statuses": {r["ticker"]: r["status"] for r in apply_results},
                "all_boundaries_continuous": artifact["verdict"][
                    "all_boundaries_continuous"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    ok = (
        artifact["verdict"]["repaired"]
        and artifact["verdict"]["after_scan_clean"]
        and artifact["verdict"]["all_boundaries_continuous"]
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
