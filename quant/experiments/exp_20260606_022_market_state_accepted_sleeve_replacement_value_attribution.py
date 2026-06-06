"""exp-20260606-022: market-state accepted-sleeve attribution.

Observed-only alpha discovery. This script labels accepted default-off paper
sleeve closed rows with market state known before paper entry and asks whether
state explains which sleeve has positive normalized realized value.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260606_021_market_state_family_replacement_value_attribution as state_lib  # noqa: E402
from regime_engine import classify_market_regime  # noqa: E402
from sentiment_surface import classify_sentiment_surface  # noqa: E402


EXPERIMENT_ID = "exp-20260606-022"
STEM = "market_state_accepted_sleeve_replacement_value_attribution"
TRIAL_FAMILY = "market_state_sleeve_replacement_value_attribution"
TRIAL_VARIANT_ID = "accepted_default_off_sleeve_state_attribution_v1"
CHANGED_VARIABLE = "market_state_accepted_sleeve_replacement_value_attribution_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260606_022_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

WINDOWS = state_lib.WINDOWS

MIN_TOTAL_ROWS_FOR_ROUTER = 150
MIN_SLEEVES_FOR_ROUTER = 5
MIN_SLEEVE_ROWS_FOR_ROUTER = 15
MIN_STATE_SLEEVE_ROWS_GLOBAL = 6
MIN_WINDOWS_WITH_STATE_SLEEVE = 2
MIN_STATE_SLEEVE_PNL_PER_10K_EDGE = 100.0

SLEEVE_SOURCES: list[dict[str, Any]] = [
    {
        "sleeve_id": "low_deployment_etf_cash_substitute",
        "accepted_adapter_id": "exp-20260606-001",
        "evidence_experiment_id": "exp-20260606-001",
        "artifact": "data/experiments/exp-20260606-001/exp_20260606_001_low_deployment_etf_cash_substitute_shared_adapter.json",
        "trade_key": "trades_by_window",
        "reason": "accepted default-off ETF cash substitute adapter",
    },
    {
        "sleeve_id": "macro_relief_stock_leadership",
        "accepted_adapter_id": "exp-20260606-020",
        "evidence_experiment_id": "exp-20260606-020",
        "artifact": "data/experiments/exp-20260606-020/exp_20260606_020_macro_relief_top2_shared_adapter.json",
        "trade_key": "target_trades_by_window",
        "reason": "accepted default-off macro relief stock leadership adapter",
    },
    {
        "sleeve_id": "lagged_independent_free_data_consensus",
        "accepted_adapter_id": "exp-20260604-009",
        "evidence_experiment_id": "exp-20260604-008",
        "artifact": "data/experiments/exp-20260604-008/lagged_independent_source_consensus.json",
        "trade_key": "target_trades_by_window",
        "reason": "accepted adapter uses this three-window evidence source",
    },
    {
        "sleeve_id": "sec_ftd_finra_confirmed",
        "accepted_adapter_id": "exp-20260604-027",
        "evidence_experiment_id": "exp-20260604-026",
        "artifact": "data/experiments/exp-20260604-026/exp_20260604_026_sec_ftd_finra_confirmed_candidate_pool.json",
        "trade_key": "target_trades_by_window",
        "reason": "accepted adapter uses this three-window evidence source",
    },
    {
        "sleeve_id": "finra_iwm_borrow_pressure",
        "accepted_adapter_id": "exp-20260603-007",
        "evidence_experiment_id": "exp-20260603-006",
        "artifact": "data/experiments/exp-20260603-006/exp_20260603_006_finra_borrow_pressure_candidate_pool.json",
        "trade_key": "target_trades_by_window",
        "reason": "accepted adapter uses this three-window evidence source",
    },
    {
        "sleeve_id": "post_earnings_underpriced_drift",
        "accepted_adapter_id": "exp-20260603-022",
        "evidence_experiment_id": "exp-20260603-022",
        "artifact": "data/experiments/exp-20260603-022/exp_20260603_022_post_earnings_non_core_overlap_shared_support.json",
        "trade_key": "target_trades_by_window",
        "reason": "latest accepted post-earnings underpriced drift support stack",
    },
]

EXCLUDED_ACCEPTED_SURFACES = {
    "state_surface_sleeve": (
        "Excluded from this run because its accepted stack already consumes "
        "market-state/profile fields; including it would make the state "
        "attribution partly circular."
    ),
}

PREDICTION = {
    "success_probability": 0.28,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "thin_state_sleeve_sample",
        "state_contrast_instability",
        "accepted_sleeve_overlap_duplicate_rows",
        "existing_state_surface_overlap",
        "no_router_justification",
    ],
    "confidence_reason": (
        "Core-only state attribution was too thin, but accepted default-off "
        "sleeve artifacts provide a wider production-visible paper outcome "
        "sample across independent mechanisms."
    ),
    "recorded_at": "2026-06-06T17:51:56Z",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "observed_only_no_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "diagnostic_only": True,
    "parity_note": (
        "This run reads accepted default-off paper sleeve artifacts and labels "
        "closed rows with market state known before paper entry. A positive "
        "result would require a separate frozen shared state router or paper "
        "allocation adapter with Gate 1-4 parity before any behavior changes."
    ),
}


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _safe(payload: Any) -> Any:
    return state_lib._safe(payload)


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _round(value: Any, digits: int = 6) -> float | None:
    return state_lib._round(value, digits)


def _load_json(path: str | Path) -> dict[str, Any]:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return json.loads(value.read_text(encoding="utf-8"))


def _state_for_date(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    state_date: str,
) -> dict[str, Any] | None:
    spy_rows = state_lib._series(snapshot, "SPY")
    qqq_rows = state_lib._series(snapshot, "QQQ")
    spy_idx = state_lib._row_index(spy_rows).get(state_date)
    qqq_idx = state_lib._row_index(qqq_rows).get(state_date)
    if spy_idx is None or qqq_idx is None:
        return None

    context = {
        "spy_pct_from_ma": state_lib._pct_from_sma(spy_rows, spy_idx, 200),
        "qqq_pct_from_ma": state_lib._pct_from_sma(qqq_rows, qqq_idx, 200),
        "spy_10d_return": state_lib._ret(spy_rows, spy_idx, 10),
        "qqq_10d_return": state_lib._ret(qqq_rows, qqq_idx, 10),
        "spy_20d_return": state_lib._ret(spy_rows, spy_idx, 20),
        "qqq_20d_return": state_lib._ret(qqq_rows, qqq_idx, 20),
        "theme_signal_count": 0,
        "breakout_signal_count": 0,
        "ai_signal_count": 0,
        "crypto_signal_count": 0,
        "space_signal_count": 0,
    }
    if context["qqq_20d_return"] is not None and context["spy_20d_return"] is not None:
        context["qqq_minus_spy_ret20"] = (
            float(context["qqq_20d_return"]) - float(context["spy_20d_return"])
        )
    else:
        context["qqq_minus_spy_ret20"] = None

    regime = classify_market_regime(context)
    sentiment = classify_sentiment_surface(context)
    buckets = state_lib._bucket_market_context(context)
    return {
        "state_date": state_date,
        "state_known_at": "signal_date_close_before_next_open_paper_entry",
        "regime": regime.get("regime"),
        "regime_confidence": regime.get("confidence"),
        "sentiment": sentiment.get("sentiment"),
        "sentiment_confidence": sentiment.get("confidence"),
        "sentiment_why": sentiment.get("why") or [],
        **buckets,
        "features": {
            key: _round(value)
            for key, value in context.items()
            if key
            in {
                "spy_pct_from_ma",
                "qqq_pct_from_ma",
                "spy_10d_return",
                "qqq_10d_return",
                "spy_20d_return",
                "qqq_20d_return",
                "qqq_minus_spy_ret20",
            }
        },
    }


def _state_for_trade(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    trading_dates: list[str],
    trade: dict[str, Any],
) -> dict[str, Any] | None:
    date_pos = {value: idx for idx, value in enumerate(trading_dates)}
    signal_date = str(trade.get("signal_date") or trade.get("date") or "")[:10]
    if signal_date in date_pos:
        return _state_for_date(snapshot=snapshot, state_date=signal_date)
    entry_date = str(trade.get("entry_date") or "")[:10]
    return state_lib._state_for_entry_date(
        snapshot=snapshot,
        trading_dates=trading_dates,
        entry_date=entry_date,
    )


def _trade_id(source: dict[str, Any], window: str, row: dict[str, Any]) -> str:
    return "|".join(
        [
            str(source["accepted_adapter_id"]),
            str(source["sleeve_id"]),
            window,
            str(row.get("signal_date") or row.get("date") or ""),
            str(row.get("entry_date") or ""),
            str(row.get("exit_date") or ""),
            str(row.get("ticker") or ""),
        ]
    )


def _normalize_trade(
    *,
    source: dict[str, Any],
    window: str,
    row: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    pnl = _round(row.get("pnl"), 10)
    if pnl is None:
        pnl = _round(row.get("paper_pnl"), 10)
    notional = _round(row.get("paper_notional_usd"), 10)
    pnl_per_10k = None
    if pnl is not None and notional is not None and notional > 0:
        pnl_per_10k = (float(pnl) / float(notional)) * 10000.0
    pnl_pct_net = _round(row.get("pnl_pct_net"), 10)
    if pnl_pct_net is None and pnl_per_10k is not None:
        pnl_pct_net = pnl_per_10k / 10000.0
    return {
        "trade_id": _trade_id(source, window, row),
        "accepted_adapter_id": source["accepted_adapter_id"],
        "evidence_experiment_id": source["evidence_experiment_id"],
        "sleeve_id": source["sleeve_id"],
        "source_artifact": source["artifact"],
        "window": window,
        "ticker": str(row.get("ticker") or "").upper(),
        "signal_date": str(row.get("signal_date") or row.get("date") or "")[:10],
        "entry_date": str(row.get("entry_date") or "")[:10],
        "exit_date": str(row.get("exit_date") or "")[:10],
        "entry_price": _round(row.get("entry_price"), 4),
        "exit_price": _round(row.get("exit_price"), 4),
        "paper_notional_usd": _round(notional, 2),
        "pnl": _round(pnl, 2),
        "pnl_pct_net": _round(pnl_pct_net, 6),
        "pnl_per_10k": _round(pnl_per_10k, 2),
        "trade_enabled": bool(row.get("trade_enabled", False)),
        "alters_orders": bool(row.get("alters_orders", False)),
        "source_names": row.get("source_names") or row.get("source") or row.get("strategy"),
        **state,
    }


def _load_all_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    snapshots = {
        label: state_lib._load_snapshot(cfg["snapshot"])
        for label, cfg in WINDOWS.items()
    }
    trading_dates = {
        label: state_lib._trading_dates(snapshot)
        for label, snapshot in snapshots.items()
    }
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    duplicate_ids: Counter[str] = Counter()
    source_summary: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for source in SLEEVE_SOURCES:
        payload = _load_json(source["artifact"])
        trade_block = payload.get(source["trade_key"]) or {}
        loaded = 0
        with_state = 0
        for window, trades in trade_block.items():
            if window not in WINDOWS:
                continue
            if not isinstance(trades, list):
                continue
            loaded += len(trades)
            for trade in trades:
                state = _state_for_trade(
                    snapshot=snapshots[window],
                    trading_dates=trading_dates[window],
                    trade=trade,
                )
                if state is None:
                    skipped.append(
                        {
                            "accepted_adapter_id": source["accepted_adapter_id"],
                            "sleeve_id": source["sleeve_id"],
                            "window": window,
                            "ticker": trade.get("ticker"),
                            "signal_date": trade.get("signal_date") or trade.get("date"),
                            "entry_date": trade.get("entry_date"),
                            "reason": "missing_market_state",
                        }
                    )
                    continue
                normalized = _normalize_trade(
                    source=source,
                    window=window,
                    row=trade,
                    state=state,
                )
                duplicate_ids[normalized["trade_id"]] += 1
                rows.append(normalized)
                with_state += 1
        source_summary[source["sleeve_id"]] = {
            "accepted_adapter_id": source["accepted_adapter_id"],
            "evidence_experiment_id": source["evidence_experiment_id"],
            "artifact": source["artifact"],
            "trade_key": source["trade_key"],
            "reason": source["reason"],
            "loaded_rows": loaded,
            "rows_with_state": with_state,
            "state_coverage_rate": _round(with_state / loaded, 4) if loaded else None,
        }

    duplicate_trade_ids = {
        trade_id: count
        for trade_id, count in duplicate_ids.items()
        if count > 1
    }
    return rows, {
        "source_summary": source_summary,
        "skipped_rows": skipped[:100],
        "skipped_count": len(skipped),
        "duplicate_trade_ids": duplicate_trade_ids,
        "duplicate_trade_id_count": len(duplicate_trade_ids),
        "excluded_accepted_surfaces": EXCLUDED_ACCEPTED_SURFACES,
    }


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnl_values = [float(value) for value in (_round(row.get("pnl"), 10) for row in rows) if value is not None]
    pnl_per_10k = [float(value) for value in (_round(row.get("pnl_per_10k"), 10) for row in rows) if value is not None]
    pct_values = [float(value) for value in (_round(row.get("pnl_pct_net"), 10) for row in rows) if value is not None]
    tickers = Counter(row.get("ticker") for row in rows if row.get("ticker"))
    windows = Counter(row.get("window") for row in rows if row.get("window"))
    sleeves = Counter(row.get("sleeve_id") for row in rows if row.get("sleeve_id"))
    if not rows:
        return {
            "trades": 0,
            "win_rate": None,
            "total_pnl": 0.0,
            "avg_pnl": None,
            "avg_pnl_per_10k": None,
            "median_pnl_per_10k": None,
            "avg_pnl_pct_net": None,
            "median_pnl_pct_net": None,
            "unique_tickers": 0,
            "windows": {},
            "sleeves": {},
        }
    return {
        "trades": len(rows),
        "win_rate": _round(sum(1 for value in pnl_values if value > 0) / len(pnl_values), 4) if pnl_values else None,
        "total_pnl": _round(sum(pnl_values), 2) if pnl_values else 0.0,
        "avg_pnl": _round(mean(pnl_values), 2) if pnl_values else None,
        "median_pnl": _round(median(pnl_values), 2) if pnl_values else None,
        "avg_pnl_per_10k": _round(mean(pnl_per_10k), 2) if pnl_per_10k else None,
        "median_pnl_per_10k": _round(median(pnl_per_10k), 2) if pnl_per_10k else None,
        "avg_pnl_pct_net": _round(mean(pct_values), 6) if pct_values else None,
        "median_pnl_pct_net": _round(median(pct_values), 6) if pct_values else None,
        "worst_pnl_per_10k": _round(min(pnl_per_10k), 2) if pnl_per_10k else None,
        "best_pnl_per_10k": _round(max(pnl_per_10k), 2) if pnl_per_10k else None,
        "unique_tickers": len(tickers),
        "top_tickers": tickers.most_common(10),
        "windows": dict(sorted(windows.items())),
        "sleeves": dict(sorted(sleeves.items())),
    }


def _group_summary(rows: list[dict[str, Any]], keys: list[str]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = "|".join(str(row.get(part) or "unknown") for part in keys)
        grouped[key].append(row)
    return {
        key: _summarize_rows(value)
        for key, value in sorted(grouped.items(), key=lambda item: item[0])
    }


def _router_readiness(rows: list[dict[str, Any]], diagnostics: dict[str, Any]) -> dict[str, Any]:
    total_rows = len(rows)
    sleeve_counts = Counter(row["sleeve_id"] for row in rows)
    state_counts = Counter(row["combined_state"] for row in rows)
    sleeve_state_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        sleeve_state_counts[row["sleeve_id"]][row["combined_state"]] += 1

    failed: list[str] = []
    if total_rows < MIN_TOTAL_ROWS_FOR_ROUTER:
        failed.append("accepted_sleeve_sample_below_router_minimum")
    if len(sleeve_counts) < MIN_SLEEVES_FOR_ROUTER:
        failed.append("sleeve_count_below_router_minimum")
    if sum(1 for count in sleeve_counts.values() if count >= MIN_SLEEVE_ROWS_FOR_ROUTER) < MIN_SLEEVES_FOR_ROUTER:
        failed.append("too_few_sleeves_have_minimum_sample")
    if diagnostics.get("duplicate_trade_id_count"):
        failed.append("duplicate_trade_ids_detected")

    sleeves_with_state_contrast = sum(
        1
        for counts in sleeve_state_counts.values()
        if sum(1 for count in counts.values() if count >= MIN_STATE_SLEEVE_ROWS_GLOBAL) >= 2
    )
    if sleeves_with_state_contrast < 1:
        failed.append("state_contrast_sample_too_small")

    global_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_window_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (row["sleeve_id"], row["combined_state"])
        global_groups[key].append(row)
        by_window_groups[(row["window"], *key)].append(row)

    candidates: list[dict[str, Any]] = []
    for (sleeve_id, state), group_rows in sorted(global_groups.items()):
        if len(group_rows) < MIN_STATE_SLEEVE_ROWS_GLOBAL:
            continue
        comparator_rows = [
            row
            for row in rows
            if row["sleeve_id"] == sleeve_id and row["combined_state"] != state
        ]
        if len(comparator_rows) < MIN_STATE_SLEEVE_ROWS_GLOBAL:
            continue
        global_summary = _summarize_rows(group_rows)
        comparator_summary = _summarize_rows(comparator_rows)
        edge = None
        if (
            global_summary.get("avg_pnl_per_10k") is not None
            and comparator_summary.get("avg_pnl_per_10k") is not None
        ):
            edge = float(global_summary["avg_pnl_per_10k"]) - float(
                comparator_summary["avg_pnl_per_10k"]
            )
        window_summaries = {
            window: _summarize_rows(window_rows)
            for (window, group_sleeve, group_state), window_rows in by_window_groups.items()
            if group_sleeve == sleeve_id and group_state == state
        }
        positive_windows = sum(
            1
            for summary in window_summaries.values()
            if summary.get("avg_pnl_per_10k") is not None
            and summary["avg_pnl_per_10k"] > 0
        )
        windows_with_sample = sum(
            1 for summary in window_summaries.values() if summary.get("trades", 0) > 0
        )
        if (
            global_summary.get("avg_pnl_per_10k") is not None
            and global_summary["avg_pnl_per_10k"] > 0
            and edge is not None
            and edge >= MIN_STATE_SLEEVE_PNL_PER_10K_EDGE
            and windows_with_sample >= MIN_WINDOWS_WITH_STATE_SLEEVE
            and positive_windows >= MIN_WINDOWS_WITH_STATE_SLEEVE
        ):
            candidates.append(
                {
                    "sleeve_id": sleeve_id,
                    "combined_state": state,
                    "global": global_summary,
                    "same_sleeve_other_states": comparator_summary,
                    "edge_vs_same_sleeve_other_states_avg_pnl_per_10k": _round(edge, 2),
                    "windows_with_sample": windows_with_sample,
                    "positive_windows": positive_windows,
                    "window_summaries": window_summaries,
                }
            )

    candidates.sort(
        key=lambda row: (
            -float(row["edge_vs_same_sleeve_other_states_avg_pnl_per_10k"] or 0.0),
            -float(row["global"].get("avg_pnl_per_10k") or 0.0),
            -int(row["global"].get("trades") or 0),
            row["sleeve_id"],
        )
    )
    if not candidates:
        failed.append("no_stable_positive_state_sleeve_candidate")
    ready = not failed
    return {
        "ready_for_router_gate": ready,
        "decision": (
            "observed_only_sleeve_state_router_candidate_requires_frozen_gate_1_4"
            if ready
            else "observed_only_no_sleeve_router_yet_state_sample_thin_or_unstable"
        ),
        "failed_reasons": failed,
        "thresholds": {
            "min_total_rows_for_router": MIN_TOTAL_ROWS_FOR_ROUTER,
            "min_sleeves_for_router": MIN_SLEEVES_FOR_ROUTER,
            "min_sleeve_rows_for_router": MIN_SLEEVE_ROWS_FOR_ROUTER,
            "min_state_sleeve_rows_global": MIN_STATE_SLEEVE_ROWS_GLOBAL,
            "min_windows_with_state_sleeve": MIN_WINDOWS_WITH_STATE_SLEEVE,
            "min_state_sleeve_pnl_per_10k_edge": MIN_STATE_SLEEVE_PNL_PER_10K_EDGE,
        },
        "total_rows": total_rows,
        "sleeve_counts": dict(sorted(sleeve_counts.items())),
        "state_counts": dict(sorted(state_counts.items())),
        "sleeve_state_counts": {
            sleeve: dict(sorted(counts.items()))
            for sleeve, counts in sorted(sleeve_state_counts.items())
        },
        "sleeves_with_state_contrast": sleeves_with_state_contrast,
        "candidate_count": len(candidates),
        "top_candidates": candidates[:12],
    }


def _build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    rows, diagnostics = _load_all_rows()
    readiness = _router_readiness(rows, diagnostics)
    decision = readiness["decision"]
    if readiness["ready_for_router_gate"]:
        interpretation = (
            "Accepted-sleeve observed-only attribution found state/sleeve "
            "cells with enough contrast to justify a separate frozen Gate 1-4 "
            "router experiment. No router is enabled in this run."
        )
    else:
        interpretation = (
            "Accepted-sleeve observed-only attribution does not yet justify a "
            "state-conditioned sleeve router. The sample is wider than core, "
            "but state contrast within individual sleeves remains too thin or "
            "unstable."
        )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_discovery",
        "status": "observed_only",
        "decision": decision,
        "accepted": False,
        "diagnostic_only": True,
        "hypothesis": (
            "Accepted default-off paper sleeve outcomes may show stable "
            "market-state-by-sleeve realized value, enabling a later frozen "
            "state-conditioned sleeve router without touching live orders now."
        ),
        "change_type": "read_only_market_state_accepted_sleeve_attribution",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "market_state_sleeve_replacement_value_prediction",
        "new_evidence_type": "accepted_default_off_sleeve_state_replacement_value_attribution",
        "nearby_prior_experiments": [
            "exp-20260606-021",
            "exp-20260606-001",
            "exp-20260606-020",
            "exp-20260604-009",
            "exp-20260604-027",
            "exp-20260603-007",
            "exp-20260603-022",
        ],
        "prior_trial_count": 1,
        "multiple_testing_risk_bucket": "moderate",
        "prediction": PREDICTION,
        "production_impact": PRODUCTION_IMPACT,
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three fixed windows; accepted sleeve artifacts only",
            "windows": WINDOWS,
            "state_timing": "signal_date_close_before_next_open_paper_entry",
            "input_artifacts": SLEEVE_SOURCES,
            "baseline_result_file": (
                "data/experiments/exp-20260602-003/"
                "exp_20260602_003_post_earnings_explicit_continuation.json"
            ),
            "normalization": (
                "Cross-sleeve value uses pnl_per_10k so ETF $100k paper rows "
                "are comparable with $4k/$10k paper sleeves."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "ranking/risk allocation precursor: market state may select "
                "which accepted default-off paper sleeve deserves capital."
            ),
            "2_history_check": (
                "exp-20260606-021 showed core-only state attribution was too "
                "thin. This run expands sample to accepted default-off paper "
                "sleeves while excluding state_surface_sleeve to avoid circular "
                "market-state attribution."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Observed-only: require enough accepted sleeve rows, enough "
                "sleeves, duplicate-free inputs, and stable same-sleeve "
                "state contrast before a separate frozen Gate 1-4 router "
                "experiment. This run cannot be accepted as production alpha."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260606_022_market_state_accepted_sleeve_replacement_value_attribution.py"
            ),
        },
        "input_diagnostics": diagnostics,
        "aggregate_summary": _summarize_rows(rows),
        "summary_by_sleeve": _group_summary(rows, ["sleeve_id"]),
        "summary_by_state": _group_summary(rows, ["combined_state"]),
        "summary_by_sentiment": _group_summary(rows, ["sentiment"]),
        "summary_by_sleeve_and_state": _group_summary(rows, ["sleeve_id", "combined_state"]),
        "summary_by_sleeve_and_sentiment": _group_summary(rows, ["sleeve_id", "sentiment"]),
        "summary_by_window_and_sleeve": _group_summary(rows, ["window", "sleeve_id"]),
        "router_readiness": readiness,
        "sample_rows": rows[:120],
        "interpretation": interpretation,
        "negative_reflection": (
            "If this remains no-router, the blocker is not implementation: "
            "accepted default-off sleeves still lack enough within-sleeve "
            "state contrast. The next credible step is forward replacement "
            "rows or a broader accepted-sleeve ledger, not fitting a router "
            "from sparse state cells."
        ),
        "next_experiment_hint": (
            "If router_readiness is false, build a forward/ledger collector "
            "that stores state labels on every accepted default-off paper "
            "decision row. If true, freeze the candidate cells and run a "
            "separate Gate 1-4 state-conditioned sleeve allocation experiment."
        ),
        "anti_js": "No JavaScript was used.",
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
    }


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_discovery",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "diagnostic_only": True,
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": payload["backtest_protocol"]["baseline_result_file"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "aggregate_summary": payload["aggregate_summary"],
        "router_readiness": payload["router_readiness"],
        "input_diagnostics": payload["input_diagnostics"],
        "prediction": PREDICTION,
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_gate4_passed": False,
            "failure_modes_observed": payload["router_readiness"]["failed_reasons"],
        },
        "production_impact": PRODUCTION_IMPACT,
        "negative_reflection": payload["negative_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _format_state(value: str) -> str:
    return str(value).replace("|", "/")


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Sleeve | Rows | Avg / $10k | Win Rate | Top State |",
        "|---|---:|---:|---:|---|",
    ]
    for sleeve, summary in payload["summary_by_sleeve"].items():
        sleeve_rows = [
            row for row in payload["sample_rows"] if row.get("sleeve_id") == sleeve
        ]
        top_state = "n/a"
        state_counts = payload["router_readiness"]["sleeve_state_counts"].get(sleeve, {})
        if state_counts:
            top_state = max(state_counts.items(), key=lambda item: item[1])[0]
        rows.append(
            "| {sleeve} | {trades} | ${avg:,.2f} | {wr:.2%} | {state} |".format(
                sleeve=sleeve,
                trades=int(summary.get("trades") or 0),
                avg=float(summary.get("avg_pnl_per_10k") or 0.0),
                wr=float(summary.get("win_rate") or 0.0),
                state=_format_state(top_state),
            )
        )

    readiness = payload["router_readiness"]
    top_candidates = readiness["top_candidates"][:5]
    candidate_lines = []
    if top_candidates:
        for row in top_candidates:
            candidate_lines.append(
                "- `{}` in `{}`: avg_per_10k `${:,.2f}`, edge `${:,.2f}`, trades `{}`".format(
                    row["sleeve_id"],
                    _format_state(row["combined_state"]),
                    float(row["global"].get("avg_pnl_per_10k") or 0.0),
                    float(row.get("edge_vs_same_sleeve_other_states_avg_pnl_per_10k") or 0.0),
                    int(row["global"].get("trades") or 0),
                )
            )
    else:
        candidate_lines.append("- none")

    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Market-State Accepted-Sleeve Attribution",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Accepted Sleeve Rows",
            "",
            *rows,
            "",
            "## Router Readiness",
            "",
            f"- Ready for router Gate 1-4: `{readiness['ready_for_router_gate']}`",
            f"- Failed reasons: `{', '.join(readiness['failed_reasons']) or 'none'}`",
            f"- Total rows with state: `{readiness['total_rows']}`",
            f"- Sleeve count: `{len(readiness['sleeve_counts'])}`",
            f"- Candidate state-sleeve cells: `{readiness['candidate_count']}`",
            "",
            "## Candidate Cells",
            "",
            *candidate_lines,
            "",
            "## Conclusion",
            "",
            payload["interpretation"],
            "",
            "## Production Impact",
            "",
            (
                "Observed-only. No shared policy, run adapter, backtester adapter, "
                "watchlist, order path, entry, ranking, sizing, or exit behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _update_ticket_and_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8")) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "result": {
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "accepted": False,
                "diagnostic_only": True,
                "aggregate_expected_value_delta": 0.0,
                "aggregate_strategy_total_pnl_delta": 0.0,
                "router_readiness": payload["router_readiness"],
                "aggregate_summary": payload["aggregate_summary"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)

    if REGISTRY_JSON.exists():
        registry = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    else:
        registry = {"schema_version": 1, "experiments": []}
    experiments = registry.setdefault("experiments", [])
    for row in experiments:
        if row.get("experiment_id") != EXPERIMENT_ID:
            continue
        row.update(
            {
                "status": payload["status"],
                "completed_at": payload["timestamp"],
                "updated_at": payload["timestamp"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "decision": payload["decision"],
                "aggregate_expected_value_delta": 0.0,
                "aggregate_strategy_total_pnl_delta": 0.0,
            }
        )
        break
    registry["updated_at"] = payload["timestamp"]
    REGISTRY_JSON.write_text(
        json.dumps(_safe(registry), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): _sha256(Path(__file__)),
            _repo_rel(OUT_JSON): _sha256(OUT_JSON),
            _repo_rel(LOG_JSON): _sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): _sha256(TICKET_JSON),
            _repo_rel(CARD_MD): _sha256(CARD_MD),
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _build_card(payload))
    _upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    persist(payload)
    print(json.dumps(_safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
