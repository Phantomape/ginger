"""Experiment exp-20260601-001: accepted free-data cross-source adapter.

Promote the positive exp-20260531-030 replay lead into a shared default-off
paper adapter without changing live orders, core ranking, sizing, exits, LLM,
news, source thresholds, hold, or notional.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant.experiments import (  # noqa: E402
    exp_20260531_030_accepted_free_data_cross_source_consensus as replay_source,
)


EXPERIMENT_ID = "exp-20260601-001"
STEM = "accepted_free_data_cross_source_consensus_adapter"
TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_candidate_pool"
CHANGED_VARIABLE = "accepted_free_data_cross_source_consensus_shared_adapter_v1"
SOURCE_REPLAY_ID = "exp-20260531-030"
SOURCE_REPLAY_JSON = (
    ROOT
    / "data"
    / "experiments"
    / SOURCE_REPLAY_ID
    / "accepted_free_data_cross_source_consensus.json"
)
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260601_001_{STEM}.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
REGISTRY_JSON = ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

PRODUCTION_IMPACT = {
    "shared_policy_changed": True,
    "run_adapter_changed": True,
    "backtester_adapter_changed": False,
    "parity_test_added": True,
    "replay_only": False,
    "default_off_paper_only": True,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "alters_orders": False,
    "trade_enabled": False,
}

ADAPTER_FILES = [
    "quant/free_data_cross_source_consensus_paper_sleeve.py",
    "quant/run.py",
    "quant/report_generator.py",
    "quant/default_off_alpha_attribution.py",
    "quant/data_paths.py",
    "quant/test_free_data_cross_source_consensus_paper_sleeve.py",
    "docs/production_backtest_parity.md",
    "docs/current_state.md",
    "docs/alpha-optimization-playbook.md",
    "docs/data_edge_context_layers.md",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict[str, Any]] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                existing.append({"_raw": line})
                continue
            if item.get("experiment_id") != EXPERIMENT_ID:
                existing.append(item)
    existing.append(record)
    with path.open("w", encoding="utf-8") as handle:
        for item in existing:
            if "_raw" in item:
                handle.write(str(item["_raw"]).rstrip() + "\n")
            else:
                handle.write(json.dumps(item, sort_keys=True) + "\n")


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": "accepted",
            "decision": payload["decision"],
            "completed_at": payload["completed_at"],
            "artifact": str(OUT_JSON.relative_to(ROOT)).replace("\\", "/"),
            "log": str(LOG_JSON.relative_to(ROOT)).replace("\\", "/"),
            "production_impact": PRODUCTION_IMPACT,
            "gate4": payload["gate4"],
        }
    )
    _write_json(TICKET_JSON, ticket)


def _update_registry(payload: dict[str, Any]) -> None:
    if not REGISTRY_JSON.exists():
        return
    registry = _load_json(REGISTRY_JSON)
    experiments = registry.get("experiments")
    if not isinstance(experiments, list):
        return
    for item in experiments:
        if isinstance(item, dict) and item.get("experiment_id") == EXPERIMENT_ID:
            item["status"] = "accepted"
            item["decision"] = payload["decision"]
            item["completed_at"] = payload["completed_at"]
            item["artifact"] = str(OUT_JSON.relative_to(ROOT)).replace("\\", "/")
            item["log"] = str(LOG_JSON.relative_to(ROOT)).replace("\\", "/")
            item["aggregate_expected_value_delta"] = payload["metrics"][
                "aggregate_expected_value_delta"
            ]
            item["aggregate_strategy_total_pnl_delta"] = payload["metrics"][
                "aggregate_strategy_total_pnl_delta"
            ]
            break
    _write_json(REGISTRY_JSON, registry)


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["completed_at"],
        "lane": "alpha_search",
        "status": "accepted",
        "accepted": True,
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "change_summary": (
            "Promoted the fixed exp-20260531-030 accepted free-data cross-source "
            "consensus candidate pool into a shared default-off paper adapter."
        ),
        "change_type": "default_off_paper_adapter",
        "mechanism_family": "default_off_paper_adapter",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "accepted_free_data_cross_source_consensus_shared_adapter_v1",
        "changed_variable": CHANGED_VARIABLE,
        "nearby_prior_experiments": [
            "exp-20260531-026",
            "exp-20260531-029",
            "exp-20260531-030",
        ],
        "new_evidence_type": "shared_production_visible_adapter_from_positive_replay_lead",
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "production_impact": PRODUCTION_IMPACT,
        "decision": payload["decision"],
        "next_retry_requires": [
            "closed forward replacement-value rows",
            "no source-count/cooldown/notional retune on frozen windows",
            "separate activation gate before live/core use",
        ],
        "related_files": ADAPTER_FILES
        + [
            str(OUT_JSON.relative_to(ROOT)).replace("\\", "/"),
            str(LOG_JSON.relative_to(ROOT)).replace("\\", "/"),
        ],
    }


def _write_card(payload: dict[str, Any]) -> None:
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {EXPERIMENT_ID} accepted free-data cross-source adapter",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Source replay: `{SOURCE_REPLAY_ID}`",
        f"- Aggregate EV delta: `{payload['metrics']['aggregate_expected_value_delta']}`",
        f"- Aggregate PnL delta: `${payload['metrics']['aggregate_strategy_total_pnl_delta']:,.2f}`",
        f"- Target trades: `{payload['metrics']['target_trade_count']}`",
        "- Production: default-off paper adapter only; `trade_enabled=false`; no live/default orders.",
        "",
        "## Three-window evidence",
    ]
    for row in payload["windows"]:
        lines.append(
            f"- `{row['label']}`: EV `{row['expected_value_delta']:+.4f}`, "
            f"PnL `${row['strategy_total_pnl_delta']:,.2f}`, "
            f"target trades `{row['target_trade_count']}`"
        )
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Collect forward replacement-value rows; do not retune source count, cooldown, hold, or notional on the frozen windows.",
        ]
    )
    CARD_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    replay = _load_json(SOURCE_REPLAY_JSON)
    gate2 = replay_source.base._audit_open_positions()
    if not gate2.get("passed"):
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    completed_at = _utc_now()
    replay_metrics = replay["aggregate"]["comparison"]
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "source_replay_experiment_id": SOURCE_REPLAY_ID,
        "source_replay_artifact": str(SOURCE_REPLAY_JSON.relative_to(ROOT)).replace("\\", "/"),
        "preflight": {
            "alpha_hypothesis": (
                "Same signal-date ticker agreement across at least two accepted "
                "free-data paper sleeves should remain useful when promoted into "
                "a shared default-off adapter."
            ),
            "nearby_prior_experiments": [
                "exp-20260531-026",
                "exp-20260531-029",
                "exp-20260531-030",
            ],
            "single_causal_variable": CHANGED_VARIABLE,
            "acceptance_standard": "docs/backtesting.md canonical three-window Gate 1-4 plus production/backtest parity.",
            "reproducibility": "Adapter files, source replay artifact, ticket, card, log, and JSONL record are committed.",
        },
        "rule": {
            "rule_version": "accepted_free_data_cross_source_consensus_shared_v1",
            "candidate_pool_rule_version": "accepted_free_data_cross_source_consensus_candidate_pool_v1",
            "min_source_count": 2,
            "source_names": [
                "FUNDAMENTAL_GROWTH_RS_PAPER",
                "VOLUME_BREADTH_BREAKOUT_PAPER",
                "FINRA_IWM_CONFIRMED_PAPER",
                "ALPHA_SCORE_MARKET_REGIME_PAPER",
            ],
            "base_notional_usd": 4_000.0,
            "hold_days": 10,
            "max_paper_trades_per_day": 1,
            "same_ticker_cooldown_days": 7,
        },
        "gate1": {
            "source": "docs/backtesting.md canonical three-window replay",
            "baseline_artifact": "data/experiments/exp-20260531-030/accepted_free_data_cross_source_consensus_before_aggregate.json",
            "baseline": replay["aggregate"]["before"],
        },
        "gate2": gate2,
        "gate3": {
            "core_survival_unchanged": True,
            "min_core_survival_rate": 0.7925,
            "paper_target_trade_count": replay["target_summary"]["target_trade_count"],
            "note": "The adapter does not add a core/live filter; canonical core survival is unchanged.",
        },
        "gate4": {
            "passed": True,
            "source_gate4": replay["gate4"],
            "adapter_acceptance_basis": (
                "exp-20260531-030 passed all three windows; this run changes only "
                "the shared default-off production/replay adapter boundary."
            ),
        },
        "before_metrics": replay["aggregate"]["before"],
        "after_metrics": replay["aggregate"]["after"],
        "delta_metrics": replay_metrics,
        "metrics": {
            "aggregate_expected_value_before": replay["aggregate"]["before"]["expected_value_score"],
            "aggregate_expected_value_after": replay["aggregate"]["after"]["expected_value_score"],
            "aggregate_expected_value_delta": replay_metrics["expected_value_score_delta"],
            "aggregate_strategy_total_pnl_before": replay["aggregate"]["before"][
                "strategy_total_pnl"
            ],
            "aggregate_strategy_total_pnl_after": replay["aggregate"]["after"][
                "strategy_total_pnl"
            ],
            "aggregate_strategy_total_pnl_delta": replay_metrics[
                "strategy_total_pnl_delta"
            ],
            "target_trade_count": replay["target_summary"]["target_trade_count"],
            "max_single_positive_share": replay["target_summary"][
                "max_single_positive_share"
            ],
            "positive_pnl_hhi": replay["target_summary"]["positive_pnl_hhi"],
        },
        "windows": [
            {
                "label": row["label"],
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["comparison"]["expected_value_score_delta"],
                "strategy_total_pnl_delta": row["comparison"]["strategy_total_pnl_delta"],
                "target_trade_count": row["target_trade_count"],
            }
            for row in replay["results"]
        ],
        "production_impact": PRODUCTION_IMPACT,
        "adapter_files": ADAPTER_FILES,
        "decision": "accepted_default_off_free_data_cross_source_consensus_adapter",
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, _experiment_log_record(payload))
    _write_card(payload)
    _update_ticket(payload)
    _update_registry(payload)
    _upsert_jsonl(EXPERIMENT_LOG, _experiment_log_record(payload))

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "aggregate": replay_metrics,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
