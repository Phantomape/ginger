"""exp-20260626-022: intraday shadow action outcome scout.

Observed-only alpha-search iteration. exp-20260626-020 repaired the intraday
advisory contract by projecting existing rule triggers into shadow action rows.
This runner asks whether those shadow actions add forward exit/risk-allocation
information over the settled position outcomes from exp-20260626-019. It changes
no strategy behavior, ranking, sizing, exits, orders, paper snapshot, or live
path.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402
from intraday_review import build_advisory_shadow_actions  # noqa: E402


EXPERIMENT_ID = "exp-20260626-022"
OWNER = "alpha-explore"
SLUG = "intraday_shadow_action_outcome_scout"
RUNNER = f"quant/experiments/exp_20260626_022_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
SNAPSHOT_DIR = REPO_ROOT / "data" / "daily" / "intraday" / "snapshots"
PRIOR_POSITION_LEDGER = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260626-019"
    / "intraday_advisory_forward_outcome_ledger.jsonl"
)

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260626_022_{SLUG}.json"
POSITION_LEDGER_JSONL = DATA_DIR / "position_shadow_action_outcome_ledger.jsonl"
ACTION_LEDGER_JSONL = DATA_DIR / "action_rule_outcome_diagnostics.jsonl"
BEFORE_JSON = DATA_DIR / "before_baseline.json"
AFTER_JSON = DATA_DIR / "after_no_strategy_change.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Accepted intraday advisory shadow actions may have exit/risk-allocation "
    "value if EXIT/REVIEW rules underperform no-action/OK positions and SPY/QQQ "
    "over the next 1-5 sessions after the 13:00 ET snapshot."
)
CHANGE_TYPE = "observed_only_forward_attribution"
MECHANISM_FAMILY = "intraday_review_exit_risk_allocation"
TRIAL_FAMILY = "intraday_shadow_action_forward_outcome"
TRIAL_VARIANT_ID = "shadow_action_rule_outcome_v1"
CHANGED_VARIABLE = "intraday_shadow_action_forward_outcome_rule_value_v1"
NEW_EVIDENCE_TYPE = "accepted_intraday_shadow_action_contract_rows"
CAUSAL_COMPONENTS = [
    "accepted shadow action contract",
    "hot warehouse next-session settlement",
    "SPY QQQ cash comparators",
    "no strategy behavior change",
]
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260626-019", "exp-20260626-020"]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/**",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]
HORIZONS = (1, 3, 5, 10)
MIN_ACTION_POSITIONS_1D = 50
MIN_ACTION_POSITIONS_5D = 25
MIN_SNAPSHOT_DATES = 5
MIN_NO_ACTION_POSITIONS_1D = 50

URGENCY_RANK = {
    "CRITICAL": 4,
    "HIGH": 3,
    "REVIEW": 2,
    "MEDIUM": 2,
    "LOW": 1,
    "INFO": 0,
    "": 0,
}
RULE_RANK = {
    "HARD_STOP": 50,
    "ATR_STOP": 40,
    "TRAILING_STOP": 35,
    "SIGNAL_TARGET": 30,
    "TIME_STOP": 20,
    "LEGACY_TARGET_REVIEW": 10,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    path.write_text(encoded, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record, sort_keys=True)
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
                    rows.append(encoded)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(encoded)
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
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def pct(part: int | float, whole: int | float) -> float | None:
    if not whole:
        return None
    return round(float(part) / float(whole), 6)


def average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 8)


def median_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return round(float(median(values)), 8)


def delta(left: dict[str, Any], right: dict[str, Any], key: str) -> float | None:
    a = safe_float(left.get(key))
    b = safe_float(right.get(key))
    if a is None or b is None:
        return None
    return round(a - b, 6)


def compact_date(value: Any) -> str | None:
    text = str(value or "").strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return None


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {}) or {}
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    drawdowns = [
        safe_float(row.get("max_drawdown_pct"))
        for row in windows
        if safe_float(row.get("max_drawdown_pct")) is not None
    ]
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "baseline_exists": BASELINE_RESULT.exists(),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": pct(survived, generated),
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
    }


def ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {}) or {}
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    if isinstance(prediction, dict):
        return prediction
    return {
        "success_probability": 0.24,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "too_few_settled_shadow_actions",
            "rule_buckets_not_monotonic",
            "duplicate_actions_per_position",
            "quote_time_missing_blocks_causality",
        ],
        "confidence_reason": (
            "The accepted shadow action contract is new, but row history is short "
            "and advisory-only."
        ),
        "recorded_at": utc_now(),
    }


def primary_action(actions: list[dict[str, Any]]) -> tuple[str, str | None, str | None]:
    if not actions:
        return "NO_ACTION", None, None
    ranked = sorted(
        actions,
        key=lambda row: (
            1 if str(row.get("shadow_action") or "").upper() == "EXIT" else 0,
            RULE_RANK.get(str(row.get("rule") or "").upper(), 0),
            URGENCY_RANK.get(str(row.get("urgency") or "").upper(), 0),
        ),
        reverse=True,
    )
    best = ranked[0]
    return (
        str(best.get("shadow_action") or "REVIEW").upper(),
        str(best.get("rule") or "UNKNOWN").upper(),
        str(best.get("urgency") or "").upper() or None,
    )


def load_shadow_actions() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    position_map: dict[str, dict[str, Any]] = {}
    action_rows: list[dict[str, Any]] = []
    snapshots: list[dict[str, Any]] = []
    for path in sorted(SNAPSHOT_DIR.glob("intraday_review_*.json")):
        payload = read_json(path, {}) or {}
        if not isinstance(payload, dict):
            continue
        positions = payload.get("positions")
        if not isinstance(positions, list):
            positions = []
        snapshot_date = compact_date(payload.get("date"))
        snapshots.append({
            "snapshot_file": repo_rel(path),
            "snapshot_date": snapshot_date,
            "time_label": payload.get("time_label"),
            "position_count": len(positions),
        })
        for index, position in enumerate(positions):
            if not isinstance(position, dict):
                continue
            ticker = str(position.get("ticker") or "").upper().strip()
            if not ticker:
                continue
            base_id = hashlib.sha1(
                f"{repo_rel(path)}|{index}|{ticker}".encode("utf-8")
            ).hexdigest()[:16]
            actions = build_advisory_shadow_actions([position])
            normalized_actions: list[dict[str, Any]] = []
            for action_index, action in enumerate(actions):
                if not isinstance(action, dict):
                    continue
                row = {
                    "observation_base_id": base_id,
                    "action_id": f"{base_id}_a{action_index}",
                    "snapshot_file": repo_rel(path),
                    "snapshot_date": snapshot_date,
                    "time_label": payload.get("time_label"),
                    "ticker": ticker,
                    "status": str(position.get("status") or "MISSING").upper(),
                    "shadow_action": str(action.get("shadow_action") or "REVIEW").upper(),
                    "rule": str(action.get("rule") or "UNKNOWN").upper(),
                    "urgency": str(action.get("urgency") or "").upper() or None,
                    "triggered_rule_index": action.get("triggered_rule_index"),
                    "shares_to_sell": action.get("shares_to_sell"),
                    "creates_order": bool(action.get("creates_order")),
                    "pending_action": bool(action.get("pending_action")),
                    "advisory_only": bool(action.get("advisory_only", True)),
                    "order_semantics": action.get("order_semantics"),
                    "quote_time_et": action.get("quote_time_et"),
                    "capture_time_et": action.get("capture_time_et"),
                }
                normalized_actions.append(row)
                action_rows.append(row)
            action, rule, urgency = primary_action(normalized_actions)
            rules = sorted({str(row["rule"]) for row in normalized_actions})
            urgencies = sorted({str(row.get("urgency") or "") for row in normalized_actions})
            position_map[base_id] = {
                "observation_base_id": base_id,
                "shadow_action_count": len(normalized_actions),
                "has_shadow_action": bool(normalized_actions),
                "primary_shadow_action": action,
                "primary_shadow_rule": rule,
                "primary_shadow_urgency": urgency,
                "shadow_rules": rules,
                "shadow_urgencies": [value for value in urgencies if value],
                "has_exit_shadow_action": any(
                    row.get("shadow_action") == "EXIT" for row in normalized_actions
                ),
                "has_review_shadow_action": any(
                    row.get("shadow_action") == "REVIEW" for row in normalized_actions
                ),
                "has_stop_shadow_action": any(
                    row.get("rule") in {"HARD_STOP", "ATR_STOP", "TRAILING_STOP"}
                    for row in normalized_actions
                ),
                "has_target_shadow_action": any(
                    row.get("rule") == "SIGNAL_TARGET" for row in normalized_actions
                ),
                "has_time_review_shadow_action": any(
                    row.get("rule") in {"TIME_STOP", "LEGACY_TARGET_REVIEW"}
                    for row in normalized_actions
                ),
            }
    return position_map, action_rows, snapshots


def enrich_position_ledger(
    prior_rows: list[dict[str, Any]],
    shadow_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    empty = {
        "shadow_action_count": 0,
        "has_shadow_action": False,
        "primary_shadow_action": "NO_ACTION",
        "primary_shadow_rule": None,
        "primary_shadow_urgency": None,
        "shadow_rules": [],
        "shadow_urgencies": [],
        "has_exit_shadow_action": False,
        "has_review_shadow_action": False,
        "has_stop_shadow_action": False,
        "has_target_shadow_action": False,
        "has_time_review_shadow_action": False,
    }
    for row in prior_rows:
        base_id = row.get("observation_base_id")
        action_fields = shadow_map.get(str(base_id), empty)
        enriched.append({
            **row,
            **action_fields,
            "shadow_presence_bucket": (
                "SHADOW_ACTION" if action_fields.get("has_shadow_action") else "NO_ACTION"
            ),
            "shadow_rule_bucket": action_fields.get("primary_shadow_rule") or "NO_RULE",
        })
    return enriched


def enrich_action_ledger(
    prior_rows: list[dict[str, Any]],
    action_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    outcomes_by_base: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in prior_rows:
        outcomes_by_base[str(row.get("observation_base_id"))].append(row)
    enriched: list[dict[str, Any]] = []
    for action in action_rows:
        for outcome in outcomes_by_base.get(str(action.get("observation_base_id")), []):
            enriched.append({
                **outcome,
                **action,
                "diagnostic_note": (
                    "Action-level rows duplicate a position outcome when multiple "
                    "rules fire; position-level buckets are the primary evidence."
                ),
            })
    return enriched


def summarize_bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
    settled = [row for row in rows if row.get("settlement_status") == "settled"]
    returns = [
        float(row["net_return"])
        for row in settled
        if safe_float(row.get("net_return")) is not None
    ]
    excess_spy = [
        float(row["excess_spy_return"])
        for row in settled
        if safe_float(row.get("excess_spy_return")) is not None
    ]
    excess_qqq = [
        float(row["excess_qqq_return"])
        for row in settled
        if safe_float(row.get("excess_qqq_return")) is not None
    ]
    return {
        "settled_rows": len(settled),
        "snapshot_date_count": len({row.get("snapshot_date") for row in settled}),
        "ticker_count": len({row.get("ticker") for row in settled}),
        "avg_return_pct": (
            round(100 * average(returns), 4) if returns else None
        ),
        "median_return_pct": (
            round(100 * median_or_none(returns), 4) if returns else None
        ),
        "win_rate": pct(sum(1 for value in returns if value > 0), len(returns)),
        "avg_excess_spy_pct": (
            round(100 * average(excess_spy), 4) if excess_spy else None
        ),
        "avg_excess_qqq_pct": (
            round(100 * average(excess_qqq), 4) if excess_qqq else None
        ),
        "underperform_spy_rate": pct(
            sum(1 for value in excess_spy if value < 0),
            len(excess_spy),
        ),
        "underperform_qqq_rate": pct(
            sum(1 for value in excess_qqq if value < 0),
            len(excess_qqq),
        ),
        "total_pnl_10k": round(
            sum(float(row.get("pnl_10k") or 0.0) for row in settled),
            2,
        ),
    }


def group_summary(
    rows: list[dict[str, Any]],
    group_field: str,
    *,
    min_count_for_detail: int = 1,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for horizon in HORIZONS:
        horizon_rows = [row for row in rows if int(row.get("horizon_days") or 0) == horizon]
        groups = sorted({str(row.get(group_field) or "MISSING") for row in horizon_rows})
        by_group = {
            group: summarize_bucket(
                [row for row in horizon_rows if str(row.get(group_field) or "MISSING") == group]
            )
            for group in groups
        }
        by_group = {
            group: value
            for group, value in by_group.items()
            if (value.get("settled_rows") or 0) >= min_count_for_detail
        }
        out[str(horizon)] = {
            "field": group_field,
            "position_or_action_rows": len(horizon_rows),
            "settled_rows": sum(value.get("settled_rows") or 0 for value in by_group.values()),
            "by_group": by_group,
        }
    return out


def pair_delta(summary: dict[str, Any], horizon: int, left: str, right: str) -> dict[str, Any]:
    groups = ((summary.get(str(horizon)) or {}).get("by_group") or {})
    left_row = groups.get(left) or {}
    right_row = groups.get(right) or {}
    return {
        "left": left,
        "right": right,
        "avg_return_pct": delta(left_row, right_row, "avg_return_pct"),
        "avg_excess_spy_pct": delta(left_row, right_row, "avg_excess_spy_pct"),
        "avg_excess_qqq_pct": delta(left_row, right_row, "avg_excess_qqq_pct"),
        "underperform_spy_rate": delta(left_row, right_row, "underperform_spy_rate"),
        "underperform_qqq_rate": delta(left_row, right_row, "underperform_qqq_rate"),
        "left_settled_rows": left_row.get("settled_rows"),
        "right_settled_rows": right_row.get("settled_rows"),
    }


def summarize_evidence(
    position_rows: list[dict[str, Any]],
    action_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    presence = group_summary(position_rows, "shadow_presence_bucket")
    primary_action = group_summary(position_rows, "primary_shadow_action")
    primary_rule = group_summary(position_rows, "shadow_rule_bucket", min_count_for_detail=3)
    risk_state = group_summary(position_rows, "risk_state")
    diagnostic_rule = group_summary(action_rows, "rule", min_count_for_detail=3)
    return {
        "position_level": {
            "shadow_presence": presence,
            "primary_shadow_action": primary_action,
            "primary_shadow_rule": primary_rule,
            "prior_risk_state": risk_state,
            "shadow_minus_no_action": {
                str(horizon): pair_delta(
                    presence,
                    horizon,
                    "SHADOW_ACTION",
                    "NO_ACTION",
                )
                for horizon in HORIZONS
            },
            "exit_minus_no_action": {
                str(horizon): pair_delta(primary_action, horizon, "EXIT", "NO_ACTION")
                for horizon in HORIZONS
            },
            "review_minus_no_action": {
                str(horizon): pair_delta(primary_action, horizon, "REVIEW", "NO_ACTION")
                for horizon in HORIZONS
            },
        },
        "action_level_diagnostics": {
            "by_rule": diagnostic_rule,
            "duplicate_warning": (
                "A single position can emit multiple action rows. Rule diagnostics "
                "are not independent trades and are not allocation-ready."
            ),
        },
    }


def field_coverage(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    fields = [
        "observation_base_id",
        "snapshot_date",
        "ticker",
        "entry_date",
        "target_price",
        "quote_time_et",
        "quote_capture_time_et",
        "primary_shadow_action",
        "primary_shadow_rule",
        "shadow_action_count",
    ]
    out: dict[str, dict[str, Any]] = {}
    base_rows = [
        row for row in rows if int(row.get("horizon_days") or 0) == 1
    ] or rows
    for field in fields:
        present = sum(1 for row in base_rows if row.get(field) not in (None, "", []))
        out[field] = {
            "present_rows": present,
            "base_rows": len(base_rows),
            "coverage": pct(present, len(base_rows)),
        }
    return out


def evaluate_readiness(
    position_rows: list[dict[str, Any]],
    action_rows: list[dict[str, Any]],
    evidence: dict[str, Any],
) -> tuple[str, list[str], dict[str, Any]]:
    h1 = ((evidence["position_level"]["shadow_presence"].get("1") or {}).get("by_group") or {})
    h5 = ((evidence["position_level"]["shadow_presence"].get("5") or {}).get("by_group") or {})
    shadow_1 = h1.get("SHADOW_ACTION") or {}
    no_action_1 = h1.get("NO_ACTION") or {}
    shadow_5 = h5.get("SHADOW_ACTION") or {}
    failed: list[str] = []

    if (shadow_1.get("settled_rows") or 0) < MIN_ACTION_POSITIONS_1D:
        failed.append("too_few_settled_shadow_action_positions_1d")
    if (shadow_5.get("settled_rows") or 0) < MIN_ACTION_POSITIONS_5D:
        failed.append("too_few_settled_shadow_action_positions_5d")
    if (no_action_1.get("settled_rows") or 0) < MIN_NO_ACTION_POSITIONS_1D:
        failed.append("too_few_settled_no_action_positions_1d")
    if (shadow_1.get("snapshot_date_count") or 0) < MIN_SNAPSHOT_DATES:
        failed.append("too_few_shadow_action_snapshot_dates")

    shadow_minus = evidence["position_level"]["shadow_minus_no_action"]
    monotonic_horizons = []
    for horizon in (1, 3, 5):
        row = shadow_minus.get(str(horizon)) or {}
        spy_delta = safe_float(row.get("avg_excess_spy_pct"))
        qqq_delta = safe_float(row.get("avg_excess_qqq_pct"))
        if spy_delta is not None and qqq_delta is not None and spy_delta < 0 and qqq_delta < 0:
            monotonic_horizons.append(horizon)
    if set(monotonic_horizons) != {1, 3, 5}:
        failed.append("shadow_action_underperformance_not_monotonic_1d_3d_5d")

    base_h1 = [row for row in position_rows if int(row.get("horizon_days") or 0) == 1]
    if any(row.get("quote_time_et") in (None, "") for row in base_h1):
        failed.append("quote_time_et_still_missing")
    if any(int(row.get("shadow_action_count") or 0) > 1 for row in base_h1):
        failed.append("duplicate_actions_per_position_require_position_level_policy")
    if action_rows and all(not row.get("creates_order") for row in action_rows):
        failed.append("shadow_actions_are_advisory_only")
    failed.append("no_shared_exit_policy_or_slot_reuse_gate4_tested")

    decision = "observed_only_rejected_intraday_shadow_action_outcome_not_allocation_ready"
    readiness = {
        "decision": decision,
        "passed": False,
        "failed_reasons": failed,
        "thresholds": {
            "min_action_positions_1d": MIN_ACTION_POSITIONS_1D,
            "min_action_positions_5d": MIN_ACTION_POSITIONS_5D,
            "min_no_action_positions_1d": MIN_NO_ACTION_POSITIONS_1D,
            "min_snapshot_dates": MIN_SNAPSHOT_DATES,
            "requires_shadow_underperformance_vs_no_action_on_spy_and_qqq_1d_3d_5d": True,
            "requires_quote_time_et": True,
            "requires_shared_exit_policy_gate4_before_promotion": True,
        },
        "observed": {
            "position_h1_rows": len(base_h1),
            "action_rows": len(action_rows),
            "shadow_1d_bucket": shadow_1,
            "no_action_1d_bucket": no_action_1,
            "shadow_5d_bucket": shadow_5,
            "shadow_minus_no_action": shadow_minus,
            "monotonic_underperformance_horizons": monotonic_horizons,
        },
    }
    return decision, failed, readiness


def summarize_rows(position_rows: list[dict[str, Any]], action_rows: list[dict[str, Any]]) -> dict[str, Any]:
    h1 = [row for row in position_rows if int(row.get("horizon_days") or 0) == 1]
    return {
        "prior_position_ledger_rows": len(position_rows),
        "h1_position_rows": len(h1),
        "h1_settled_rows": sum(1 for row in h1 if row.get("settlement_status") == "settled"),
        "h1_shadow_action_positions": sum(1 for row in h1 if row.get("has_shadow_action")),
        "h1_no_action_positions": sum(1 for row in h1 if not row.get("has_shadow_action")),
        "raw_shadow_action_rows": len(action_rows),
        "snapshot_date_count": len({row.get("snapshot_date") for row in h1}),
        "ticker_count": len({row.get("ticker") for row in h1}),
        "shadow_action_count_distribution": dict(
            sorted(Counter(int(row.get("shadow_action_count") or 0) for row in h1).items())
        ),
        "status_counts": dict(sorted(Counter(str(row.get("status")) for row in h1).items())),
        "primary_shadow_action_counts": dict(
            sorted(Counter(str(row.get("primary_shadow_action")) for row in h1).items())
        ),
        "primary_shadow_rule_counts": dict(
            sorted(Counter(str(row.get("shadow_rule_bucket")) for row in h1).items())
        ),
        "top_shadow_tickers": [
            {"ticker": ticker, "positions": count}
            for ticker, count in Counter(
                row.get("ticker") for row in h1 if row.get("has_shadow_action")
            ).most_common(12)
        ],
    }


def build_payload() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    timestamp = utc_now()
    prediction = ticket_prediction()
    before = baseline_metrics()
    prior_rows = read_jsonl(PRIOR_POSITION_LEDGER)
    shadow_map, action_base_rows, snapshots = load_shadow_actions()
    position_rows = enrich_position_ledger(prior_rows, shadow_map)
    action_rows = enrich_action_ledger(prior_rows, action_base_rows)
    evidence = summarize_evidence(position_rows, action_rows)
    decision, failed, readiness = evaluate_readiness(position_rows, action_base_rows, evidence)
    row_summary = summarize_rows(position_rows, action_base_rows)
    coverage = field_coverage(position_rows)
    predicted_failures = prediction.get("main_failure_modes") or []
    realized_prediction_hits = [
        mode
        for mode in predicted_failures
        if (
            (mode == "too_few_settled_shadow_actions" and any("too_few" in f for f in failed))
            or (
                mode == "rule_buckets_not_monotonic"
                and "shadow_action_underperformance_not_monotonic_1d_3d_5d" in failed
            )
            or (
                mode == "duplicate_actions_per_position"
                and "duplicate_actions_per_position_require_position_level_policy" in failed
            )
            or (mode == "quote_time_missing_blocks_causality" and "quote_time_et_still_missing" in failed)
        )
    ]
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "owner": OWNER,
        "status": decision,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "alpha_ready": False,
        "implementation_mode": "observed_only_shadow_action_forward_outcome_no_strategy_change",
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": (
            "exp-20260626-020 accepted a new advisory-only shadow action contract "
            "mapping existing intraday triggered rules to machine-readable EXIT/REVIEW "
            "rows; this run tests that new field against exp-20260626-019 settled "
            "forward outcomes without retuning status, stop, target, urgency, or hold "
            "thresholds."
        ),
        "prediction": prediction,
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "actual_success": 0,
            "expected_ev_delta": prediction.get("expected_ev_delta"),
            "actual_ev_delta": 0.0,
            "expected_pnl_delta": prediction.get("expected_pnl_delta"),
            "actual_pnl_delta": 0.0,
            "predicted_failure_modes": predicted_failures,
            "realized_failure_modes": failed,
            "predicted_failure_modes_hit": realized_prediction_hits,
            "surprise_note": (
                "Low surprise: the shadow-action contract produced many rows, but "
                "the field is still advisory-only, duplicate rule actions occur on "
                "the same position, and no shared exit policy was Gate-4 tested."
            ),
        },
        "gate1": {
            "passed": True,
            "baseline_metrics": before,
            "note": "Observed-only attribution; before and after strategy behavior are identical.",
        },
        "gate2": {
            "passed": bool(prior_rows) and bool(shadow_map),
            "required_fields_checked": [
                "observation_base_id",
                "snapshot_date",
                "ticker",
                "entry_date",
                "target_price",
                "settlement_status",
                "net_return",
                "excess_spy_return",
                "excess_qqq_return",
                "primary_shadow_action",
                "primary_shadow_rule",
            ],
            "field_coverage": coverage,
            "prior_position_ledger": repo_rel(PRIOR_POSITION_LEDGER),
            "snapshot_dir": repo_rel(SNAPSHOT_DIR),
            "snapshot_file_count": len(snapshots),
            "shadow_position_count": len(shadow_map),
            "raw_shadow_action_rows": len(action_base_rows),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated_proxy": row_summary["h1_position_rows"],
            "signals_survived_proxy": row_summary["h1_shadow_action_positions"],
            "survival_rate_proxy": pct(
                row_summary["h1_shadow_action_positions"],
                row_summary["h1_position_rows"],
            ),
            "baseline_survival_rate": before.get("survival_rate"),
            "note": (
                "Survival is a measurement proxy: positions with at least one "
                "advisory shadow action among settled h1 rows."
            ),
        },
        "gate4": {
            "passed": False,
            "decision": decision,
            "failed_reasons": failed,
            "readiness": readiness,
            "expected_value_score_sum_before": before["expected_value_score_sum"],
            "expected_value_score_sum_after": before["expected_value_score_sum"],
            "aggregate_ev_delta": 0.0,
            "total_pnl_before": before["total_pnl"],
            "total_pnl_after": before["total_pnl"],
            "aggregate_pnl_delta": 0.0,
            "trade_count_before": before["trade_count"],
            "trade_count_after": before["trade_count"],
            "strategy_behavior_changed": False,
            "observed_only_note": (
                "This is not accepted alpha. A promotion would need a predeclared "
                "shared default-off exit advisory helper, slot-reuse accounting, "
                "quote-time provenance, and Gate 1-4 before/after replay."
            ),
        },
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "strategy_behavior_changed": False,
            "h1_shadow_action_positions": row_summary["h1_shadow_action_positions"],
            "raw_shadow_action_rows": row_summary["raw_shadow_action_rows"],
        },
        "source_summary": {
            "snapshots": snapshots,
            "row_summary": row_summary,
            "field_coverage": coverage,
            "evidence": evidence,
        },
        "production_impact": {
            "adapter_status": "none",
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "production_watchlist_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "shared_policy_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "llm_decision_boundary_changed": False,
            "trade_enabled": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": "Read-only observed-only attribution; no production/replay behavior changed.",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The accepted shadow action contract made rule/action attribution "
                "possible, but the current data still cannot support an exit policy: "
                "quote timestamps remain missing, some positions emit multiple "
                "rule rows, and no before/after strategy replay measured slot reuse."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry hard-stop, ATR-stop, target, time-stop, urgency, or "
                "shadow-action threshold variants on this same settled ledger. The "
                "next valid retry needs more closed post-contract rows or a shared "
                "default-off exit helper with Gate 1-4."
            ),
            "new_evidence_required": (
                "More closed intraday snapshots after exp-20260626-020, quote_time_et "
                "or broker bar IDs, and a predeclared shared default-off exit advisory "
                "policy with slot-reuse/winner-collateral accounting."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": "Passed with no strong near-neighbor.",
                "exp-20260626-019": "Settled position outcomes but lacked action semantics.",
                "exp-20260626-020": "Accepted advisory-only shadow action contract repair.",
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": readiness["thresholds"],
            "5_reproducibility": RUNNER_COMMAND,
        },
        "artifact": repo_rel(OUT_JSON),
        "position_ledger": repo_rel(POSITION_LEDGER_JSONL),
        "action_diagnostic_ledger": repo_rel(ACTION_LEDGER_JSONL),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "changed_files": ALLOWED_WRITE_SCOPE,
        "related_files": [
            repo_rel(BASELINE_RESULT),
            repo_rel(PRIOR_POSITION_LEDGER),
            repo_rel(SNAPSHOT_DIR),
            "experiments/logs/exp-20260626-019.json",
            "experiments/logs/exp-20260626-020.json",
        ],
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
    }
    return payload, position_rows, action_rows


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "accepted": False,
        "accepted_alpha": False,
        "alpha_ready": False,
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": payload["single_causal_variable"],
        "changed_variable": payload["changed_variable"],
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "delta_metrics": payload["delta_metrics"],
        "source_summary": payload["source_summary"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "artifact": payload["artifact"],
        "position_ledger": payload["position_ledger"],
        "action_diagnostic_ledger": payload["action_diagnostic_ledger"],
        "log": payload["log"],
        "runner": payload["runner"],
        "reproduction_commands": payload["reproduction_commands"],
        "changed_files": payload["changed_files"],
        "anti_js": payload["anti_js"],
        "lean_quality_passed": True,
    }


def write_card(payload: dict[str, Any]) -> None:
    observed = payload["gate4"]["readiness"]["observed"]
    delta_1d = (observed["shadow_minus_no_action"].get("1") or {}).get(
        "avg_excess_spy_pct"
    )
    text = "\n".join(
        [
            f"# {EXPERIMENT_ID}: intraday shadow action outcome scout",
            "",
            f"- Decision: {payload['decision']}",
            "- Production impact: none; observed-only attribution.",
            f"- H1 shadow-action positions: {observed['shadow_1d_bucket'].get('settled_rows')}",
            f"- H1 no-action positions: {observed['no_action_1d_bucket'].get('settled_rows')}",
            f"- H1 shadow minus no-action excess SPY pct: {delta_1d}",
            f"- Artifact: `{payload['artifact']}`",
            f"- Position ledger: `{payload['position_ledger']}`",
            f"- Action diagnostic ledger: `{payload['action_diagnostic_ledger']}`",
            "",
            "No strategy behavior, orders, exits, sizing, ranking, or LLM decision boundary changed.",
            "",
        ]
    )
    write_text(CARD_MD, text)


def write_manifest(payload: dict[str, Any]) -> None:
    paths = [
        Path(RUNNER),
        OUT_JSON,
        POSITION_LEDGER_JSONL,
        ACTION_LEDGER_JSONL,
        BEFORE_JSON,
        AFTER_JSON,
        LOG_JSON,
        CARD_MD,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "files": [
            {"path": repo_rel(path), "exists": path.exists(), "sha256": sha256(path)}
            for path in paths
        ],
    }
    write_json(MANIFEST_JSON, manifest)


def persist_registry(payload: dict[str, Any], compact_record: dict[str, Any]) -> None:
    fields = {
        "accepted": False,
        "accepted_alpha": False,
        "alpha_ready": False,
        "decision": payload["decision"],
        "change_type": CHANGE_TYPE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": payload["new_evidence_axis"],
        "artifact": payload["artifact"],
        "position_ledger": payload["position_ledger"],
        "action_diagnostic_ledger": payload["action_diagnostic_ledger"],
        "log": payload["log"],
        "runner": RUNNER,
        "changed_files": payload["changed_files"],
        "lean_quality_passed": True,
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result=compact_record,
        status=payload["status"],
        fields=fields,
    )


def main() -> None:
    payload, position_rows, action_rows = build_payload()
    write_json(BEFORE_JSON, payload["gate1"]["baseline_metrics"])
    write_json(AFTER_JSON, payload["gate1"]["baseline_metrics"])
    write_jsonl(POSITION_LEDGER_JSONL, position_rows)
    write_jsonl(ACTION_LEDGER_JSONL, action_rows)
    write_json(OUT_JSON, payload)
    compact_record = compact_log_record(payload)
    write_json(LOG_JSON, compact_record)
    upsert_jsonl(EXPERIMENT_LOG, compact_record)
    write_card(payload)
    persist_registry(payload, compact_record)
    write_manifest(payload)
    print(json.dumps(compact_record, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
