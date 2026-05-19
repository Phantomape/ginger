"""exp-20260509-007 current-stack non-generic event state add-on.

Alpha search. Revalidates the strongest current event-bundle allocation lead
after exp-20260509-006 refreshed the accepted core stack: only event-bundle
rows with a positive PIT state score on a named non-generic state surface get a
2.0x paper-notional add-on. This does not change live orders, default backtest
behavior, core A/B ranking, sizing, exits, add-ons, LLM, or news behavior.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from experiments import exp_20260507_026_non_generic_event_state_addon as base


EXPERIMENT_ID = "exp-20260509-007"
STEM = "non_generic_event_state_addon_current_stack"
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(base._safe(payload), indent=2, ensure_ascii=True, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _retag_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = dict(payload)
    payload["experiment_id"] = EXPERIMENT_ID
    payload["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload["change_type"] = "current_stack_event_state_surface_addon_revalidation"
    payload["hypothesis"] = (
        "After the current accepted stack refresh, the highest-value event-bundle "
        "allocation alpha is still to add bounded paper notional only to event rows "
        "with positive PIT state score on non-generic state surfaces."
    )
    payload["alpha_hypothesis"] = {
        "category": "allocation/event-quality",
        "entry_exit_ranking_or_allocation": "allocation",
        "why_this_now": (
            "exp-20260509-006 shows the frozen event bundle is still the strongest "
            "positive non-core alpha direction, while LLM soft-ranking, earnings "
            "revision fields, core threshold/ranking/slot surfaces, and generic "
            "add-on reserve work are blocked, rejected, or too small."
        ),
    }
    payload["historical_experiment_check"] = {
        "direct_parent": {
            "exp-20260507-026": (
                "Non-generic positive state-surface event add-on beat the full bundle "
                "on the prior stack."
            ),
            "exp-20260509-006": (
                "Current-stack full event bundle revalidation improved EV in all "
                "three canonical windows and remained the strongest alpha surface."
            ),
        },
        "nearby_rejected_or_blocked": {
            "exp-20260509-002": "Core-overlap event filter failed to improve the full bundle.",
            "exp-20260509-004": "Generic entry-heat reserve was inert or harmful.",
            "exp-20260509-005": "Clean mid-dispersion trend top-up was positive but below Gate 4 materiality.",
            "LLM soft-ranking": "Still too few production-aligned ranking-eligible outcome rows.",
            "earnings/revisions": "Still lacks enough multi-window candidate touches for ranking promotion.",
        },
        "why_not_simple_repeat": (
            "This is not a new threshold/source/hold-period sweep. It is a current-stack "
            "revalidation of the one prior event-allocation discriminator that already "
            "beat the full bundle, with all source definitions and core behavior locked."
        ),
        "mechanism_insight_conflict": (
            "No conflict: the run avoids LLM ranking, earnings field promotion, raw "
            "heat-cap relaxation, source pruning, same-sector/TQS ordering, and broad "
            "universe growth."
        ),
    }
    payload["production_impact"] = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "parity_test_added": False,
        "production_signal_path_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "production_impact": "experiment_only_no_live_or_default_backtest_strategy_change",
        "parity_note": (
            "Production already exposes the same default-off event bundle "
            "state_surface_addon schema as paper attribution; this experiment only "
            "replays the paper notional effect historically."
        ),
        "promotion_blocker_if_positive": (
            "Before live capital, add an explicit shared trade-enabled event adapter, "
            "backtester/run parity tests, and closed forward paper replacement-value evidence."
        ),
    }
    if payload.get("decision") != "rejected":
        payload["decision_rationale"] = (
            "Accepted as the current event-bundle allocation alpha lead for "
            "default-off paper optimization: non_generic_positive_add_200 beat "
            "the full frozen event bundle and the current core baseline across "
            "all three canonical windows with zero EV regressions. Production "
            "already exposes matching paper attribution fields, but live orders "
            "remain blocked until a shared trade-enabled event adapter, parity "
            "tests, and closed forward replacement-value outcomes exist."
        )
        payload["rejection_reason"] = None
    else:
        payload["decision_rationale"] = (
            "Rejected on the current stack: the non-generic state-surface event "
            "add-on did not beat the full frozen event bundle with enough stable "
            "three-window EV improvement and materiality."
        )
        payload["rejection_reason"] = payload["decision_rationale"]
    payload["next_action"] = (
        "Keep this as the current event-bundle allocation alpha lead; do not enable "
        "orders until forward paper outcomes and a shared trade adapter clear parity."
    )
    payload["why_not_other_attractive_points"] = (
        "I skipped LLM ranking, earnings revisions, event source pruning, generic heat "
        "reserve, clean mid-dispersion risk, and core ranking/slot retunes because recent "
        "records mark them data-limited, rejected, or below materiality."
    )
    payload["risk_of_change"] = (
        "The 2.0x paper add-on concentrates a sparse event subset; it can overstate live "
        "capacity until forward paper replacement-value outcomes close."
    )
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(ARTIFACT_MD),
        "docs/experiment_log.jsonl",
        "docs/alpha-optimization-playbook.md",
    ]
    return payload


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    gate = payload["delta_metrics"]["variant_vs_full_bundle"][best]
    lines = [
        "# exp-20260509-007 Non-Generic Event State Add-On Current Stack",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "Alpha search. Current-stack revalidation of the event-bundle paper allocation add-on: 2.0x paper notional only for positive PIT state-score events on non-generic state surfaces.",
        "",
        "## Best Variant Vs Full Bundle",
        "",
        "| Window | Full EV | Variant EV | Delta EV | Full PnL | Variant PnL | Delta PnL | Event trades | Event PnL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"]["full_event_bundle"][label]
        after = payload["after_metrics"][best][label]
        delta = gate["delta"]["by_window"][label]
        selected = payload["event_selection"][best][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | "
            "${apnl:,.2f} | ${dpnl:+,.2f} | {trades} | ${epnl:+,.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                trades=selected["trade_count"],
                epnl=selected["total_pnl"],
            )
        )
    lines.extend(
        [
            "",
            "## Aggregate Gate",
            "",
            "- EV delta vs full bundle: {:+.4f} ({:+.2%})".format(
                gate["delta"]["aggregate_ev_delta"],
                gate["delta"]["aggregate_ev_delta_pct"] or 0.0,
            ),
            "- PnL delta vs full bundle: ${:+,.2f} ({:+.2%})".format(
                gate["delta"]["aggregate_pnl_delta"],
                gate["delta"]["aggregate_pnl_delta_pct"] or 0.0,
            ),
            "- EV windows improved/regressed: {}/{}".format(
                gate["delta"]["windows_ev_improved"],
                gate["delta"]["windows_ev_regressed"],
            ),
            "",
            "## Coverage",
            "",
            "```json",
            json.dumps(
                payload["coverage"]["state_surface_addon"],
                indent=2,
                sort_keys=True,
            ),
            "```",
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"],
            "",
            "## Production Impact",
            "",
            "No live orders, default backtest strategy, core A/B behavior, LLM, or news path changed. Production already exposes the same default-off paper attribution schema; live capital still needs an explicit shared trade adapter and parity tests.",
            "",
        ]
    )
    return "\n".join(lines)


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Non-generic event state add-on current stack",
            "status": payload["status"],
            "decision": payload["decision"],
            "summary": payload["decision_rationale"],
            "created_at": payload["timestamp"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "log": _repo_rel(LOG_JSON),
            "next_action": payload["next_action"],
        },
    )
    _write_text(ARTIFACT_MD, _artifact_markdown(payload))

    compact = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "market_regime_summary": payload["market_regime_summary"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "delta_metrics": payload["delta_metrics"],
        "best_variant": payload["best_variant"],
        "coverage": payload["coverage"],
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "decision_rationale": payload["decision_rationale"],
        "rejection_reason": payload["rejection_reason"],
        "related_files": payload["related_files"],
    }
    lines: list[str] = []
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()
        lines = [
            line
            for line in lines
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    lines.append(json.dumps(base._safe(compact), sort_keys=True))
    EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = _retag_payload(base.build_payload())
    persist(payload)
    best = payload["best_variant"]
    print(
        json.dumps(
            base._safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "best_variant": best,
                    "best_variant_vs_full_bundle": payload["delta_metrics"]["variant_vs_full_bundle"][best]["delta"],
                    "best_variant_vs_core": payload["delta_metrics"]["variant_vs_core"][best]["delta"],
                    "coverage": payload["coverage"]["state_surface_addon"],
                    "production_impact": payload["production_impact"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
