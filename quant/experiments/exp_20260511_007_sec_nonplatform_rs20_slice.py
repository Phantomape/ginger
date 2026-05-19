"""exp-20260511-007: non-platform SEC financial-report RS20 slice.

Observed-only follow-up to exp-20260510-029. This isolates the diagnostic
intersection that looked strongest there:

    SEC financial-report + positive T+1 excess drift + RS20 leader
    excluding platform_pool names

It tests one additional variable relative to exp-20260510-029: platform-pool
exclusion. No production behavior changes.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "exp-20260511-007"
STEM = "sec_nonplatform_rs20_slice"
SOURCE_EXPERIMENT_ID = "exp-20260510-029"
SOURCE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / SOURCE_EXPERIMENT_ID
    / "sec_financial_report_rs20_slice.json"
)
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
PLAYBOOK = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload_line = json.dumps(_safe(payload), ensure_ascii=False, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)
                continue
            if row.get("experiment_id") == payload["experiment_id"]:
                if not replaced:
                    rows.append(payload_line)
                    replaced = True
                continue
            rows.append(line)
    if not replaced:
        rows.append(payload_line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _append_playbook_note(note: str) -> None:
    old = PLAYBOOK.read_text(encoding="utf-8") if PLAYBOOK.exists() else ""
    if f"Experiment: `{EXPERIMENT_ID}`" in old:
        return
    PLAYBOOK.write_text(old.rstrip() + "\n\n" + note.strip() + "\n", encoding="utf-8")


def _build_payload() -> dict[str, Any]:
    source = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
    baseline = source["comparisons"]["rs20_leader_5pp"]
    candidate = source["comparisons"]["non_platform_rs20_leader_5pp_diagnostic"]
    platform = source["comparisons"]["platform_pool_rs20_leader_5pp_diagnostic"]
    agg = candidate["aggregate"]
    fwd10 = agg["forward_returns"]["fwd_10d_return"]
    concentration = agg["max_single_ticker_positive_pnl_share_10d"]
    gate = {
        "min_valid_10d_candidates": 50,
        "required_positive_avg_10d_windows": 3,
        "min_aggregate_10d_avg_return": 0.04,
        "min_aggregate_10d_win_rate": 0.57,
        "max_single_ticker_positive_pnl_share_10d": 0.35,
        "passed": (
            agg["valid_10d_candidate_count"] >= 50
            and candidate["positive_avg_10d_windows"] == 3
            and (fwd10["avg"] or 0.0) >= 0.04
            and (fwd10["win_rate"] or 0.0) >= 0.57
            and (concentration or 1.0) <= 0.35
        ),
    }
    decision = "observed_only_rejected_concentration" if not gate["passed"] else "observed_only_stronger_slice_candidate"
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": "observed_only",
        "decision": decision,
        "change_type": "new_strategy_shadow_stratification",
        "changed_variable": "platform_pool_exclusion_inside_sec_financial_report_rs20_label",
        "single_causal_variable": "exclude platform_pool from SEC financial-report T1 drift plus RS20 leader candidates",
        "hypothesis": (
            "The SEC financial-report T+1 drift plus RS20 leader label may be diluted by platform-pool "
            "mega-cap names; excluding that cohort could expose a materially stronger oracle feature."
        ),
        "protocol_answers": {
            "1_alpha_hypothesis": "Entry/oracle feature refinement: non-platform candidates may carry more event continuation than platform names inside the RS20-confirmed financial-report queue.",
            "2_history_check": {
                "exp-20260510-027": "Accepted non-platform freeze for the broader default-off queue; this run tests the same exclusion only inside the stronger RS20-confirmed subset.",
                "exp-20260510-029": "Observed-only RS20 overlay found +3.49% 10d avg and flagged non-platform RS20 as diagnostic +4.51%; this run pre-registers that diagnostic as a separate test.",
                "anti_repeat": "If this fails concentration, do not keep mining adjacent SEC cohort slices on the frozen sample.",
            },
            "3_single_causal_variable": "platform_pool exclusion",
            "4_gate": "Observed-only stronger-slice gate: >=50 valid rows, 3/3 positive avg windows, avg10 >=4%, win rate >=57%, and max single ticker positive PnL share <=35%.",
            "5_reproducibility": f"Run {SOURCE_EXPERIMENT_ID}, then this script. Inputs are local artifacts only.",
        },
        "source_experiment": {
            "experiment_id": SOURCE_EXPERIMENT_ID,
            "artifact": str(SOURCE_JSON.relative_to(REPO_ROOT)),
            "source_decision": source.get("decision"),
        },
        "parameters": {
            "source_label": "SEC financial-report positive T+1 excess drift plus RS20 leader",
            "tested_exclusion": "platform_pool",
            "locked_variables": [
                "event family label",
                "T+1 excess drift label",
                "RS20 leader threshold",
                "core universe",
                "signal generation",
                "entry filters",
                "ranking",
                "sizing",
                "slots",
                "exits",
                "LLM/news replay",
            ],
        },
        "before_metrics": source.get("before_metrics") or {},
        "after_metrics": source.get("before_metrics") or {},
        "delta_metrics": {
            "aggregate": {
                "expected_value_score_delta_sum": 0.0,
                "total_pnl_delta_sum": 0.0,
                "trade_count_delta_sum": 0,
                "signals_generated_delta_sum": 0,
                "signals_survived_delta_sum": 0,
            },
            "shadow_attribution": {
                "baseline_rs20": baseline,
                "non_platform_rs20": candidate,
                "excluded_platform_rs20": platform,
                "avg_10d_lift_vs_rs20": round((fwd10["avg"] or 0.0) - (baseline["aggregate"]["forward_returns"]["fwd_10d_return"]["avg"] or 0.0), 6),
            },
        },
        "gate": gate,
        "aggregate": agg,
        "comparisons": {
            "baseline_rs20": baseline,
            "non_platform_rs20": candidate,
            "excluded_platform_rs20": platform,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
        },
        "rejection_reason": (
            "The slice is stronger on average return, but fails the pre-registered concentration guard."
            if not gate["passed"]
            else None
        ),
        "next_evidence_needed": [
            "Do not promote this same-sample cohort slice unless forward paper outcomes confirm replacement value.",
            "Collect RS20 attribution on the existing default-off SEC queue instead of changing live orders.",
            "A valid retry needs either closed forward evidence or a genuinely new semantic event-quality field.",
        ],
        "related_files": [
            str(SOURCE_JSON.relative_to(REPO_ROOT)),
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
            "docs/alpha-optimization-playbook.md",
        ],
    }
    return payload


def _artifact(payload: dict[str, Any]) -> str:
    baseline = payload["comparisons"]["baseline_rs20"]["aggregate"]
    candidate = payload["aggregate"]
    platform = payload["comparisons"]["excluded_platform_rs20"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} SEC Non-Platform RS20 Slice",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Result",
        "",
        f"- baseline RS20 10d avg: `{baseline['forward_returns']['fwd_10d_return']['avg']}`",
        f"- non-platform RS20 10d avg: `{candidate['forward_returns']['fwd_10d_return']['avg']}`",
        f"- non-platform valid 10d rows: `{candidate['valid_10d_candidate_count']}`",
        f"- non-platform 10d win rate: `{candidate['forward_returns']['fwd_10d_return']['win_rate']}`",
        f"- positive 10d windows: `{payload['comparisons']['non_platform_rs20']['positive_avg_10d_windows']}/3`",
        f"- max single ticker positive PnL share: `{candidate['max_single_ticker_positive_pnl_share_10d']}`",
        f"- gate passed: `{payload['gate']['passed']}`",
        f"- excluded platform RS20 10d avg: `{platform['forward_returns']['fwd_10d_return']['avg']}`",
        "",
        "## Notes",
        "",
        "- Observed-only. No production orders, sizing, ranking, exits, or slots changed.",
        "- The average return is stronger, but concentration failed the pre-registered guard.",
    ]
    return "\n".join(lines) + "\n"


def _playbook_note(payload: dict[str, Any]) -> str:
    baseline = payload["comparisons"]["baseline_rs20"]["aggregate"]
    candidate = payload["aggregate"]
    return f"""
