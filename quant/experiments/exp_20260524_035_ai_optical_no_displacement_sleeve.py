"""exp-20260524-035: AI optical no-displacement paper sleeve scout.

This alpha search tests one causal variable: route governed AI optical
connectivity candidates into an additive default-off paper sleeve instead of
letting them displace core slots. The direct core-pool version
(`exp-20260523-003`) failed because slot/capital competition hurt core metrics
despite positive target-cohort PnL. This replay asks whether the same
production-visible cohort has standalone replacement value when core entries,
ranking, sizing, exits, heat, LLM/news, and live orders stay fixed.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260510_007_low_deployment_dynamic_etf_overlay as overlay_helper  # noqa: E402
import exp_20260523_009_ai_power_datacenter_core_pool as base  # noqa: E402
import risk_engine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260524-035"
STEM = "ai_optical_no_displacement_sleeve"
TRIAL_FAMILY = "governed_ai_optical_no_displacement_paper_sleeve"
CHANGED_VARIABLE = "ai_optical_no_displacement_paper_sleeve_routing"
TARGET_THEME = "ai_optical_connectivity"
TARGET_SEGMENT = "optical_connectivity"
SOURCE_UNIVERSE_STATE = base.SOURCE_UNIVERSE_STATE
SOURCE_OHLCV_EXPERIMENT_ID = base.SOURCE_OHLCV_EXPERIMENT_ID

TARGET_SECTOR_MAP = {
    "AAOI": "Technology",
    "CIEN": "Technology",
    "COHR": "Technology",
    "FN": "Technology",
    "GLW": "Technology",
    "LITE": "Technology",
    "MRVL": "Technology",
    "MTSI": "Technology",
}

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
OPEN_POSITIONS_JSON = REPO_ROOT / "operator_inputs" / "open_positions.json"
WINDOWS = base.WINDOWS
CANONICAL_WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
    },
}

MIN_TARGET_TRADES = 10
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.45


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


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _audit_open_positions() -> dict[str, Any]:
    if not OPEN_POSITIONS_JSON.exists():
        return {"passed": False, "reason": "open_positions.json missing"}
    payload = _load_json(OPEN_POSITIONS_JSON)
    rows = payload if isinstance(payload, list) else payload.get("positions", [])
    missing: list[dict[str, Any]] = []
    for index, row in enumerate(rows or []):
        if not isinstance(row, dict):
            continue
        for field in ("entry_date", "target_price"):
            if row.get(field) in (None, ""):
                missing.append({"index": index, "ticker": row.get("ticker"), "field": field})
    return {
        "path": _repo_rel(OPEN_POSITIONS_JSON),
        "checked_positions": len(rows or []),
        "missing_required_fields": missing,
        "passed": not missing,
    }


def _target_universe() -> dict[str, Any]:
    state = _load_json(SOURCE_UNIVERSE_STATE)
    core = {str(ticker).upper() for ticker in state.get("core_trade_universe") or []}
    records = state.get("records") or {}
    selected: list[str] = []
    selected_records: dict[str, Any] = {}
    excluded: dict[str, list[str]] = {}

    for ticker, record in sorted(records.items()):
        if not isinstance(record, dict):
            continue
        symbol = str(ticker).upper()
        reasons: list[str] = []
        if record.get("theme") != TARGET_THEME:
            reasons.append("not_target_theme")
        if record.get("theme_segment") != TARGET_SEGMENT:
            reasons.append("not_target_segment")
        if record.get("status") not in {"pilot", "research"}:
            reasons.append("not_pilot_or_research")
        if record.get("history_class") != "full_history":
            reasons.append("not_full_history")
        if record.get("liquidity_tier") not in {"ok", "watch"}:
            reasons.append("liquidity_not_ok_or_watch")
        if symbol in core:
            reasons.append("already_core")

        if reasons:
            if record.get("theme") == TARGET_THEME or record.get("theme_segment") == TARGET_SEGMENT:
                excluded[symbol] = reasons
            continue

        selected.append(symbol)
        selected_records[symbol] = {
            key: record.get(key)
            for key in (
                "status",
                "theme",
                "theme_segment",
                "liquidity_tier",
                "history_class",
                "first_trade_allowed_as_of",
                "max_capital_scalar",
                "max_risk_scalar",
                "requires_event_guard",
                "event_guard_profile",
                "pilot_sleeve",
                "source",
                "source_reason",
                "notes",
            )
        }
        selected_records[symbol]["sector_patch"] = TARGET_SECTOR_MAP.get(symbol, "Unknown")

    return {
        "source_universe_state": _repo_rel(SOURCE_UNIVERSE_STATE),
        "as_of": state.get("as_of"),
        "selection_rule": (
            "records.theme == ai_optical_connectivity, theme_segment == "
            "optical_connectivity, status in {pilot, research}, history_class "
            "full_history, liquidity_tier in {ok, watch}, and not already core"
        ),
        "why_this_cohort_is_not_noise": (
            "The target set is the current governed universe-state optical "
            "connectivity cohort with full OHLCV coverage in the observation "
            "snapshots. It is not an arbitrary ticker add; the experiment changes "
            "only routing from core slot competition to default-off "
            "no-displacement paper observation."
        ),
        "target_tickers": selected,
        "target_records": selected_records,
        "excluded_related_records": excluded,
    }


def _snapshot_coverage_for_windows(
    target_tickers: list[str],
    windows: dict[str, dict[str, str]],
) -> dict[str, Any]:
    coverage: dict[str, Any] = {}
    passed = True
    for label, spec in windows.items():
        snapshot_path = REPO_ROOT / spec["snapshot"]
        payload = _load_json(snapshot_path)
        ohlcv = payload.get("ohlcv") or {}
        if not ohlcv:
            ohlcv = payload
        ticker_rows = {ticker: len(ohlcv.get(ticker) or []) for ticker in target_tickers}
        missing = [ticker for ticker, count in ticker_rows.items() if count <= 0]
        if missing:
            passed = False
        coverage[label] = {
            "snapshot": spec["snapshot"],
            "ticker_row_counts": ticker_rows,
            "missing_tickers": missing,
        }
    return {"passed": passed, "by_window": coverage}


def _snapshot_coverage(target_tickers: list[str]) -> dict[str, Any]:
    return _snapshot_coverage_for_windows(target_tickers, WINDOWS)


@contextmanager
def _target_sector_patch(target_tickers: list[str]):
    original = {ticker: risk_engine.SECTOR_MAP.get(ticker) for ticker in target_tickers}
    for ticker in target_tickers:
        risk_engine.SECTOR_MAP[ticker] = TARGET_SECTOR_MAP.get(ticker, "Unknown")
    try:
        yield
    finally:
        for ticker, value in original.items():
            if value is None:
                risk_engine.SECTOR_MAP.pop(ticker, None)
            else:
                risk_engine.SECTOR_MAP[ticker] = value


def _target_trades(result: dict[str, Any], target_tickers: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for trade in result.get("trades") or []:
        ticker = str(trade.get("ticker") or "").upper()
        if ticker not in target_tickers:
            continue
        rows.append(
            {
                "ticker": ticker,
                "sector": trade.get("sector"),
                "strategy": trade.get("strategy"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "exit_reason": trade.get("exit_reason"),
                "entry_price": _round(trade.get("entry_price"), 4),
                "exit_price": _round(trade.get("exit_price"), 4),
                "shares": trade.get("shares"),
                "pnl": _round(trade.get("pnl"), 2),
                "pnl_pct_net": _round(trade.get("pnl_pct_net"), 6),
            }
        )
    return rows


def _overlay_from_target_trades(
    before_result: dict[str, Any],
    target_trades: list[dict[str, Any]],
) -> dict[str, Any]:
    pnl_by_exit_date: Counter[str] = Counter()
    overlay_days: list[dict[str, Any]] = []
    for trade in target_trades:
        exit_date = str(trade.get("exit_date") or "")
        pnl = float(trade.get("pnl") or 0.0)
        pnl_by_exit_date[exit_date] += pnl
        overlay_days.append(
            {
                "date": exit_date,
                "ticker": trade.get("ticker"),
                "entry_date": trade.get("entry_date"),
                "exit_date": exit_date,
                "strategy": trade.get("strategy"),
                "pnl": _round(pnl, 2),
                "source": "expanded_universe_target_trade_no_core_displacement",
            }
        )

    cumulative_overlay = 0.0
    combined_curve = []
    for day, equity in before_result.get("equity_curve") or []:
        cumulative_overlay += float(pnl_by_exit_date.get(str(day), 0.0))
        combined_curve.append((str(day), round(float(equity) + cumulative_overlay, 2)))

    return {
        "overlay_total_pnl": _round(sum(pnl_by_exit_date.values()), 2),
        "combined_equity_curve": combined_curve,
        "overlay_days": overlay_days,
        "overlay_day_count": len(overlay_days),
    }


def _target_trade_summary(
    target_trades_by_window: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    by_ticker_count: Counter[str] = Counter()
    by_ticker_pnl: Counter[str] = Counter()
    for trades in target_trades_by_window.values():
        for trade in trades:
            ticker = str(trade.get("ticker") or "").upper()
            pnl = float(trade.get("pnl") or 0.0)
            by_ticker_count[ticker] += 1
            by_ticker_pnl[ticker] += pnl

    positive = {ticker: pnl for ticker, pnl in by_ticker_pnl.items() if pnl > 0}
    positive_total = sum(positive.values())
    max_positive_share = (
        round(max(positive.values()) / positive_total, 6)
        if positive_total > 0 and positive
        else None
    )
    positive_hhi = (
        round(sum((pnl / positive_total) ** 2 for pnl in positive.values()), 6)
        if positive_total > 0 and positive
        else None
    )
    return {
        "total_trade_count": sum(by_ticker_count.values()),
        "windows_with_target_trades": [
            label for label, trades in target_trades_by_window.items() if trades
        ],
        "total_pnl": round(sum(by_ticker_pnl.values()), 2),
        "by_ticker_count": dict(sorted(by_ticker_count.items())),
        "by_ticker_pnl": {ticker: round(pnl, 2) for ticker, pnl in sorted(by_ticker_pnl.items())},
        "positive_by_ticker_pnl": {
            ticker: round(pnl, 2) for ticker, pnl in sorted(positive.items())
        },
        "max_single_positive_pnl_share": max_positive_share,
        "positive_pnl_hhi": positive_hhi,
    }


def _aggregate(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ev_before = sum(row["before"]["expected_value_score"] for row in rows.values())
    ev_after = sum(row["after"]["expected_value_score"] for row in rows.values())
    pnl_before = sum(row["before"]["total_pnl"] for row in rows.values())
    pnl_after = sum(row["after"]["total_pnl"] for row in rows.values())
    return {
        "baseline_expected_value_score_sum": _round(ev_before, 6),
        "after_expected_value_score_sum": _round(ev_after, 6),
        "expected_value_score_delta_sum": _round(ev_after - ev_before, 6),
        "expected_value_score_delta_pct": _round((ev_after - ev_before) / ev_before, 6)
        if ev_before
        else None,
        "baseline_total_pnl_sum": _round(pnl_before, 2),
        "after_total_pnl_sum": _round(pnl_after, 2),
        "total_pnl_delta_sum": _round(pnl_after - pnl_before, 2),
        "total_pnl_delta_pct": _round((pnl_after - pnl_before) / pnl_before, 6)
        if pnl_before
        else None,
        "windows_ev_improved": sum(
            1 for row in rows.values() if row["delta"]["expected_value_score"] > 0
        ),
        "windows_ev_regressed": sum(
            1 for row in rows.values() if row["delta"]["expected_value_score"] < 0
        ),
        "windows_pnl_improved": sum(
            1 for row in rows.values() if row["delta"]["total_pnl"] > 0
        ),
        "windows_pnl_regressed": sum(
            1 for row in rows.values() if row["delta"]["total_pnl"] < 0
        ),
        "max_drawdown_delta_max": _round(
            max(row["delta"]["max_drawdown_pct"] for row in rows.values()), 6
        ),
        "target_trade_count_sum": sum(row["target_trade_count"] for row in rows.values()),
    }


def _build_payload() -> dict[str, Any]:
    gate2_open_positions = _audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    target_universe = _target_universe()
    target_tickers = target_universe["target_tickers"]
    if not target_tickers:
        raise RuntimeError("No target tickers selected from universe state")
    coverage = _snapshot_coverage(target_tickers)
    canonical_coverage = _snapshot_coverage_for_windows(target_tickers, CANONICAL_WINDOWS)
    if not coverage["passed"]:
        raise RuntimeError(f"Gate 2 OHLCV coverage failed: {coverage}")

    base_universe = sorted(get_universe())
    expanded_universe = sorted(set(base_universe) | set(target_tickers))
    target_set = set(target_tickers)

    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    direct_core_admission_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    with _target_sector_patch(target_tickers):
        for label in WINDOWS:
            print(f"[{label}] baseline core universe")
            before_result = base._run_window(label, base_universe)
            print(f"[{label}] expanded universe for target trade discovery")
            expanded_result = base._run_window(label, expanded_universe)

            target_trades = _target_trades(expanded_result, target_set)
            overlay = _overlay_from_target_trades(before_result, target_trades)
            before = overlay_helper._metrics(before_result)
            after = overlay_helper._metrics_with_overlay(before_result, overlay)
            delta = overlay_helper._delta(after, before)

            target_trades_by_window[label] = target_trades
            before_metrics[label] = before
            after_metrics[label] = after
            direct_core_admission_metrics[label] = base._metrics(expanded_result)
            window_rows[label] = {
                "before": before,
                "after": after,
                "delta": delta,
                "overlay_total_pnl": overlay["overlay_total_pnl"],
                "overlay_day_count": overlay["overlay_day_count"],
                "overlay_days": overlay["overlay_days"],
                "target_trade_count": len(target_trades),
            }

    aggregate = _aggregate(window_rows)
    target_summary = _target_trade_summary(target_trades_by_window)
    target_windows = target_summary["windows_with_target_trades"]
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    gate4_passed = (
        aggregate["expected_value_score_delta_sum"] > 0
        and aggregate["total_pnl_delta_sum"] > 0
        and aggregate["windows_ev_improved"] == len(WINDOWS)
        and aggregate["windows_ev_regressed"] == 0
        and aggregate["windows_pnl_regressed"] == 0
        and target_summary["total_trade_count"] >= MIN_TARGET_TRADES
        and len(target_windows) >= MIN_TARGET_WINDOWS
        and aggregate["max_drawdown_delta_max"] <= MAX_DRAWDOWN_WORSE
        and min_survival >= 0.05
        and concentration_passed
    )
    decision = (
        "promising_replay_only_ai_optical_no_displacement_sleeve"
        if gate4_passed
        else "rejected_ai_optical_no_displacement_sleeve"
    )
    rejection_reason = None
    if not gate4_passed:
        failed = []
        if aggregate["expected_value_score_delta_sum"] <= 0:
            failed.append("aggregate_ev_not_positive")
        if aggregate["total_pnl_delta_sum"] <= 0:
            failed.append("aggregate_pnl_not_positive")
        if aggregate["windows_ev_improved"] != len(WINDOWS) or aggregate["windows_ev_regressed"]:
            failed.append("window_ev_regression")
        if aggregate["windows_pnl_regressed"]:
            failed.append("window_pnl_regression")
        if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
            failed.append("target_sample_too_small")
        if len(target_windows) < MIN_TARGET_WINDOWS:
            failed.append("target_window_coverage_too_small")
        if aggregate["max_drawdown_delta_max"] > MAX_DRAWDOWN_WORSE:
            failed.append("drawdown_drift_too_high")
        if not concentration_passed:
            failed.append("target_concentration_failed")
        rejection_reason = "; ".join(failed)

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The governed AI optical connectivity cohort may have positive "
            "standalone replacement value, but direct core admission failed by "
            "displacing stronger core opportunities. Routing the fixed cohort into "
            "a no-displacement default-off paper sleeve may preserve the edge "
            "without changing core slots, ranking, sizing, exits, LLM/news, or "
            "orders."
        ),
        "change_type": "candidate_pool_no_displacement_paper_sleeve",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "prior_trial_count": 2,
        "nearby_prior_experiments": [
            "exp-20260523-003",
            "exp-20260519-014",
            "exp-20260524-033",
            "exp-20260524-034",
        ],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "candidate_pool_capital_routing_no_displacement_test",
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md three-window replay using exp-20260519-029 "
                "observation-universe OHLCV snapshots; target trades are discovered "
                "from expanded-universe replay and added to baseline core equity "
                "without displacing core trades."
            ),
            "canonical_snapshot_target_coverage": canonical_coverage,
            "snapshot_coverage_note": (
                "The docs/backtesting.md canonical core snapshots preserve the "
                "standard date windows but do not contain the governed optical "
                "target tickers, so target-trade discovery uses the existing "
                "exp-20260519-029 observation-universe snapshots. Promotion still "
                "requires a shared/default-off adapter and parity validation."
            ),
            "windows": WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
        },
        "parameters": {
            "target_theme": TARGET_THEME,
            "target_segment": TARGET_SEGMENT,
            "target_sector_map": TARGET_SECTOR_MAP,
            "target_tickers": target_tickers,
            "target_universe": target_universe,
            "base_universe_count": len(base_universe),
            "expanded_universe_count": len(expanded_universe),
            "source_ohlcv_experiment_id": SOURCE_OHLCV_EXPERIMENT_ID,
            "target_trade_discovery": "expanded_universe_replay",
            "paper_sleeve_routing": "additive_no_core_displacement",
            "locked_variables": [
                "core universe",
                "core signal generation",
                "core ranking",
                "core position sizing",
                "core exits",
                "portfolio heat",
                "slot rules",
                "target cohort definition",
                "LLM/news replay",
                "live/default orders",
            ],
            "acceptance": {
                "aggregate_ev_delta_gt": 0,
                "aggregate_pnl_delta_gt": 0,
                "ev_improved_windows": 3,
                "max_ev_regressed_windows": 0,
                "max_pnl_regressed_windows": 0,
                "min_target_trades": MIN_TARGET_TRADES,
                "min_target_windows": MIN_TARGET_WINDOWS,
                "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "max_positive_hhi": MAX_POSITIVE_HHI,
            },
            "anti_js": "No JavaScript was used.",
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool / capital allocation: the optical cohort should "
                "be evaluated as a no-displacement sleeve rather than a raw core "
                "universe expansion."
            ),
            "2_history_check": {
                "exp-20260523-003": (
                    "Direct AI optical core-pool admission had 15 target trades "
                    "and positive target PnL but failed aggregate EV/PnL and all "
                    "three windows due core slot/capital competition."
                ),
                "exp-20260519-014": (
                    "AI infra pilot segment shadow was positive in parts but not "
                    "promotion-grade due baseline alignment, regression, drawdown, "
                    "and sample issues."
                ),
                "exp-20260524-033": (
                    "Compute-memory/storage raw core admission was positive but "
                    "failed risk/concentration."
                ),
                "exp-20260524-034": (
                    "Compute-memory/storage governance caps still failed sample "
                    "and concentration gates."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Same three docs/backtesting.md windows, positive aggregate EV/PnL, "
                "3/3 EV-improved windows, no EV/PnL-regressed window, >=10 target "
                "trades across all 3 windows, drawdown drift <=0.5pp, survival "
                ">=5%, and target concentration inside guardrails."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260524_035_ai_optical_no_displacement_sleeve.py"
            ),
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": f"{_repo_rel(OUT_JSON)}#before_metrics",
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "ohlcv_coverage": {
                "observation_snapshot_target_coverage": coverage,
                "canonical_snapshot_target_coverage": canonical_coverage,
                "note": (
                    "Canonical docs/backtesting snapshots have zero rows for "
                    "the optical target tickers; this replay therefore uses the "
                    "same date windows with exp-20260519-029 observation snapshots."
                ),
            },
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "universe_state records.theme/theme_segment/status/liquidity_tier/history_class",
                "target OHLCV rows in all three exp-20260519-029 snapshots",
                "risk_engine.SECTOR_MAP target tickers patched from TARGET_SECTOR_MAP in replay",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": _round(min_survival, 4),
            "passed": min_survival >= 0.05,
            "note": (
                "No new core filter or core entry rule was added. The target cohort "
                "is evaluated as additive default-off paper, so core survival is "
                "unchanged from the baseline replay."
            ),
        },
        "gate4": {
            "passed": gate4_passed,
            "aggregate_ev_delta_positive": aggregate["expected_value_score_delta_sum"] > 0,
            "aggregate_pnl_delta_positive": aggregate["total_pnl_delta_sum"] > 0,
            "windows_ev_improved": aggregate["windows_ev_improved"],
            "windows_ev_regressed": aggregate["windows_ev_regressed"],
            "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
            "target_trade_count": target_summary["total_trade_count"],
            "target_trade_count_min": MIN_TARGET_TRADES,
            "target_windows": target_windows,
            "target_window_count_min": MIN_TARGET_WINDOWS,
            "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
            "survival_guard_passed": min_survival >= 0.05,
            "target_concentration": {
                "passed": concentration_passed,
                "max_single_positive_pnl_share": target_summary[
                    "max_single_positive_pnl_share"
                ],
                "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
                "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
                "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
            },
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "target_trades_by_window": target_trades_by_window,
        "target_trade_summary": target_summary,
        "direct_core_admission_metrics": direct_core_admission_metrics,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "default_off_paper_only": True,
            "production_watchlist_changed": False,
            "production_orders_changed": False,
            "trade_enabled": False,
            "promotion_requirement": (
                "A retained result is a research lead only. Promotion requires a "
                "shared default-off optical paper adapter, daily report exposure, "
                "forward replacement-value ledger, and parity tests before any "
                "live/default behavior changes."
            ),
        },
        "why_not_other_changes": (
            "Skipped LLM soft-ranking because replay-safe attribution remains sparse; "
            "skipped SEC/event/state-surface/broad-market scalar retunes due recent "
            "anti-repeat gates; skipped another raw core candidate-pool admission "
            "because recent evidence shows slot displacement is the blocker. This "
            "tests capital routing for a fixed governed cohort instead."
        ),
        "interpretation": (
            "The optical cohort has positive no-displacement paper replacement "
            "value on frozen windows, but no production/shared policy was promoted. "
            "Treat this as a forward-watch sleeve lead, not a core-universe change."
            if gate4_passed
            else (
                "The optical no-displacement sleeve did not clear Gate 4; keep "
                "the cohort in observation until forward replacement value or a "
                "stronger catalyst-quality field arrives."
            )
        ),
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "Build forward default-off optical paper replacement-value rows or a "
            "shared paper adapter before any promotion; do not convert this into "
            "raw core universe membership."
            if gate4_passed
            else (
                "Forward optical replacement-value outcomes or a materially new "
                "source/event-quality field."
            )
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} AI Optical No-Displacement Paper Sleeve",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: route the fixed governed AI optical connectivity cohort into an additive default-off paper sleeve instead of core slot competition.",
            "",
            "## Trial Accounting",
            "",
            f"- trial_family: `{payload['trial_family']}`",
            f"- changed_variable: `{payload['changed_variable']}`",
            f"- prior_trial_count: `{payload['prior_trial_count']}`",
            f"- multiple_testing_risk_bucket: `{payload['multiple_testing_risk_bucket']}`",
            f"- new_evidence_type: `{payload['new_evidence_type']}`",
            f"- snapshot_note: {payload['backtest_protocol']['snapshot_coverage_note']}",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "AI optical no-displacement paper sleeve",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "summary": payload["interpretation"],
        },
    )
    _write_text(ARTIFACT_MD, _build_report(payload))
    _upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    payload = _build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "artifact": _repo_rel(ARTIFACT_MD),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
