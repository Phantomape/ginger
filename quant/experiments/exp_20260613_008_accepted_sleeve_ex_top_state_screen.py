"""exp-20260613-008: accepted-sleeve x market-state ex-top-ticker screen.

Observed-only (no strategy change). Applies the exp-20260612-027 ex-top-ticker
robustness screen to the six accepted default-off paper sleeves attributed in
exp-20260606-022 (low-deployment ETF, macro relief, cross-source consensus,
SEC FTD+FINRA, FINRA/IWM borrow, post-earnings drift). Those sleeves were
originally screened WITHOUT the robustness check; re-screening looks for
additional source x state cells whose edge survives removing the top ticker,
to supply more clean cells for a multi-cell regime router beyond the single
industry_stable_core_flow cell accepted in exp-20260613-005.

Reuses, unchanged:
- exp-20260606-022 SOURCE_SPECS + `_extract_source_rows` (row loaders + the
  same prior-close PIT state classifier);
- exp-20260612-027 `_cell_stats` / `_screen` (the predeclared ex-top-ticker
  robustness screen and its thresholds).

Multiple-testing posture: 6 sleeves x ~15 states screened, observed-only by
construction. Survivors only justify a separate frozen Gate 1-4 sleeve tilt
experiment (the exp-20260613-005 template); they are not accepted alpha.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260613-008"
STEM = "accepted_sleeve_ex_top_state_screen"
TRIAL_FAMILY = "market_state_conditioned_sleeve_router"
TRIAL_VARIANT_ID = "accepted_sleeve_ex_top_state_screen_v1"
CHANGED_VARIABLE = "accepted_sleeve_market_state_cells_under_ex_top_ticker_screen"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENT_DIR / "legacy"
for path in (QUANT_DIR, EXPERIMENT_DIR, LEGACY_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260606_022_market_state_accepted_sleeve_replacement_value_attribution as src  # noqa: E402
import exp_20260612_027_broad_state_source_attribution as scr  # noqa: E402

WINDOWS = src.WINDOWS
MIN_CELL_FOR_REPORT = 4

OUT_JSON = (
    REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"exp_20260613_008_{STEM}.json"
)
BEFORE_AGG_JSON = OUT_JSON.parent / f"exp_20260613_008_{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_JSON.parent / f"exp_20260613_008_{STEM}_after_aggregate.json"


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    if isinstance(value, set):
        return sorted(_safe(v) for v in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_payload() -> dict[str, Any]:
    snapshots: dict[str, Any] = {}
    trading_dates_by_window: dict[str, list[str]] = {}
    for label, cfg in WINDOWS.items():
        snap = src._load_snapshot(cfg["snapshot"])
        snapshots[label] = snap
        trading_dates_by_window[label] = src._trading_dates(snap)

    all_rows: list[dict[str, Any]] = []
    source_reports: list[dict[str, Any]] = []
    for spec in src.SOURCE_SPECS:
        rows, report = src._extract_source_rows(
            spec, snapshots, trading_dates_by_window
        )
        for r in rows:
            cs = r.get("combined_state")
            if not cs:
                continue
            all_rows.append(
                {
                    "sleeve": r["sleeve"],
                    "ticker": r["ticker"],
                    "window": r["window"],
                    "pnl_pct": float(r.get("pnl_pct_net") or 0.0),
                    "combined_state": cs,
                    "entry_date": r["entry_date"],
                }
            )
        source_reports.append(
            {
                "sleeve": report["sleeve"],
                "accepted_experiment_id": report["accepted_experiment_id"],
                "artifact_exists": report["artifact_exists"],
                "rows_total": report["rows_total"],
                "rows_with_state": report["rows_with_state"],
                "blocker": report.get("blocker"),
            }
        )

    by_sleeve: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in all_rows:
        by_sleeve[r["sleeve"]].append(r)

    duplicate_groups = Counter((r["ticker"], r["entry_date"]) for r in all_rows)
    duplicate_rows = sum(c for c in duplicate_groups.values() if c > 1)

    cells: list[dict[str, Any]] = []
    for sleeve, srows in sorted(by_sleeve.items()):
        for state in sorted({r["combined_state"] for r in srows}):
            cell_rows = [r for r in srows if r["combined_state"] == state]
            if len(cell_rows) < MIN_CELL_FOR_REPORT:
                continue
            other_rows = [r for r in srows if r["combined_state"] != state]
            stats = scr._cell_stats(cell_rows, other_rows)
            screen = scr._screen(stats)
            cells.append(
                {"sleeve": sleeve, "combined_state": state, **stats, "screen": screen}
            )

    survivors = [c for c in cells if c["screen"]["passed"]]
    survivors.sort(key=lambda c: -(c["ex_top_edge_vs_other_states"] or 0))
    near_misses = sorted(
        (
            c
            for c in cells
            if not c["screen"]["passed"]
            and sum(1 for v in c["screen"]["checks"].values() if not v) == 1
        ),
        key=lambda c: -(c["ex_top_edge_vs_other_states"] or -1),
    )

    decision = (
        "observed_only_additional_router_cells_found_requires_separate_gate_1_4"
        if survivors
        else "observed_only_no_additional_cell_survives_ex_top_ticker_screen"
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "lane": "alpha_search",
        "status": "observed_only",
        "decision": decision,
        "diagnostic_only": True,
        "hypothesis": (
            "Applying the exp-20260612-027 ex-top-ticker robustness screen to the "
            "six accepted default-off sleeves of exp-20260606-022 surfaces "
            "additional source x state cells whose edge survives removing the top "
            "ticker, for a multi-cell regime router beyond exp-20260613-005."
        ),
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "change_type": "observed_only_state_attribution",
        "screen_thresholds": {
            "min_cell_rows": scr.MIN_CELL_ROWS,
            "min_cell_windows": scr.MIN_CELL_WINDOWS,
            "min_positive_windows": scr.MIN_POSITIVE_WINDOWS,
            "edge_floor_vs_other_states": scr.ROUTER_CELL_FLOOR_EDGE,
            "ex_top_edge_floor": scr.ROUTER_CELL_FLOOR_EDGE,
            "min_ex_top_positive_windows": scr.MIN_EX_TOP_POSITIVE_WINDOWS,
            "max_top_ticker_positive_share": scr.MAX_TOP_TICKER_POSITIVE_SHARE,
        },
        "sample": {
            "total_rows_with_state": len(all_rows),
            "rows_by_sleeve": dict(
                sorted(Counter(r["sleeve"] for r in all_rows).items())
            ),
            "rows_by_state": dict(
                sorted(Counter(r["combined_state"] for r in all_rows).items())
            ),
            "unique_tickers": len({r["ticker"] for r in all_rows}),
            "cross_sleeve_duplicate_row_count": duplicate_rows,
            "cells_evaluated": len(cells),
        },
        "source_reports": source_reports,
        "router_candidates": survivors,
        "near_misses_single_check_failed": near_misses[:10],
        "all_cells_compact": [
            {
                "sleeve": c["sleeve"],
                "combined_state": c["combined_state"],
                "n": c["n"],
                "avg_pnl_pct": c["avg_pnl_pct"],
                "edge": c["edge_vs_other_states"],
                "ex_top_edge": c["ex_top_edge_vs_other_states"],
                "top_ticker": c["top_ticker"],
                "top_share": c["top_ticker_positive_share"],
                "positive_windows": c["positive_windows"],
                "screen_passed": c["screen"]["passed"],
            }
            for c in sorted(cells, key=lambda c: -(c["edge_vs_other_states"] or -9))
        ],
        "cross_reference": {
            "exp-20260613-005": (
                "Accepted cell industry_stable_core_flow x mixed|balanced|normal "
                "(allocator source family; not re-screened here)."
            ),
            "exp-20260612-027": "Screened the 7 allocator source families (disjoint scope).",
            "note": (
                "This run screens the 6 standalone accepted sleeves; consensus "
                "appears in both 027 and 606-022 and already fails ex-top on APP."
            ),
        },
        "production_impact": {
            "trade_enabled": False,
            "alters_orders": False,
            "shared_policy_changed": False,
            "replay_only": True,
            "diagnostic_only": True,
            "note": (
                "Read-only attribution over existing accepted sleeve artifacts; no "
                "candidate, notional, exit, or order behavior changed. Survivors "
                "justify only a separate frozen Gate 1-4 sleeve tilt experiment."
            ),
        },
        "multiple_testing_note": (
            f"{len(cells)} sleeve x state cells evaluated; the predeclared "
            "ex-top-ticker robustness screen plus observed-only status are the "
            "controls. Any survivor must be retested as a single frozen "
            "hypothesis (exp-20260613-005 template) before any allocation change."
        ),
        "anti_js": "No JavaScript was used.",
        "related_files": [
            "quant/experiments/exp_20260613_008_accepted_sleeve_ex_top_state_screen.py",
            "data/experiments/exp-20260613-008/exp_20260613_008_accepted_sleeve_ex_top_state_screen.json",
            "quant/experiments/exp_20260606_022_market_state_accepted_sleeve_replacement_value_attribution.py",
            "quant/experiments/exp_20260612_027_broad_state_source_attribution.py",
        ],
    }
    return _safe(payload)


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    stub = {
        "expected_value_score": 0.0,
        "total_pnl": 0.0,
        "note": "observed-only attribution; no strategy change, before==after by construction",
    }
    _write_json(BEFORE_AGG_JSON, stub)
    _write_json(AFTER_AGG_JSON, stub)
    print(json.dumps(payload["sample"], indent=2, sort_keys=True))
    print("source row coverage:")
    for r in payload["source_reports"]:
        print(f"  {r['sleeve']:45s} rows_with_state={r['rows_with_state']:4d} blocker={r['blocker']}")
    print(f"cells evaluated: {payload['sample']['cells_evaluated']}")
    print(f"router candidates (screen passed): {len(payload['router_candidates'])}")
    for c in payload["router_candidates"][:8]:
        print(
            f"  {c['sleeve']:42s} {c['combined_state']:38s} n={c['n']:3d} "
            f"edge={c['edge_vs_other_states']:+.4f} ex_top={c['ex_top_edge_vs_other_states']:+.4f} "
            f"top={c['top_ticker']}({c['top_ticker_positive_share']})"
        )
    print("near-misses (failed exactly 1 check):")
    for c in payload["near_misses_single_check_failed"][:6]:
        failed = [k for k, v in c["screen"]["checks"].items() if not v]
        print(
            f"  {c['sleeve']:42s} {c['combined_state']:30s} n={c['n']:3d} "
            f"edge={c['edge_vs_other_states']} ex_top={c['ex_top_edge_vs_other_states']} failed={failed}"
        )
    print(f"{EXPERIMENT_ID} {payload['decision']}")


if __name__ == "__main__":
    main()
