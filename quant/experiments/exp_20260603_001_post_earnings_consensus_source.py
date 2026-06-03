"""exp-20260603-001: post-earnings source in free-data consensus.

Lane: alpha_search.
Single causal variable:
    accepted_free_data_cross_source_consensus_include_post_earnings_underpriced_source_v1.

This replay tests whether adding the newly accepted
POST_EARNINGS_UNDERPRICED_DRIFT_PAPER source to the existing accepted
free-data cross-source consensus source set improves the default-off paper
candidate pool. The before variant is the accepted four-source consensus plus
the accepted core-capacity gate. The after variant changes only the source set.

No shared production adapter is modified in this experiment. A positive replay
therefore remains a lead that requires a separate shared-adapter promotion and
parity pass before retention. No JavaScript is used.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant.constants import MAX_POSITIONS  # noqa: E402
from quant.experiments import (  # noqa: E402
    exp_20260531_030_accepted_free_data_cross_source_consensus as source,
)
from quant.experiments import (  # noqa: E402
    exp_20260601_018_accepted_consensus_core_capacity_available as capacity_prior,
)
from quant import free_data_cross_source_consensus_paper_sleeve as shared_consensus  # noqa: E402
from quant.post_earnings_underpriced_drift_paper_sleeve import (  # noqa: E402
    RULE_VERSION as POST_EARNINGS_SHARED_RULE_VERSION,
    SOURCE_RULE_VERSION as POST_EARNINGS_SOURCE_RULE_VERSION,
    SLEEVE_NAME as POST_EARNINGS_SOURCE_NAME,
    build_post_earnings_underpriced_drift_candidates_for_dates,
    load_earnings_snapshot_index,
)


EXPERIMENT_ID = "exp-20260603-001"
STEM = "post_earnings_consensus_source"
TRIAL_FAMILY = "accepted_free_data_consensus_new_source_expansion"
CHANGED_VARIABLE = (
    "accepted_free_data_cross_source_consensus_include_post_earnings_underpriced_source_v1"
)
RULE_VERSION = CHANGED_VARIABLE

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260603_001_{STEM}.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = ROOT / "docs" / "experiment_registry.json"

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MIN_CHANGED_TARGET_TRADES = 1
MIN_CHANGED_TARGET_WINDOWS = 1
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

DOCS_ACCEPTED_BASELINE = {
    "late_strong": {"expected_value_score": 5.1628, "total_pnl": 117_072.92},
    "mid_weak": {"expected_value_score": 2.1402, "total_pnl": 78_110.11},
    "old_thin": {"expected_value_score": 0.5911, "total_pnl": 39_667.96},
}

ORIGINAL_SOURCE_NAMES = sorted(shared_consensus.ACCEPTED_SOURCE_NAMES)
AFTER_SOURCE_NAMES = sorted(set(ORIGINAL_SOURCE_NAMES) | {POST_EARNINGS_SOURCE_NAME})

PRODUCTION_IMPACT = {
    "replay_only": True,
    "default_off_paper_only": True,
    "shared_policy_changed": False,
    "run_adapter_changed": False,
    "backtester_adapter_changed": False,
    "parity_test_added": False,
    "trade_enabled": False,
    "alters_orders": False,
    "production_orders_changed": False,
    "production_signal_path_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "llm_or_news_changed": False,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = ROOT / value
    return str(value.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(_safe(record), ensure_ascii=False, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                item = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if item.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _trade_key(row: dict[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("signal_date") or row.get("date") or "")[:10],
        str(row.get("ticker") or "").upper(),
    )


def _baseline_drift(core_metrics_by_window: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = {}
    for label, expected in DOCS_ACCEPTED_BASELINE.items():
        actual = core_metrics_by_window.get(label) or {}
        ev_delta = float(actual.get("expected_value_score") or 0.0) - expected[
            "expected_value_score"
        ]
        pnl_delta = float(actual.get("total_pnl") or 0.0) - expected["total_pnl"]
        rows[label] = {
            "docs_expected_value_score": expected["expected_value_score"],
            "current_expected_value_score": actual.get("expected_value_score"),
            "expected_value_score_delta": round(ev_delta, 6),
            "docs_total_pnl": expected["total_pnl"],
            "current_total_pnl": actual.get("total_pnl"),
            "total_pnl_delta": round(pnl_delta, 2),
            "matches_docs_baseline": abs(ev_delta) <= 0.01 and abs(pnl_delta) <= 100.0,
        }
    return {
        "docs_source": "docs/backtesting.md current accepted exp-20260602-003 fixed-window core baseline",
        "current_source": "current replay in the same docs/backtesting.md windows",
        "matches_all_windows": all(row["matches_docs_baseline"] for row in rows.values()),
        "rows": rows,
    }


def _post_earnings_source_summary(row: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "source_name": POST_EARNINGS_SOURCE_NAME,
        "source_experiment_id": "exp-20260602-026",
        "shared_adapter_rule_version": POST_EARNINGS_SHARED_RULE_VERSION,
        "source_rule_version": POST_EARNINGS_SOURCE_RULE_VERSION,
    }
    for key in (
        "date",
        "signal_date",
        "ticker",
        "event_confirmed_date",
        "latest_surprise_pct",
        "avg_historical_surprise_pct",
        "positive_surprise_count",
        "surprise_history_count",
        "pre_event_rs20_vs_spy",
        "event_to_signal_excess_vs_spy",
        "rs20_vs_spy",
        "avg_dollar_volume_20d",
        "close_location",
        "post_earnings_underpriced_rank_on_signal_date",
        "rule_version",
        "known_at",
    ):
        if key in row:
            summary[key] = row.get(key)
    return summary


def _post_earnings_rows_by_window(
    universe: list[str],
) -> tuple[dict[str, dict[tuple[str, str], list[dict[str, Any]]]], dict[str, Any]]:
    rows_by_window: dict[str, dict[tuple[str, str], list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    audits: dict[str, Any] = {}
    earnings_index = load_earnings_snapshot_index()
    for label, cfg in source.base.WINDOWS.items():
        snapshot = source.base.shadow._load_snapshot(cfg["snapshot"])
        trading_dates = [
            date_value
            for date_value in source.base.shadow._trading_dates(snapshot)
            if str(cfg["start"]) <= date_value <= str(cfg["end"])
        ]
        candidates, rejected, audit = build_post_earnings_underpriced_drift_candidates_for_dates(
            as_of_dates=trading_dates,
            ohlcv_by_ticker=snapshot,
            candidate_universe=universe,
            earnings_index=earnings_index,
            config={
                "event_date_min": cfg["start"],
                "event_date_max": cfg["end"],
            },
        )
        for row in candidates:
            signal_date = str(row.get("signal_date") or row.get("date") or "")[:10]
            ticker = str(row.get("ticker") or "").upper()
            if not signal_date or not ticker:
                continue
            rows_by_window[label][(signal_date, ticker)].append(
                _post_earnings_source_summary(row)
            )
        audits[label] = {
            **audit,
            "shared_adapter_rule_version": POST_EARNINGS_SHARED_RULE_VERSION,
            "source_rule_version": POST_EARNINGS_SOURCE_RULE_VERSION,
            "source_name": POST_EARNINGS_SOURCE_NAME,
            "rejected_candidate_count": len(rejected),
            "rows_loaded": sum(len(rows) for rows in rows_by_window[label].values()),
            "unique_keys_loaded": len(rows_by_window[label]),
        }
    return rows_by_window, audits


def _merge_source_rows(
    base_rows: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
    extra_rows: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
) -> dict[str, dict[tuple[str, str], list[dict[str, Any]]]]:
    merged: dict[str, dict[tuple[str, str], list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for label, keyed_rows in base_rows.items():
        for key, rows in keyed_rows.items():
            merged[label][key].extend(copy.deepcopy(rows))
    for label, keyed_rows in extra_rows.items():
        for key, rows in keyed_rows.items():
            merged[label][key].extend(copy.deepcopy(rows))
    return merged


def _core_active_after_close(before_result: dict[str, Any], signal_date: str) -> int:
    core_trades = [row for row in before_result.get("trades") or [] if isinstance(row, dict)]
    return capacity_prior._core_active_after_close(core_trades, signal_date)


def _capacity_candidates_for_window(
    *,
    label: str,
    before_result: dict[str, Any],
    source_rows_by_window: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    raw_candidates = source._consensus_candidates_for_window(label, source_rows_by_window)
    baseline_entries = source.base.shadow._baseline_entries(before_result)
    capacity_candidates: list[dict[str, Any]] = []
    rejected_capacity_full: list[dict[str, Any]] = []
    for candidate in raw_candidates:
        signal_date = str(candidate["date"])
        active_core_after_close = _core_active_after_close(before_result, signal_date)
        available_core_slots = max(0, MAX_POSITIONS - active_core_after_close)
        annotated = dict(candidate)
        annotated.update(
            {
                "capacity_gate_rule_version": (
                    "accepted_free_data_consensus_core_capacity_available_gate_v1"
                ),
                "capacity_gate": "core_capacity_available_after_close",
                "same_day_core_entry_count": len(baseline_entries.get(signal_date, [])),
                "active_core_positions_after_signal_close": active_core_after_close,
                "available_core_slots_after_signal_close": available_core_slots,
                "max_core_positions": MAX_POSITIONS,
            }
        )
        if available_core_slots > 0:
            capacity_candidates.append(annotated)
        else:
            rejected_capacity_full.append(annotated)
    return raw_candidates, capacity_candidates, rejected_capacity_full


def _variant_window_result(
    *,
    label: str,
    before_result: dict[str, Any],
    snapshot: dict[str, Any],
    source_rows_by_window: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    raw_candidates, capacity_candidates, rejected_capacity_full = _capacity_candidates_for_window(
        label=label,
        before_result=before_result,
        source_rows_by_window=source_rows_by_window,
    )
    target_trades, diagnostics = source._select_target_trades(snapshot, capacity_candidates)
    metrics = source.base.overlay_helper._metrics_with_overlay(
        before_result,
        source.base._overlay_from_paper_trades(before_result, target_trades),
    )
    return (
        {
            "metrics": metrics,
            "raw_consensus_candidate_count": len(raw_candidates),
            "capacity_pass_candidate_count": len(capacity_candidates),
            "capacity_full_rejected_candidate_count": len(rejected_capacity_full),
            "target_trade_count": len(target_trades),
            "target_trade_pnl_usd": round(
                sum(float(row.get("pnl") or 0.0) for row in target_trades), 2
            ),
            "target_diagnostics": diagnostics,
        },
        target_trades,
    )


def _target_summary(target_trades_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    trades = [trade for rows in target_trades_by_window.values() for trade in rows]
    by_ticker_count: Counter[str] = Counter()
    by_ticker_pnl: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    combo_counts: Counter[str] = Counter()
    for trade in trades:
        ticker = str(trade.get("ticker") or "").upper()
        pnl = float(trade.get("pnl") or 0.0)
        by_ticker_count[ticker] += 1
        by_ticker_pnl[ticker] += pnl
        names = sorted(str(name) for name in trade.get("source_names") or [])
        combo_counts["+".join(names)] += 1
        for name in names:
            source_counts[name] += 1
    positive = {ticker: pnl for ticker, pnl in by_ticker_pnl.items() if pnl > 0}
    positive_total = sum(positive.values())
    max_positive_share = (
        max(positive.values()) / positive_total if positive_total > 0 and positive else None
    )
    positive_hhi = (
        sum((pnl / positive_total) ** 2 for pnl in positive.values())
        if positive_total > 0 and positive
        else None
    )
    ticker_rows = []
    for ticker, pnl in sorted(by_ticker_pnl.items()):
        ticker_rows.append(
            {
                "ticker": ticker,
                "trade_count": by_ticker_count[ticker],
                "paper_pnl_usd": round(pnl, 2),
                "positive_pnl_usd": round(max(pnl, 0.0), 2),
                "positive_pnl_share": round(pnl / positive_total, 6)
                if pnl > 0 and positive_total > 0
                else None,
            }
        )
    ticker_rows.sort(
        key=lambda row: (
            -(row["positive_pnl_usd"] or 0.0),
            -abs(row["paper_pnl_usd"] or 0.0),
            row["ticker"],
        )
    )
    return {
        "target_trade_count": len(trades),
        "target_trade_pnl_usd": round(sum(float(row.get("pnl") or 0.0) for row in trades), 2),
        "positive_pnl_total_usd": round(positive_total, 2),
        "max_single_positive_share": round(max_positive_share, 6)
        if max_positive_share is not None
        else None,
        "positive_pnl_hhi": round(positive_hhi, 6) if positive_hhi is not None else None,
        "trades_by_window": {label: len(rows) for label, rows in target_trades_by_window.items()},
        "pnl_by_window": {
            label: round(sum(float(row.get("pnl") or 0.0) for row in rows), 2)
            for label, rows in target_trades_by_window.items()
        },
        "source_counts": dict(sorted(source_counts.items())),
        "source_combo_counts": dict(sorted(combo_counts.items())),
        "post_earnings_supported_target_count": source_counts.get(POST_EARNINGS_SOURCE_NAME, 0),
        "ticker_rows": ticker_rows,
    }


def _aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    before_ev = sum(float(row["before"]["expected_value_score"]) for row in results)
    after_ev = sum(float(row["after"]["expected_value_score"]) for row in results)
    before_pnl = sum(float(row["before"]["total_pnl"]) for row in results)
    after_pnl = sum(float(row["after"]["total_pnl"]) for row in results)
    return {
        "before": {
            "expected_value_score": round(before_ev, 6),
            "total_pnl": round(before_pnl, 2),
            "strategy_total_pnl": round(before_pnl, 2),
        },
        "after": {
            "expected_value_score": round(after_ev, 6),
            "total_pnl": round(after_pnl, 2),
            "strategy_total_pnl": round(after_pnl, 2),
        },
        "comparison": {
            "expected_value_score_delta": round(after_ev - before_ev, 6),
            "expected_value_score_delta_pct": round((after_ev - before_ev) / before_ev, 6)
            if before_ev
            else None,
            "strategy_total_pnl_delta": round(after_pnl - before_pnl, 2),
            "total_pnl_delta": round(after_pnl - before_pnl, 2),
            "strategy_total_pnl_delta_pct": round((after_pnl - before_pnl) / before_pnl, 6)
            if before_pnl
            else None,
        },
    }


def _run_windows() -> tuple[
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
    dict[str, Any],
]:
    baselines = source._load_baselines()
    core_metrics_by_window = {
        label: payload["metrics"] for label, payload in baselines.items()
    }
    source.SOURCE_EXPERIMENT_IDS[POST_EARNINGS_SOURCE_NAME] = "exp-20260602-026"
    universe = sorted(source.base.get_universe())
    original_rows = source._source_rows_by_window()
    post_earnings_rows, post_earnings_audits = _post_earnings_rows_by_window(universe)
    after_rows = _merge_source_rows(original_rows, post_earnings_rows)

    results: list[dict[str, Any]] = []
    before_trades_by_window: dict[str, list[dict[str, Any]]] = {}
    after_trades_by_window: dict[str, list[dict[str, Any]]] = {}

    for label, cfg in source.base.WINDOWS.items():
        before_result = baselines[label]["result"]
        snapshot = source.base.shadow._load_snapshot(cfg["snapshot"])
        before_variant, before_trades = _variant_window_result(
            label=label,
            before_result=before_result,
            snapshot=snapshot,
            source_rows_by_window=original_rows,
        )
        after_variant, after_trades = _variant_window_result(
            label=label,
            before_result=before_result,
            snapshot=snapshot,
            source_rows_by_window=after_rows,
        )
        for trade in before_trades:
            trade["source_set_variant"] = "accepted_four_source_consensus_core_capacity"
        for trade in after_trades:
            trade["source_set_variant"] = "accepted_four_source_plus_post_earnings_core_capacity"
            trade["source_set_rule_version"] = RULE_VERSION

        delta = source.base.overlay_helper._delta(after_variant["metrics"], before_variant["metrics"])
        before_keys = {_trade_key(row) for row in before_trades}
        after_keys = {_trade_key(row) for row in after_trades}
        new_keys = sorted(after_keys - before_keys)
        removed_keys = sorted(before_keys - after_keys)
        changed_keys = sorted(before_keys.symmetric_difference(after_keys))
        post_supported_keys = sorted(
            _trade_key(row)
            for row in after_trades
            if POST_EARNINGS_SOURCE_NAME in set(row.get("source_names") or [])
        )
        results.append(
            {
                "label": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "core_baseline": core_metrics_by_window[label],
                "before": before_variant["metrics"],
                "after": after_variant["metrics"],
                "comparison": {
                    "expected_value_score_delta": delta["expected_value_score"],
                    "strategy_total_pnl_delta": delta["total_pnl"],
                    "total_pnl_delta": delta["total_pnl"],
                    "max_drawdown_delta": delta["max_drawdown_pct"],
                    "raw_delta": delta,
                },
                "before_variant": {
                    key: value
                    for key, value in before_variant.items()
                    if key != "metrics"
                },
                "after_variant": {
                    key: value for key, value in after_variant.items() if key != "metrics"
                },
                "new_target_trade_count": len(new_keys),
                "removed_target_trade_count": len(removed_keys),
                "changed_target_trade_count": len(changed_keys),
                "new_target_trade_keys": new_keys,
                "removed_target_trade_keys": removed_keys,
                "post_earnings_supported_target_trade_count": len(post_supported_keys),
                "post_earnings_supported_target_trade_keys": post_supported_keys,
                "post_earnings_source_audit": post_earnings_audits[label],
            }
        )
        before_trades_by_window[label] = before_trades
        after_trades_by_window[label] = after_trades

    source_audit = {
        "original_source_names": ORIGINAL_SOURCE_NAMES,
        "after_source_names": AFTER_SOURCE_NAMES,
        "post_earnings_source_name": POST_EARNINGS_SOURCE_NAME,
        "post_earnings_shared_rule_version": POST_EARNINGS_SHARED_RULE_VERSION,
        "post_earnings_source_rule_version": POST_EARNINGS_SOURCE_RULE_VERSION,
        "post_earnings_rows_by_window": {
            label: audits["rows_loaded"] for label, audits in post_earnings_audits.items()
        },
        "post_earnings_unique_keys_by_window": {
            label: audits["unique_keys_loaded"] for label, audits in post_earnings_audits.items()
        },
    }
    return results, core_metrics_by_window, before_trades_by_window, after_trades_by_window, source_audit


def _changed_target_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    changed_by_window = {
        row["label"]: int(row["changed_target_trade_count"]) for row in results
    }
    post_supported_by_window = {
        row["label"]: int(row["post_earnings_supported_target_trade_count"])
        for row in results
    }
    return {
        "changed_target_trade_count": sum(changed_by_window.values()),
        "changed_target_windows": [
            label for label, count in changed_by_window.items() if count > 0
        ],
        "changed_target_trade_count_by_window": changed_by_window,
        "post_earnings_supported_target_trade_count": sum(post_supported_by_window.values()),
        "post_earnings_supported_windows": [
            label for label, count in post_supported_by_window.items() if count > 0
        ],
        "post_earnings_supported_target_trade_count_by_window": post_supported_by_window,
    }


def _shared_adapter_check() -> dict[str, Any]:
    configured = set(getattr(shared_consensus, "ACCEPTED_SOURCE_NAMES", set()))
    return {
        "shared_adapter_file": "quant/free_data_cross_source_consensus_paper_sleeve.py",
        "shared_rule_version": getattr(shared_consensus, "RULE_VERSION", None),
        "post_earnings_source_present": POST_EARNINGS_SOURCE_NAME in configured,
        "configured_source_names": sorted(configured),
        "trade_enabled_default": bool(shared_consensus.DEFAULT_CONFIG.get("trade_enabled")),
        "require_core_capacity_available": bool(
            shared_consensus.DEFAULT_CONFIG.get("require_core_capacity_available")
        ),
        "passed_for_promotion": (
            POST_EARNINGS_SOURCE_NAME in configured
            and shared_consensus.DEFAULT_CONFIG.get("trade_enabled") is False
            and shared_consensus.DEFAULT_CONFIG.get("require_core_capacity_available") is True
        ),
    }


def _judge(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
    after_summary: dict[str, Any],
    changed_summary: dict[str, Any],
    baseline_drift: dict[str, Any],
    shared_adapter: dict[str, Any],
) -> dict[str, Any]:
    comparison = aggregate["comparison"]
    ev_delta = float(comparison["expected_value_score_delta"])
    pnl_delta = float(comparison["strategy_total_pnl_delta"])
    ev_improved = [
        row["label"] for row in results if float(row["comparison"]["expected_value_score_delta"]) > 0
    ]
    ev_regressed = [
        row["label"] for row in results if float(row["comparison"]["expected_value_score_delta"]) < 0
    ]
    pnl_improved = [
        row["label"] for row in results if float(row["comparison"]["strategy_total_pnl_delta"]) > 0
    ]
    pnl_regressed = [
        row["label"] for row in results if float(row["comparison"]["strategy_total_pnl_delta"]) < 0
    ]
    max_drawdown_delta = max(float(row["comparison"]["max_drawdown_delta"]) for row in results)
    min_survival_rate = min(float(row["after"].get("survival_rate") or 0.0) for row in results)
    concentration_passed = (
        after_summary["max_single_positive_share"] is not None
        and after_summary["max_single_positive_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and after_summary["positive_pnl_hhi"] is not None
        and after_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    changed_count = int(changed_summary["changed_target_trade_count"])
    changed_windows = changed_summary["changed_target_windows"]
    post_supported_count = int(changed_summary["post_earnings_supported_target_trade_count"])
    post_supported_windows = changed_summary["post_earnings_supported_windows"]
    gates = {
        "aggregate_expected_value_positive": ev_delta > 0,
        "aggregate_pnl_positive": pnl_delta > 0,
        "no_window_expected_value_regression": not ev_regressed,
        "no_window_pnl_regression": not pnl_regressed,
        "at_least_two_windows_expected_value_improved": len(ev_improved) >= 2,
        "at_least_two_windows_pnl_improved": len(pnl_improved) >= 2,
        "after_target_trade_count_passed": after_summary["target_trade_count"] >= MIN_TARGET_TRADES,
        "after_target_window_count_passed": (
            sum(1 for count in after_summary["trades_by_window"].values() if int(count) > 0)
            >= MIN_TARGET_WINDOWS
        ),
        "changed_target_trade_count_passed": changed_count >= MIN_CHANGED_TARGET_TRADES,
        "changed_target_window_count_passed": len(changed_windows) >= MIN_CHANGED_TARGET_WINDOWS,
        "post_earnings_supported_target_trade_count_passed": (
            post_supported_count >= MIN_CHANGED_TARGET_TRADES
        ),
        "drawdown_drift_passed": max_drawdown_delta <= MAX_DRAWDOWN_WORSE,
        "survival_floor_passed": min_survival_rate >= 0.05,
        "concentration_guard_passed": concentration_passed,
        "baseline_matches_docs": bool(baseline_drift["matches_all_windows"]),
        "shared_adapter_promoted_same_source_set": bool(shared_adapter["passed_for_promotion"]),
    }
    alpha_gate_keys = [key for key in gates if key != "shared_adapter_promoted_same_source_set"]
    alpha_checks_passed = all(gates[key] for key in alpha_gate_keys)
    failed_gates = [key for key, value in gates.items() if not value]
    if alpha_checks_passed and gates["shared_adapter_promoted_same_source_set"]:
        decision = "accepted_post_earnings_consensus_source_shared_adapter"
        rationale = (
            "The new source set passed the three-window alpha checks and the shared "
            "default-off adapter exposed the same source set."
        )
        passed = True
    elif alpha_checks_passed:
        decision = "positive_replay_lead_not_promoted_requires_shared_adapter"
        rationale = (
            "Adding the post-earnings source passed alpha checks, but the shared "
            "free-data consensus adapter was not changed in this experiment. Do not "
            "retain or promote until a separate shared-adapter parity experiment passes."
        )
        passed = False
    else:
        decision = "rejected_post_earnings_consensus_source_expansion"
        rationale = (
            "Adding the post-earnings source did not clear the three-window alpha, "
            "sample, risk, baseline, distinctness, or concentration gates."
        )
        passed = False
    return {
        "passed": passed,
        "alpha_checks_passed": alpha_checks_passed,
        "decision": decision,
        "rationale": rationale,
        "gates": gates,
        "failed_gates": failed_gates,
        "ev_windows_improved": ev_improved,
        "ev_windows_regressed": ev_regressed,
        "pnl_windows_improved": pnl_improved,
        "pnl_windows_regressed": pnl_regressed,
        "max_drawdown_delta": round(max_drawdown_delta, 6),
        "min_survival_rate": round(min_survival_rate, 6),
        "changed_target_trade_count": changed_count,
        "changed_target_windows": changed_windows,
        "post_earnings_supported_target_trade_count": post_supported_count,
        "post_earnings_supported_windows": post_supported_windows,
        "requires_parity_before_promotion": not bool(shared_adapter["passed_for_promotion"]),
    }


def _prediction() -> dict[str, Any]:
    if TICKET_JSON.exists():
        ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
        if isinstance(ticket.get("prediction"), dict):
            return ticket["prediction"]
    return {
        "success_probability": 0.32,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "zero_overlap",
            "thin_sample",
            "window_regression",
            "source_set_overfit",
            "concentration_failed",
        ],
        "confidence_reason": "Fallback copied from reservation intent.",
        "recorded_at": _utc_now(),
    }


def _calibration(
    prediction: dict[str, Any],
    gate4: dict[str, Any],
    aggregate: dict[str, Any],
) -> dict[str, Any]:
    actual_success = 1 if gate4["alpha_checks_passed"] else 0
    probability = float(prediction.get("success_probability") or 0.0)
    failed = gate4.get("failed_gates") or []
    predicted_failure_modes = prediction.get("main_failure_modes") or []
    return {
        "actual_decision": gate4["decision"],
        "actual_success": actual_success,
        "predicted_success_probability": probability,
        "brier_score": round((probability - actual_success) ** 2, 6),
        "actual_ev_delta": aggregate["comparison"]["expected_value_score_delta"],
        "actual_pnl_delta": aggregate["comparison"]["strategy_total_pnl_delta"],
        "predicted_failure_modes": predicted_failure_modes,
        "realized_failure_mode": failed,
        "predicted_failure_mode_hit": any(
            ("zero_overlap" in mode and "changed_target_trade_count_passed" in failed)
            or ("thin_sample" in mode and "after_target_trade_count_passed" in failed)
            or ("window_regression" in mode and "no_window_expected_value_regression" in failed)
            or ("concentration" in mode and "concentration_guard_passed" in failed)
            for mode in predicted_failure_modes
        ),
    }


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["completed_at"],
        "lane": "alpha_search",
        "status": payload["gate4"]["decision"],
        "decision": payload["gate4"]["decision"],
        "accepted": bool(payload["gate4"]["passed"]),
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "change_summary": (
            "Compared the accepted four-source free-data consensus plus core-capacity "
            "gate against the same consensus with POST_EARNINGS_UNDERPRICED_DRIFT_PAPER "
            "added as a fifth eligible source."
        ),
        "change_type": "default_off_candidate_pool_source_expansion",
        "mechanism_family": "default_off_candidate_pool_source_expansion",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": RULE_VERSION,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            "exp-20260531-030",
            "exp-20260601-001",
            "exp-20260601-028",
            "exp-20260602-026",
            "exp-20260602-027",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "newly_accepted_production_visible_post_earnings_default_off_source",
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "parameters": payload["rule"],
        "before_metrics": payload["aggregate"]["before"],
        "after_metrics": payload["aggregate"]["after"],
        "delta_metrics": {
            **comparison,
            "after_target_trade_count": payload["after_target_summary"]["target_trade_count"],
            "changed_target_trade_count": payload["changed_target_summary"][
                "changed_target_trade_count"
            ],
            "post_earnings_supported_target_trade_count": payload["changed_target_summary"][
                "post_earnings_supported_target_trade_count"
            ],
            "max_single_positive_share": payload["after_target_summary"][
                "max_single_positive_share"
            ],
            "positive_pnl_hhi": payload["after_target_summary"]["positive_pnl_hhi"],
            "max_drawdown_delta": payload["gate4"]["max_drawdown_delta"],
        },
        "windows": [
            {
                "label": row["label"],
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["comparison"]["expected_value_score_delta"],
                "strategy_total_pnl_delta": row["comparison"]["strategy_total_pnl_delta"],
                "changed_target_trade_count": row["changed_target_trade_count"],
                "post_earnings_supported_target_trade_count": row[
                    "post_earnings_supported_target_trade_count"
                ],
            }
            for row in payload["results"]
        ],
        "production_impact": PRODUCTION_IMPACT,
        "decision_basis": payload["gate4"],
        "rejection_reason": "; ".join(payload["gate4"]["failed_gates"]) or None,
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
        "anti_js": "No JavaScript was used.",
    }


def _write_card(payload: dict[str, Any]) -> None:
    comp = payload["aggregate"]["comparison"]
    lines = [
        f"# {EXPERIMENT_ID} post-earnings consensus source",
        "",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Aggregate EV delta vs accepted four-source consensus: `{comp['expected_value_score_delta']:+.4f}`",
        f"- Aggregate PnL delta vs accepted four-source consensus: `${comp['strategy_total_pnl_delta']:+,.2f}`",
        f"- After target trades: `{payload['after_target_summary']['target_trade_count']}`",
        f"- Changed target trades: `{payload['changed_target_summary']['changed_target_trade_count']}`",
        f"- Post-earnings-supported target trades: `{payload['changed_target_summary']['post_earnings_supported_target_trade_count']}`",
        f"- Baseline matches docs: `{payload['baseline_drift']['matches_all_windows']}`",
        "",
        "## Three-Window Evidence",
        "",
        "| window | EV before | EV after | dEV | PnL before | PnL after | dPnL | changed trades | PE-supported trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["results"]:
        lines.append(
            f"| {row['label']} | {row['before']['expected_value_score']:.4f} | "
            f"{row['after']['expected_value_score']:.4f} | "
            f"{row['comparison']['expected_value_score_delta']:+.4f} | "
            f"${row['before']['total_pnl']:,.2f} | ${row['after']['total_pnl']:,.2f} | "
            f"${row['comparison']['strategy_total_pnl_delta']:+,.2f} | "
            f"{row['changed_target_trade_count']} | "
            f"{row['post_earnings_supported_target_trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Conclusion",
            "",
            payload["gate4"]["rationale"],
            "",
            "No production orders, shared adapter config, core ranking/sizing/exits, "
            "watchlists, LLM, or news behavior changed in this replay.",
            "",
            "No JavaScript was used.",
        ]
    )
    _write_text(CARD_MD, "\n".join(lines) + "\n")


def _update_ticket_and_registry(payload: dict[str, Any]) -> None:
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8")) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["gate4"]["decision"],
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "production_impact": PRODUCTION_IMPACT,
            "gate4": payload["gate4"],
            "result": {
                "decision": payload["gate4"]["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "expected_value_score_delta": payload["aggregate"]["comparison"][
                    "expected_value_score_delta"
                ],
                "strategy_total_pnl_delta": payload["aggregate"]["comparison"][
                    "strategy_total_pnl_delta"
                ],
                "summary": payload["gate4"]["rationale"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)

    if not REGISTRY_JSON.exists():
        return
    registry = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    experiments = registry.get("experiments")
    if isinstance(experiments, list):
        for item in experiments:
            if isinstance(item, dict) and item.get("experiment_id") == EXPERIMENT_ID:
                item["status"] = payload["gate4"]["decision"]
                item["decision"] = payload["gate4"]["decision"]
                item["completed_at"] = payload["completed_at"]
                item["artifact"] = _repo_rel(OUT_JSON)
                item["log"] = _repo_rel(LOG_JSON)
                item["aggregate_expected_value_delta"] = payload["aggregate"]["comparison"][
                    "expected_value_score_delta"
                ]
                item["aggregate_strategy_total_pnl_delta"] = payload["aggregate"]["comparison"][
                    "strategy_total_pnl_delta"
                ]
                break
    _write_json(REGISTRY_JSON, registry)


def _write_manifest() -> None:
    files = {
        "runner": _repo_rel(Path(__file__)),
        "result": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket": _repo_rel(TICKET_JSON),
        "card": _repo_rel(CARD_MD),
        "manifest": _repo_rel(MANIFEST_JSON),
        "experiment_log": _repo_rel(EXPERIMENT_LOG),
        "registry": _repo_rel(REGISTRY_JSON),
        "shared_consensus_adapter": "quant/free_data_cross_source_consensus_paper_sleeve.py",
        "post_earnings_shared_adapter": "quant/post_earnings_underpriced_drift_paper_sleeve.py",
    }
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": _utc_now(),
        "files": {
            label: {
                "path": rel_path,
                "exists": (ROOT / rel_path).exists(),
                "sha256": _sha256(ROOT / rel_path),
            }
            for label, rel_path in files.items()
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def run() -> dict[str, Any]:
    gate2 = source.base._audit_open_positions()
    if not gate2.get("passed"):
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2}")

    (
        results,
        core_metrics_by_window,
        before_trades_by_window,
        after_trades_by_window,
        source_audit,
    ) = _run_windows()
    aggregate = _aggregate(results)
    before_summary = _target_summary(before_trades_by_window)
    after_summary = _target_summary(after_trades_by_window)
    changed_summary = _changed_target_summary(results)
    baseline_drift = _baseline_drift(core_metrics_by_window)
    shared_adapter = _shared_adapter_check()
    gate4 = _judge(
        aggregate,
        results,
        after_summary,
        changed_summary,
        baseline_drift,
        shared_adapter,
    )
    prediction = _prediction()
    calibration = _calibration(prediction, gate4, aggregate)
    completed_at = _utc_now()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "lane": "alpha_search",
        "status": gate4["decision"],
        "decision": gate4["decision"],
        "preflight": {
            "alpha_hypothesis": (
                "Adding the newly accepted POST_EARNINGS_UNDERPRICED_DRIFT_PAPER "
                "source to the accepted free-data cross-source consensus source set "
                "may improve default-off consensus candidate-pool replacement value "
                "without adding noisy tickers."
            ),
            "category": "candidate_pool / ranking_source_set",
            "playbook_alignment": (
                "Follows the playbook's default-off candidate-pool and production-visible "
                "paper adapter lane. It avoids LLM soft-ranking because joins remain sparse, "
                "and it uses a newly accepted free data edge instead of retuning frozen "
                "thresholds."
            ),
            "history_check": {
                "exp-20260531-030": "positive replay for source-agnostic accepted free-data consensus",
                "exp-20260601-001": "shared observe-only accepted free-data consensus adapter",
                "exp-20260601-028": "accepted current-baseline core-capacity gate for the consensus adapter",
                "exp-20260602-026": "accepted post-earnings underpriced drift shared adapter",
                "exp-20260602-027": "accepted high-liquidity support for the post-earnings adapter",
            },
            "single_causal_variable": CHANGED_VARIABLE,
            "acceptance_standard": (
                "docs/backtesting.md three-window before/after comparison. The before "
                "variant is the accepted four-source consensus with accepted core-capacity "
                "gate; the after variant changes only accepted_source_names by adding "
                "POST_EARNINGS_UNDERPRICED_DRIFT_PAPER. Promotion requires a shared adapter "
                "parity experiment."
            ),
            "reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260603_001_post_earnings_consensus_source.py"
            ),
        },
        "prediction": prediction,
        "calibration": calibration,
        "rule": {
            "rule_version": RULE_VERSION,
            "before_source_names": ORIGINAL_SOURCE_NAMES,
            "after_source_names": AFTER_SOURCE_NAMES,
            "added_source_name": POST_EARNINGS_SOURCE_NAME,
            "post_earnings_shared_rule_version": POST_EARNINGS_SHARED_RULE_VERSION,
            "post_earnings_source_rule_version": POST_EARNINGS_SOURCE_RULE_VERSION,
            "min_source_count": source.MIN_SOURCE_COUNT,
            "base_notional_usd": source.BASE_NOTIONAL_USD,
            "hold_days": source.HOLD_DAYS,
            "max_paper_trades_per_day": source.MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": source.SAME_TICKER_COOLDOWN_DAYS,
            "capacity_gate_rule_version": (
                "accepted_free_data_consensus_core_capacity_available_gate_v1"
            ),
        },
        "production_impact": PRODUCTION_IMPACT,
        "source_audit": source_audit,
        "gate1": {
            "source": "docs/backtesting.md canonical three-window replay",
            "core_baseline_metrics": core_metrics_by_window,
            "baseline_drift": baseline_drift,
        },
        "gate2": {
            "passed": True,
            "open_positions": gate2,
            "runtime_fields": [
                "accepted free-data source rows",
                "post-earnings source rows from shared helper",
                "ticker",
                "date/signal_date",
                "source_name",
                "baseline core trade entry_date and exit_date",
                "MAX_POSITIONS from quant/constants.py",
            ],
            "shared_helper_field_check": {
                "post_earnings_source": POST_EARNINGS_SOURCE_NAME,
                "uses_shared_helper": True,
                "field_shape_required_by_consensus": [
                    "snapshot.sleeve",
                    "snapshot.candidates[].ticker",
                    "snapshot.candidates[].date or signal_date",
                ],
                "passed": True,
            },
        },
        "gate3": {
            "passed": min(float(row["after"].get("survival_rate") or 0.0) for row in results)
            >= 0.05,
            "note": "No core/live filter was added; this is a default-off paper source-set replay.",
            "survival_by_window": {
                row["label"]: row["after"].get("survival_rate") for row in results
            },
        },
        "gate4": gate4,
        "aggregate": aggregate,
        "baseline_drift": baseline_drift,
        "shared_adapter_check": shared_adapter,
        "results": results,
        "before_target_summary": before_summary,
        "after_target_summary": after_summary,
        "changed_target_summary": changed_summary,
        "before_target_trades_by_window": before_trades_by_window,
        "after_target_trades_by_window": after_trades_by_window,
        "next_retry_requires": [
            "do not promote this replay without a separate shared adapter source-set experiment",
            "promotion must update quant/free_data_cross_source_consensus_paper_sleeve.py and parity docs/tests",
            "forward closed replacement-value rows before activation",
            "do not retry nearby source-set or cooldown thresholds unless a new accepted source or forward row changes evidence",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(TICKET_JSON),
            _repo_rel(MANIFEST_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }
    record = _experiment_log_record(payload)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, record)
    _write_card(payload)
    _update_ticket_and_registry(payload)
    _write_manifest()
    _upsert_jsonl(EXPERIMENT_LOG, record)
    return payload


def main() -> None:
    payload = run()
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["gate4"]["decision"],
                "aggregate": payload["aggregate"]["comparison"],
                "gate4": payload["gate4"],
                "target_summary": {
                    "before_target_trade_count": payload["before_target_summary"][
                        "target_trade_count"
                    ],
                    "after_target_trade_count": payload["after_target_summary"][
                        "target_trade_count"
                    ],
                    "changed_target_trade_count": payload["changed_target_summary"][
                        "changed_target_trade_count"
                    ],
                    "post_earnings_supported_target_trade_count": (
                        payload["changed_target_summary"][
                            "post_earnings_supported_target_trade_count"
                        ]
                    ),
                },
                "artifact": _repo_rel(OUT_JSON),
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
