"""exp-20260612-027: broad-universe source x market-state attribution.

Observed-only (no strategy change). Reruns the exp-20260606-022 market-state
attribution on the WIDE sample the regime-router line was missing: all source
trades produced by the accepted helper source-priority allocator's eight
source families over the ~1237-ticker broad warehouse, across the three
canonical windows. The thin 20-ticker consensus-sleeve sample could not
separate regime effect from one name (APP, exp-20260612-018/020); this run
asks whether any source x state cell survives a predeclared ex-top-ticker
robustness screen.

Frozen semantics:
- state classifier: exp-20260606-022 `_state_for_entry_date`, evaluated on the
  canonical window snapshot files (same partial-SMA semantics), prior trading
  day close before paper entry;
- source trades: allocator_helper._build_source_trades with the exact inputs
  the accepted exp-20260611-005 allocator run used;
- no notional change, no selection change, no production change.

Multiple-testing posture: ~8 families x ~15 states are screened, so this run
is observed-only by construction. Survivors only justify a separate frozen
Gate 1-4 router experiment; they are not accepted alpha.

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


EXPERIMENT_ID = "exp-20260612-027"
STEM = "broad_state_source_attribution"
TRIAL_FAMILY = "market_state_conditioned_sleeve_router"
TRIAL_VARIANT_ID = "broad_source_state_attribution_ex_top_screen_v1"
CHANGED_VARIABLE = "broad_source_market_state_attribution_with_ex_top_ticker_screen"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENT_DIR / "legacy"
for path in (QUANT_DIR, EXPERIMENT_DIR, LEGACY_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260611_005_lagged_consensus_shared_allocator_source as allocexp  # noqa: E402
import exp_20260606_022_market_state_accepted_sleeve_replacement_value_attribution as statemod  # noqa: E402
import accepted_helper_source_priority_allocator_paper_sleeve as allocator_helper  # noqa: E402
from data_layer import get_universe  # noqa: E402

framework = allocexp.framework
exp008 = allocexp.exp008
WINDOWS = framework.WINDOWS
ROUTER_CELL_FLOOR_EDGE = 0.015
MIN_CELL_ROWS = 12
MIN_CELL_WINDOWS = 2
MIN_POSITIVE_WINDOWS = 2
MIN_EX_TOP_POSITIVE_WINDOWS = 2
MAX_TOP_TICKER_POSITIVE_SHARE = 0.50

OUT_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / f"exp_20260612_027_{STEM}.json"
)
BEFORE_AGG_JSON = OUT_JSON.parent / f"exp_20260612_027_{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_JSON.parent / f"exp_20260612_027_{STEM}_after_aggregate.json"

CANONICAL_SNAPSHOTS = {
    "late_strong": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    "mid_weak": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    "old_thin": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
}


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, set):
        return sorted(_safe(row) for row in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _pnl_pct(row: dict[str, Any]) -> float | None:
    for key in ("pnl_pct_net", "net_return_pct", "pnl_pct"):
        value = _float(row.get(key))
        if value is not None:
            return value
    pnl = _float(row.get("pnl"))
    notional = (
        _float(row.get("paper_notional_usd"))
        or _float(row.get("notional_usd"))
        or _float(row.get("notional"))
    )
    if pnl is not None and notional:
        return pnl / notional
    return None


def _entry_date(row: dict[str, Any], window_dates: list[str]) -> str | None:
    entry = str(row.get("entry_date") or "")[:10]
    if entry:
        return entry
    signal = str(row.get("signal_date") or row.get("date") or "")[:10]
    if not signal:
        return None
    for day in window_dates:
        if day > signal:
            return day
    return None


def _avg(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _positive_share_top_ticker(rows: list[dict[str, Any]]) -> tuple[str | None, float | None]:
    positive = [r for r in rows if (r["pnl_pct"] or 0.0) > 0]
    total = sum(r["pnl_pct"] for r in positive)
    if total <= 0:
        return None, None
    by_ticker: dict[str, float] = defaultdict(float)
    for r in positive:
        by_ticker[r["ticker"]] += r["pnl_pct"]
    top = max(by_ticker.items(), key=lambda kv: kv[1])
    return top[0], round(top[1] / total, 6)


def _cell_stats(cell_rows: list[dict[str, Any]], other_rows: list[dict[str, Any]]) -> dict[str, Any]:
    windows = sorted({r["window"] for r in cell_rows})
    per_window = {}
    positive_windows = 0
    for label in WINDOWS:
        sub = [r["pnl_pct"] for r in cell_rows if r["window"] == label]
        a = _avg(sub)
        per_window[label] = {"n": len(sub), "avg_pnl_pct": round(a, 6) if a is not None else None}
        if a is not None and a > 0:
            positive_windows += 1
    cell_avg = _avg([r["pnl_pct"] for r in cell_rows])
    other_avg = _avg([r["pnl_pct"] for r in other_rows])
    edge = (cell_avg - other_avg) if (cell_avg is not None and other_avg is not None) else None

    top_ticker, top_share = _positive_share_top_ticker(cell_rows)
    ex_top_cell = [r for r in cell_rows if r["ticker"] != top_ticker]
    ex_top_other = [r for r in other_rows if r["ticker"] != top_ticker]
    ex_top_avg = _avg([r["pnl_pct"] for r in ex_top_cell])
    ex_top_other_avg = _avg([r["pnl_pct"] for r in ex_top_other])
    ex_top_edge = (
        (ex_top_avg - ex_top_other_avg)
        if (ex_top_avg is not None and ex_top_other_avg is not None)
        else None
    )
    ex_top_positive_windows = 0
    for label in WINDOWS:
        sub = [r["pnl_pct"] for r in ex_top_cell if r["window"] == label]
        a = _avg(sub)
        if a is not None and a > 0:
            ex_top_positive_windows += 1

    return {
        "n": len(cell_rows),
        "windows_with_rows": windows,
        "avg_pnl_pct": round(cell_avg, 6) if cell_avg is not None else None,
        "win_rate": round(
            sum(1 for r in cell_rows if (r["pnl_pct"] or 0.0) > 0) / len(cell_rows), 4
        )
        if cell_rows
        else None,
        "per_window": per_window,
        "positive_windows": positive_windows,
        "same_source_other_states_n": len(other_rows),
        "same_source_other_states_avg_pnl_pct": round(other_avg, 6)
        if other_avg is not None
        else None,
        "edge_vs_other_states": round(edge, 6) if edge is not None else None,
        "top_ticker": top_ticker,
        "top_ticker_positive_share": top_share,
        "ex_top_n": len(ex_top_cell),
        "ex_top_avg_pnl_pct": round(ex_top_avg, 6) if ex_top_avg is not None else None,
        "ex_top_edge_vs_other_states": round(ex_top_edge, 6)
        if ex_top_edge is not None
        else None,
        "ex_top_positive_windows": ex_top_positive_windows,
        "unique_tickers": len({r["ticker"] for r in cell_rows}),
    }


def _screen(stats: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "cell_rows_min": stats["n"] >= MIN_CELL_ROWS,
        "cell_windows_min": len(stats["windows_with_rows"]) >= MIN_CELL_WINDOWS,
        "positive_windows_min": stats["positive_windows"] >= MIN_POSITIVE_WINDOWS,
        "edge_floor": (stats["edge_vs_other_states"] or -1) >= ROUTER_CELL_FLOOR_EDGE,
        "ex_top_edge_floor": (stats["ex_top_edge_vs_other_states"] or -1)
        >= ROUTER_CELL_FLOOR_EDGE,
        "ex_top_positive_windows_min": stats["ex_top_positive_windows"]
        >= MIN_EX_TOP_POSITIVE_WINDOWS,
        "top_ticker_share_max": (
            stats["top_ticker_positive_share"] is None
            or stats["top_ticker_positive_share"] <= MAX_TOP_TICKER_POSITIVE_SHARE
        ),
    }
    return {"passed": all(checks.values()), "checks": checks}


def build_payload() -> dict[str, Any]:
    universe = sorted(get_universe())
    sector_entries = framework._load_sector_entries()
    rows: list[dict[str, Any]] = []
    window_audit: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for label, cfg in WINDOWS.items():
        print(f"[{label}] building broad source trades + state annotation")
        before_result = framework.shadow._run_baseline(universe, cfg)
        core_entries = framework.shadow._baseline_entries(before_result)
        deep_snapshot = exp008._load_window_snapshot_deep(
            cfg=cfg,
            eligible_tickers=set(sector_entries),
        )
        window_sector_entries = {
            ticker: meta
            for ticker, meta in sector_entries.items()
            if ticker in deep_snapshot
        }
        candidate_universe = allocexp._candidate_universe_from_sector_entries(
            window_sector_entries
        )
        rows_by_ticker = allocator_helper.leader._normalise_ohlcv_by_ticker(deep_snapshot)
        sector_map = allocator_helper._sector_entries(
            sector_entries=window_sector_entries,
            candidate_universe=candidate_universe,
            rows_by_ticker=rows_by_ticker,
        )
        all_dates = allocator_helper._trading_dates(rows_by_ticker)
        dates = [d for d in all_dates if str(cfg["start"]) <= d <= str(cfg["end"])]
        source_trades, source_audit = allocator_helper._build_source_trades(
            rows_by_ticker=rows_by_ticker,
            dates=dates,
            window_label=label,
            window=cfg,
            core_entries_by_date=core_entries,
            sector_entries=sector_map,
            candidate_universe=candidate_universe,
            calendar_dates=all_dates,
        )
        selected, _filtered, _audit = allocator_helper.select_accepted_helper_source_priority_rows(
            source_rows=source_trades,
            trading_dates=dates,
            config=None,
            create_trades=True,
        )
        selected_keys = {
            (
                str(r.get("source_family") or ""),
                str(r.get("ticker") or "").upper(),
                str(r.get("signal_date") or "")[:10],
            )
            for r in selected
        }

        state_snapshot = statemod._load_snapshot(
            cfg.get("snapshot") or CANONICAL_SNAPSHOTS[label]
        )
        state_dates = statemod._trading_dates(state_snapshot)
        missing_state = 0
        missing_pnl = 0
        for trade in source_trades:
            ticker = str(trade.get("ticker") or "").upper()
            family = str(trade.get("source_family") or "unknown")
            pnl_pct = _pnl_pct(trade)
            entry = _entry_date(trade, state_dates)
            if pnl_pct is None:
                missing_pnl += 1
                continue
            state = (
                statemod._state_for_entry_date(
                    snapshot=state_snapshot,
                    trading_dates=state_dates,
                    entry_date=entry,
                )
                if entry
                else None
            )
            if not state or not state.get("combined_state"):
                missing_state += 1
                continue
            rows.append(
                {
                    "window": label,
                    "source_family": family,
                    "ticker": ticker,
                    "entry_date": entry,
                    "pnl_pct": float(pnl_pct),
                    "combined_state": str(state["combined_state"]),
                    "allocator_selected": (
                        family,
                        ticker,
                        str(trade.get("signal_date") or "")[:10],
                    )
                    in selected_keys,
                }
            )
        window_audit[label] = {
            "source_trade_counts": source_audit["source_trade_counts"],
            "allocator_selected_count": len(selected),
            "rows_with_state_and_pnl": sum(1 for r in rows if r["window"] == label),
            "missing_state_count": missing_state,
            "missing_pnl_count": missing_pnl,
            "deep_snapshot_ticker_count": len(deep_snapshot),
        }

    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_family[r["source_family"]].append(r)

    duplicate_groups = Counter(
        (r["ticker"], r["entry_date"]) for r in rows
    )
    duplicate_rows = sum(c for c in duplicate_groups.values() if c > 1)

    cells: list[dict[str, Any]] = []
    for family, frows in sorted(by_family.items()):
        states = sorted({r["combined_state"] for r in frows})
        for state in states:
            cell_rows = [r for r in frows if r["combined_state"] == state]
            if len(cell_rows) < 4:
                continue
            other_rows = [r for r in frows if r["combined_state"] != state]
            stats = _cell_stats(cell_rows, other_rows)
            screen = _screen(stats)
            cells.append(
                {
                    "source_family": family,
                    "combined_state": state,
                    **stats,
                    "screen": screen,
                }
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

    state_counts = Counter(r["combined_state"] for r in rows)
    family_counts = Counter(r["source_family"] for r in rows)

    decision = (
        "observed_only_router_candidates_found_requires_separate_gate_1_4"
        if survivors
        else "observed_only_no_cell_survives_ex_top_ticker_screen"
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
            "Broad-universe accepted allocator sources may contain market-state "
            "cells whose edge survives an ex-top-ticker robustness screen, "
            "identifying regime-router candidates the thin consensus-sleeve "
            "sample could not support."
        ),
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "change_type": "observed_only_state_attribution",
        "screen_thresholds": {
            "min_cell_rows": MIN_CELL_ROWS,
            "min_cell_windows": MIN_CELL_WINDOWS,
            "min_positive_windows": MIN_POSITIVE_WINDOWS,
            "edge_floor_vs_other_states": ROUTER_CELL_FLOOR_EDGE,
            "ex_top_edge_floor": ROUTER_CELL_FLOOR_EDGE,
            "min_ex_top_positive_windows": MIN_EX_TOP_POSITIVE_WINDOWS,
            "max_top_ticker_positive_share": MAX_TOP_TICKER_POSITIVE_SHARE,
        },
        "sample": {
            "total_rows_with_state_and_pnl": len(rows),
            "rows_by_source_family": dict(sorted(family_counts.items())),
            "rows_by_state": dict(sorted(state_counts.items())),
            "unique_tickers": len({r["ticker"] for r in rows}),
            "cross_source_duplicate_row_count": duplicate_rows,
            "cells_evaluated": len(cells),
        },
        "window_audit": window_audit,
        "router_candidates": survivors,
        "near_misses_single_check_failed": near_misses[:10],
        "all_cells_compact": [
            {
                "source_family": c["source_family"],
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
        "production_impact": {
            "trade_enabled": False,
            "alters_orders": False,
            "shared_policy_changed": False,
            "replay_only": True,
            "diagnostic_only": True,
            "note": (
                "Read-only attribution over existing accepted source replay "
                "machinery; no candidate, notional, exit, or order behavior "
                "changed. Survivors only justify a separate frozen Gate 1-4 "
                "router experiment."
            ),
        },
        "multiple_testing_note": (
            f"{len(cells)} source x state cells evaluated; the predeclared "
            "ex-top-ticker robustness screen plus observed-only status are the "
            "controls. Any survivor must be retested as a single frozen "
            "hypothesis with Gate 1-4 before any allocation change."
        ),
        "anti_js": "No JavaScript was used.",
        "related_files": [
            "quant/experiments/exp_20260612_027_broad_state_source_attribution.py",
            "data/experiments/exp-20260612-027/exp_20260612_027_broad_state_source_attribution.json",
            "quant/accepted_helper_source_priority_allocator_paper_sleeve.py",
            "quant/experiments/exp_20260606_022_market_state_accepted_sleeve_replacement_value_attribution.py",
        ],
    }
    return _safe(payload)


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    stub = {
        "expected_value_score": 0.0,
        "total_pnl": 0.0,
        "note": (
            "observed-only attribution; no strategy change, before==after by "
            "construction"
        ),
    }
    _write_json(BEFORE_AGG_JSON, stub)
    _write_json(AFTER_AGG_JSON, stub)
    print(json.dumps(payload["sample"], indent=2, sort_keys=True))
    print(f"cells evaluated: {payload['sample']['cells_evaluated']}")
    print(f"router candidates (screen passed): {len(payload['router_candidates'])}")
    for c in payload["router_candidates"][:8]:
        print(
            f"  {c['source_family']:35s} {c['combined_state']:40s} "
            f"n={c['n']:3d} edge={c['edge_vs_other_states']:+.4f} "
            f"ex_top_edge={c['ex_top_edge_vs_other_states']:+.4f} "
            f"top={c['top_ticker']}({c['top_ticker_positive_share']})"
        )
    print(f"{EXPERIMENT_ID} {payload['decision']}")


if __name__ == "__main__":
    main()
