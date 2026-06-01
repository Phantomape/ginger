"""exp-20260601-022: gross-margin alpha blocker decision.

This is a measurement-repair closeout for the current Alpha Search run. It
does not change strategy behavior. It records why the strongest current alpha
lead should not be promoted until baseline parity is resolved.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


EXPERIMENT_ID = "exp-20260601-022"
STEM = "exp_20260601_022_gross_margin_alpha_blocker_decision"

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

BASELINE_AUDIT_JSON = (
    ROOT
    / "data"
    / "experiments"
    / "exp-20260601-016"
    / "exp_20260601_016_current_baseline_parity_audit.json"
)
GROSS_MARGIN_JSON = (
    ROOT
    / "data"
    / "experiments"
    / "exp-20260601-021"
    / "exp_20260601_021_companyfacts_gross_margin_rs_candidate_pool.json"
)
META_RESEARCH_JSON = (
    ROOT / "data" / "tmp" / "meta_research_report_alpha_search_20260601_next.json"
)

PRODUCTION_IMPACT = {
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "parity_test_added": False,
    "replay_only": False,
    "trade_enabled": False,
    "production_orders_changed": False,
    "production_signal_path_changed": False,
    "production_watchlist_changed": False,
    "alters_orders": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = ROOT / value
    return str(value.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _git_output(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return (proc.stdout or proc.stderr or "").strip()


def _sum_window_metric(windows: dict[str, Any], side: str, metric: str) -> float:
    total = 0.0
    for row in windows.values():
        total += float((row.get(side) or {}).get(metric) or 0.0)
    return round(total, 4 if "expected_value" in metric else 2)


def _window_summary(gross_margin: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for label, row in gross_margin.get("window_results", {}).items():
        before = row.get("before") or {}
        after = row.get("after") or {}
        delta = row.get("delta") or {}
        rows.append(
            {
                "label": label,
                "start": row.get("start"),
                "end": row.get("end"),
                "snapshot": row.get("snapshot"),
                "before_expected_value_score": before.get("expected_value_score"),
                "after_expected_value_score": after.get("expected_value_score"),
                "expected_value_score_delta": delta.get("expected_value_score"),
                "before_total_pnl": before.get("total_pnl"),
                "after_total_pnl": after.get("total_pnl"),
                "total_pnl_delta": delta.get("total_pnl"),
                "target_trade_count": row.get("target_trade_count"),
                "survival_rate": before.get("survival_rate"),
                "max_drawdown_delta": delta.get("max_drawdown_pct"),
            }
        )
    return rows


def _summarize_meta_research() -> dict[str, Any]:
    if not META_RESEARCH_JSON.exists():
        return {
            "path": _repo_rel(META_RESEARCH_JSON),
            "available": False,
            "note": "Meta research output was not present.",
        }
    report = _read_json(META_RESEARCH_JSON)
    return {
        "path": _repo_rel(META_RESEARCH_JSON),
        "available": True,
        "research_priorities": report.get("research_priorities", [])[:5],
        "freeze_candidates": report.get("freeze_candidates", [])[:5],
        "recommendations": report.get("recommendations", [])[:5],
    }


def _write_card(payload: dict[str, Any]) -> None:
    baseline = payload["gate1_baseline_blocker"]["aggregate"]
    gm = payload["strongest_alpha_lead"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} gross-margin alpha blocker decision",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Alpha direction: `{payload['recommended_alpha_direction']}`",
        f"- Blocker: `{payload['blocking_item']}`",
        f"- Docs accepted EV/PnL: `{baseline['docs_expected_value_score']:.4f}` / `${baseline['docs_total_pnl']:,.2f}`",
        f"- Current EV/PnL: `{baseline['current_expected_value_score']:.4f}` / `${baseline['current_total_pnl']:,.2f}`",
        f"- Drift: `{baseline['expected_value_score_delta']:+.4f}` EV / `${baseline['total_pnl_delta']:+,.2f}`",
        f"- Gross-margin three-window EV/PnL lead: `{gm['expected_value_score_delta']:+.4f}` / `${gm['total_pnl_delta']:+,.2f}`",
        f"- Gross-margin target trades: `{gm['target_trade_count']}`",
        "",
        "## Three-Window Gross-Margin Evidence",
        "",
        "| window | EV before | EV after | EV delta | PnL delta | target trades |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in payload["strongest_alpha_lead"]["windows"]:
        lines.append(
            f"| {row['label']} | {row['before_expected_value_score']:.4f} | "
            f"{row['after_expected_value_score']:.4f} | "
            f"{row['expected_value_score_delta']:+.4f} | "
            f"${row['total_pnl_delta']:+,.2f} | {row['target_trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            payload["conclusion"],
            "",
            "No entries, exits, ranking, sizing, LLM/news path, watchlists, paper-ledger semantics, or live/default orders changed.",
            "",
        ]
    )
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.write_text("\n".join(lines), encoding="utf-8")


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _read_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": "accepted",
            "decision": payload["decision"],
            "completed_at": payload["timestamp"],
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "production_impact": PRODUCTION_IMPACT,
            "result": {
                "blocking_item": payload["blocking_item"],
                "recommended_alpha_direction": payload["recommended_alpha_direction"],
                "baseline_matches_docs": False,
                "gross_margin_ev_delta": payload["strongest_alpha_lead"]["aggregate"][
                    "expected_value_score_delta"
                ],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)


def build_payload() -> dict[str, Any]:
    baseline = _read_json(BASELINE_AUDIT_JSON)
    gross_margin = _read_json(GROSS_MARGIN_JSON)
    baseline_aggregate = baseline["baseline_comparison"]["aggregate"]
    gm_aggregate = gross_margin["aggregate"]["delta"]
    gm_windows = _window_summary(gross_margin)
    target_trade_count = sum(int(row.get("target_trade_count") or 0) for row in gm_windows)

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": _utc_now(),
        "lane": "measurement_repair",
        "status": "accepted_measurement_repair_alpha_blocker_recorded",
        "decision": "accepted_measurement_repair_alpha_blocker_recorded",
        "hypothesis": (
            "Gate 1 baseline drift blocks retaining or promoting the current "
            "strongest gross-margin quality alpha lead."
        ),
        "alpha_hypothesis_for_this_run": {
            "hypothesis": (
                "SEC Companyfacts gross-margin quality should be the next alpha "
                "to convert into a shared default-off adapter after baseline parity."
            ),
            "category": "candidate_pool / default_off_paper_adapter",
            "playbook_alignment": (
                "Matches the playbook preference for broad, cheap, "
                "production-visible Companyfacts fields with forward "
                "replacement-value maturation."
            ),
        },
        "required_preflight_answers": {
            "1_alpha_hypothesis": (
                "Promote/validate gross_margin_quality_candidate_source_v1 as "
                "the next Companyfacts + RS alpha surface."
            ),
            "2_prior_history": {
                "exp-20260601-019": "FCF-yield value was positive but concentration failed.",
                "exp-20260601-020": "Accepted consensus source-pair was positive but failed drawdown/concentration.",
                "exp-20260601-021": "Gross-margin quality passed alpha checks but failed retention only because baseline_matches_docs=false.",
            },
            "3_single_causal_variable": (
                "No strategy variable changed in this blocker record. The blocked "
                "future variable would be a shared gross-margin quality adapter."
            ),
            "4_acceptance_standard": (
                "Use docs/backtesting.md three windows, all-window EV/PnL "
                "improvement, survival floor, drawdown and concentration guards, "
                "plus baseline_matches_docs=true before retention."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260601_022_gross_margin_alpha_blocker_decision.py"
            ),
        },
        "blocking_item": "baseline_matches_docs=false",
        "gate1_baseline_blocker": {
            "source_experiment": "exp-20260601-016",
            "artifact": _repo_rel(BASELINE_AUDIT_JSON),
            "aggregate": baseline_aggregate,
            "rows": baseline["baseline_comparison"]["rows"],
            "blocks_alpha_retention": bool(baseline.get("blocks_alpha_retention")),
        },
        "strongest_alpha_lead": {
            "source_experiment": "exp-20260601-021",
            "changed_variable": gross_margin.get("changed_variable"),
            "decision": gross_margin.get("decision"),
            "artifact": _repo_rel(GROSS_MARGIN_JSON),
            "aggregate": {
                "before_expected_value_score": gross_margin["aggregate"]["before"][
                    "expected_value_score"
                ],
                "after_expected_value_score": gross_margin["aggregate"]["after"][
                    "expected_value_score"
                ],
                "expected_value_score_delta": gm_aggregate["expected_value_score"],
                "before_total_pnl": gross_margin["aggregate"]["before"]["total_pnl"],
                "after_total_pnl": gross_margin["aggregate"]["after"]["total_pnl"],
                "total_pnl_delta": gm_aggregate["total_pnl"],
                "target_trade_count": target_trade_count,
                "baseline_matches_docs": gross_margin["baseline_caveat"][
                    "baseline_matches_docs"
                ],
            },
            "windows": gm_windows,
            "gate4": gross_margin.get("gate4"),
        },
        "meta_research": _summarize_meta_research(),
        "recommended_alpha_direction": (
            "Companyfacts gross-margin quality default-off adapter after clean "
            "baseline parity; then forward replacement-value maturation."
        ),
        "rejected_next_actions": [
            "Do not run another gross-margin threshold/scalar retune on the frozen windows.",
            "Do not continue accepted-consensus capacity/source-pair retunes while baseline parity is dirty.",
            "Do not use LLM soft-ranking until replay-safe attribution coverage is sufficient.",
            "Do not promote any positive replay-only alpha unless the production path can expose the same shared adapter.",
        ],
        "production_backtest_consistency": {
            "current_run_changed_strategy": False,
            "future_requirement": (
                "Any retained gross-margin alpha must live in a shared adapter "
                "called by both backtest/replay and production reporting; "
                "backtester-only logic is not acceptable."
            ),
            "production_impact": PRODUCTION_IMPACT,
        },
        "conclusion": (
            "Do not start a new alpha mutation in this worktree right now. The "
            "best current alpha direction is gross-margin quality, because "
            "exp-20260601-021 improved all three windows by aggregate EV "
            "+6.3389 and PnL +$107,596.26 with 265 target trades. However, "
            "Gate 1 is not trustworthy: current baseline EV/PnL is 6.3596 / "
            "$192,538.61 versus docs/backtesting.md accepted 7.8941 / "
            "$234,850.99. Retaining or promoting the alpha before resolving "
            "that mismatch would create an untrustworthy production/backtest "
            "decision."
        ),
        "next_retry_requires": [
            "Resolve or explicitly accept the current baseline drift versus docs/backtesting.md.",
            "Rerun exp-20260601-021 gross-margin evidence on the clean accepted baseline.",
            "If it reproduces, implement only as a shared default-off adapter surfaced in production, with no live/default orders.",
            "Collect forward replacement-value and concentration rows before any activation review.",
        ],
        "production_impact": PRODUCTION_IMPACT,
        "anti_js": "No JavaScript was used.",
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(TICKET_JSON),
            _repo_rel(BASELINE_AUDIT_JSON),
            _repo_rel(GROSS_MARGIN_JSON),
        ],
        "git": {
            "head": _git_output(["rev-parse", "--short", "HEAD"]),
            "dirty_status_count": len(_git_output(["status", "--short"]).splitlines()),
        },
    }


def run() -> dict[str, Any]:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_card(payload)
    _update_ticket(payload)
    return payload


def main() -> None:
    payload = run()
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "blocking_item": payload["blocking_item"],
                "recommended_alpha_direction": payload[
                    "recommended_alpha_direction"
                ],
                "gross_margin_ev_delta": payload["strongest_alpha_lead"][
                    "aggregate"
                ]["expected_value_score_delta"],
                "baseline_ev_delta": payload["gate1_baseline_blocker"][
                    "aggregate"
                ]["expected_value_score_delta"],
                "artifact": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
