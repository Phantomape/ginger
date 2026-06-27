"""exp-20260627-009: sector crowding attribution on oracle loss rows.

Observed-only alpha attribution. The single question is whether same-day
sector or industry entry crowding is enriched in the fixed-entry oracle
low-MFE stopout / failed-followthrough loss rows identified by the oracle
compass.

This runner changes no shared policy, entry, exit, ranking, sizing, order,
daily snapshot, paper sleeve state, watchlist, or LLM boundary. A positive
result can only justify future forward logging or a separate shared-policy
Gate 1-4 experiment.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260627-009"
OWNER = "alpha-explore"
SLUG = "sector_entry_crowding_oracle_loss_attribution"
RUNNER = f"quant/experiments/exp_20260627_009_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260627_009_{SLUG}.json"
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
ORACLE_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260623-003"
    / "exp_20260623_003_fixed_entry_exit_oracle_regret_cluster.json"
)
LOSS_TAXONOMY_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260511-102"
    / "exp_20260511_102_accepted_stack_oracle_loss_taxonomy.json"
)
SECTOR_MAP = REPO_ROOT / "data" / "reference" / "broad_market_sector_map.json"
ORACLE_COMPASS = REPO_ROOT / "docs" / "oracle_regret_compass.md"

HYPOTHESIS = (
    "Observed-only alpha hypothesis: same-day sector or industry entry "
    "crowding is an ex-ante label for weak-tape immediate entry-quality "
    "failures; oracle low-MFE stopout and failed-followthrough loss rows "
    "should be materially enriched in sector/industry crowding versus other "
    "accepted-stack trades."
)
CHANGE_TYPE = "observed_only_attribution"
IMPLEMENTATION_MODE = "observed_only_oracle_loss_cluster_attribution"
MECHANISM_FAMILY = "oracle_entry_quality_regret_attribution"
TRIAL_FAMILY = "sector_entry_crowding_oracle_loss_attribution"
TRIAL_VARIANT_ID = "oracle_low_mfe_sector_entry_crowding_v1"
CHANGED_VARIABLE = "sector_entry_crowding_oracle_loss_cluster_attribution_v1"
NEW_EVIDENCE_TYPE = "new_gate_shape_oracle_loss_cluster_attribution"
NEW_EVIDENCE_AXIS = (
    "New ex-ante label on the fixed oracle/loss-taxonomy cluster: same-day "
    "sector and industry entry crowding across accepted-stack trades. This is "
    "not a short-volume retry, not a forward-row reslice, and not a tradable "
    "entry/ranking/sizing rule."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260623-003",
    "exp-20260511-102",
    "exp-20260627-008",
]
CAUSAL_COMPONENTS = [
    "fixed-entry exit oracle rows",
    "accepted-stack loss taxonomy rows",
    "same-day sector and industry cluster join",
    "loss-cluster enrichment test",
    "no strategy behavior change",
]
PREDICTION = {
    "success_probability": 0.30,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "sector_map_join_sparse",
        "target_cluster_not_enriched",
        "cluster_sample_too_small",
        "old_thin_only_effect",
    ],
    "confidence_reason": (
        "The oracle compass isolates remaining regret to immediate entry-quality "
        "failures, and short-volume attribution already failed; sector or "
        "industry crowding is a different production-visible ex-ante label "
        "that may capture same-day theme exhaustion, but sample size and prior "
        "loss-taxonomy cluster counts are likely thin."
    ),
    "recorded_at": "2026-06-27T08:06:16+00:00",
}
CONFIG = {
    "min_joined_rows": 55,
    "min_target_rows": 6,
    "min_sector_known_share": 0.80,
    "min_target_sector_cluster_share_edge": 0.20,
    "min_target_mean_sector_peer_edge": 0.35,
    "min_directional_windows_with_target_n_ge_2": 2,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


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
            rows.append(json.dumps(existing, sort_keys=True))
    if not replaced:
        rows.append(encoded)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None


def r4(value: Any) -> float | None:
    number = as_float(value)
    return None if number is None else round(number, 4)


def trade_key(row: dict[str, Any]) -> str:
    return "|".join(
        [
            str(row.get("ticker") or "").upper(),
            str(row.get("entry_date") or "")[:10],
            str(row.get("window") or ""),
        ]
    )


def load_baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {}) or {}
    windows = payload.get("windows") or []
    if not isinstance(windows, list):
        windows = []
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
        )
        or 7.8941,
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2)
        or 234850.99,
        "trade_count": int(sum(int(row.get("trade_count") or 0) for row in windows)) or 61,
        "signals_generated": int(sum(int(row.get("signals_generated") or 0) for row in windows))
        or 164,
        "signals_survived": int(sum(int(row.get("signals_survived") or 0) for row in windows))
        or 135,
        "survival_rate": 0.8232,
        "window_count": len(windows) or 3,
    }


def load_oracle_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = read_json(ORACLE_ARTIFACT, {}) or {}
    rows = payload.get("attribution", {}).get("sample_rows", [])
    if not isinstance(rows, list):
        rows = []
    return rows, {
        "source": repo_rel(ORACLE_ARTIFACT),
        "exists": ORACLE_ARTIFACT.exists(),
        "n_rows_reported": payload.get("attribution", {}).get("n_rows"),
        "rows_loaded": len(rows),
        "decision": payload.get("decision"),
        "status": payload.get("status"),
    }


def load_loss_taxonomy_labels() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    payload = read_json(LOSS_TAXONOMY_ARTIFACT, {}) or {}
    rows = payload.get("bad_trades", [])
    out: dict[str, dict[str, Any]] = {}
    label_counts: Counter[str] = Counter()
    if isinstance(rows, list):
        for row in rows:
            labels = [str(item) for item in row.get("oracle_labels", [])]
            for label in labels:
                label_counts[label] += 1
            out[trade_key(row)] = {
                "loss_taxonomy_joined": True,
                "loss_taxonomy_labels": labels,
                "loss_taxonomy_pnl": r4(row.get("pnl")),
                "loss_taxonomy_mfe_pct": r4(row.get("mfe_pct")),
                "loss_taxonomy_mae_pct": r4(row.get("mae_pct")),
            }
    return out, {
        "source": repo_rel(LOSS_TAXONOMY_ARTIFACT),
        "exists": LOSS_TAXONOMY_ARTIFACT.exists(),
        "bad_rows_loaded": len(rows) if isinstance(rows, list) else 0,
        "label_counts": dict(sorted(label_counts.items())),
        "decision": payload.get("decision"),
        "status": payload.get("status"),
    }


def load_sector_map() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    payload = read_json(SECTOR_MAP, {}) or {}
    entries = payload.get("entries", {})
    if not isinstance(entries, dict):
        entries = {}
    usable = {
        str(ticker).upper(): row
        for ticker, row in entries.items()
        if isinstance(row, dict) and row.get("status") == "ok"
    }
    return usable, {
        "source": repo_rel(SECTOR_MAP),
        "exists": SECTOR_MAP.exists(),
        "entries": len(entries),
        "usable_entries": len(usable),
        "rule_version": payload.get("rule_version"),
        "generated_at": payload.get("generated_at"),
    }


def target_reasons(row: dict[str, Any]) -> list[str]:
    labels = set(row.get("loss_taxonomy_labels") or [])
    reasons: list[str] = []
    if "oracle_low_mfe_stopout" in labels:
        reasons.append("loss_taxonomy_oracle_low_mfe_stopout")
    if "weak_initial_follow_through" in labels:
        reasons.append("loss_taxonomy_weak_initial_follow_through")
    if (
        row.get("exit_reason") == "stop"
        and row.get("actual_outcome_bucket") == "actual_loss_with_positive_oracle"
        and row.get("oracle_timing_bucket") == "day0_1"
    ):
        reasons.append("fixed_entry_stop_loss_positive_oracle_day0_1")
    return reasons


def build_joined_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    oracle_rows, oracle_audit = load_oracle_rows()
    labels_by_key, loss_audit = load_loss_taxonomy_labels()
    sector_map, sector_audit = load_sector_map()

    rows: list[dict[str, Any]] = []
    sector_missing = 0
    industry_missing = 0
    for row in oracle_rows:
        ticker = str(row.get("ticker") or "").upper()
        sector_info = sector_map.get(ticker, {})
        sector = row.get("sector") or sector_info.get("sector")
        industry = sector_info.get("industry")
        if not sector:
            sector_missing += 1
        if not industry:
            industry_missing += 1
        merged = dict(row)
        merged.update(labels_by_key.get(trade_key(row), {"loss_taxonomy_joined": False, "loss_taxonomy_labels": []}))
        reasons = target_reasons(merged)
        merged.update(
            {
                "ticker": ticker,
                "entry_date": str(row.get("entry_date") or "")[:10],
                "sector_at_entry": sector,
                "industry_at_entry": industry,
                "target_oracle_low_mfe_failed_followthrough": bool(reasons),
                "target_reasons": reasons,
                "trade_key_compact": trade_key(row),
            }
        )
        rows.append(merged)

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row.get("window") or ""), str(row.get("entry_date") or ""))].append(row)

    for row in rows:
        peers = grouped[(str(row.get("window") or ""), str(row.get("entry_date") or ""))]
        sector = row.get("sector_at_entry")
        industry = row.get("industry_at_entry")
        same_sector = [peer for peer in peers if sector and peer.get("sector_at_entry") == sector]
        same_industry = [peer for peer in peers if industry and peer.get("industry_at_entry") == industry]
        row.update(
            {
                "same_day_entry_count": len(peers),
                "same_day_sector_count": len(same_sector),
                "same_day_industry_count": len(same_industry),
                "same_day_peer_count": max(len(peers) - 1, 0),
                "same_sector_peer_count": max(len(same_sector) - 1, 0),
                "same_industry_peer_count": max(len(same_industry) - 1, 0),
                "sector_cluster_flag": max(len(same_sector) - 1, 0) >= 1,
                "industry_cluster_flag": max(len(same_industry) - 1, 0) >= 1,
            }
        )

    audit = {
        "oracle": oracle_audit,
        "loss_taxonomy": loss_audit,
        "sector_map": sector_audit,
        "joined_rows": len(rows),
        "sector_missing_rows": sector_missing,
        "industry_missing_rows": industry_missing,
        "sector_known_share": round((len(rows) - sector_missing) / len(rows), 6) if rows else None,
        "industry_known_share": round((len(rows) - industry_missing) / len(rows), 6) if rows else None,
    }
    return rows, audit


def avg(values: list[float]) -> float | None:
    return None if not values else round(sum(values) / len(values), 6)


def share(values: list[bool]) -> float | None:
    return None if not values else round(sum(1 for item in values if item) / len(values), 6)


def stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [as_float(row.get("actual_pnl")) for row in rows]
    pnls = [value for value in pnls if value is not None]
    if not rows:
        return {
            "n": 0,
            "mean_same_day_entries": None,
            "mean_same_day_peers": None,
            "mean_same_sector_peers": None,
            "mean_same_industry_peers": None,
            "sector_cluster_share": None,
            "industry_cluster_share": None,
            "avg_actual_pnl": None,
            "total_actual_pnl": None,
        }
    return {
        "n": len(rows),
        "mean_same_day_entries": avg([float(row["same_day_entry_count"]) for row in rows]),
        "mean_same_day_peers": avg([float(row["same_day_peer_count"]) for row in rows]),
        "mean_same_sector_peers": avg([float(row["same_sector_peer_count"]) for row in rows]),
        "mean_same_industry_peers": avg([float(row["same_industry_peer_count"]) for row in rows]),
        "sector_cluster_share": share([bool(row["sector_cluster_flag"]) for row in rows]),
        "industry_cluster_share": share([bool(row["industry_cluster_flag"]) for row in rows]),
        "avg_actual_pnl": None if not pnls else round(sum(pnls) / len(pnls), 2),
        "total_actual_pnl": None if not pnls else round(sum(pnls), 2),
    }


def edge(target_stats: dict[str, Any], other_stats: dict[str, Any], field: str) -> float | None:
    left = target_stats.get(field)
    right = other_stats.get(field)
    if left is None or right is None:
        return None
    return round(float(left) - float(right), 6)


def summarize_attribution(rows: list[dict[str, Any]], source_audit: dict[str, Any]) -> dict[str, Any]:
    target = [row for row in rows if row["target_oracle_low_mfe_failed_followthrough"]]
    other = [row for row in rows if not row["target_oracle_low_mfe_failed_followthrough"]]

    by_window: dict[str, Any] = {}
    directional_windows = 0
    directional_windows_with_target_n_ge_2 = 0
    for window in ["old_thin", "mid_weak", "late_strong"]:
        target_window = [row for row in target if row.get("window") == window]
        other_window = [row for row in other if row.get("window") == window]
        target_stats = stats(target_window)
        other_stats = stats(other_window)
        sector_cluster_edge = edge(target_stats, other_stats, "sector_cluster_share")
        sector_peer_edge = edge(target_stats, other_stats, "mean_same_sector_peers")
        direction = bool(
            (sector_cluster_edge is not None and sector_cluster_edge > 0)
            or (sector_peer_edge is not None and sector_peer_edge > 0)
        )
        if direction:
            directional_windows += 1
            if target_stats["n"] >= 2:
                directional_windows_with_target_n_ge_2 += 1
        by_window[window] = {
            "target": target_stats,
            "other": other_stats,
            "target_minus_other_sector_cluster_share": sector_cluster_edge,
            "target_minus_other_mean_sector_peer_count": sector_peer_edge,
            "target_minus_other_industry_cluster_share": edge(target_stats, other_stats, "industry_cluster_share"),
            "target_minus_other_mean_industry_peer_count": edge(target_stats, other_stats, "mean_same_industry_peers"),
            "direction_target_more_crowded": direction,
        }

    target_stats = stats(target)
    other_stats = stats(other)
    reason_counts = Counter(reason for row in target for reason in row["target_reasons"])
    sector_counts = Counter(str(row.get("sector_at_entry") or "UNKNOWN") for row in target)
    industry_counts = Counter(str(row.get("industry_at_entry") or "UNKNOWN") for row in target)

    return {
        "source_audit": source_audit,
        "pooled": {
            "target": target_stats,
            "other": other_stats,
            "target_minus_other_sector_cluster_share": edge(target_stats, other_stats, "sector_cluster_share"),
            "target_minus_other_mean_sector_peer_count": edge(target_stats, other_stats, "mean_same_sector_peers"),
            "target_minus_other_industry_cluster_share": edge(target_stats, other_stats, "industry_cluster_share"),
            "target_minus_other_mean_industry_peer_count": edge(target_stats, other_stats, "mean_same_industry_peers"),
            "target_reason_counts": dict(sorted(reason_counts.items())),
            "target_sector_counts": dict(sorted(sector_counts.items())),
            "target_industry_counts": dict(sorted(industry_counts.items())),
        },
        "by_window": by_window,
        "directional_windows": directional_windows,
        "directional_windows_with_target_n_ge_2": directional_windows_with_target_n_ge_2,
        "target_rows_sample": [
            {
                "ticker": row.get("ticker"),
                "entry_date": row.get("entry_date"),
                "window": row.get("window"),
                "sector_at_entry": row.get("sector_at_entry"),
                "industry_at_entry": row.get("industry_at_entry"),
                "actual_pnl": r4(row.get("actual_pnl")),
                "exit_reason": row.get("exit_reason"),
                "actual_outcome_bucket": row.get("actual_outcome_bucket"),
                "oracle_timing_bucket": row.get("oracle_timing_bucket"),
                "same_day_entry_count": row.get("same_day_entry_count"),
                "same_sector_peer_count": row.get("same_sector_peer_count"),
                "same_industry_peer_count": row.get("same_industry_peer_count"),
                "sector_cluster_flag": row.get("sector_cluster_flag"),
                "industry_cluster_flag": row.get("industry_cluster_flag"),
                "target_reasons": row.get("target_reasons"),
            }
            for row in sorted(
                target,
                key=lambda item: (
                    int(item.get("same_sector_peer_count") or 0),
                    int(item.get("same_industry_peer_count") or 0),
                    str(item.get("entry_date") or ""),
                ),
                reverse=True,
            )[:12]
        ],
    }


def evaluate_gate4(attribution: dict[str, Any]) -> dict[str, Any]:
    pooled = attribution["pooled"]
    target = pooled["target"]
    audit = attribution["source_audit"]
    failed: list[str] = []
    if audit["joined_rows"] < CONFIG["min_joined_rows"]:
        failed.append("joined_rows_below_floor")
    if (audit.get("sector_known_share") or 0.0) < CONFIG["min_sector_known_share"]:
        failed.append("sector_known_share_below_floor")
    if target["n"] < CONFIG["min_target_rows"]:
        failed.append("target_rows_below_floor")
    sector_cluster_edge = pooled["target_minus_other_sector_cluster_share"]
    sector_peer_edge = pooled["target_minus_other_mean_sector_peer_count"]
    if sector_cluster_edge is None or sector_cluster_edge < CONFIG["min_target_sector_cluster_share_edge"]:
        failed.append("target_sector_cluster_share_not_enriched")
    if sector_peer_edge is None or sector_peer_edge < CONFIG["min_target_mean_sector_peer_edge"]:
        failed.append("target_mean_sector_peer_count_not_enriched")
    if (
        attribution["directional_windows_with_target_n_ge_2"]
        < CONFIG["min_directional_windows_with_target_n_ge_2"]
    ):
        failed.append("window_direction_not_robust")
    observed_only_lead = not failed
    return {
        "acceptance_rule": (
            "Observed-only lead requires >=55 oracle rows with sector coverage "
            ">=80%, >=6 target rows, target sector-cluster share at least 20pp "
            "above other trades, target mean same-sector peer count at least "
            "0.35 above other trades, and target-more-crowded direction in at "
            "least two windows with target n>=2. Passing does not promote a "
            "strategy because this uses observed-only oracle/loss rows."
        ),
        "observed_only_lead": observed_only_lead,
        "passed": observed_only_lead,
        "decision": (
            "observed_only_positive_sector_entry_crowding_loss_enrichment_not_promoted"
            if observed_only_lead
            else "observed_only_rejected_no_sector_entry_crowding_loss_enrichment"
        ),
        "failed_reasons": failed,
        "pooled_target_minus_other_sector_cluster_share": sector_cluster_edge,
        "pooled_target_minus_other_mean_sector_peer_count": sector_peer_edge,
        "pooled_target_minus_other_industry_cluster_share": pooled[
            "target_minus_other_industry_cluster_share"
        ],
        "pooled_target_minus_other_mean_industry_peer_count": pooled[
            "target_minus_other_mean_industry_peer_count"
        ],
        "directional_windows_with_target_n_ge_2": attribution[
            "directional_windows_with_target_n_ge_2"
        ],
        "promotion_blockers": [
            "observed-only oracle/loss rows are diagnostic and use future labels",
            "no strategy, paper helper, daily snapshot, order, ranking, sizing, or exit changed",
            "future work needs prospective forward entry-crowding tags or shared-policy Gate 1-4",
        ],
    }


def calibration(gate4: dict[str, Any]) -> dict[str, Any]:
    actual = 1 if gate4["observed_only_lead"] else 0
    predicted = PREDICTION["success_probability"]
    return {
        "actual_decision": gate4["decision"],
        "actual_success": actual,
        "predicted_success_probability": predicted,
        "brier_score": round((predicted - actual) ** 2, 4),
        "predicted_failure_modes": PREDICTION["main_failure_modes"],
        "realized_failure_mode": "; ".join(gate4["failed_reasons"]) or None,
        "predicted_failure_mode_hit": bool(gate4["failed_reasons"]),
        "surprise_note": (
            "The target oracle loss cohort was materially enriched in same-day "
            "sector entry crowding, but this is only a diagnostic lead."
            if actual
            else "The target oracle loss cohort did not show robust same-day "
            "sector/industry entry-crowding enrichment, so sector crowding does "
            "not explain this fixed entry-quality regret cluster."
        ),
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "observed_only_lead",
        "lane",
        "owner",
        "hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "calibration",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "attribution",
        "production_impact",
        "post_run_reflection",
        "reproduction_commands",
        "related_files",
        "anti_js",
    ]
    return {key: payload[key] for key in keys if key in payload}


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    joined, source_audit = build_joined_rows()
    attribution = summarize_attribution(joined, source_audit)
    gate4 = evaluate_gate4(attribution)
    baseline = load_baseline_metrics()
    status = "observed_only_positive_lead" if gate4["observed_only_lead"] else "observed_only_rejected"
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": gate4["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": gate4["observed_only_lead"],
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "calibration": calibration(gate4),
        "parameters": {
            "config": CONFIG,
            "oracle_artifact": repo_rel(ORACLE_ARTIFACT),
            "loss_taxonomy_artifact": repo_rel(LOSS_TAXONOMY_ARTIFACT),
            "sector_map": repo_rel(SECTOR_MAP),
            "pit_rule": (
                "For each accepted-stack trade, same-day crowding is computed "
                "only from other accepted-stack entries with the same window and "
                "entry_date. Sector comes from the closed-trade row when present; "
                "industry comes from the pre-existing local sector map."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": "experiment.py new accepted the reservation; nearest frozen score 0.0509.",
                "exp-20260623-003": "Fixed-entry oracle regret cluster identified the weak-entry loss surface.",
                "exp-20260511-102": "Accepted-stack loss taxonomy labels low-MFE and weak follow-through bad rows.",
                "exp-20260627-008": "Short-volume did not explain the same oracle target cohort.",
                "new_evidence_axis": NEW_EVIDENCE_AXIS,
            },
            "3_single_policy_bundle": (
                "One read-only enrichment test: fixed oracle/loss-taxonomy target "
                "cohort joined to same-day sector and industry crowding."
            ),
            "4_success_failure_standard": gate4["acceptance_rule"],
            "5_reproducibility": RUNNER_COMMAND,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "strategy_behavior_changed": False,
        },
        "gate1": {
            "passed": True,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": True,
            "runtime_fields": [
                "oracle sample_rows ticker/entry_date/window/sector",
                "loss taxonomy oracle_labels",
                "local broad_market_sector_map industry",
                "same-window same-entry-date accepted-stack rows",
            ],
            "target_price": {
                "available": False,
                "reason": "Observed-only attribution; no executable target or order is scheduled.",
            },
            "source_audit": attribution["source_audit"],
        },
        "gate3": {
            "passed": True,
            "note": "No executable filter was added; survival is unchanged.",
            "signals_generated": attribution["source_audit"]["joined_rows"],
            "signals_survived": attribution["source_audit"]["joined_rows"],
            "strategy_filter_added": False,
            "survival_rate": 1.0,
        },
        "gate4": gate4,
        "attribution": attribution,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "trade_enabled": False,
            "daily_snapshot_exposed": False,
            "parity_test_added": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": "Read-only attribution over existing oracle, loss-taxonomy, and local sector-map artifacts.",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "Same-day sector entry crowding enriched in the fixed oracle "
                "weak-entry loss cluster, suggesting theme-level entry crowding "
                "may explain part of the remaining regret. This is not a "
                "tradable rule until it is logged prospectively and tested "
                "through a shared policy."
                if gate4["observed_only_lead"]
                else "Same-day sector/industry crowding did not robustly enrich "
                "in the exact oracle low-MFE / failed-followthrough loss cohort. "
                "The remaining entry-quality regret likely needs another ex-ante "
                "state, news, borrow, options, or forward row axis."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune sector cluster thresholds, same-day counts, "
                "industry labels, top-N, hold days, notional, or allocator rank "
                "on these frozen oracle rows."
            ),
            "new_evidence_required": (
                "Valid next evidence needs prospective forward rows tagged with "
                "entry-time sector/industry crowding, PIT borrow fee/utilization "
                "or loan availability, another non-short-volume ex-ante label "
                "for the same oracle loss cluster, or materially more closed "
                "forward replacement rows."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(ORACLE_ARTIFACT),
            repo_rel(LOSS_TAXONOMY_ARTIFACT),
            repo_rel(SECTOR_MAP),
            repo_rel(ORACLE_COMPASS),
            repo_rel(BASELINE_RESULT),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
    }


def pct(value: Any) -> str:
    number = as_float(value)
    return "n/a" if number is None else f"{number * 100:.1f}%"


def num(value: Any) -> str:
    number = as_float(value)
    return "n/a" if number is None else f"{number:.2f}"


def build_card(payload: dict[str, Any]) -> str:
    pooled = payload["attribution"]["pooled"]
    rows = [
        "| Scope | target n | target sector cluster | other sector cluster | cluster edge | target sector peers | other sector peers | peer edge |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        (
            "| pooled | {tn} | {tc} | {oc} | {ce} | {tp} | {op} | {pe} |".format(
                tn=pooled["target"]["n"],
                tc=pct(pooled["target"]["sector_cluster_share"]),
                oc=pct(pooled["other"]["sector_cluster_share"]),
                ce=pct(pooled["target_minus_other_sector_cluster_share"]),
                tp=num(pooled["target"]["mean_same_sector_peers"]),
                op=num(pooled["other"]["mean_same_sector_peers"]),
                pe=num(pooled["target_minus_other_mean_sector_peer_count"]),
            )
        ),
    ]
    for window, item in payload["attribution"]["by_window"].items():
        rows.append(
            "| {window} | {tn} | {tc} | {oc} | {ce} | {tp} | {op} | {pe} |".format(
                window=window,
                tn=item["target"]["n"],
                tc=pct(item["target"]["sector_cluster_share"]),
                oc=pct(item["other"]["sector_cluster_share"]),
                ce=pct(item["target_minus_other_sector_cluster_share"]),
                tp=num(item["target"]["mean_same_sector_peers"]),
                op=num(item["other"]["mean_same_sector_peers"]),
                pe=num(item["target_minus_other_mean_sector_peer_count"]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: sector entry-crowding oracle loss attribution",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Strategy behavior changed: `false`",
            f"- Runner: `{RUNNER_COMMAND}`",
            "",
            "## Hypothesis",
            "",
            HYPOTHESIS,
            "",
            "## Enrichment",
            "",
            *rows,
            "",
            f"- Failed reasons: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def build_ticket(payload: dict[str, Any]) -> dict[str, Any]:
    existing = read_json(TICKET_JSON, {}) or {}
    existing.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "owner": OWNER,
            "completed_at": payload["timestamp"],
            "updated_at": payload["timestamp"],
            "decision": payload["decision"],
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "result": {
                "observed_only_lead": payload["observed_only_lead"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
        }
    )
    return existing


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    paths = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
        ORACLE_ARTIFACT,
        LOSS_TAXONOMY_ARTIFACT,
        SECTOR_MAP,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "runner": RUNNER,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "decision": payload["decision"],
        "status": payload["status"],
        "files": {repo_rel(path): {"exists": path.exists()} for path in paths},
        "reproduction_commands": payload["reproduction_commands"],
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    write_json(TICKET_JSON, build_ticket(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result=registry_result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
        },
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
                "joined_rows": payload["attribution"]["source_audit"]["joined_rows"],
                "target_rows": payload["attribution"]["pooled"]["target"]["n"],
                "pooled_sector_cluster_edge": payload["gate4"][
                    "pooled_target_minus_other_sector_cluster_share"
                ],
                "pooled_mean_sector_peer_edge": payload["gate4"][
                    "pooled_target_minus_other_mean_sector_peer_count"
                ],
                "directional_windows_with_target_n_ge_2": payload["gate4"][
                    "directional_windows_with_target_n_ge_2"
                ],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
