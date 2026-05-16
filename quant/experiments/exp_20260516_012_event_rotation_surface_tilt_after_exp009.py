"""exp-20260516-012: event rotation-surface tilt after exp009.

Alpha search, replay-only. Revalidates the strongest event-bundle paper
allocation refinement after the accepted exp-20260516-009 core stack: keep the
full default-off event bundle and current non-generic positive state-surface
add-on fixed, and test only whether `rotation_breakout_leadership` event rows
still deserve extra bounded paper notional.

No JavaScript is used. No live orders, default backtest behavior, core A/B
ranking, sizing, exits, add-ons, LLM, or news behavior are changed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260504_008_sec_negative_reaction_absorption as sec_negative
import exp_20260504_010_sec_event_sleeve_backtest as sec_event
import exp_20260503_051_sec_filing_reaction_drift as sec_reaction
import exp_20260504_039_sec_governance_procedural_overlay as sec_governance
import exp_20260504_049_default_off_event_overlay_bundle as event_bundle
import exp_20260507_025_event_state_score_tilt as event_state_score
import exp_20260516_006_event_rotation_surface_tilt_current_stack as prior


EXPERIMENT_ID = "exp-20260516-012"
EXPERIMENT_SLUG = "event_rotation_surface_tilt_after_exp009"

REPO_ROOT = prior.REPO_ROOT
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
CANONICAL_SNAPSHOT_FILES = {
    "old_thin": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20241002_20250422.json",
    "mid_weak": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20250423_20251022.json",
    "late_strong": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20251023_20260421.json",
}
CANONICAL_WINDOW_SNAPSHOTS = {
    "old_thin": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
    "mid_weak": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    "late_strong": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _configure_prior_module() -> None:
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    prior.OUT_JSON = OUT_JSON
    prior.LOG_JSON = LOG_JSON
    prior.TICKET_JSON = TICKET_JSON
    prior.ARTIFACT_MD = ARTIFACT_MD
    prior.EXPERIMENT_LOG = EXPERIMENT_LOG
    # Older event-sleeve modules still keep their historical snapshot paths in
    # module globals. Configure them to the canonical data/ohlcv paths for this
    # replay without changing strategy logic.
    for module in (sec_negative, sec_event):
        module.SNAPSHOT_FILES.clear()
        module.SNAPSHOT_FILES.update(CANONICAL_SNAPSHOT_FILES)
    for module in (sec_reaction, sec_governance, event_bundle, event_state_score):
        for label, snapshot in CANONICAL_WINDOW_SNAPSHOTS.items():
            module.WINDOWS[label]["snapshot"] = snapshot


def _finalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload["experiment_id"] = EXPERIMENT_ID
    payload["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload["change_type"] = "post_exp009_event_rotation_surface_tilt_revalidation"
    payload["changed_variable"] = "rotation_breakout_leadership_paper_notional_tilt"
    payload["hypothesis"] = (
        "After the accepted exp-20260516-009 core sizing stack, the strongest "
        "available non-core alpha family is still the default-off event bundle. "
        "Within that paper sleeve, rotation-breakout leadership events may "
        "retain better replacement-quality than other positive non-generic "
        "event surfaces and deserve a bounded extra paper-notional tilt."
    )
    payload["alpha_hypothesis"] = {
        "category": "allocation/event-quality",
        "entry_exit_ranking_or_allocation": "allocation",
        "why_this_now": (
            "LLM soft-ranking and SEC semantic branches remain data-limited, "
            "Space/candidate-pool extensions remain sample-limited or old-window "
            "fragile, and recent core scalar branches are mostly exhausted. "
            "This revalidates the prior strongest replay-positive event "
            "allocation state after the exp-20260516-009 accepted core baseline."
        ),
    }
    history = dict(payload.get("historical_experiment_check") or {})
    history["exp-20260516-009"] = (
        "Accepted green-deceleration quality non-consumer core sizing changed "
        "the core baseline from aggregate EV 7.7345 to 7.7654, so event tilt "
        "needs revalidation rather than inherited acceptance."
    )
    payload["historical_experiment_check"] = history
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "event-bundle paper allocation: rotation_breakout_leadership rows "
            "retain superior event-quality/replacement signal after exp009."
        ),
        "2_history_check": (
            "exp-20260516-006 was promising replay-only before exp009; "
            "exp-20260516-009 changed the accepted core baseline, while recent "
            "LLM/SEC/Space pool branches remain blocked, sample-limited, or "
            "rejected."
        ),
        "3_single_causal_variable": (
            "rotation_breakout_leadership scalar above the current 2.0x "
            "non-generic positive event-surface paper add-on."
        ),
        "4_acceptance_standard": (
            "docs/backtesting.md three fixed windows; compare current lead vs "
            "candidate, require majority EV improvement, zero EV regression, "
            "material aggregate EV/PnL lift, and sample guard pass."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe quant\\experiments\\"
            "exp_20260516_012_event_rotation_surface_tilt_after_exp009.py"
        ),
    }
    params = dict(payload.get("parameters") or {})
    params["accepted_core_checkpoint"] = "exp-20260516-009"
    params["anti_js"] = "No JavaScript was used."
    payload["parameters"] = params
    payload["why_not_other_attractive_points"] = (
        "Skipped LLM soft-ranking, SEC semantic tuning, Space ticker/pool "
        "breadth, simple SPY-excess, gap-vulnerability, close-location, R:R, "
        "and green momentum variants because recent logs mark those branches "
        "rejected, sample-limited, or field-blocked."
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
    text = prior._artifact_markdown(payload)
    return text.replace(
        "after the accepted exp-20260515-028 core stack",
        "after the accepted exp-20260516-009 core stack",
    ).replace(
        "Event Rotation-Surface Tilt Current Stack",
        "Event Rotation-Surface Tilt After Exp009",
    )


def persist(payload: dict[str, Any]) -> None:
    prior.parent._write_json(OUT_JSON, payload)
    prior.parent._write_json(LOG_JSON, payload)
    prior.parent._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Event rotation-surface tilt after exp009",
            "status": payload["status"],
            "decision": payload["decision"],
            "best_variant": payload["best_variant"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "next_action": payload["next_action"],
        },
    )
    prior.parent._write_text(ARTIFACT_MD, _artifact_markdown(payload))

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
    compact = prior._compact_log(payload)
    compact["changed_variable"] = payload["changed_variable"]
    lines.append(json.dumps(prior.parent._safe(compact), sort_keys=True))
    EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    _configure_prior_module()
    payload = prior._retag_payload(prior.parent.build_payload())
    payload = _finalize_payload(payload)
    persist(payload)
    best = payload["best_variant"]
    gate = payload["delta_metrics"]["variant_vs_current_lead"][best]
    print(
        json.dumps(
            prior.parent._safe(
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