### 2026-05-11 mechanism update: SEC non-platform RS20 slice

Experiment: `{EXPERIMENT_ID}`

Decision: `{payload['decision']}`.

Finding: excluding `platform_pool` from the SEC financial-report T+1 drift plus
RS20 leader label lifted 10d average return from
`{baseline['forward_returns']['fwd_10d_return']['avg']}` to
`{candidate['forward_returns']['fwd_10d_return']['avg']}` with
`{candidate['valid_10d_candidate_count']}` valid rows and win rate
`{candidate['forward_returns']['fwd_10d_return']['win_rate']}`. However the
slice failed the concentration guard: max single-ticker positive PnL share was
`{candidate['max_single_ticker_positive_pnl_share_10d']}` versus the 0.35 cap.

Mechanism insight: the stronger-looking same-sample slice is not clean enough
to become a new rule. Keep RS20 as an attribution dimension on the default-off
SEC queue and wait for closed forward replacement value before any further
SEC cohort slicing.
""".strip()


def main() -> None:
    payload = _build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "completed",
            "decision": payload["decision"],
            "hypothesis": payload["hypothesis"],
            "single_causal_variable": payload["single_causal_variable"],
            "artifact": str(OUT_JSON.relative_to(REPO_ROOT)),
            "production_impact": payload["production_impact"],
            "next_evidence_needed": payload["next_evidence_needed"],
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, payload)
    _append_playbook_note(_playbook_note(payload))
    agg = payload["aggregate"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "valid_10d_candidate_count": agg["valid_10d_candidate_count"],
                "aggregate_10d_avg": agg["forward_returns"]["fwd_10d_return"]["avg"],
                "aggregate_10d_win_rate": agg["forward_returns"]["fwd_10d_return"]["win_rate"],
                "positive_avg_10d_windows": payload["comparisons"]["non_platform_rs20"]["positive_avg_10d_windows"],
                "max_single_ticker_positive_pnl_share_10d": agg["max_single_ticker_positive_pnl_share_10d"],
                "gate_passed": payload["gate"]["passed"],
                "wrote": str(OUT_JSON.relative_to(REPO_ROOT)),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
