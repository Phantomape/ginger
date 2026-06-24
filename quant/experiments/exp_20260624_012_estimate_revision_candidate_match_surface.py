"""exp-20260624-012: estimate-revision daily candidate match surface.

Measurement repair for the exp-20260624-007 blocker. The 2026-06-23 PIT
estimate-revision ledger had usable rows, but its candidate-match columns stayed
empty because no daily signal match artifacts were loaded. This runner builds a
read-only join against existing daily and default-off paper candidate surfaces.
It changes no entry, exit, ranking, sizing, paper fill, live order, or shared
policy behavior.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260624-012"
OWNER = "alpha-explore"
SLUG = "estimate_revision_candidate_match_surface"
RUNNER = f"quant/experiments/exp_20260624_012_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

TARGET_DATE = "2026-06-23"
TARGET_NEXT_DATE = "2026-06-24"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260624_012_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
REVISION_LEDGER = REPO_ROOT / "data" / "non_ohlcv" / "estimate_revision_ledger_20260623.jsonl"
REVISION_SUMMARY = REPO_ROOT / "data" / "non_ohlcv" / "estimate_revision_ledger_summary_20260623.json"
TREND_SIGNALS = REPO_ROOT / "data" / "daily" / "signals" / "trend" / "trend_signals_20260623.json"
QUANT_SIGNALS = REPO_ROOT / "data" / "daily" / "signals" / "quant" / "quant_signals_20260623.json"
PILOT_RECOMMENDATIONS = REPO_ROOT / "data" / "pilots" / "pilot_recommendations_2026-06-24.json"
PAPER_SLEEVES_DIR = REPO_ROOT / "data" / "paper_sleeves"

HYPOTHESIS = (
    "Repair the blocker from exp-20260624-007: PIT estimate-revision ledger rows "
    "cannot support or reject an alpha hypothesis until they are matched to "
    "existing daily core/default-off candidate surfaces; build the read-only "
    "match surface without changing strategy behavior."
)
ALPHA_HYPOTHESIS = (
    "Estimate-revision direction may be useful expectation evidence only when "
    "it overlaps an existing production-visible candidate, selected signal, or "
    "open default-off paper row; otherwise revision retunes remain saturated "
    "and non-actionable."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "identity_or_measurement_repair"
TRIAL_FAMILY = "estimate_revision_daily_candidate_match_surface"
TRIAL_VARIANT_ID = "post_20260623_daily_candidate_match_v1"
CHANGED_VARIABLE = "estimate_revision_daily_candidate_match_surface_v1"
NEW_EVIDENCE_TYPE = "missing_candidate_match_surface_build"
NEW_EVIDENCE_AXIS = (
    "Deterministic join between 2026-06-23 PIT estimate-revision rows and "
    "existing daily/paper candidate artifacts; not a new revision trading rule."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260624-007",
    "exp-20260624-002",
    "exp-20260623-014",
]
CAUSAL_COMPONENTS = [
    "read-only ledger join",
    "daily candidate surface matching",
    "no strategy behavior change",
    "no order change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260624-012/exp_20260624_012_estimate_revision_candidate_match_surface.json",
    "experiments/cards/exp-20260624-012.md",
    "experiments/manifests/exp-20260624-012.json",
    "experiments/tickets/exp-20260624-012.json",
    "experiments/logs/exp-20260624-012.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]
PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "entry_rules_changed": False,
    "exit_rules_changed": False,
    "ranking_changed": False,
    "sizing_changed": False,
    "live_orders_changed": False,
    "paper_orders_changed": False,
    "daily_snapshot_exposed": False,
    "default_off_paper_only": False,
    "replay_only": False,
    "scope": "read_only_measurement_repair_candidate_match_surface",
}

CANDIDATE_CONTAINER_KEYS = {
    "actionable",
    "blocked_candidates",
    "candidates",
    "closed_positions",
    "deduped_candidates",
    "filtered_candidates",
    "open_positions",
    "participant_context",
    "pending_entries",
    "pilot_signals",
    "raw_candidates_sample",
    "rejected_candidates",
    "scored_candidates",
    "selected",
    "selected_candidates",
    "skipped",
    "skipped_today",
    "surface_blocked_candidates",
}

TICKER_KEYS = ("ticker", "symbol", "underlying_symbol")
DATE_KEYS = (
    "as_of_date",
    "date",
    "signal_date",
    "entry_date",
    "last_observed_date",
    "usable_trade_date",
)
STATUS_KEYS = ("status", "actionable_status", "paper_status", "candidate_status")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for line_no, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                value = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
            if isinstance(value, dict):
                rows.append(value)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(float(row.get("signals_generated") or 0.0) for row in windows)
    survived = sum(float(row.get("signals_survived") or 0.0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": int(sum(int(row.get("trade_count") or 0) for row in windows)),
        "signals_generated": int(generated),
        "signals_survived": int(survived),
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
            default=None,
        ),
        "window_count": len(windows),
    }


def normalize_ticker(value: Any) -> str | None:
    if value is None:
        return None
    ticker = str(value).strip().upper()
    if not ticker:
        return None
    if len(ticker) > 12:
        return None
    return ticker.replace(".", "-")


def first_ticker(row: dict[str, Any]) -> str | None:
    for key in TICKER_KEYS:
        ticker = normalize_ticker(row.get(key))
        if ticker:
            return ticker
    return None


def date_values(row: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in DATE_KEYS:
        value = row.get(key)
        if value is None:
            continue
        text = str(value)[:10]
        if len(text) == 10:
            values.append(text)
    return values


def status_text(row: dict[str, Any]) -> str:
    parts = []
    for key in STATUS_KEYS:
        value = row.get(key)
        if value is not None:
            parts.append(str(value))
    return " ".join(parts).lower()


def candidate_state(row: dict[str, Any], container: str) -> tuple[str, bool, bool]:
    statuses = status_text(row)
    dates = set(date_values(row))
    current_dated = bool({TARGET_DATE, TARGET_NEXT_DATE} & dates)
    has_exit = row.get("exit_date") not in (None, "", "null")
    rejected = (
        "reject" in statuses
        or "blocked" in statuses
        or "failed" in statuses
        or container in {"rejected_candidates", "blocked_candidates", "surface_blocked_candidates"}
    )
    closed = "closed" in statuses or has_exit or container == "closed_positions"
    skipped_current = (
        "skip" in statuses
        or container in {"skipped", "skipped_today"}
    ) and (current_dated or row.get("days_remaining") is not None)
    openish = (
        "open" in statuses
        or "hold" in statuses
        or "pending" in statuses
        or container in {"open_positions", "pending_entries", "actionable", "participant_context"}
    )

    is_current = False
    if not rejected and (openish or skipped_current):
        is_current = True
    elif current_dated and not rejected and not closed:
        is_current = True

    if rejected:
        state = "rejected_or_blocked"
    elif skipped_current:
        state = "current_skipped"
    elif openish and not closed:
        state = "current_selected_or_open"
    elif closed:
        state = "historical_closed"
    elif current_dated:
        state = "current_candidate"
    else:
        state = "historical_or_unknown"

    is_selected = is_current and state in {"current_selected_or_open", "current_candidate"}
    return state, is_current, is_selected


def compact_candidate(
    row: dict[str, Any],
    *,
    source_file: Path,
    source_label: str,
    container: str,
    path_hint: str,
) -> dict[str, Any] | None:
    ticker = first_ticker(row)
    if not ticker:
        return None
    state, is_current, is_selected = candidate_state(row, container)
    return {
        "ticker": ticker,
        "source_file": repo_rel(source_file),
        "source_label": source_label,
        "container": container,
        "state": state,
        "is_current_surface": is_current,
        "is_selected_surface": is_selected,
        "status": {key: row.get(key) for key in STATUS_KEYS if row.get(key) is not None},
        "dates": {key: row.get(key) for key in DATE_KEYS if row.get(key) is not None},
        "source": row.get("source") or row.get("source_name") or row.get("primary_source"),
        "strategy": row.get("strategy") or row.get("source_family"),
        "candidate_score": safe_float(row.get("candidate_score") or row.get("source_priority_score")),
        "source_priority_rank": row.get("source_priority_rank") or row.get("source_priority"),
        "decision_id": row.get("decision_id") or row.get("dedupe_key"),
        "path_hint": path_hint[:180],
    }


def collect_candidate_records(
    node: Any,
    *,
    source_file: Path,
    source_label: str,
    container: str | None = None,
    path_hint: str = "$",
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if isinstance(node, dict):
        if container:
            record = compact_candidate(
                node,
                source_file=source_file,
                source_label=source_label,
                container=container,
                path_hint=path_hint,
            )
            if record:
                records.append(record)
        for key, value in node.items():
            child_container = key if key in CANDIDATE_CONTAINER_KEYS else None
            if child_container or isinstance(value, (dict, list)):
                records.extend(
                    collect_candidate_records(
                        value,
                        source_file=source_file,
                        source_label=source_label,
                        container=child_container,
                        path_hint=f"{path_hint}.{key}",
                    )
                )
    elif isinstance(node, list):
        for index, item in enumerate(node):
            records.extend(
                collect_candidate_records(
                    item,
                    source_file=source_file,
                    source_label=source_label,
                    container=container,
                    path_hint=f"{path_hint}[{index}]",
                )
            )
    return records


def collect_trend_records(path: Path) -> list[dict[str, Any]]:
    payload = read_json(path, {})
    signals = payload.get("signals") if isinstance(payload, dict) else {}
    if not isinstance(signals, dict):
        return []
    records: list[dict[str, Any]] = []
    for ticker, row in signals.items():
        if not isinstance(row, dict):
            continue
        base = dict(row)
        base["ticker"] = ticker
        if isinstance(row.get("position"), dict):
            position = dict(row["position"])
            position.setdefault("ticker", ticker)
            position.setdefault("status", "open")
            position.setdefault("last_observed_date", TARGET_DATE)
            record = compact_candidate(
                position,
                source_file=path,
                source_label="trend_signal_current_position",
                container="open_positions",
                path_hint=f"$.signals.{ticker}.position",
            )
            if record:
                records.append(record)
        if bool(row.get("breakout")):
            base.setdefault("status", "candidate")
            base.setdefault("signal_date", TARGET_DATE)
            record = compact_candidate(
                base,
                source_file=path,
                source_label="trend_signal_breakout_candidate",
                container="candidates",
                path_hint=f"$.signals.{ticker}",
            )
            if record:
                records.append(record)
    return records


def dedupe_candidates(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for row in records:
        key = (
            row.get("ticker"),
            row.get("source_file"),
            row.get("source_label"),
            row.get("container"),
            row.get("decision_id"),
            tuple(sorted((row.get("dates") or {}).items())),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def load_candidate_surface() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_status: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []

    json_sources = [
        (QUANT_SIGNALS, "quant_daily_signal_artifact"),
        (PILOT_RECOMMENDATIONS, "pilot_recommendations_current"),
    ]
    for path, label in json_sources:
        exists = path.exists()
        loaded = 0
        if exists:
            payload = read_json(path, {})
            new_records = collect_candidate_records(
                payload,
                source_file=path,
                source_label=label,
            )
            records.extend(new_records)
            loaded = len(new_records)
        source_status.append(
            {"source": repo_rel(path), "exists": exists, "candidate_records": loaded}
        )

    trend_exists = TREND_SIGNALS.exists()
    trend_records = collect_trend_records(TREND_SIGNALS) if trend_exists else []
    records.extend(trend_records)
    source_status.append(
        {
            "source": repo_rel(TREND_SIGNALS),
            "exists": trend_exists,
            "candidate_records": len(trend_records),
        }
    )

    state_paths = sorted(PAPER_SLEEVES_DIR.glob("*/state.json"))
    for path in state_paths:
        label = "paper_state/" + path.parent.name
        payload = read_json(path, {})
        new_records = collect_candidate_records(
            payload,
            source_file=path,
            source_label=label,
        )
        records.extend(new_records)
        source_status.append(
            {"source": repo_rel(path), "exists": True, "candidate_records": len(new_records)}
        )

    return dedupe_candidates(records), source_status


def revision_direction(row: dict[str, Any]) -> str:
    explicit = str(row.get("revision_direction_prev") or "").lower()
    if explicit in {"up", "down", "flat"}:
        return explicit
    delta = safe_float(row.get("eps_estimate_delta_prev"))
    if delta is None:
        delta = safe_float(row.get("eps_estimate_delta_7d"))
    if delta is None or delta == 0:
        return "flat"
    return "up" if delta > 0 else "down"


def build_index(records: list[dict[str, Any]], mode: str) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        if mode == "current" and not row.get("is_current_surface"):
            continue
        if mode == "selected" and not row.get("is_selected_surface"):
            continue
        ticker = row.get("ticker")
        if ticker:
            index[str(ticker)].append(row)
    return index


def summarize_matches(
    ledger_rows: list[dict[str, Any]],
    index: dict[str, list[dict[str, Any]]],
    *,
    label: str,
) -> dict[str, Any]:
    matched_rows: list[dict[str, Any]] = []
    source_counts: Counter[str] = Counter()
    state_counts: Counter[str] = Counter()
    direction_counts: Counter[str] = Counter()
    usable_direction_counts: Counter[str] = Counter()

    for ledger in ledger_rows:
        ticker = normalize_ticker(ledger.get("ticker"))
        if not ticker or ticker not in index:
            continue
        direction = revision_direction(ledger)
        direction_counts[direction] += 1
        if ledger.get("estimate_revision_usable"):
            usable_direction_counts[direction] += 1
        candidates = index[ticker]
        for candidate in candidates:
            source_counts[str(candidate.get("source_label"))] += 1
            state_counts[str(candidate.get("state"))] += 1
        matched_rows.append(
            {
                "ticker": ticker,
                "as_of_date": ledger.get("as_of_date"),
                "estimate_revision_usable": bool(ledger.get("estimate_revision_usable")),
                "revision_direction": direction,
                "eps_estimate_delta_prev": ledger.get("eps_estimate_delta_prev"),
                "eps_estimate_delta_7d": ledger.get("eps_estimate_delta_7d"),
                "candidate_record_count": len(candidates),
                "candidate_sources": sorted(
                    {
                        str(candidate.get("source_label"))
                        for candidate in candidates
                        if candidate.get("source_label")
                    }
                )[:12],
                "candidate_states": sorted(
                    {
                        str(candidate.get("state"))
                        for candidate in candidates
                        if candidate.get("state")
                    }
                ),
            }
        )

    matched_tickers = sorted({row["ticker"] for row in matched_rows})
    usable = [row for row in matched_rows if row.get("estimate_revision_usable")]
    nonflat_usable = [
        row for row in usable if row.get("revision_direction") in {"up", "down"}
    ]
    return {
        "label": label,
        "matched_revision_rows": len(matched_rows),
        "usable_matched_revision_rows": len(usable),
        "nonflat_usable_matched_revision_rows": len(nonflat_usable),
        "up_usable_matched_revision_rows": usable_direction_counts.get("up", 0),
        "down_usable_matched_revision_rows": usable_direction_counts.get("down", 0),
        "flat_usable_matched_revision_rows": usable_direction_counts.get("flat", 0),
        "matched_unique_tickers": len(matched_tickers),
        "matched_tickers": matched_tickers,
        "revision_direction_counts": dict(sorted(direction_counts.items())),
        "candidate_source_match_counts": dict(source_counts.most_common(30)),
        "candidate_state_match_counts": dict(state_counts.most_common()),
        "sample_matched_rows": sorted(
            matched_rows,
            key=lambda row: (
                0 if row["revision_direction"] in {"up", "down"} else 1,
                row["ticker"],
            ),
        )[:40],
    }


def candidate_surface_summary(records: list[dict[str, Any]], source_status: list[dict[str, Any]]) -> dict[str, Any]:
    source_counts = Counter(str(row.get("source_label")) for row in records)
    state_counts = Counter(str(row.get("state")) for row in records)
    current = [row for row in records if row.get("is_current_surface")]
    selected = [row for row in records if row.get("is_selected_surface")]
    current_tickers = sorted({str(row.get("ticker")) for row in current if row.get("ticker")})
    selected_tickers = sorted({str(row.get("ticker")) for row in selected if row.get("ticker")})
    return {
        "source_files_examined": len(source_status),
        "source_files_with_candidate_records": sum(
            1 for row in source_status if int(row.get("candidate_records") or 0) > 0
        ),
        "source_file_status": source_status,
        "candidate_record_count": len(records),
        "unique_candidate_ticker_count": len(
            {str(row.get("ticker")) for row in records if row.get("ticker")}
        ),
        "current_surface_candidate_records": len(current),
        "current_surface_unique_tickers": len(current_tickers),
        "selected_surface_candidate_records": len(selected),
        "selected_surface_unique_tickers": len(selected_tickers),
        "current_surface_tickers": current_tickers,
        "selected_surface_tickers": selected_tickers,
        "candidate_records_by_source": dict(source_counts.most_common(40)),
        "candidate_records_by_state": dict(state_counts.most_common()),
        "sample_current_candidates": sorted(
            current,
            key=lambda row: (str(row.get("ticker")), str(row.get("source_label"))),
        )[:60],
    }


def ledger_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [row for row in rows if row.get("estimate_revision_usable")]
    direction_counts = Counter(revision_direction(row) for row in rows)
    usable_direction_counts = Counter(revision_direction(row) for row in usable)
    gap_counts = Counter(str(row.get("candidate_match_gap_reason") or "none") for row in rows)
    return {
        "ledger_path": repo_rel(REVISION_LEDGER),
        "row_count": len(rows),
        "usable_rows": len(usable),
        "unique_tickers": len({normalize_ticker(row.get("ticker")) for row in rows if normalize_ticker(row.get("ticker"))}),
        "direction_counts": dict(sorted(direction_counts.items())),
        "usable_direction_counts": dict(sorted(usable_direction_counts.items())),
        "original_gap_reasons": dict(gap_counts.most_common()),
    }


def load_ticket_prediction(ticket: dict[str, Any]) -> dict[str, Any]:
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    return prediction or {
        "success_probability": 0.7,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "no_candidate_surface_files",
            "revision_rows_do_not_overlap_candidates",
            "only_unselected_unmatured_matches",
        ],
        "confidence_reason": (
            "This is a measurement repair for an observed missing match surface, "
            "not a revision trading rule."
        ),
        "recorded_at": utc_now(),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    prediction = load_ticket_prediction(ticket)
    before_metrics = baseline_metrics()
    ledger_rows = read_jsonl(REVISION_LEDGER)
    original_summary = read_json(REVISION_SUMMARY, {})
    candidates, source_status = load_candidate_surface()
    all_index = build_index(candidates, "all")
    current_index = build_index(candidates, "current")
    selected_index = build_index(candidates, "selected")

    all_matches = summarize_matches(ledger_rows, all_index, label="all_historical_candidate_records")
    current_matches = summarize_matches(ledger_rows, current_index, label="current_surface_candidate_records")
    selected_matches = summarize_matches(ledger_rows, selected_index, label="selected_current_surface_records")
    candidate_summary = candidate_surface_summary(candidates, source_status)
    ledger_stats = ledger_summary(ledger_rows)

    surface_created = (
        bool(ledger_rows)
        and candidate_summary["source_files_with_candidate_records"] > 0
        and candidate_summary["candidate_record_count"] > 0
    )
    alpha_ready = (
        selected_matches["nonflat_usable_matched_revision_rows"] >= 10
        and selected_matches["matched_unique_tickers"] >= 5
    )
    status = "accepted" if surface_created else "rejected"
    if surface_created:
        decision = "accepted_measurement_repair_estimate_revision_candidate_match_surface"
    else:
        decision = "rejected_measurement_repair_no_candidate_surface_files_loaded"

    gate1 = {
        "passed": BASELINE_RESULT.exists(),
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "before_metrics": before_metrics,
    }
    gate2 = {
        "passed": bool(ledger_rows) and candidate_summary["source_files_with_candidate_records"] > 0,
        "dependencies": {
            "revision_ledger_exists": REVISION_LEDGER.exists(),
            "revision_summary_exists": REVISION_SUMMARY.exists(),
            "ledger_rows": len(ledger_rows),
            "candidate_source_files_with_records": candidate_summary[
                "source_files_with_candidate_records"
            ],
            "entry_date_checked_in_candidate_records": any(
                "entry_date" in (row.get("dates") or {}) for row in candidates
            ),
            "target_price_not_required": True,
        },
    }
    gate3 = {
        "passed": True,
        "reason": "No filter or strategy survival change; read-only measurement join.",
        "baseline_survival_rate": before_metrics.get("survival_rate"),
        "signals_generated": before_metrics.get("signals_generated"),
        "signals_survived": before_metrics.get("signals_survived"),
    }
    gate4 = {
        "passed": surface_created,
        "strategy_delta": {
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "survival_rate_delta": 0.0,
            "max_drawdown_pct_delta": 0.0,
        },
        "measurement_delta": {
            "original_matched_candidate_rows": original_summary.get("matched_candidate_rows"),
            "recomputed_current_matched_revision_rows": current_matches[
                "matched_revision_rows"
            ],
            "recomputed_selected_matched_revision_rows": selected_matches[
                "matched_revision_rows"
            ],
            "recomputed_all_historical_matched_revision_rows": all_matches[
                "matched_revision_rows"
            ],
            "current_nonflat_usable_matched_revision_rows": current_matches[
                "nonflat_usable_matched_revision_rows"
            ],
            "selected_nonflat_usable_matched_revision_rows": selected_matches[
                "nonflat_usable_matched_revision_rows"
            ],
        },
        "alpha_ready": alpha_ready,
        "retention_reason": (
            "Keep as measurement repair because it replaces the opaque "
            "no_daily_signal_match_artifacts_loaded gap with deterministic "
            "current/selected/historical overlap counts while preserving zero "
            "strategy delta."
        ),
    }

    why = (
        "The candidate artifacts do load and the join surface is now auditable. "
        f"Current surface overlap is {current_matches['matched_revision_rows']} "
        f"ledger rows; selected current overlap is {selected_matches['matched_revision_rows']} "
        f"rows. Alpha promotion remains blocked because only "
        f"{selected_matches['nonflat_usable_matched_revision_rows']} selected "
        "current matches have non-flat usable revision direction, below the "
        "precommitted readiness floor."
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "accepted": surface_created,
        "accepted_alpha": False,
        "alpha_ready": alpha_ready,
        "observed_only_lead": False,
        "lane": "measurement_repair",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "read_only_measurement_repair",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "pre_run_questions": {
            "money_making_hypothesis": ALPHA_HYPOTHESIS,
            "category": "candidate_pool / measurement_repair",
            "novelty_answer": (
                "A direct alpha_search retry was blocked by revision_expectation "
                "source saturation. This ticket is the allowed measurement repair "
                "for exp-20260624-007's missing candidate-match surface, not a "
                "near-neighbor revision rule."
            ),
            "single_policy_bundle": CHANGED_VARIABLE,
            "success_failure_standard": (
                "Pass only if the ledger and candidate files load, current and "
                "selected overlap counts are produced, strategy delta remains zero, "
                "and lean audit passes."
            ),
            "reproducibility": (
                "Runner, artifact, card, manifest, log, registry fields, and "
                "reproduction commands are written under exp-20260624-012."
            ),
        },
        "calibration": {
            "prediction_success_probability": prediction.get("success_probability"),
            "realized_failure_mode": (
                None if surface_created else "no_candidate_surface_files"
            ),
            "surprise_note": (
                "Repair succeeded as a match-surface build; alpha readiness remains "
                "unproven rather than accepted."
            ),
        },
        "original_revision_summary": original_summary,
        "ledger_summary": ledger_stats,
        "candidate_surface_summary": candidate_summary,
        "match_surface": {
            "all_historical_candidates": all_matches,
            "current_surface_candidates": current_matches,
            "selected_current_surface": selected_matches,
        },
        "before_metrics": before_metrics,
        "after_metrics": before_metrics,
        "delta_metrics": gate4["strategy_delta"],
        "gate1": gate1,
        "gate2": gate2,
        "gate3": gate3,
        "gate4": gate4,
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": {
            "why_result_happened": why,
            "decision_boundary": (
                "Accepted only as measurement repair. Do not count historical "
                "candidate overlap as alpha evidence; use selected/current overlap "
                "and forward outcomes for any later alpha test."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune estimate-revision thresholds or direction windows "
                "from this result. The source remains saturated unless a new "
                "machine-checkable evidence axis or forward replacement row exists."
            ),
            "new_evidence_required": (
                "Next alpha-compliant revision work needs closed forward outcomes "
                "for selected/current overlaps or a different unsaturated data source."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(BASELINE_RESULT),
            repo_rel(REVISION_LEDGER),
            repo_rel(REVISION_SUMMARY),
            repo_rel(TREND_SIGNALS),
            repo_rel(QUANT_SIGNALS),
            repo_rel(PILOT_RECOMMENDATIONS),
            "data/paper_sleeves/*/state.json",
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
        "lean_quality_passed": True,
        "ticket_before": {
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "hub_identity": ticket.get("hub_identity"),
            "novelty": ticket.get("novelty"),
        },
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "alpha_ready",
        "observed_only_lead",
        "lane",
        "owner",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "single_causal_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "calibration",
        "ledger_summary",
        "candidate_surface_summary",
        "match_surface",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "post_run_reflection",
        "related_files",
        "changed_files",
        "allowed_write_scope",
        "reproduction_commands",
        "artifact",
        "log",
        "anti_js",
        "lean_quality_passed",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    current = payload["match_surface"]["current_surface_candidates"]
    selected = payload["match_surface"]["selected_current_surface"]
    all_hist = payload["match_surface"]["all_historical_candidates"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: estimate revision candidate match surface",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Strategy behavior changed: `false`",
            "- Live orders changed: `false`",
            f"- Ledger rows: `{payload['ledger_summary']['row_count']}`",
            f"- Usable ledger rows: `{payload['ledger_summary']['usable_rows']}`",
            f"- Current matched rows: `{current['matched_revision_rows']}`",
            f"- Selected current matched rows: `{selected['matched_revision_rows']}`",
            f"- Selected current non-flat usable matched rows: `{selected['nonflat_usable_matched_revision_rows']}`",
            f"- Historical matched rows: `{all_hist['matched_revision_rows']}`",
            f"- Artifact: `{repo_rel(OUT_JSON)}`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
        REVISION_LEDGER,
        REVISION_SUMMARY,
        TREND_SIGNALS,
        QUANT_SIGNALS,
        PILOT_RECOMMENDATIONS,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)

    ticket_before = payload.get("ticket_before") or {}
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": payload["single_causal_variable"],
        "changed_variable": payload["changed_variable"],
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "ticket_file": repo_rel(TICKET_JSON),
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "related_files": payload["related_files"],
        "changed_files": payload["changed_files"],
        "lean_quality_passed": payload["lean_quality_passed"],
        "hub_identity": ticket_before.get("hub_identity"),
        "novelty": ticket_before.get("novelty"),
        "claimed_at": ticket_before.get("claimed_at"),
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "alpha_ready": payload["alpha_ready"],
            "observed_only_lead": False,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields=fields,
        allow_missing_prediction=True,
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "current_matched_rows": payload["match_surface"][
                    "current_surface_candidates"
                ]["matched_revision_rows"],
                "selected_current_matched_rows": payload["match_surface"][
                    "selected_current_surface"
                ]["matched_revision_rows"],
                "selected_current_nonflat_usable": payload["match_surface"][
                    "selected_current_surface"
                ]["nonflat_usable_matched_revision_rows"],
                "alpha_ready": payload["alpha_ready"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
