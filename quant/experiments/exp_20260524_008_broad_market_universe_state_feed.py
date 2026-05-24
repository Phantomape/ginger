"""exp-20260524-008: broad-market paper feed fallback.

Measurement repair for an alpha blocker. The accepted broad-market paper sleeve
has production-visible selection logic, but daily snapshots were still blocked
because the optional static universe feed was missing. This run records the
fallback that derives a conservative default-off paper feed from the persisted
daily universe governance snapshot.

No live orders, core ranking, core sizing, entries, exits, or backtest fills are
changed.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260524-008"
EXPERIMENT_SLUG = "broad_market_universe_state_feed"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from broad_market_paper_sleeve import (  # noqa: E402
    UNIVERSE_STATE_FEED_RULE_VERSION,
    build_broad_market_candidate_universe_from_universe_state,
)


OUT_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / f"{EXPERIMENT_SLUG}.json"
)
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
OPEN_POSITIONS_JSON = REPO_ROOT / "operator_inputs" / "open_positions.json"
UNIVERSE_STATE_DIR = REPO_ROOT / "data" / "daily" / "universe"


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, set):
        return sorted(_safe(row) for row in value)
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                rows.append(line)
                replaced = True
            else:
                rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _repo_rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_universe_state_path() -> Path:
    paths = sorted(UNIVERSE_STATE_DIR.glob("universe_state_*.json"))
    if not paths:
        raise RuntimeError("No daily universe_state artifact found")
    return paths[-1]


def _audit_open_positions() -> dict[str, Any]:
    payload = _load_json(OPEN_POSITIONS_JSON)
    rows: list[dict[str, Any]] = []
    for section in ("positions", "observations"):
        rows.extend([row for row in payload.get(section, []) if isinstance(row, dict)])
    missing: list[dict[str, str]] = []
    for row in rows:
        for field in ("entry_date", "target_price"):
            value = row.get(field)
            if value is None or str(value).strip() == "":
                missing.append({"ticker": str(row.get("ticker") or ""), "field": field})
    return {
        "path": _repo_rel(OPEN_POSITIONS_JSON),
        "position_rows_checked": len(rows),
        "required_fields": ["entry_date", "target_price"],
        "missing": missing,
        "passed": not missing,
    }


def build_payload() -> dict[str, Any]:
    universe_state_path = _latest_universe_state_path()
    universe_state = _load_json(universe_state_path)
    universe_state["artifact_path"] = _repo_rel(universe_state_path)
    feed = build_broad_market_candidate_universe_from_universe_state(universe_state)
    gate2 = _audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    production_impact = {
        "shared_policy_changed": True,
        "run_adapter_changed": True,
        "backtester_adapter_changed": False,
        "parity_test_added": True,
        "replay_only": False,
        "default_off_paper_only": True,
        "production_signal_path_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "trade_enabled": False,
        "scope": "default_off_broad_market_forward_maturation_feed",
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "measurement_repair",
        "status": "accepted_measurement_repair_no_strategy_change",
        "decision": "accepted_measurement_repair_no_strategy_change",
        "hypothesis": (
            "The accepted default-off broad-market paper edge cannot mature into "
            "forward replacement-value evidence while the production candidate "
            "feed is missing; a conservative feed from daily universe_state can "
            "unblock observation without changing live/core decisions."
        ),
        "alpha_hypothesis": {
            "category": "candidate_pool / measurement_repair",
            "playbook_alignment": (
                "Matches the playbook's broad-market priority: production candidate "
                "feed, closed forward outcomes, replacement value, and concentration "
                "governance before any live sleeve activation."
            ),
        },
        "change_type": "measurement_repair",
        "changed_variable": "broad_market_universe_state_observation_feed_fallback",
        "single_causal_variable": (
            "When the static broad-market paper universe file is missing, run.py "
            "derives an in-memory default-off paper feed from the persisted daily "
            "universe_state observation records."
        ),
        "date_range": {
            "as_of": universe_state.get("as_of"),
            "universe_state_path": _repo_rel(universe_state_path),
        },
        "before_metrics": {
            "canonical_core_ev": 7.8941,
            "canonical_core_pnl": 234850.99,
            "broad_market_feed_status": "missing",
        },
        "after_metrics": {
            "canonical_core_metrics_changed": False,
            "broad_market_feed_status": feed.get("status"),
            "broad_market_feed_ticker_count": len(feed.get("tickers") or []),
            "broad_market_feed_sample": (feed.get("tickers") or [])[:20],
        },
        "delta_metrics": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
        },
        "expected_value_score_delta": 0.0,
        "total_pnl_delta": 0.0,
        "gate1": {
            "baseline": "exp-20260517-009 canonical core baseline",
            "expected_value_score": 7.8941,
            "total_pnl": 234850.99,
            "artifact": "data/experiments/exp-20260517-009/",
        },
        "gate2": gate2,
        "gate3": {
            "strategy_filter_added": False,
            "survival_rate_changed": False,
            "baseline_min_survival_rate": 0.7925,
            "passed": True,
        },
        "gate4": {
            "strategy_gate4_required": False,
            "reason": (
                "No entry, exit, ranking, sizing, live order, or core backtest "
                "decision changes. This is a default-off paper-feed repair."
            ),
            "accepted_as": "measurement_repair",
        },
        "feed": {
            "status": feed.get("status"),
            "rule_version": feed.get("rule_version"),
            "ticker_count": len(feed.get("tickers") or []),
            "excluded_count": feed.get("excluded_count"),
            "source_counts": feed.get("source_counts"),
            "sample_tickers": (feed.get("tickers") or [])[:25],
            "excluded_sample": feed.get("excluded_sample"),
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "candidate_pool/measurement_repair: broad-market paper alpha needs "
                "a production candidate feed before forward replacement-value can "
                "be evaluated."
            ),
            "2_past_similar_experiments": (
                "exp-20260519-035 accepted price_floor_40 replay evidence; "
                "exp-20260519-036 moved it into a shared default-off adapter; "
                "exp-20260520-027 recorded that the current daily blocker is a "
                "missing production feed and zero closed outcomes."
            ),
            "3_single_variable": (
                "Only the missing-feed fallback changes. Broad-market profile, "
                "thresholds, notional scalars, hold days, slots, and trade-enabled "
                "state stay fixed."
            ),
            "4_acceptance": (
                "Accepted if focused tests pass, core metrics are unchanged by "
                "design, the feed is non-missing from the latest universe_state, "
                "and production impact remains default-off/no-orders."
            ),
            "5_reproducibility": (
                "This script, JSON artifact, JSONL log row, tests, and docs identify "
                "the universe_state source, feed rule version, output ticker count, "
                "and zero-decision production impact."
            ),
        },
        "production_impact": production_impact,
        "validation": {
            "focused_tests": [
                ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_broad_market_paper_sleeve.py quant\\test_default_off_alpha_attribution.py",
                ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\broad_market_paper_sleeve.py quant\\run.py quant\\test_broad_market_paper_sleeve.py",
            ],
            "strategy_backtest_rerun_required": False,
        },
        "next_evidence_needed": (
            "Run daily production long enough for the broad-market paper sleeve to "
            "collect pending, open, and closed 20-day replacement-value outcomes; "
            "do not enable a trade adapter until the forward gate passes."
        ),
        "related_files": {
            "shared_module": "quant/broad_market_paper_sleeve.py",
            "run_adapter": "quant/run.py",
            "tests": "quant/test_broad_market_paper_sleeve.py",
            "output": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "ticket": _repo_rel(TICKET_JSON),
            "artifact": _repo_rel(ARTIFACT_MD),
        },
    }


def _experiment_log_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": payload["experiment_id"],
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "trial_family": "broad_market_forward_maturation",
        "changed_variable": payload["changed_variable"],
        "parameters": {
            "feed_rule_version": payload["feed"]["rule_version"],
            "feed_ticker_count": payload["feed"]["ticker_count"],
            "static_feed_precedence": True,
            "trade_enabled": False,
        },
        "date_range": payload["date_range"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "gate4": payload["gate4"],
        "decision": payload["decision"],
        "production_impact": payload["production_impact"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "related_files": payload["related_files"],
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Broad-Market Universe-State Feed",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single causal variable: derive a default-off broad-market paper feed from "
            "`universe_state` only when the static feed file is missing.",
            "",
            "## Gate Summary",
            "",
            f"- Gate 1 baseline: EV `{payload['gate1']['expected_value_score']}`, PnL `${payload['gate1']['total_pnl']:,.2f}`.",
            f"- Gate 2: `{payload['gate2']['passed']}` across `{payload['gate2']['position_rows_checked']}` open-position rows.",
            "- Gate 3: no strategy filter added; survival unchanged.",
            f"- Gate 4: `{payload['gate4']['strategy_gate4_required']}` because this is a no-orders measurement repair.",
            "",
            "## Feed",
            "",
            f"- source: `{payload['date_range']['universe_state_path']}`",
            f"- rule_version: `{payload['feed']['rule_version']}`",
            f"- ticker_count: `{payload['feed']['ticker_count']}`",
            f"- excluded_count: `{payload['feed']['excluded_count']}`",
            f"- sample: `{', '.join(payload['feed']['sample_tickers'][:15])}`",
            "",
            "## Production Impact",
            "",
            "```json",
            json.dumps(payload["production_impact"], indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": payload["experiment_id"],
            "status": payload["status"],
            "decision": payload["decision"],
            "feed": payload["feed"],
            "production_impact": payload["production_impact"],
            "next_evidence_needed": payload["next_evidence_needed"],
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG, _experiment_log_payload(payload))
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "feed_status": payload["feed"]["status"],
                "feed_ticker_count": payload["feed"]["ticker_count"],
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "output": payload["related_files"]["output"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
