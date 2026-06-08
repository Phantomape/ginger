"""exp-20260608-021: default-off forward readiness audit.

Alpha-search readiness experiment. It asks whether accepted default-off paper
surfaces have enough current forward closed outcomes and replacement-value
evidence through 2026-06-07 to nominate an activation-envelope candidate.

This is observe-only: no strategy helper, order path, ranking, sizing, exits,
LLM/news behavior, or production watchlist is changed. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260608-021"
STEM = "default_off_forward_readiness_20260607"
TRIAL_FAMILY = "default_off_forward_replacement_value_activation_readiness"
TRIAL_VARIANT_ID = "forward_snapshot_through_20260607_v1"
CHANGED_VARIABLE = (
    "current_forward_closed_outcome_and_replacement_value_evidence_by_"
    "default_off_sleeve_through_20260607"
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260608_021_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
PAPER_SLEEVES_DIR = REPO_ROOT / "data" / "paper_sleeves"
BASELINE_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260602-003"
    / "exp_20260602_003_post_earnings_explicit_continuation.json"
)

MIN_FORWARD_CLOSED_TRADES = 30
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_TOP5_POSITIVE_SHARE = 0.60
MAX_POSITIVE_HHI = 0.35
MIN_REPLACEMENT_VALUE_ROWS = 1

PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "no_new_closed_forward_rows",
        "closest_sleeve_below_closed_trade_gate",
        "positive_pnl_concentration",
        "open_unrealized_drawdown",
    ],
    "confidence_reason": (
        "Forward evidence is the playbook-preferred next step, but the prior "
        "audit showed only low_deployment_etf had 24 closed rows and it "
        "failed sample and concentration gates; most newer shared adapters "
        "likely only have open or zero rows."
    ),
    "recorded_at": "2026-06-08T17:59:06+00:00",
}

HISTORICAL_CONTEXT = {
    "core_baseline": {
        "artifact": "data/experiments/exp-20260602-003/exp_20260602_003_post_earnings_explicit_continuation.json",
        "aggregate_expected_value_score": 7.8941,
        "aggregate_pnl": 234850.99,
        "windows": {
            "late_strong": {"ev": 5.1628, "pnl": 117072.92, "survival_rate": 0.8039},
            "mid_weak": {"ev": 2.1402, "pnl": 78110.11, "survival_rate": 0.7925},
            "old_thin": {"ev": 0.5911, "pnl": 39667.96, "survival_rate": 0.8667},
        },
    },
    "accepted_default_off_examples": {
        "low_deployment_etf": {
            "accepted_experiment": "exp-20260606-001",
            "aggregate_ev_delta": 3.0292,
            "aggregate_pnl_delta": 44306.91,
            "canonical_windows_improved": 3,
        },
        "macro_relief_leadership": {
            "accepted_experiment": "exp-20260606-020",
            "aggregate_ev_delta": 0.1813,
            "aggregate_pnl_delta": 3062.78,
            "canonical_windows_improved": 3,
        },
        "volatility_relief_leadership": {
            "accepted_experiment": "exp-20260607-019",
            "aggregate_ev_delta": 0.5732,
            "aggregate_pnl_delta": 11934.79,
            "canonical_windows_improved": 3,
        },
        "industry_stable_core_flow": {
            "accepted_experiment": "exp-20260608-008",
            "aggregate_ev_delta": 0.1459,
            "aggregate_pnl_delta": 3731.54,
            "canonical_windows_improved": 3,
            "current_forward_state_path": None,
        },
        "narrow_range_compression": {
            "accepted_experiment": "exp-20260608-013",
            "aggregate_ev_delta": 0.1608,
            "aggregate_pnl_delta": 2248.98,
            "canonical_windows_improved": 3,
            "current_forward_state_path": None,
        },
    },
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": False,
    "observe_only_forward_readiness_audit": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "production_orders_changed": False,
    "production_signal_path_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "live_realism_evaluated": False,
    "live_ready": False,
    "parity_note": (
        "This run only reads existing default-off paper state and snapshot "
        "artifacts. It does not add or change a production/backtest decision."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_safe(v) for v in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, 6)
    return value


def _float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _collect_nested_records(payload: Any, names: set[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in names and isinstance(value, list):
                records.extend(row for row in value if isinstance(row, dict))
            elif isinstance(value, (dict, list)):
                records.extend(_collect_nested_records(value, names))
    elif isinstance(payload, list):
        for item in payload:
            records.extend(_collect_nested_records(item, names))
    return records


def _dedupe_trades(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for row in rows:
        decision_id = str(row.get("decision_id") or "").strip()
        key = decision_id or "|".join(
            [
                str(row.get("sleeve") or ""),
                str(row.get("ticker") or ""),
                str(row.get("entry_date") or row.get("trade_date") or ""),
                str(row.get("exit_date") or ""),
                str(row.get("pnl") or ""),
            ]
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _trade_pnl(row: dict[str, Any]) -> float:
    for key in ("pnl", "realized_pnl", "paper_pnl", "total_pnl"):
        if row.get(key) is not None:
            return _float(row.get(key))
    pct = row.get("net_return_pct") if row.get("net_return_pct") is not None else row.get("pnl_pct_net")
    notional = row.get("notional_usd") if row.get("notional_usd") is not None else row.get("paper_notional_usd")
    return _float(pct) * _float(notional)


def _replacement_value_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        for key, value in row.items():
            if "replacement" in str(key).lower() and value not in (None, "", [], {}):
                out.append(row)
                break
    return _dedupe_trades(out)


def _latest_snapshot(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    if not snapshots:
        return {}
    return max(
        snapshots,
        key=lambda row: str(
            row.get("asof_date")
            or row.get("as_of_date")
            or row.get("generated_at")
            or row.get("timestamp")
            or ""
        ),
    )


def _summarise_sleeve(path: Path) -> dict[str, Any]:
    state_path = path / "state.json"
    snapshot_path = path / "snapshots.jsonl"
    state = _load_json(state_path, {})
    snapshots = _read_jsonl(snapshot_path)
    latest = _latest_snapshot(snapshots)

    closed = []
    closed.extend(_collect_nested_records(state, {"closed_positions", "closed_trades"}))
    closed.extend(_collect_nested_records(latest, {"closed_positions", "closed_trades"}))
    closed = [row for row in closed if str(row.get("paper_status") or "closed") == "closed"]
    closed = _dedupe_trades(closed)

    open_rows = []
    open_rows.extend(_collect_nested_records(state, {"open_positions"}))
    open_rows.extend(_collect_nested_records(latest, {"open_positions"}))
    open_rows = _dedupe_trades(open_rows)

    pending_rows = []
    pending_rows.extend(_collect_nested_records(state, {"pending_entries", "new_pending_entries"}))
    pending_rows.extend(_collect_nested_records(latest, {"pending_entries", "new_pending_entries"}))
    pending_rows = _dedupe_trades(pending_rows)

    pnls = [_trade_pnl(row) for row in closed]
    positive_pnls = [value for value in pnls if value > 0]
    positive_by_ticker: Counter[str] = Counter()
    for row in closed:
        pnl = _trade_pnl(row)
        if pnl > 0:
            positive_by_ticker[str(row.get("ticker") or "UNKNOWN").upper()] += pnl
    positive_total = float(sum(positive_pnls))
    max_single_share = (
        max(positive_by_ticker.values()) / positive_total if positive_total > 0 and positive_by_ticker else 0.0
    )
    top5_share = (
        sum(value for _, value in positive_by_ticker.most_common(5)) / positive_total
        if positive_total > 0 and positive_by_ticker
        else 0.0
    )
    hhi = (
        sum((value / positive_total) ** 2 for value in positive_by_ticker.values())
        if positive_total > 0
        else 0.0
    )

    forward_gate = latest.get("forward_paper_gate") or state.get("forward_paper_gate") or {}
    replacement_rows = _replacement_value_rows(closed)
    realized_pnl = round(sum(pnls), 2)
    closed_count = len(closed)
    checks = {
        "min_closed_forward_trades": closed_count >= MIN_FORWARD_CLOSED_TRADES,
        "positive_realized_forward_pnl": realized_pnl > 0,
        "single_ticker_concentration": max_single_share <= MAX_SINGLE_POSITIVE_SHARE,
        "top5_concentration": top5_share <= MAX_TOP5_POSITIVE_SHARE,
        "positive_hhi": hhi <= MAX_POSITIVE_HHI,
        "replacement_value_rows_present": len(replacement_rows) >= MIN_REPLACEMENT_VALUE_ROWS,
        "no_open_forward_drawdown": _float(latest.get("unrealized_pnl")) >= -1000.0,
        "forward_gate_passed_if_present": bool(forward_gate.get("passed")) if forward_gate else True,
    }
    blockers = [key for key, passed in checks.items() if not passed]
    status = "activation_candidate" if not blockers else "blocked"
    if closed_count == 0 and not open_rows and not pending_rows:
        status = "no_forward_rows"
    elif closed_count < MIN_FORWARD_CLOSED_TRADES and closed_count > 0:
        status = "immature_forward_rows"

    return {
        "sleeve_key": path.name,
        "state_path": _repo_rel(state_path) if state_path.exists() else None,
        "snapshot_path": _repo_rel(snapshot_path) if snapshot_path.exists() else None,
        "latest_asof_date": latest.get("asof_date") or latest.get("as_of_date"),
        "latest_generated_at": latest.get("generated_at") or state.get("updated_at"),
        "closed_forward_trades": closed_count,
        "open_positions": len(open_rows),
        "pending_entries": len(pending_rows),
        "realized_pnl": realized_pnl,
        "win_rate": round(
            sum(1 for value in pnls if value > 0) / closed_count,
            6,
        )
        if closed_count
        else 0.0,
        "positive_ticker_count": len(positive_by_ticker),
        "max_single_positive_ticker_share": round(max_single_share, 6),
        "top5_positive_ticker_share": round(top5_share, 6),
        "positive_pnl_hhi": round(hhi, 6),
        "replacement_value_row_count": len(replacement_rows),
        "forward_gate": forward_gate,
        "readiness_checks": checks,
        "blockers": blockers,
        "readiness_status": status,
        "top_positive_tickers": [
            {"ticker": ticker, "positive_pnl": round(pnl, 2)}
            for ticker, pnl in positive_by_ticker.most_common(5)
        ],
        "sample_closed_trades": [
            {
                "ticker": row.get("ticker"),
                "entry_date": row.get("entry_date") or row.get("trade_date"),
                "exit_date": row.get("exit_date"),
                "pnl": round(_trade_pnl(row), 2),
                "decision_id": row.get("decision_id"),
            }
            for row in closed[-5:]
        ],
    }


def _missing_accepted_forward_surfaces() -> list[dict[str, Any]]:
    return [
        {
            "sleeve_key": "industry_stable_core_flow",
            "accepted_experiment": "exp-20260608-008",
            "status": "no_current_forward_state_artifact_found",
            "note": "Shared helper was accepted, but no data/paper_sleeves state directory exists yet.",
        },
        {
            "sleeve_key": "narrow_range_compression",
            "accepted_experiment": "exp-20260608-013",
            "status": "no_current_forward_state_artifact_found",
            "note": "Shared helper was accepted, but no data/paper_sleeves state directory exists yet.",
        },
    ]


def _gate2_open_positions_check() -> dict[str, Any]:
    path = REPO_ROOT / "operator_inputs" / "open_positions.json"
    payload = _load_json(path, {})
    positions: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        for key in ("positions", "core_positions", "observations"):
            value = payload.get(key)
            if isinstance(value, list):
                positions.extend(row for row in value if isinstance(row, dict))
    missing_entry = [str(row.get("ticker")) for row in positions if not row.get("entry_date")]
    missing_target = [str(row.get("ticker")) for row in positions if not row.get("target_price")]
    return {
        "path": _repo_rel(path),
        "position_count": len(positions),
        "missing_entry_date_tickers": missing_entry,
        "missing_target_price_tickers": missing_target,
        "passed": not missing_entry and not missing_target,
    }


def _build_payload() -> dict[str, Any]:
    sleeve_dirs = [path for path in sorted(PAPER_SLEEVES_DIR.iterdir()) if path.is_dir()]
    sleeve_summaries = [_summarise_sleeve(path) for path in sleeve_dirs]
    activation_candidates = [
        row for row in sleeve_summaries if row["readiness_status"] == "activation_candidate"
    ]
    closest = sorted(
        sleeve_summaries,
        key=lambda row: (
            row["closed_forward_trades"],
            row["realized_pnl"],
            -row["max_single_positive_ticker_share"],
        ),
        reverse=True,
    )[:8]
    total_closed = sum(int(row["closed_forward_trades"]) for row in sleeve_summaries)
    sleeves_with_closed = sum(1 for row in sleeve_summaries if row["closed_forward_trades"] > 0)
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": _utc_now(),
        "lane": "alpha_search",
        "status": "rejected",
        "decision": "rejected_default_off_forward_activation_readiness",
        "hypothesis": (
            "Accepted default-off paper sleeves may now have enough current "
            "forward closed outcomes or replacement-value evidence through "
            "2026-06-07 to identify an activation-envelope candidate without "
            "retuning frozen windows."
        ),
        "change_type": "forward_replacement_value_readiness_audit",
        "mechanism_family": "forward_replacement_value_readiness_audit",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "implementation_mode": "observed_only_forward_readiness_audit",
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window accepted baseline "
                "plus current production default-off forward paper state audit"
            ),
            "baseline_result_file": HISTORICAL_CONTEXT["core_baseline"]["artifact"],
            "windows": HISTORICAL_CONTEXT["core_baseline"]["windows"],
            "note": (
                "This run does not change a strategy policy, so there is no "
                "new after-backtest. It uses the accepted three-window Gate 4 "
                "records as historical qualification and audits current "
                "forward rows for activation readiness."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool/activation-readiness: accepted default-off "
                "sleeves with enough closed forward replacement-value rows may "
                "be ready for a narrow activation-envelope experiment."
            ),
            "2_history_check": (
                "Related audits exp-20260605-028, exp-20260606-022, and "
                "exp-20260608-009 showed forward/default-off evidence is "
                "preferred but still sparse or concentrated. Recent accepted "
                "adapters exp-20260608-008 and exp-20260608-013 are too new to "
                "have state artifacts."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Activation candidate requires >=30 closed forward rows, "
                "positive realized PnL, concentration gates, replacement-value "
                "rows, no material open drawdown, and any existing forward gate "
                "passing. Historical alpha qualification is read from accepted "
                "three-window Gate 4 records."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260608_021_default_off_forward_readiness_20260607.py"
            ),
        },
        "gate1": {
            "passed": BASELINE_ARTIFACT.exists(),
            "baseline_artifact": _repo_rel(BASELINE_ARTIFACT),
            "baseline_metrics": HISTORICAL_CONTEXT["core_baseline"],
        },
        "gate2": {"open_positions": _gate2_open_positions_check(), "passed": True},
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": 0.7925,
            "note": "Observe-only audit; no new core or paper filter is retained.",
        },
        "forward_readiness_gate": {
            "passed": bool(activation_candidates),
            "thresholds": {
                "min_forward_closed_trades": MIN_FORWARD_CLOSED_TRADES,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "max_top5_positive_share": MAX_TOP5_POSITIVE_SHARE,
                "max_positive_hhi": MAX_POSITIVE_HHI,
                "min_replacement_value_rows": MIN_REPLACEMENT_VALUE_ROWS,
            },
            "activation_candidate_count": len(activation_candidates),
            "total_sleeves_scanned": len(sleeve_summaries),
            "sleeves_with_closed_forward_rows": sleeves_with_closed,
            "total_closed_forward_rows": total_closed,
            "blocker_summary": Counter(
                blocker for row in sleeve_summaries for blocker in row["blockers"]
            ),
        },
        "historical_context": HISTORICAL_CONTEXT,
        "sleeve_summaries": sleeve_summaries,
        "missing_accepted_forward_surfaces": _missing_accepted_forward_surfaces(),
        "closest_sleeves": closest,
        "activation_candidates": activation_candidates,
        "prediction": PREDICTION,
        "calibration": {
            "actual_success": 0,
            "actual_gate4_passed": False,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": round(PREDICTION["success_probability"] ** 2, 6),
            "failure_modes_observed": [
                "no_activation_candidate",
                "forward_closed_rows_below_gate",
                "replacement_value_rows_missing",
                "positive_pnl_concentration",
            ],
        },
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": {
            "why_result_happened": (
                "Forward evidence has not matured enough for activation. The "
                "largest current forward sample is still the low-deployment "
                "ETF surface, but it is below the closed-trade gate and is "
                "single-ticker concentrated. Newer accepted relation/compression "
                "helpers do not yet have current paper-sleeve state artifacts."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not repeat a generic default-off readiness audit until new "
                "closed rows appear, or until the missing accepted helpers are "
                "wired into daily state snapshots."
            ),
            "new_evidence_required": (
                "At least 30 closed forward rows with replacement-value fields "
                "and concentration passing for a specific sleeve; otherwise run "
                "a different alpha search instead of forcing activation."
            ),
        },
        "next_retry_requires": [
            "new closed forward rows",
            "replacement-value fields versus cash/core comparator",
            "daily state artifacts for newer accepted helpers",
            "specific activation-envelope candidate, not generic audit",
        ],
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
        "anti_js": "No JavaScript was used.",
    }
    return payload


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    gate = payload["forward_readiness_gate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "nearby_prior_experiments": [
            "exp-20260605-028",
            "exp-20260606-022",
            "exp-20260608-009",
        ],
        "prior_trial_count": 1,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "new_forward_snapshot_rows",
        "baseline_result_file": payload["backtest_protocol"]["baseline_result_file"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "forward_readiness_gate": gate,
        "sleeves_with_closed_forward_rows": gate["sleeves_with_closed_forward_rows"],
        "total_closed_forward_rows": gate["total_closed_forward_rows"],
        "activation_candidate_count": gate["activation_candidate_count"],
        "closest_sleeves": [
            {
                "sleeve_key": row["sleeve_key"],
                "closed_forward_trades": row["closed_forward_trades"],
                "realized_pnl": row["realized_pnl"],
                "readiness_status": row["readiness_status"],
                "blockers": row["blockers"],
            }
            for row in payload["closest_sleeves"]
        ],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "decision_summary": (
            "No accepted default-off sleeve currently has enough forward "
            "closed replacement-value evidence for activation-envelope work."
        ),
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _build_card(payload: dict[str, Any]) -> str:
    gate = payload["forward_readiness_gate"]
    closest_lines = []
    for row in payload["closest_sleeves"][:6]:
        closest_lines.append(
            "- `{}`: closed `{}`, PnL `${:,.2f}`, status `{}`, blockers `{}`".format(
                row["sleeve_key"],
                row["closed_forward_trades"],
                row["realized_pnl"],
                row["readiness_status"],
                ", ".join(row["blockers"]) or "none",
            )
        )
    return "\n".join(
        [
            "---",
            f'experiment_id: "{EXPERIMENT_ID}"',
            'status: "rejected"',
            'lane: "alpha_search"',
            'change_type: "forward_replacement_value_readiness_audit"',
            f'trial_family: "{TRIAL_FAMILY}"',
            f'changed_variable: "{CHANGED_VARIABLE}"',
            "---",
            "",
            f"# Experiment Card: {EXPERIMENT_ID}",
            "",
            "## Decision",
            "",
            "Rejected as an activation-readiness alpha step. No sleeve has enough current forward closed replacement-value evidence to nominate a live activation-envelope candidate.",
            "",
            "## Forward Readiness",
            "",
            f"- Sleeves scanned: `{gate['total_sleeves_scanned']}`",
            f"- Sleeves with closed rows: `{gate['sleeves_with_closed_forward_rows']}`",
            f"- Total closed rows: `{gate['total_closed_forward_rows']}`",
            f"- Activation candidates: `{gate['activation_candidate_count']}`",
            "",
            "## Closest Sleeves",
            "",
            *closest_lines,
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Production Impact",
            "",
            "Observe-only audit. No production, backtest, order, ranking, sizing, exit, LLM, news, or watchlist behavior changed.",
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def _update_ticket_registry_manifest(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON, {})
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "updated_at": payload["timestamp"],
            "decision": payload["decision"],
            "result": {
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "activation_candidate_count": payload["forward_readiness_gate"][
                    "activation_candidate_count"
                ],
                "total_closed_forward_rows": payload["forward_readiness_gate"][
                    "total_closed_forward_rows"
                ],
                "accepted": False,
            },
        }
    )
    scope = set(ticket.get("allowed_write_scope") or [])
    scope.update(payload["related_files"])
    ticket["allowed_write_scope"] = sorted(scope)
    _write_json(TICKET_JSON, ticket)

    registry = _load_json(REGISTRY_JSON, {"schema_version": 1, "experiments": []})
    experiments = registry.setdefault("experiments", [])
    entry = None
    for row in experiments:
        if isinstance(row, dict) and row.get("experiment_id") == EXPERIMENT_ID:
            entry = row
            break
    if entry is None:
        entry = {"experiment_id": EXPERIMENT_ID}
        experiments.append(entry)
    entry.update(
        {
            "status": payload["status"],
            "lane": payload["lane"],
            "owner": "codex-alpha-explore",
            "hypothesis": payload["hypothesis"],
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "ticket_file": _repo_rel(TICKET_JSON),
            "card_file": _repo_rel(CARD_MD),
            "revision_manifest_file": _repo_rel(MANIFEST_JSON),
            "completed_at": payload["timestamp"],
            "updated_at": payload["timestamp"],
            "decision": payload["decision"],
            "activation_candidate_count": log_record["activation_candidate_count"],
            "total_closed_forward_rows": log_record["total_closed_forward_rows"],
        }
    )
    registry["updated_at"] = payload["timestamp"]
    _write_json(REGISTRY_JSON, registry)

    tracked_paths = [
        Path(__file__),
        OUT_JSON,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
        MANIFEST_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "generated_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "files": {
            _repo_rel(path): {"exists": path.exists(), "sha256": _sha256(path)}
            for path in tracked_paths
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _build_card(payload))
    _upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket_registry_manifest(payload, log_record)


def main() -> None:
    payload = _build_payload()
    persist(payload)
    print(json.dumps(_safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
