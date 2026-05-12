"""Build a read-only forward ledger coverage manifest.

This observed-only measurement experiment inventories default-off forward
ledgers and paper state files. It does not import strategy modules or alter
entries, exits, ranking, sizing, risk, filters, prompts, or orders.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260511-101"
DEFAULT_BASELINE = Path("data/experiments/exp-20260510-015/trip_sector_taxonomy.json")
DEFAULT_OUTPUT = Path(
    "data/experiments/exp-20260511-101/"
    "exp_20260511_101_forward_ledger_coverage_manifest.json"
)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def try_load_json(path: Path) -> tuple[Any, str | None]:
    if not path.exists():
        return None, "missing"
    try:
        return load_json(path), None
    except Exception as exc:  # noqa: BLE001 - manifest should record parse gaps.
        return None, str(exc)


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig") as handle:
        return sum(1 for line in handle if line.strip())


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def repo_path(path: Path) -> str:
    return str(path).replace("\\", "/")


def snapshot_path_for_state(path: Path) -> Path:
    name = path.name
    if name.endswith("_paper_state.json"):
        return path.with_name(name.replace("_paper_state.json", "_paper_snapshots.jsonl"))
    if name.endswith("_state.json"):
        return path.with_name(name.replace("_state.json", "_snapshots.jsonl"))
    return path.with_suffix(".jsonl")


def state_counts(payload: Any) -> dict[str, int]:
    doc = payload if isinstance(payload, dict) else {}
    skipped = as_list(doc.get("skipped_entries")) + as_list(doc.get("skipped_days"))
    pending = as_list(doc.get("pending_entries")) + as_list(doc.get("new_pending_entries"))
    closed_today = as_list(doc.get("closed_positions_today"))
    return {
        "pending_entries": len(pending),
        "open_positions": len(as_list(doc.get("open_positions"))),
        "closed_positions": len(as_list(doc.get("closed_positions"))),
        "closed_positions_today": len(closed_today),
        "skipped_entries": len(skipped),
    }


def has_frozen_counterfactual(row: Any) -> bool:
    if not isinstance(row, dict):
        return False
    for key in ("counterfactual", "counterfactuals"):
        value = row.get(key)
        if isinstance(value, dict) and (value.get("frozen") is True or value.get("frozen_asof")):
            return True
    source = row.get("source_candidate")
    if isinstance(source, dict):
        return has_frozen_counterfactual(source)
    candidate = row.get("candidate")
    if isinstance(candidate, dict):
        return has_frozen_counterfactual(candidate)
    return False


def summarize_state_file(path: Path) -> dict[str, Any]:
    payload, error = try_load_json(path)
    doc = payload if isinstance(payload, dict) else {}
    counts = state_counts(doc)
    closed_rows = as_list(doc.get("closed_positions")) + as_list(doc.get("closed_positions_today"))
    open_rows = as_list(doc.get("open_positions"))
    snapshot_path = snapshot_path_for_state(path)
    closed_with_counterfactual = sum(1 for row in closed_rows if has_frozen_counterfactual(row))
    open_with_counterfactual = sum(1 for row in open_rows if has_frozen_counterfactual(row))
    ledger_rows = (
        counts["pending_entries"]
        + counts["open_positions"]
        + counts["closed_positions"]
        + counts["closed_positions_today"]
        + counts["skipped_entries"]
    )
    blocked_reasons: list[str] = []
    if error:
        blocked_reasons.append(f"state_file_{error}")
    if counts["closed_positions"] + counts["closed_positions_today"] == 0:
        blocked_reasons.append("no_closed_forward_outcomes")
    if closed_with_counterfactual == 0:
        blocked_reasons.append("no_closed_frozen_counterfactual_outcomes")
    if ledger_rows == 0:
        blocked_reasons.append("no_current_ledger_rows")

    return {
        "family": "paper_state",
        "name": path.stem,
        "state_file": repo_path(path),
        "exists": path.exists(),
        "parse_error": error if error != "missing" else None,
        "sleeve": doc.get("sleeve"),
        "schema_version": doc.get("schema_version"),
        "updated_at": doc.get("updated_at"),
        "snapshot_file": repo_path(snapshot_path),
        "snapshot_exists": snapshot_path.exists(),
        "snapshot_rows": count_jsonl(snapshot_path),
        "counts": counts,
        "ledger_rows": ledger_rows,
        "has_candidate_coverage": ledger_rows > 0 or count_jsonl(snapshot_path) > 0,
        "has_open_outcomes": counts["open_positions"] > 0,
        "has_closed_outcomes": counts["closed_positions"] + counts["closed_positions_today"] > 0,
        "has_closed_replacement_value": closed_with_counterfactual > 0,
        "open_positions_with_frozen_counterfactual": open_with_counterfactual,
        "closed_positions_with_frozen_counterfactual": closed_with_counterfactual,
        "blocked_reasons": blocked_reasons,
    }


def latest_file(paths: list[Path]) -> Path | None:
    existing = [path for path in paths if path.exists()]
    if not existing:
        return None
    return max(existing, key=lambda p: p.stat().st_mtime)


def summarize_watch_summary(path: Path) -> dict[str, Any]:
    payload, error = try_load_json(path)
    doc = payload if isinstance(payload, dict) else {}
    ledger_path = Path(str(doc.get("ledger_path") or ""))
    ledger_rows = int(doc.get("ledger_row_count") or count_jsonl(ledger_path))
    candidate_count = int(doc.get("candidate_count") or doc.get("row_count") or 0)
    matched_candidates = int(
        doc.get("matched_candidate_rows")
        or doc.get("estimate_revision_usable_and_matched_candidate_rows")
        or 0
    )
    blocked_reasons: list[str] = []
    if error:
        blocked_reasons.append(f"summary_file_{error}")
    if ledger_rows == 0:
        blocked_reasons.append("no_ledger_rows")
    if candidate_count == 0:
        blocked_reasons.append("no_current_candidates")
    if matched_candidates == 0 and "estimate_revision" in path.name:
        blocked_reasons.append("no_candidate_signal_matches")

    return {
        "family": "forward_watch_summary",
        "name": path.stem,
        "summary_file": repo_path(path),
        "exists": path.exists(),
        "parse_error": error if error != "missing" else None,
        "watch_name": doc.get("watch_name") or doc.get("mode") or doc.get("scope"),
        "schema_version": doc.get("schema_version"),
        "updated_at": doc.get("updated_at") or doc.get("generated_at"),
        "as_of_date": doc.get("asof_date") or doc.get("as_of_date"),
        "ledger_file": repo_path(ledger_path) if str(ledger_path) else None,
        "ledger_exists": ledger_path.exists() if str(ledger_path) else False,
        "ledger_rows": ledger_rows,
        "candidate_count": candidate_count,
        "matched_candidate_rows": matched_candidates,
        "matched_selected_signal_rows": int(doc.get("matched_selected_signal_rows") or 0),
        "has_candidate_coverage": candidate_count > 0 or ledger_rows > 0,
        "has_closed_outcomes": bool(doc.get("outcome_close_summary", {}).get("closed_count"))
        if isinstance(doc.get("outcome_close_summary"), dict)
        else False,
        "has_closed_replacement_value": False,
        "blocked_reasons": blocked_reasons,
        "selected_metrics": {
            key: doc.get(key)
            for key in sorted(doc)
            if key.endswith("_count")
            or key.endswith("_rows")
            or key.endswith("_rate")
            or key in {"pit_safe_rate", "candidate_match_rate", "row_count"}
        },
    }


def baseline_metrics(path: Path) -> dict[str, Any]:
    payload, _ = try_load_json(path)
    doc = payload if isinstance(payload, dict) else {}
    aggregate = doc.get("aggregate") if isinstance(doc.get("aggregate"), dict) else {}
    return {
        "baseline_result_file": repo_path(path),
        "expected_value_score": doc.get("expected_value_score") or aggregate.get("expected_value_score"),
        "total_pnl": doc.get("total_pnl") or aggregate.get("total_pnl"),
        "max_drawdown_pct": doc.get("max_drawdown_pct") or aggregate.get("max_drawdown_pct"),
        "trade_count": doc.get("trade_count") or doc.get("total_trades") or aggregate.get("trade_count"),
    }


def discover_state_files(data_dir: Path) -> list[Path]:
    patterns = [
        "*_paper_state.json",
        "*_overlay_state.json",
        "low_deployment_etf_overlay_state.json",
    ]
    out: set[Path] = set()
    for pattern in patterns:
        out.update(data_dir.glob(pattern))
    return sorted(out)


def discover_summary_files(data_dir: Path) -> list[Path]:
    paths = [
        data_dir / "platform_rs20_no_gap_forward_watch_summary.json",
        data_dir / "sec_10k_liquidity_forward_watch_summary.json",
    ]
    estimate_latest = latest_file(sorted((data_dir / "non_ohlcv").glob("estimate_revision_ledger_summary_*.json")))
    if estimate_latest:
        paths.append(estimate_latest)
    options_report = data_dir / "non_ohlcv" / "options_forward_candidate_ledger_report.json"
    if options_report.exists():
        paths.append(options_report)
    return paths


def build_manifest(data_dir: Path, baseline_path: Path) -> dict[str, Any]:
    states = [summarize_state_file(path) for path in discover_state_files(data_dir)]
    summaries = [summarize_watch_summary(path) for path in discover_summary_files(data_dir)]
    ledgers = states + summaries
    totals = {
        "ledger_count": len(ledgers),
        "ledgers_with_candidate_coverage": sum(1 for row in ledgers if row.get("has_candidate_coverage")),
        "ledgers_with_open_outcomes": sum(1 for row in ledgers if row.get("has_open_outcomes")),
        "ledgers_with_closed_outcomes": sum(1 for row in ledgers if row.get("has_closed_outcomes")),
        "ledgers_with_closed_replacement_value": sum(1 for row in ledgers if row.get("has_closed_replacement_value")),
        "paper_state_snapshot_rows": sum(int(row.get("snapshot_rows") or 0) for row in states),
        "paper_state_open_positions": sum(int(row.get("counts", {}).get("open_positions") or 0) for row in states),
        "paper_state_closed_positions": sum(
            int(row.get("counts", {}).get("closed_positions") or 0)
            + int(row.get("counts", {}).get("closed_positions_today") or 0)
            for row in states
        ),
        "forward_watch_ledger_rows": sum(int(row.get("ledger_rows") or 0) for row in summaries),
        "forward_watch_candidate_count": sum(int(row.get("candidate_count") or 0) for row in summaries),
    }
    blocked = []
    if totals["ledgers_with_closed_replacement_value"] == 0:
        blocked.append("no ledger currently has closed frozen-counterfactual replacement-value outcomes")
    if totals["paper_state_open_positions"] > 0 and totals["paper_state_closed_positions"] == 0:
        blocked.append("paper positions exist but are still open, so forward outcomes are immature")
    if totals["forward_watch_candidate_count"] == 0:
        blocked.append("watch summaries do not yet expose current matched candidate coverage")

    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "measurement_repair",
        "change_type": "measurement_instrumentation",
        "single_causal_variable": "forward ledger coverage manifest",
        "strategy_behavior_changed": False,
        "baseline_metrics": baseline_metrics(baseline_path),
        "after_metrics": baseline_metrics(baseline_path),
        "expected_value_score_delta": 0.0,
        "alpha_hypothesis_blocked": {
            "category": "LLM/event/ranking/forward attribution",
            "hypothesis": (
                "Default-off forward ledgers can support future LLM/event/ranking alpha "
                "only when they expose candidate coverage and enough closed replacement-value outcomes."
            ),
            "blocked_reasons": blocked,
        },
        "historical_constraints": {
            "related_prior_closeouts": [
                "docs/experiments/logs/exp-20260505-027.json",
                "docs/experiments/logs/exp-20260506-027.json",
                "docs/experiments/logs/exp-20260508-030.json",
                "docs/experiments/logs/exp-20260509-022.json",
            ],
            "guardrails": [
                "Do not treat LLM output schema inconsistency as the main issue here.",
                "Do not promote default-off event, state-surface, ETF, options, estimate-revision, or watch ledgers until closed outcomes exist.",
                "This manifest changes one measurement variable only: forward ledger coverage visibility.",
            ],
        },
        "coverage_totals": totals,
        "ledgers": ledgers,
        "readiness": {
            "ready_for_forward_alpha_promotion_test": totals["ledgers_with_closed_replacement_value"] > 0,
            "ready_for_open_position_monitoring": totals["paper_state_open_positions"] > 0,
            "blocked": blocked,
            "minimum_next_step": (
                "Keep daily default-off ledgers running until paper positions close; "
                "then run a separate alpha ticket using this manifest to select the "
                "ledger family with closed replacement-value coverage."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
        },
        "gate4": {
            "applicable": False,
            "reason": "Observed-only coverage manifest; no strategy behavior or backtest metrics changed.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    manifest = build_manifest(Path(args.data_dir), Path(args.baseline))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "experiment_id": manifest["experiment_id"],
                "output": repo_path(output),
                "coverage_totals": manifest["coverage_totals"],
                "readiness": manifest["readiness"],
                "strategy_behavior_changed": manifest["strategy_behavior_changed"],
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
