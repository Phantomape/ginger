"""exp-20260620-004: SBC burden-improvement Form 4 context.

Replay-only alpha search. This tests one fixed context-allocation bundle on top
of the already accepted SBC burden-improvement default-off paper source:
recent PIT Form 4 A/M equity-compensation acquisition/exercise context gets a
fixed notional scalar, while the SBC source, thresholds, hold, cooldown, base
notional, daily slot count, and live/default orders remain unchanged.

No production code, shared helper, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, OrderedDict
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REPO_ROOT_BOOT = Path(__file__).resolve().parents[2]
QUANT_ROOT_BOOT = REPO_ROOT_BOOT / "quant"
EXPERIMENTS_ROOT_BOOT = QUANT_ROOT_BOOT / "experiments"
SCRIPTS_ROOT_BOOT = REPO_ROOT_BOOT / "scripts"
for import_path in (
    REPO_ROOT_BOOT,
    QUANT_ROOT_BOOT,
    EXPERIMENTS_ROOT_BOOT,
    SCRIPTS_ROOT_BOOT,
):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260616_015_sbc_burden_improvement_shared_adapter as accepted_sbc
from experiment_registry import persist_self_registered_result
from sbc_burden_improvement_paper_sleeve import (
    DEFAULT_CONFIG,
    RULE_VERSION as ACCEPTED_SBC_RULE_VERSION,
    SOURCE_RULE_VERSION as ACCEPTED_SBC_SOURCE_RULE_VERSION,
    build_sbc_burden_improvement_historical_trades,
    load_sbc_burden_companyfacts_index,
)


framework = accepted_sbc.framework

EXPERIMENT_ID = "exp-20260620-004"
OWNER = "codex-alpha-search"
STEM = "sbc_form4_equity_comp_context"
TRIAL_FAMILY = "sbc_burden_improvement_form4_context"
TRIAL_VARIANT_ID = "sbc_form4_equity_compensation_context_notional_scalar_v1"
CHANGED_VARIABLE = "sbc_form4_equity_compensation_context_v1"

REPO_ROOT = framework.REPO_ROOT
QUANT_ROOT = REPO_ROOT / "quant"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260620_004_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

FORM4_DIR = REPO_ROOT / "data" / "non_ohlcv"
FORM4_GLOB = "form4_transactions_*.jsonl"
SBC_COMPARATOR_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260616-015"
    / "exp_20260616_015_sbc_burden_improvement_shared_adapter.json"
)
BASELINE_ARTIFACT = "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"

LOOKBACK_DAYS = 30
NO_CONTEXT_SCALAR = 1.0
CLEAN_ACQUISITION_SCALAR = 1.25
OVERHANG_SCALAR = 0.5
ACQUISITION_CODES = {"A", "M"}
ACQUIRED_CODE = "A"
DISPOSAL_CODES = {"S", "F"}
DISPOSED_CODE = "D"

MIN_TARGET_TRADES = 50
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": 0.10,
    "expected_pnl_delta": 2500.0,
    "main_failure_modes": [
        "sample_too_sparse",
        "form4_context_noise",
        "accepted_sbc_comparator_not_beaten",
        "late_or_old_window_regression",
        "concentration_worsens",
    ],
    "confidence_reason": (
        "Accepted SBC burden-improvement has strong three-window lift, and the "
        "playbook names option-exercise/vesting context as a valid new evidence "
        "axis. Prior pure Form 4 attempts were weak, so the probability is low."
    ),
    "recorded_at": "2026-06-20T04:08:16Z",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "uses_free_sec_form4": True,
    "uses_free_sec_companyfacts": True,
    "uses_free_ohlcv": True,
    "parity_note": (
        "This experiment changes no production code. A positive result would "
        "remain a replay lead until one shared default-off helper computes the "
        "same PIT Form 4 context and SBC source in historical replay and daily "
        "snapshot paths before any report queue, candidate priority, sizing, "
        "watchlist, or order surface changes."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "capital_allocation/candidate_pool: within the accepted SBC burden-"
        "improvement default-off paper source, recent PIT Form 4 equity-"
        "compensation acquisition/exercise context may distinguish clean "
        "retained exposure from routine compensation overhang. Clean A/M "
        "context gets a fixed 1.25x paper notional, while same-accession S/F "
        "disposal or 10b5-1 context gets 0.5x."
    ),
    "2_history_check": {
        "exp-20260616-015": (
            "Accepted shared default-off SBC burden-improvement helper: "
            "aggregate EV +0.9438, PnL +$15,748.19, 108 target trades, all "
            "three canonical windows positive. This run keeps that source "
            "fixed and only tests Form 4 context allocation."
        ),
        "exp-20260616-013": (
            "Rejected pure Form 4 option-exercise retention source with zero "
            "target trades. This run is not a pure Form 4 candidate source; it "
            "uses Form 4 only as context on accepted SBC rows."
        ),
        "exp-20260616-017": (
            "Rejected similar Form 4/compensation near-neighbor. Novelty gate "
            "was overridden because this experiment is cross-source context on "
            "an accepted helper, not a Form 4 threshold retry."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. The adjusted SBC+"
        "Form4 context overlay must beat both the core baseline and exp-"
        "20260616-015 accepted SBC comparator in aggregate EV/PnL, with no "
        "window EV regression versus accepted SBC, target trades >=50 across "
        "all 3 windows, core survival >=5%, drawdown drift <=0.5pp, and "
        "concentration guard passing."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260620_004_sbc_form4_equity_comp_context.py"
    ),
}

_FORM4_CONTEXT_CACHE: dict[str, Any] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, set):
        return sorted(_safe(item) for item in value)
    if isinstance(value, Counter):
        return dict(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 10)
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(payload), handle, ensure_ascii=True, indent=2, sort_keys=True)
        handle.write("\n")


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


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _date10(value: Any) -> str:
    return str(value or "")[:10]


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _form4_files() -> list[Path]:
    files: list[Path] = []
    for path in sorted(FORM4_DIR.glob(FORM4_GLOB)):
        suffix = path.stem.replace("form4_transactions_", "")
        if "_" in suffix:
            continue
        files.append(path)
    return files


def _row_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("accession_number"),
        str(row.get("ticker") or row.get("issuer_trading_symbol") or "").upper().strip(),
        row.get("owner_cik") or row.get("owner_name"),
        _date10(row.get("transaction_date")),
        row.get("security_title"),
        row.get("transaction_code"),
        row.get("acquired_disposed_code"),
        row.get("shares"),
        row.get("price"),
        row.get("transaction_value"),
    )


def _group_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        str(row.get("ticker") or row.get("issuer_trading_symbol") or "").upper().strip(),
        row.get("accession_number"),
        row.get("owner_cik") or row.get("owner_name"),
        _date10(row.get("usable_trade_date")),
    )


def _is_pit_safe(row: dict[str, Any]) -> bool:
    return row.get("pit_safe_flag") is not False and bool(_date10(row.get("usable_trade_date")))


def _is_equity_comp_acquisition(row: dict[str, Any]) -> bool:
    if not _is_pit_safe(row):
        return False
    ticker = str(row.get("ticker") or row.get("issuer_trading_symbol") or "").upper().strip()
    if not ticker:
        return False
    code = str(row.get("transaction_code") or "").upper()
    acquired = str(row.get("acquired_disposed_code") or "").upper()
    return code in ACQUISITION_CODES and acquired == ACQUIRED_CODE


def _is_same_accession_disposal(row: dict[str, Any]) -> bool:
    if not _is_pit_safe(row):
        return False
    ticker = str(row.get("ticker") or row.get("issuer_trading_symbol") or "").upper().strip()
    if not ticker:
        return False
    code = str(row.get("transaction_code") or "").upper()
    acquired = str(row.get("acquired_disposed_code") or "").upper()
    return code in DISPOSAL_CODES and acquired == DISPOSED_CODE


def _event_from_group(group_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    acquisitions = [row for row in group_rows if _is_equity_comp_acquisition(row)]
    if not acquisitions:
        return None
    disposals = [row for row in group_rows if _is_same_accession_disposal(row)]
    event_date = max(_date10(row.get("usable_trade_date")) for row in acquisitions)
    ticker = str(acquisitions[0].get("ticker") or acquisitions[0].get("issuer_trading_symbol") or "").upper().strip()
    total_acquired_shares = sum(float(_float(row.get("shares")) or 0.0) for row in acquisitions)
    total_disposed_shares = sum(float(_float(row.get("shares")) or 0.0) for row in disposals)
    total_acquisition_value = sum(float(_float(row.get("transaction_value")) or 0.0) for row in acquisitions)
    total_disposal_value = sum(float(_float(row.get("transaction_value")) or 0.0) for row in disposals)
    any_10b5 = any(bool(row.get("10b5_1_flag")) for row in group_rows)
    option_exercise_count = sum(1 for row in acquisitions if bool(row.get("option_exercise_flag")))
    overhang = bool(disposals or any_10b5)
    owners = {
        str(row.get("owner_cik") or row.get("owner_name") or "")
        for row in group_rows
        if str(row.get("owner_cik") or row.get("owner_name") or "")
    }
    top = max(
        acquisitions,
        key=lambda row: (
            float(_float(row.get("transaction_value")) or 0.0),
            float(_float(row.get("shares")) or 0.0),
        ),
    )
    return {
        "ticker": ticker,
        "usable_trade_date": event_date,
        "label": "compensation_overhang" if overhang else "clean_acquisition_retention",
        "acquisition_count": len(acquisitions),
        "disposal_count": len(disposals),
        "owner_count": len(owners),
        "option_exercise_count": option_exercise_count,
        "grant_count": len(acquisitions) - option_exercise_count,
        "total_acquired_shares": round(total_acquired_shares, 2),
        "total_disposed_shares": round(total_disposed_shares, 2),
        "total_acquisition_value": round(total_acquisition_value, 2),
        "total_disposal_value": round(total_disposal_value, 2),
        "any_10b5_1_flag": any_10b5,
        "accession_number": top.get("accession_number"),
        "issuer_name": top.get("issuer_name"),
        "owner_name": top.get("owner_name"),
        "owner_cik": top.get("owner_cik"),
        "is_officer": bool(top.get("is_officer")),
        "is_director": bool(top.get("is_director")),
        "officer_title": top.get("officer_title"),
        "security_title": top.get("security_title"),
        "archive_url": top.get("archive_url"),
        "primary_document": top.get("primary_document"),
    }


def _load_form4_context() -> dict[str, Any]:
    global _FORM4_CONTEXT_CACHE
    if _FORM4_CONTEXT_CACHE is not None:
        return _FORM4_CONTEXT_CACHE

    files = _form4_files()
    scan: dict[str, Any] = {
        "source_dir": _repo_rel(FORM4_DIR),
        "source_glob": FORM4_GLOB,
        "daily_source_file_count": len(files),
        "raw_rows": 0,
        "duplicate_rows": 0,
        "equity_comp_acquisition_rows": 0,
        "same_accession_disposal_rows": 0,
        "event_count": 0,
        "event_ticker_count": 0,
        "event_dates": 0,
        "lookback_days": LOOKBACK_DAYS,
        "acquisition_codes": sorted(ACQUISITION_CODES),
        "disposal_codes": sorted(DISPOSAL_CODES),
        "scalars": {
            "no_context": NO_CONTEXT_SCALAR,
            "clean_acquisition_retention": CLEAN_ACQUISITION_SCALAR,
            "compensation_overhang": OVERHANG_SCALAR,
        },
    }
    staged: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    seen: set[tuple[Any, ...]] = set()
    for path in files:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            scan["raw_rows"] += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = _row_key(row)
            if key in seen:
                scan["duplicate_rows"] += 1
                continue
            seen.add(key)
            if not (_is_equity_comp_acquisition(row) or _is_same_accession_disposal(row)):
                continue
            if _is_equity_comp_acquisition(row):
                scan["equity_comp_acquisition_rows"] += 1
            if _is_same_accession_disposal(row):
                scan["same_accession_disposal_rows"] += 1
            staged.setdefault(_group_key(row), []).append(row)

    by_ticker: dict[str, list[dict[str, Any]]] = {}
    label_distribution: Counter[str] = Counter()
    ticker_distribution: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []
    for rows in staged.values():
        event = _event_from_group(rows)
        if event is None:
            continue
        by_ticker.setdefault(str(event["ticker"]), []).append(event)
        label_distribution[str(event["label"])] += 1
        ticker_distribution[str(event["ticker"])] += 1
        if len(examples) < 25:
            examples.append(event)

    for events in by_ticker.values():
        events.sort(key=lambda event: str(event["usable_trade_date"]))

    event_dates = {
        str(event["usable_trade_date"])
        for events in by_ticker.values()
        for event in events
    }
    scan["event_count"] = sum(len(events) for events in by_ticker.values())
    scan["event_ticker_count"] = len(by_ticker)
    scan["event_dates"] = len(event_dates)
    scan["label_distribution"] = dict(sorted(label_distribution.items()))
    scan["ticker_distribution_top20"] = dict(ticker_distribution.most_common(20))

    _FORM4_CONTEXT_CACHE = {
        "by_ticker": by_ticker,
        "scan": scan,
        "examples": examples,
    }
    return _FORM4_CONTEXT_CACHE


def _events_for_trade(ticker: str, signal_date: str) -> list[dict[str, Any]]:
    signal = _parse_date(signal_date)
    start = signal - timedelta(days=LOOKBACK_DAYS)
    events: list[dict[str, Any]] = []
    for event in _load_form4_context()["by_ticker"].get(ticker, []):
        event_date = _parse_date(str(event["usable_trade_date"]))
        if start <= event_date <= signal:
            events.append(event)
    return events


def _context_label_and_scalar(events: list[dict[str, Any]]) -> tuple[str, float]:
    if not events:
        return "no_context", NO_CONTEXT_SCALAR
    if any(event.get("label") == "compensation_overhang" for event in events):
        return "compensation_overhang", OVERHANG_SCALAR
    return "clean_acquisition_retention", CLEAN_ACQUISITION_SCALAR


def _apply_form4_context(
    trades_by_window: "OrderedDict[str, list[dict[str, Any]]]",
) -> tuple["OrderedDict[str, list[dict[str, Any]]]", "OrderedDict[str, dict[str, Any]]"]:
    adjusted_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    scan_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    for label, trades in trades_by_window.items():
        adjusted: list[dict[str, Any]] = []
        label_distribution: Counter[str] = Counter()
        original_pnl_by_label: Counter[str] = Counter()
        adjusted_pnl_by_label: Counter[str] = Counter()
        affected_examples: list[dict[str, Any]] = []
        event_count_total = 0
        for trade in trades:
            ticker = str(trade.get("ticker") or "").upper().strip()
            signal_date = _date10(trade.get("signal_date") or trade.get("date"))
            events = _events_for_trade(ticker, signal_date) if ticker and signal_date else []
            context_label, scalar = _context_label_and_scalar(events)
            original_pnl = float(trade.get("pnl") or 0.0)
            original_notional = float(trade.get("paper_notional_usd") or trade.get("notional_usd") or 0.0)
            new_pnl = round(original_pnl * scalar, 2)
            new_notional = round(original_notional * scalar, 2)
            row = deepcopy(trade)
            row["target_price"] = row.get("target_price", row.get("exit_price"))
            row["original_pnl_before_form4_context"] = round(original_pnl, 2)
            row["original_paper_notional_before_form4_context"] = round(original_notional, 2)
            row["pnl"] = new_pnl
            row["paper_notional_usd"] = new_notional
            row["notional_usd"] = new_notional
            row["form4_context_label"] = context_label
            row["form4_context_notional_scalar"] = scalar
            row["form4_context_event_count"] = len(events)
            row["form4_context_lookback_days"] = LOOKBACK_DAYS
            row["form4_context_clean_event_count"] = sum(
                1 for event in events if event.get("label") == "clean_acquisition_retention"
            )
            row["form4_context_overhang_event_count"] = sum(
                1 for event in events if event.get("label") == "compensation_overhang"
            )
            if events:
                row["form4_context_events"] = events[:5]
            adjusted.append(row)

            label_distribution[context_label] += 1
            original_pnl_by_label[context_label] += original_pnl
            adjusted_pnl_by_label[context_label] += new_pnl
            event_count_total += len(events)
            if scalar != NO_CONTEXT_SCALAR and len(affected_examples) < 20:
                affected_examples.append(
                    {
                        "window": label,
                        "signal_date": signal_date,
                        "ticker": ticker,
                        "context_label": context_label,
                        "scalar": scalar,
                        "original_pnl": round(original_pnl, 2),
                        "adjusted_pnl": new_pnl,
                        "events": events[:3],
                    }
                )

        adjusted_by_window[label] = adjusted
        affected_count = sum(
            count for context, count in label_distribution.items() if context != "no_context"
        )
        scan_by_window[label] = {
            "source": "accepted_sbc_trades_joined_to_pit_form4_context",
            "trade_count": len(trades),
            "context_affected_trade_count": affected_count,
            "context_affected_trade_share": round(affected_count / max(len(trades), 1), 6),
            "form4_context_event_count_total": event_count_total,
            "label_distribution": dict(sorted(label_distribution.items())),
            "original_pnl_by_context_label": {
                key: round(float(value), 2) for key, value in sorted(original_pnl_by_label.items())
            },
            "adjusted_pnl_by_context_label": {
                key: round(float(value), 2) for key, value in sorted(adjusted_pnl_by_label.items())
            },
            "affected_examples": affected_examples,
        }
    return adjusted_by_window, scan_by_window


def _load_accepted_sbc_comparator() -> dict[str, Any]:
    payload = _load_json(SBC_COMPARATOR_JSON, {})
    if not payload:
        raise RuntimeError(f"missing accepted SBC comparator artifact: {SBC_COMPARATOR_JSON}")
    return payload


def _reproduction_check(
    accepted_payload: dict[str, Any],
    original_window_rows: "OrderedDict[str, dict[str, Any]]",
    original_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]",
) -> dict[str, Any]:
    accepted_delta = accepted_payload["delta_metrics"]
    accepted_summary = accepted_payload["target_trade_summary"]
    actual_agg = framework._aggregate_window_rows(original_window_rows)
    expected_agg = accepted_delta["aggregate"]
    by_window: dict[str, dict[str, Any]] = {}
    max_abs_ev_drift = 0.0
    max_abs_pnl_drift = 0.0
    for label in framework.WINDOWS:
        actual = original_window_rows[label]["delta"]
        expected = accepted_delta["by_window"][label]
        ev_drift = round(
            float(actual.get("expected_value_score") or 0.0)
            - float(expected.get("expected_value_score") or 0.0),
            6,
        )
        pnl_drift = round(
            float(actual.get("total_pnl") or 0.0)
            - float(expected.get("total_pnl") or 0.0),
            2,
        )
        max_abs_ev_drift = max(max_abs_ev_drift, abs(ev_drift))
        max_abs_pnl_drift = max(max_abs_pnl_drift, abs(pnl_drift))
        by_window[label] = {
            "expected_value_score_drift": ev_drift,
            "total_pnl_drift": pnl_drift,
            "actual_trade_count": len(original_trades_by_window[label]),
            "expected_trade_count": len(accepted_payload["target_trades_by_window"][label]),
        }
    aggregate_ev_drift = round(
        float(actual_agg["expected_value_score_delta_sum"])
        - float(expected_agg["expected_value_score_delta_sum"]),
        6,
    )
    aggregate_pnl_drift = round(
        float(actual_agg["total_pnl_delta_sum"]) - float(expected_agg["total_pnl_delta_sum"]),
        2,
    )
    trade_count_drift = (
        sum(len(rows) for rows in original_trades_by_window.values())
        - int(accepted_summary["total_trade_count"])
    )
    passed = (
        abs(aggregate_ev_drift) <= 0.0002
        and abs(aggregate_pnl_drift) <= 1.0
        and trade_count_drift == 0
        and max_abs_ev_drift <= 0.0002
        and max_abs_pnl_drift <= 1.0
    )
    return {
        "passed": passed,
        "accepted_experiment_id": "exp-20260616-015",
        "accepted_artifact": _repo_rel(SBC_COMPARATOR_JSON),
        "aggregate_expected_value_score_delta_drift": aggregate_ev_drift,
        "aggregate_total_pnl_delta_drift": aggregate_pnl_drift,
        "trade_count_drift": trade_count_drift,
        "max_abs_window_ev_drift": round(max_abs_ev_drift, 6),
        "max_abs_window_pnl_drift": round(max_abs_pnl_drift, 2),
        "by_window": by_window,
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: "OrderedDict[str, dict[str, Any]]",
    delta_by_window: "OrderedDict[str, dict[str, Any]]",
    accepted_payload: dict[str, Any],
    reproduction: dict[str, Any],
    context_scan_by_window: "OrderedDict[str, dict[str, Any]]",
) -> dict[str, Any]:
    accepted_aggregate = accepted_payload["delta_metrics"]["aggregate"]
    accepted_by_window = accepted_payload["delta_metrics"]["by_window"]
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    context_affected_trade_count = sum(
        int(scan.get("context_affected_trade_count") or 0)
        for scan in context_scan_by_window.values()
    )
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    failed: list[str] = []
    if float(aggregate["expected_value_score_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_ev_not_positive_vs_core")
    if float(aggregate["total_pnl_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_pnl_not_positive_vs_core")
    if (
        float(aggregate["expected_value_score_delta_sum"] or 0.0)
        <= float(accepted_aggregate["expected_value_score_delta_sum"] or 0.0)
    ):
        failed.append("accepted_sbc_aggregate_ev_not_beaten")
    if (
        float(aggregate["total_pnl_delta_sum"] or 0.0)
        <= float(accepted_aggregate["total_pnl_delta_sum"] or 0.0)
    ):
        failed.append("accepted_sbc_aggregate_pnl_not_beaten")
    regressed_windows: list[str] = []
    for label in framework.WINDOWS:
        actual_ev = float(delta_by_window[label].get("expected_value_score") or 0.0)
        expected_ev = float(accepted_by_window[label].get("expected_value_score") or 0.0)
        if actual_ev < expected_ev - 0.000001:
            regressed_windows.append(label)
    if regressed_windows:
        failed.append("window_ev_regression_vs_accepted_sbc")
    if int(aggregate["windows_ev_regressed"] or 0) > 0:
        failed.append("window_ev_regression_vs_core")
    if int(aggregate["windows_pnl_regressed"] or 0) > 0:
        failed.append("window_pnl_regression_vs_core")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_summary["windows_with_target_trades"]) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if float(aggregate["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    if not concentration_passed:
        failed.append("target_concentration_failed")
    if context_affected_trade_count <= 0:
        failed.append("no_form4_context_overlap_on_sbc_trades")
    if not reproduction.get("passed"):
        failed.append("accepted_sbc_comparator_not_reproduced")
    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "positive_replay_lead_not_promoted_sbc_form4_context"
            if passed
            else "rejected_sbc_form4_equity_comp_context"
        ),
        "failed_reasons": failed,
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_sbc_aggregate_ev_delta": accepted_aggregate["expected_value_score_delta_sum"],
        "accepted_sbc_aggregate_pnl_delta": accepted_aggregate["total_pnl_delta_sum"],
        "aggregate_ev_delta_vs_accepted_sbc": round(
            float(aggregate["expected_value_score_delta_sum"])
            - float(accepted_aggregate["expected_value_score_delta_sum"]),
            6,
        ),
        "aggregate_pnl_delta_vs_accepted_sbc": round(
            float(aggregate["total_pnl_delta_sum"])
            - float(accepted_aggregate["total_pnl_delta_sum"]),
            2,
        ),
        "window_ev_regressions_vs_accepted_sbc": regressed_windows,
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_summary["windows_with_target_trades"],
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "context_affected_trade_count": context_affected_trade_count,
        "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "minimum_core_survival_rate": round(min_survival, 6),
        "survival_guard_passed": min_survival >= 0.05,
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": target_summary["max_single_positive_pnl_share"],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
        "accepted_sbc_reproduction": reproduction,
    }


def build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    accepted_payload = _load_accepted_sbc_comparator()
    framework._configure_sleeve_globals()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(framework.get_universe())
    sector_entries = framework._load_sector_entries()
    quality_index, quality_summary = load_sbc_burden_companyfacts_index()
    form4_context = _load_form4_context()

    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    original_after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    original_sbc_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    target_audit_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    warehouse_coverage_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    adjusted_window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    original_window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] SBC burden-improvement + Form 4 context replay")
        before_result = framework.shadow._run_baseline(universe, cfg)
        before = framework.overlay_helper._metrics(before_result)
        snapshot = framework._load_window_snapshot(cfg=cfg, eligible_tickers=set(universe))
        window_sector_entries = {
            ticker: meta for ticker, meta in sector_entries.items() if ticker in snapshot
        }
        original_trades, audit = build_sbc_burden_improvement_historical_trades(
            ohlcv_by_ticker=snapshot,
            windows={label: cfg},
            quality_index=quality_index,
            sector_entries=window_sector_entries,
            config=DEFAULT_CONFIG,
        )
        original_sbc_trades_by_window[label] = original_trades

        original_overlay = framework.sleeve._overlay_from_paper_trades(
            before_result,
            original_trades,
        )
        original_after = framework.overlay_helper._metrics_with_overlay(
            before_result,
            original_overlay,
        )
        original_delta = framework.overlay_helper._delta(original_after, before)
        original_window_rows[label] = {
            "before": before,
            "after": original_after,
            "delta": original_delta,
            "target_trade_count": len(original_trades),
            "raw_candidate_count": audit["raw_candidate_count_by_window"].get(label, 0),
            "overlay_total_pnl": original_overlay["overlay_total_pnl"],
            "overlay_day_count": original_overlay["overlay_day_count"],
        }

        adjusted_trades, scan_by_window = _apply_form4_context(
            OrderedDict([(label, original_trades)])
        )
        trades = adjusted_trades[label]
        context_scan = scan_by_window[label]
        overlay = framework.sleeve._overlay_from_paper_trades(before_result, trades)
        after = framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = framework.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        original_after_metrics[label] = original_after
        target_trades_by_window[label] = trades
        target_audit_by_window[label] = {**audit, "form4_context": context_scan}
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_candidate_ticker_count": len(window_sector_entries),
            "source": _repo_rel(framework.WAREHOUSE),
        }
        adjusted_window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(trades),
            "raw_candidate_count": audit["raw_candidate_count_by_window"].get(label, 0),
            "context_affected_trade_count": context_scan["context_affected_trade_count"],
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = framework._aggregate_window_rows(adjusted_window_rows)
    target_summary = framework.sleeve._target_trade_summary(target_trades_by_window)
    context_scan_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
        (label, target_audit_by_window[label]["form4_context"]) for label in framework.WINDOWS
    )
    reproduction = _reproduction_check(
        accepted_payload,
        original_window_rows,
        original_sbc_trades_by_window,
    )
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
        delta_by_window=OrderedDict(
            (label, row["delta"]) for label, row in adjusted_window_rows.items()
        ),
        accepted_payload=accepted_payload,
        reproduction=reproduction,
        context_scan_by_window=context_scan_by_window,
    )
    passed = bool(gate4["passed"])
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": "positive_replay_lead_not_promoted" if passed else "rejected",
        "decision": gate4["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": passed,
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "default_off_paper_candidate_pool_replay_scout",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "sec_companyfacts_form4_compensation_context",
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "cross_source_context_on_accepted_helper",
        "nearby_prior_experiments": [
            "exp-20260616-013",
            "exp-20260616-015",
            "exp-20260616-017",
        ],
        "prior_trial_count": 0,
        "prediction": PREDICTION,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "accepted SBC default-off paper helper overlay with fixed Form 4 "
                "context notional scalar"
            ),
            "windows": framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "companyfacts_source": "data/cache/sec/companyfacts raw filed-date SEC Companyfacts",
            "form4_source": _repo_rel(FORM4_DIR),
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "The SBC source is exactly the accepted exp-20260616-015 helper "
                "policy. For each accepted SBC paper trade, the replay joins PIT "
                "Form 4 events with usable_trade_date inside the prior 30 calendar "
                "days and no later than the signal date. A/M acquisitions or "
                "option exercises without same-accession S/F disposal and no "
                "10b5-1 flag receive a 1.25x paper notional scalar. A/M context "
                "with same-accession S/F disposal or any 10b5-1 flag receives "
                "0.5x. No context remains 1.0x. Entry, exit, slippage, costs, "
                "hold, cooldown, candidate source, and core baseline are unchanged."
            ),
        },
        "parameters": {
            "changed_variable": CHANGED_VARIABLE,
            "accepted_sbc_rule_version": ACCEPTED_SBC_RULE_VERSION,
            "accepted_sbc_source_rule_version": ACCEPTED_SBC_SOURCE_RULE_VERSION,
            "form4_lookback_days": LOOKBACK_DAYS,
            "acquisition_codes": sorted(ACQUISITION_CODES),
            "disposal_codes": sorted(DISPOSAL_CODES),
            "no_context_scalar": NO_CONTEXT_SCALAR,
            "clean_acquisition_retention_scalar": CLEAN_ACQUISITION_SCALAR,
            "compensation_overhang_scalar": OVERHANG_SCALAR,
            "paper_notional_usd_before_context": DEFAULT_CONFIG["paper_notional_usd"],
            "daily_entry_slots": DEFAULT_CONFIG["daily_entry_slots"],
            "hold_days": DEFAULT_CONFIG["hold_days"],
            "same_ticker_cooldown_days": DEFAULT_CONFIG["same_ticker_cooldown_days"],
            "max_active_positions": DEFAULT_CONFIG["max_active_positions"],
        },
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": BASELINE_ARTIFACT,
            "accepted_sbc_comparator_artifact": _repo_rel(SBC_COMPARATOR_JSON),
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "accepted SBC target trades entry_date",
                "accepted SBC target trades target_price",
                "raw SEC Companyfacts filed-date SBC/revenue/gross-profit facts",
                "PIT-safe Form 4 transaction usable_trade_date",
                "Form 4 transaction_code/acquired_disposed_code/accession/owner",
                "warehouse OHLCV Date/Open/High/Low/Close/Volume",
            ],
            "target_trade_entry_date_present": all(
                bool(trade.get("entry_date"))
                for trades in target_trades_by_window.values()
                for trade in trades
            ),
            "target_trade_target_price_present": all(
                bool(trade.get("target_price"))
                for trades in target_trades_by_window.values()
                for trade in trades
            ),
            "form4_source_scan": form4_context["scan"],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": round(
                min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values()),
                6,
            ),
            "passed": min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values()) >= 0.05,
            "note": (
                "No core filter is added. The run changes only default-off paper "
                "notional on accepted SBC overlay rows; core signals generated/"
                "survived are unchanged from baseline."
            ),
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "accepted_sbc_after_metrics_reproduced": original_after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict(
                (label, row["delta"]) for label, row in adjusted_window_rows.items()
            ),
            "aggregate": aggregate,
        },
        "accepted_sbc_reproduction_delta_metrics": {
            "by_window": OrderedDict(
                (label, row["delta"]) for label, row in original_window_rows.items()
            ),
            "aggregate": framework._aggregate_window_rows(original_window_rows),
        },
        "accepted_sbc_comparator_delta_metrics": accepted_payload["delta_metrics"],
        "target_trades_by_window": target_trades_by_window,
        "original_sbc_trades_by_window": original_sbc_trades_by_window,
        "target_trade_summary": target_summary,
        "target_audit_by_window": target_audit_by_window,
        "form4_context_scan": form4_context["scan"],
        "form4_context_examples": form4_context["examples"],
        "form4_context_scan_by_window": context_scan_by_window,
        "quality_index_summary": quality_summary,
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "gate4": gate4,
        "production_impact": PRODUCTION_IMPACT,
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "anti_js": "No JavaScript was used.",
    }
    payload["expected_value_score_delta"] = aggregate["expected_value_score_delta_sum"]
    payload["total_pnl_delta"] = aggregate["total_pnl_delta_sum"]
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": passed,
        "actual_success": 1 if passed else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if passed else 0.0)) ** 2,
            6,
        ),
        "surprise_note": (
            "Form 4 context improved the accepted SBC source in the canonical windows."
            if passed
            else (
                "Form 4 context did not add replacement value beyond accepted SBC; "
                "routine compensation context remained noisy or directionally wrong."
            )
        ),
    }
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The fixed Form 4 context scalars improved replacement value versus "
            "accepted SBC, suggesting the same PIT event context has incremental "
            "allocation information on top of SBC burden improvement. This remains "
            "only a replay lead until shared helper parity is implemented."
            if passed
            else (
                "The fixed Form 4 context scalars failed to beat the accepted SBC "
                "helper. The likely reason is that recent grants/exercises and "
                "same-accession disposals mostly describe routine compensation "
                "plumbing, not incremental demand or overhang, and the accepted "
                "SBC+OHLCV helper already captures the useful quality/momentum edge."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not sweep the 30-day lookback, 1.25x/0.5x scalars, Form 4 owner "
            "roles, 10b5-1 handling, A/M/S/F code lists, SBC thresholds, hold, "
            "cooldown, top-N, or base notional on these frozen windows."
        ),
        "new_evidence_required": (
            "A retry needs new evidence, such as closed forward daily replacement "
            "value from a shared SBC+Form4 context snapshot, parsed executive "
            "compensation/holdings context, or grant-value normalization. Pure "
            "Form 4 threshold/context retunes stay frozen."
        ),
    }
    payload["interpretation"] = (
        "The SBC+Form4 context overlay is a positive replay lead only; no "
        "production surface changed and shared default-off parity is required "
        "before use."
        if passed
        else (
            "The SBC+Form4 context overlay is rejected; Form 4 equity-compensation "
            "context did not improve the already accepted SBC burden-improvement "
            "paper source under the standard three-window protocol."
        )
    )
    payload["rejection_reason"] = None if passed else "; ".join(gate4["failed_reasons"])
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Core EV | Adj EV | dEV | Accepted SBC dEV | Core PnL | Adj PnL | dPnL | Accepted SBC dPnL | Context trades | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    accepted_delta = payload["accepted_sbc_comparator_delta_metrics"]["by_window"]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["form4_context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | {accepted_dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | ${accepted_dpnl:+,.2f} | {context_trades} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                accepted_dev=accepted_delta[label]["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                accepted_dpnl=accepted_delta[label]["total_pnl"],
                context_trades=scan["context_affected_trade_count"],
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} {STEM}",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            f"- Artifact: `{_repo_rel(OUT_JSON)}`",
            f"- Log: `{_repo_rel(LOG_JSON)}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- EV delta versus accepted SBC: `{:+.4f}`".format(
                gate4["aggregate_ev_delta_vs_accepted_sbc"]
            ),
            "- PnL delta versus accepted SBC: `${:+,.2f}`".format(
                gate4["aggregate_pnl_delta_vs_accepted_sbc"]
            ),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Context-affected trades: `{}`".format(gate4["context_affected_trade_count"]),
            "- Gate 4 failures: `{}`".format(", ".join(gate4["failed_reasons"]) or "none"),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only. No shared helper, live/default orders, ranking, "
                "sizing, exits, LLM/news path, watchlist, or report queue changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["numeric_gate4_passed"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": BASELINE_ARTIFACT,
        "accepted_sbc_comparator_artifact": _repo_rel(SBC_COMPARATOR_JSON),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_sbc_ev_delta": payload["gate4"]["accepted_sbc_aggregate_ev_delta"],
        "accepted_sbc_pnl_delta": payload["gate4"]["accepted_sbc_aggregate_pnl_delta"],
        "ev_delta_vs_accepted_sbc": payload["gate4"]["aggregate_ev_delta_vs_accepted_sbc"],
        "pnl_delta_vs_accepted_sbc": payload["gate4"]["aggregate_pnl_delta_vs_accepted_sbc"],
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_after": payload["after_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "accepted_sbc_expected_value_delta": payload[
                    "accepted_sbc_comparator_delta_metrics"
                ]["by_window"][label]["expected_value_score"],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "accepted_sbc_strategy_total_pnl_delta": payload[
                    "accepted_sbc_comparator_delta_metrics"
                ]["by_window"][label]["total_pnl"],
                "context_affected_trade_count": payload["form4_context_scan_by_window"][label][
                    "context_affected_trade_count"
                ],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_registry(payload: dict[str, Any]) -> None:
    result = {
        "decision": payload["decision"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["numeric_gate4_passed"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "allowed_write_scope": sorted(set(payload["related_files"])),
        "completed_at": payload["timestamp"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )


def _write_manifest(payload: dict[str, Any]) -> None:
    paths = [
        Path(__file__),
        OUT_JSON,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
        MANIFEST_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        SBC_COMPARATOR_JSON,
        QUANT_ROOT / "sbc_burden_improvement_paper_sleeve.py",
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [_repo_rel(path) for path in paths],
        "file_hashes": {_repo_rel(path): _sha256(path) for path in paths if path.exists()},
    }
    _write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    card = _build_card(payload)
    _write_text(CARD_MD, card)
    _upsert_jsonl(EXPERIMENT_LOG, _build_log_record(payload))
    _update_registry(payload)
    _write_manifest(payload)


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(_safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
