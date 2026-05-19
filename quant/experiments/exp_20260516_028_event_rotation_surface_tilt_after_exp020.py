"""exp-20260516-028: event rotation-surface tilt after exp020.

Alpha search, replay-only. Revalidates the strongest deterministic event-bundle
paper allocation refinement after the accepted exp-20260516-020 core stack. The
only changed variable is the bounded `rotation_breakout_leadership` paper
notional tilt above the current 2.0x non-generic positive event-surface lead.

No JavaScript is used. No live orders, default backtest behavior, core A/B
ranking, sizing, exits, add-ons, LLM, or news behavior are changed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260516_013_event_rotation_surface_tilt_after_exp009 as base


EXPERIMENT_ID = "exp-20260516-028"
EXPERIMENT_SLUG = "event_rotation_surface_tilt_after_exp020"

REPO_ROOT = base.REPO_ROOT
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


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _configure_modules() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.ARTIFACT_MD = ARTIFACT_MD
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base._configure_prior_module()


def _retag_after_exp020(payload: dict[str, Any]) -> dict[str, Any]:
    payload["experiment_id"] = EXPERIMENT_ID
    payload["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload["change_type"] = "post_exp020_event_rotation_surface_tilt_revalidation"
    payload["changed_variable"] = "rotation_breakout_leadership_paper_notional_tilt"
    payload["hypothesis"] = (
        "After the accepted exp-20260516-020 Technology trend DTE residual-risk "
        "promotion, the strongest available non-core alpha family is still the "
        "default-off event bundle. Within that paper sleeve, "
        "rotation_breakout_leadership events may retain superior replacement "
        "quality and deserve a bounded extra paper-notional tilt."
    )
    payload["alpha_hypothesis"] = {
        "category": "allocation/event-quality",
        "entry_exit_ranking_or_allocation": "allocation",
        "why_this_now": (
            "Core allocation retunes around ATR, RS, price-extension, DTE, "
            "pullback, breadth, and lifecycle are either accepted-but-exhausted "
            "or recently rejected. LLM/SEC semantic ranking remains field-limited. "
            "This keeps the fixed core candidate set and revalidates the best "
            "deterministic default-off event allocation state on the latest "
            "accepted core baseline."
        ),
    }
    history = dict(payload.get("historical_experiment_check") or {})
    history["exp-20260516-013"] = (
        "The same rotation surface cleared the paper-only gate after exp009; "
        "this run checks portability after the later exp020 core promotion."
    )
    history["exp-20260516-020"] = (
        "Accepted Technology trend DTE residual-risk change moved the canonical "
        "core baseline to aggregate EV 7.7693, so the event overlay must be "
        "revalidated rather than inherited."
    )
    history["recent_avoided_branches"] = (
        "Skipped LLM soft-ranking, SEC semantic tuning, Space nearby "
        "interactions, ATR expansion, pullback/reclaim, RS scalar, DTE scalar, "
        "market-breadth, add-on, and exit-lifecycle retunes because the recent "
        "logs mark those branches blocked, sample-limited, or rejected."
    )
    payload["historical_experiment_check"] = history
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "default-off event allocation: rotation_breakout_leadership rows "
            "retain superior replacement value after the exp020 core baseline."
        ),
        "2_history_check": (
            "exp-20260516-013 passed after exp009; exp020 later changed the core "
            "baseline, while nearby deterministic core branches are exhausted or "
            "recently rejected."
        ),
        "3_single_causal_variable": (
            "rotation_breakout_leadership scalar above the current 2.0x "
            "non-generic positive event-surface paper add-on."
        ),
        "4_acceptance_standard": (
            "docs/backtesting.md three fixed windows; compare current paper lead "
            "vs candidate, require aggregate EV/PnL improvement, at least two "
            "EV-improved windows, no EV-regressed windows, and sample guard pass."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe quant\\experiments\\"
            "exp_20260516_028_event_rotation_surface_tilt_after_exp020.py"
        ),
    }
    params = dict(payload.get("parameters") or {})
    params["accepted_core_checkpoint"] = "exp-20260516-020"
    params["anti_js"] = "No JavaScript was used."
    payload["parameters"] = params
    payload["why_not_other_attractive_points"] = (
        "Avoided LLM/SEC soft-ranking because fields and attribution are still "
        "insufficient; avoided Space nearby retunes because recent positives are "
        "default-off and interaction-sensitive; avoided broad candidate-pool "
        "expansion because recent pools added old-window noise; avoided nearby "
        "core scalar/lifecycle retunes because the recent log marks them "
        "rejected or exhausted."
    )
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(ARTIFACT_MD),
        _repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    gate = payload["delta_metrics"]["variant_vs_current_lead"][best]
    current = payload["before_metrics"][base.prior.parent.CURRENT_LEAD_VARIANT]
    after = payload["after_metrics"][best]

    lines = [
        f"# {EXPERIMENT_ID} Event Rotation-Surface Tilt After Exp020",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        (
            "Alpha search, replay-only. Tests whether "
            "`rotation_breakout_leadership` event rows still deserve higher "
            "bounded paper notional than the current 2.0x non-generic positive "
            "event-surface add-on after the accepted exp-20260516-020 core stack."
        ),
        "",
        "## Best Variant Vs Current Lead",
        "",
        "| Window | Current EV | Variant EV | Delta EV | Current PnL | Variant PnL | Delta PnL |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.prior.parent.base.WINDOWS:
        delta = gate["delta"]["by_window"][label]
        lines.append(
            "| {label} | {cev:.4f} | {aev:.4f} | {dev:+.4f} | ${cpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} |".format(
                label=label,
                cev=current[label]["expected_value_score"],
                aev=after[label]["expected_value_score"],
                dev=delta["expected_value_score"],
                cpnl=current[label]["total_pnl"],
                apnl=after[label]["total_pnl"],
                dpnl=delta["total_pnl"],
            )
        )
    lines.extend(
        [
            "",
            "## Aggregate Gate",
            "",
            "- EV delta vs current lead: {:+.4f} ({:+.2%})".format(
                gate["delta"]["aggregate_ev_delta"],
                gate["delta"]["aggregate_ev_delta_pct"] or 0.0,
            ),
            "- PnL delta vs current lead: ${:+,.2f} ({:+.2%})".format(
                gate["delta"]["aggregate_pnl_delta"],
                gate["delta"]["aggregate_pnl_delta_pct"] or 0.0,
            ),
            "- EV windows improved/regressed: {}/{}".format(
                gate["delta"]["windows_ev_improved"],
                gate["delta"]["windows_ev_regressed"],
            ),
            "- Sample guard passed: `{}`".format(gate["sample_guard_passed"]),
            "",
            "## Selection",
            "",
            "```json",
            json.dumps(payload["selection"], indent=2, sort_keys=True),
            "```",
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"] or "",
            "",
            "## Production Impact",
            "",
            (
                "Replay only. Production and default backtest order paths are "
                "unchanged. A positive live-capital version still requires a "
                "shared trade-enabled event adapter, run/backtester parity tests, "
                "and forward paper replacement-value evidence."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def persist(payload: dict[str, Any]) -> None:
    base.prior.parent._write_json(OUT_JSON, payload)
    base.prior.parent._write_json(LOG_JSON, payload)
    base.prior.parent._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Event rotation-surface tilt after exp020",
            "status": payload["status"],
            "decision": payload["decision"],
            "best_variant": payload["best_variant"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "next_action": payload["next_action"],
        },
    )
    base.prior.parent._write_text(ARTIFACT_MD, _artifact_markdown(payload))

    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = [
            line
            for line in lines
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    compact = base.prior._compact_log(payload)
    compact["changed_variable"] = payload["changed_variable"]
    lines.append(json.dumps(base.prior.parent._safe(compact), sort_keys=True))
    EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    _configure_modules()
    payload = base.prior._retag_payload(base.prior.parent.build_payload())
    payload = base._finalize_payload(payload)
    payload = _retag_after_exp020(payload)
    persist(payload)
    best = payload["best_variant"]
    gate = payload["delta_metrics"]["variant_vs_current_lead"][best]
    print(
        json.dumps(
            base.prior.parent._safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "best_variant": best,
                    "ev_delta_vs_current": gate["delta"]["aggregate_ev_delta"],
                    "pnl_delta_vs_current": gate["delta"]["aggregate_pnl_delta"],
                    "windows_ev_improved": gate["delta"]["windows_ev_improved"],
                    "windows_ev_regressed": gate["delta"]["windows_ev_regressed"],
                    "sample_guard_passed": gate["sample_guard_passed"],
                    "out_json": str(OUT_JSON),
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
