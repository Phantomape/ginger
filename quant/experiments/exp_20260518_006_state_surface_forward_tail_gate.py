"""exp-20260518-006: state-surface forward tail promotion gate.

Measurement repair supporting the next state-surface alpha search. This
experiment adds a read-only PnL tail-concentration diagnostic to the existing
default-off state-surface forward paper gate.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260518-006"
EXPERIMENT_SLUG = "state_surface_forward_tail_gate"
SOURCE_EXPERIMENT_ID = "exp-20260518-005"
SOURCE_SLUG = "state_surface_regime_rank_notional"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from state_surface_sleeve import (  # noqa: E402
    DEFAULT_CONFIG,
    build_state_surface_forward_tail_diagnostics,
    build_state_surface_sleeve_snapshot,
    empty_state_surface_sleeve_state,
)


OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
SOURCE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / SOURCE_EXPERIMENT_ID
    / f"{SOURCE_SLUG}.json"
)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, set):
        return sorted(_safe(row) for row in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), sort_keys=True)
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


def _money(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(parsed) or math.isinf(parsed):
        return 0.0
    return parsed


def _load_source() -> dict[str, Any]:
    if not SOURCE_JSON.exists():
        raise FileNotFoundError(f"Missing source artifact: {_repo_rel(SOURCE_JSON)}")
    return json.loads(SOURCE_JSON.read_text(encoding="utf-8"))


def _closed_positions_from_source(source: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for window, surface in (source.get("surface_sleeve") or {}).items():
        for trade in surface.get("selected_trades") or []:
            ticker = str(trade.get("ticker") or "").upper()
            decision_date = str(trade.get("decision_date") or "")[:10]
            queue_rank = trade.get("queue_rank")
            rows.append(
                {
                    "decision_id": (
                        f"{window}:{decision_date}:{ticker}:"
                        f"{queue_rank or trade.get('rank') or 'unknown'}"
                    ),
                    "window": window,
                    "ticker": ticker,
                    "surface": trade.get("surface"),
                    "source_event_date": decision_date,
                    "entry_date": trade.get("entry_date"),
                    "exit_date": trade.get("exit_date"),
                    "pnl": _money(trade.get("pnl")),
                    "notional": _money(trade.get("notional")),
                    "queue_rank": queue_rank,
                    "rank": trade.get("rank"),
                    "score": trade.get("score"),
                    "rank_notional_multiplier": trade.get("rank_notional_multiplier"),
                    "rank_notional_profile_name": trade.get("regime_rank_profile_name")
                    or trade.get("rank_notional_profile_name"),
                    "market_regime": {
                        "regime": trade.get("regime"),
                        "confidence": trade.get("regime_confidence"),
                    },
                    "trade_enabled": False,
                    "paper_status": "closed",
                    "source_candidate": {
                        "ret20_excess_spy": trade.get("ret20_excess_spy"),
                        "ret5": trade.get("ret5"),
                        "ret60": trade.get("ret60"),
                        "near_high_60": trade.get("near_high_60"),
                        "volume_ratio_20": trade.get("volume_ratio_20"),
                    },
                }
            )
    return rows


def _legacy_forward_gate(closed_positions: list[dict[str, Any]]) -> dict[str, Any]:
    closed_count = len(closed_positions)
    realized = round(sum(_money(row.get("pnl")) for row in closed_positions), 2)
    wins = sum(1 for row in closed_positions if _money(row.get("pnl")) > 0)
    win_rate = round(wins / closed_count, 4) if closed_count else None
    checks = {
        "min_closed_trades": closed_count >= int(DEFAULT_CONFIG["forward_gate_min_closed_trades"]),
        "min_win_rate": win_rate is not None
        and win_rate >= float(DEFAULT_CONFIG["forward_gate_min_win_rate"]),
        "positive_net_pnl": realized > 0,
    }
    reasons = [name for name, passed in checks.items() if not passed]
    return {
        "passed": not reasons,
        "status": "passed" if not reasons else "blocked",
        "reasons": reasons,
        "checks": checks,
        "metrics": {
            "closed_trades": closed_count,
            "realized_pnl": realized,
            "win_rate": win_rate,
        },
        "trade_enabled_after_gate": False,
    }


def _by_window_tail(closed_positions: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for window in sorted({str(row.get("window") or "unknown") for row in closed_positions}):
        rows = [row for row in closed_positions if str(row.get("window") or "unknown") == window]
        out[window] = build_state_surface_forward_tail_diagnostics(rows)
    return out


def _write_markdown(payload: dict[str, Any]) -> None:
    md = [
        f"# {EXPERIMENT_ID}: State-Surface Forward Tail Gate",
        "",
        "## Decision",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Source: `{_repo_rel(SOURCE_JSON)}`",
        f"- Legacy forward gate would pass: `{payload['legacy_forward_gate']['passed']}`",
        f"- Tail-aware forward gate passes: `{payload['tail_aware_snapshot_gate']['passed']}`",
        "",
        "## Metrics",
        "",
        f"- Closed paper trades: `{payload['tail_diagnostics']['metrics_for_gates']['total_trades']}`",
        f"- Realized paper PnL: `${payload['tail_diagnostics']['metrics_for_gates']['total_pnl']:,.2f}`",
        f"- Win rate: `{payload['tail_diagnostics']['metrics_for_gates']['win_rate']}`",
        f"- PnL top-five contribution: `{payload['tail_diagnostics']['metrics_for_gates']['pnl_top_5_contribution_pct']}`",
        f"- PnL HHI concentration: `{payload['tail_diagnostics']['metrics_for_gates']['pnl_hhi_concentration']}`",
        f"- Tail hard failures: `{payload['tail_diagnostics']['gate_report']['hard_failures']}`",
        "",
        "## Interpretation",
        "",
        (
            "The accepted state-surface paper sleeve remains profitable and default-off, "
            "but promotion readiness should stay blocked until forward outcomes show "
            "less dependence on the top five winners."
        ),
        "",
        "## Production Impact",
        "",
        "- Live/default orders: unchanged",
        "- Candidate ranking, eligibility, notional profile, hold days: unchanged",
        "- Production report and shared paper-sleeve snapshot now expose tail diagnostics",
    ]
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")


def build_payload() -> dict[str, Any]:
    source = _load_source()
    closed_positions = _closed_positions_from_source(source)
    state = empty_state_surface_sleeve_state()
    state["closed_positions"] = closed_positions
    snapshot = build_state_surface_sleeve_snapshot(
        state_surface_queue={"candidates": [], "candidate_count": 0},
        as_of="2026-05-18",
        state=state,
        persist=False,
    )
    tail_diagnostics = build_state_surface_forward_tail_diagnostics(closed_positions)
    legacy_gate = _legacy_forward_gate(closed_positions)
    tail_gate = snapshot["forward_paper_gate"]
    tail_blocks_legacy_pass = (
        bool(legacy_gate["passed"])
        and not bool(tail_gate["passed"])
        and "tail_gate" in set(tail_gate.get("reasons") or [])
    )
    decision = (
        "accepted_measurement_repair_forward_tail_gate"
        if tail_blocks_legacy_pass
        else "needs_review_forward_tail_gate"
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "anti_js": "No JavaScript was used.",
        "lane": "measurement_repair",
        "change_type": "state_surface_forward_promotion_gate_diagnostics",
        "changed_variable": "state_surface_forward_paper_tail_concentration_gate",
        "single_causal_variable": (
            "add read-only PnL tail concentration diagnostics to the state-surface "
            "forward paper promotion gate"
        ),
        "hypothesis": (
            "Forward promotion readiness for the accepted default-off state-surface "
            "paper sleeve can be falsely positive when win rate and total PnL are "
            "good but top-winner concentration remains high."
        ),
        "history_check": {
            "exp-20260517-019": "Rejected ret60 floor; do not retry single-field momentum floors.",
            "exp-20260517-020": "Rejected near_high_60 floor.",
            "exp-20260517-021": "Rejected volume_ratio_20 floor.",
            "exp-20260517-023": "Rejected underpowered ret5 floor.",
            "exp-20260518-004": "Observed tail concentration risk in rank-notional.",
            "exp-20260518-005": "Accepted a production-visible chop regime discriminator; adjacent regime-profile retunes are frozen.",
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-window evidence inherited from exp-20260518-005",
            "note": "This experiment does not rerun or alter core backtest execution.",
        },
        "source_artifact": _repo_rel(SOURCE_JSON),
        "before_metrics": {
            "legacy_forward_gate": legacy_gate,
            "source_expected_value_score_delta": source.get("expected_value_score_delta"),
            "source_total_pnl_delta": source.get("total_pnl_delta"),
        },
        "after_metrics": {
            "tail_aware_forward_gate": tail_gate,
            "tail_diagnostics": tail_diagnostics,
        },
        "delta_metrics": {
            "core_expected_value_score_delta": 0.0,
            "core_total_pnl_delta": 0.0,
            "strategy_behavior_changed": False,
            "promotion_readiness_changed": tail_blocks_legacy_pass,
        },
        "expected_value_score_delta": 0.0,
        "total_pnl_delta": 0.0,
        "tail_diagnostics": tail_diagnostics,
        "tail_by_window": _by_window_tail(closed_positions),
        "legacy_forward_gate": legacy_gate,
        "tail_aware_snapshot_gate": tail_gate,
        "tail_blocks_legacy_pass": tail_blocks_legacy_pass,
        "decision": decision,
        "status": decision,
        "interpretation": (
            "The accepted state-surface default-off paper sleeve remains profitable, "
            "but the matured historical paper sample is not clean enough for a promotion "
            "readiness signal because PnL top-five contribution breaches the tail gate."
        ),
        "next_evidence_needed": (
            "Collect forward closed state-surface paper outcomes until top-five PnL "
            "contribution and HHI improve; do not run another nearby profile retune "
            "without a genuinely new production-visible discriminator."
        ),
        "production_impact": {
            "shared_policy_changed": True,
            "shared_policy_file": "quant/state_surface_sleeve.py",
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "report_changed": True,
            "report_file": "quant/report_generator.py",
            "replay_only": False,
            "parity_test_added": True,
            "parity_test_file": "quant/test_state_surface_sleeve.py",
            "live_default_orders_changed": False,
            "candidate_ranking_changed": False,
            "sizing_or_notional_changed": False,
        },
        "related_files": [
            "quant/state_surface_sleeve.py",
            "quant/report_generator.py",
            "quant/test_state_surface_sleeve.py",
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            "docs/experiment_log.jsonl",
        ],
        "gate_questions": {
            "1_alpha_hypothesis": (
                "Measurement repair: state-surface alpha is blocked by promotion-readiness "
                "tail concentration; next alpha remains a production-visible rank-quality "
                "or heat/regime discriminator after forward evidence matures."
            ),
            "2_history_check": "Nearby field floors and regime/rank profile retunes are already logged; this changes only the promotion diagnostic.",
            "3_single_causal_variable": "state_surface_forward_paper_tail_concentration_gate",
            "4_acceptance_standard": "Focused tests pass; core strategy metrics remain unchanged; exp005 historical sample is correctly blocked by tail concentration.",
            "5_reproducibility": f".venv/Scripts/python.exe quant/experiments/{Path(__file__).name}",
        },
    }
    return payload


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, payload)
    _write_markdown(payload)
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    print(
        json.dumps(
            {
                "anti_js": payload["anti_js"],
                "decision": payload["decision"],
                "experiment_id": EXPERIMENT_ID,
                "legacy_forward_gate_passed": payload["legacy_forward_gate"]["passed"],
                "tail_aware_forward_gate_passed": payload["tail_aware_snapshot_gate"]["passed"],
                "tail_blocks_legacy_pass": payload["tail_blocks_legacy_pass"],
                "pnl_top_5_contribution_pct": payload["tail_diagnostics"]["metrics_for_gates"][
                    "pnl_top_5_contribution_pct"
                ],
                "pnl_hhi_concentration": payload["tail_diagnostics"]["metrics_for_gates"][
                    "pnl_hhi_concentration"
                ],
                "hard_failures": payload["tail_diagnostics"]["gate_report"]["hard_failures"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
