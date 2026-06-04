"""exp-20260604-025: theme-density no-core-overlap candidate scout.

This replay-only alpha search keeps the original theme-density confirmed
breakout source fixed and changes exactly one discriminator: candidate rows are
eligible only when they do not overlap same-day core A/B entries. The goal is
to test replacement value rather than another theme-density threshold retune.

Core signal generation, ranking, sizing, exits, LLM/news, watchlists, and
live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path
from typing import Any

import exp_20260526_016_theme_density_breakout_sleeve as parent


EXP_ID = "exp-20260604-025"
STEM = "theme_density_no_core_overlap"
TRIAL_FAMILY = "theme_density_core_overlap_displacement"
CHANGED_VARIABLE = "theme_density_no_same_day_core_overlap_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

ROOT = parent.REPO_ROOT
OUT_DIR = ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
MANIFEST_JSON = ROOT / "experiments" / "manifests" / f"{EXP_ID}.json"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

_ORIGINAL_CANDIDATES = parent._candidate_rows_for_window


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


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _json_load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _window_label(cfg: dict[str, str]) -> str:
    for label, window in parent.base.WINDOWS.items():
        if window is cfg:
            return label
    return str(cfg.get("start") or "unknown")


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = _ORIGINAL_CANDIDATES(snapshot, cfg, universe, before_result)
    kept: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    for row in rows:
        if bool(row.get("same_day_ab_overlap")):
            removed.append({**row, "filter_reason": "same_day_ab_overlap"})
            continue
        kept.append(
            {
                **row,
                "theme_density_no_same_day_core_overlap": True,
                "core_overlap_discriminator_rule_version": RULE_VERSION,
            }
        )

    label = _window_label(cfg)
    audit = parent.THEME_DENSITY_AUDIT.setdefault(label, {})
    audit.update(
        {
            "pre_core_overlap_filter_candidate_count": len(rows),
            "post_core_overlap_filter_candidate_count": len(kept),
            "same_day_ab_overlap_filtered_count": len(removed),
            "same_day_ab_overlap_filtered_days": len({row["date"] for row in removed}),
            "post_core_overlap_filter_candidate_days": len({row["date"] for row in kept}),
            "post_core_overlap_filter_unique_tickers": len({row["ticker"] for row in kept}),
            "core_overlap_discriminator_rule_version": RULE_VERSION,
            "sample_filtered_candidates": removed[:20],
        }
    )
    return kept


def _configure() -> None:
    parent.EXPERIMENT_ID = EXP_ID
    parent.STEM = STEM
    parent.TRIAL_FAMILY = TRIAL_FAMILY
    parent.CHANGED_VARIABLE = CHANGED_VARIABLE
    parent.RULE_VERSION = "theme_density_confirmed_breakout_v1"
    parent.OUT_DIR = OUT_DIR
    parent.OUT_JSON = OUT_JSON
    parent.LOG_JSON = LOG_JSON
    parent.TICKET_JSON = TICKET_JSON
    parent.ARTIFACT_MD = ARTIFACT_MD
    parent.EXPERIMENT_LOG = EXPERIMENT_LOG
    parent._configure_base_module()
    parent.base._candidate_rows_for_window = _candidate_rows_for_window


def _aggregate_for_close(metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ev = sum(float(row.get("expected_value_score") or 0.0) for row in metrics.values())
    pnl = sum(float(row.get("total_pnl") or 0.0) for row in metrics.values())
    return {
        "experiment_id": EXP_ID,
        "expected_value_score": round(ev, 6),
        "total_pnl": round(pnl, 2),
        "sharpe_daily": None,
        "max_drawdown_pct": round(
            max(float(row.get("max_drawdown_pct") or 0.0) for row in metrics.values()),
            6,
        ),
        "win_rate": None,
        "total_trades": sum(int(row.get("trade_count") or 0) for row in metrics.values()),
        "survival_rate": round(
            min(float(row.get("survival_rate") or 0.0) for row in metrics.values()),
            6,
        ),
        "windows": metrics,
    }


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4_passed = bool(payload["gate4"]["passed"])
    decision = (
        "positive_replay_lead_not_promoted_requires_shared_adapter"
        if gate4_passed
        else "rejected_theme_density_no_core_overlap"
    )
    ticket = _json_load(TICKET_JSON, {})
    payload.update(
        {
            "experiment_id": EXP_ID,
            "experiment_uid": ticket.get("experiment_uid") if isinstance(ticket, dict) else None,
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "Theme-density confirmed breakout candidates may have cleaner "
                "replacement value when they do not compete with same-day core A/B "
                "entries, reducing slot opportunity cost while keeping the "
                "free-OHLCV theme-strength source fixed."
            ),
            "change_type": "theme_density_replacement_value_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "mechanism_family": "free_ohlcv_theme_density_replacement_value",
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": "no_same_day_core_overlap_v1",
            "prior_trial_count": 2,
            "nearby_prior_experiments": [
                "exp-20260526-016",
                "exp-20260604-006",
                "exp-20260603-021",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "free_ohlcv_theme_density_replacement_value_discriminator",
            "accepted": gate4_passed,
            "prediction": ticket.get("prediction") if isinstance(ticket, dict) else None,
        }
    )
    payload["parameters"]["displacement_discriminator"] = {
        "same_day_ab_overlap_required": False,
        "core_overlap_discriminator_rule_version": RULE_VERSION,
        "fixed_parent_rule_version": "theme_density_confirmed_breakout_v1",
    }
    payload["parameters"]["locked_variables"].append("theme-density thresholds")
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool / replacement value: theme-density candidates may be "
            "more useful when they do not collide with same-day core entries."
        ),
        "2_history_check": {
            "exp-20260526-016": (
                "Raw theme-density had positive aggregate PnL but failed Gate 4 "
                "because late_strong and old_thin regressed."
            ),
            "exp-20260604-006": (
                "Theme-density consensus-source family did not clear the accepted "
                "free-data consensus comparator."
            ),
            "why_not_repeat": (
                "This keeps all theme-density thresholds fixed and only tests the "
                "replacement-value discriminator same_day_ab_overlap=false."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "docs/backtesting.md three windows; aggregate EV/PnL positive; no "
            "EV/PnL window regression; >=20 trades across all 3 windows; drawdown "
            "and concentration guards pass; promotion requires shared adapter parity."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260604_025_theme_density_no_core_overlap.py"
        ),
    }
    payload["interpretation"] = (
        "Gate 4 passed, but this remains replay-only until a shared default-off "
        "adapter proves production/backtest parity."
        if gate4_passed
        else "Gate 4 failed; the no-core-overlap discriminator is not retained."
    )
    payload["next_evidence_needed"] = (
        "Do not promote theme-density no-core-overlap without forward replacement "
        "value rows or a shared default-off adapter parity experiment."
    )
    payload["production_impact"].update(
        {
            "replay_only": True,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "trade_enabled": False,
            "alters_orders": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "production_signal_path_changed": False,
        }
    )
    payload["related_files"] = [
        parent.base._repo_rel(Path(__file__)),
        parent.base._repo_rel(OUT_JSON),
        parent.base._repo_rel(BEFORE_JSON),
        parent.base._repo_rel(AFTER_JSON),
        parent.base._repo_rel(LOG_JSON),
        parent.base._repo_rel(ARTIFACT_MD),
        parent.base._repo_rel(CARD_MD),
        parent.base._repo_rel(TICKET_JSON),
        parent.base._repo_rel(MANIFEST_JSON),
        parent.base._repo_rel(EXPERIMENT_LOG),
    ]
    payload["anti_js"] = "No JavaScript was used."
    return payload


def _report(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    lines = [
        "# Theme-Density No Core-Overlap Candidate Scout",
        "",
        f"- experiment_id: `{EXP_ID}`",
        f"- decision: `{payload['decision']}`",
        f"- EV delta: `{aggregate['expected_value_score_delta_sum']}`",
        f"- PnL delta: `${aggregate['total_pnl_delta_sum']:,.2f}`",
        f"- target trades: `{payload['target_trade_summary']['total_trade_count']}`",
        "",
        "## Three-Window Result",
        "",
        "| Window | Before EV | After EV | dEV | dPnL | Trades | Post-filter candidates | Filtered overlap |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in parent.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["theme_density_audit"].get(label, {})
        lines.append(
            f"| {label} | {before['expected_value_score']:.4f} | "
            f"{after['expected_value_score']:.4f} | "
            f"{delta.get('expected_value_score', 0.0):+.4f} | "
            f"${delta.get('total_pnl', 0.0):+,.2f} | "
            f"{len(payload['target_trades_by_window'][label])} | "
            f"{audit.get('post_core_overlap_filter_candidate_count')} | "
            f"{audit.get('same_day_ab_overlap_filtered_count')} |"
        )
    lines.extend(
        [
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Theme-Density Audit",
            "",
            "```json",
            json.dumps(payload["theme_density_audit"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_ticket(payload: dict[str, Any]) -> None:
    ticket = _json_load(TICKET_JSON, {})
    if not isinstance(ticket, dict):
        ticket = {"experiment_id": EXP_ID}
    ticket.update(
        {
            "status": payload["status"],
            "decision": payload["decision"],
            "completed_at": payload["timestamp"],
            "result": {
                "artifact": parent.base._repo_rel(ARTIFACT_MD),
                "json": parent.base._repo_rel(OUT_JSON),
                "before": parent.base._repo_rel(BEFORE_JSON),
                "after": parent.base._repo_rel(AFTER_JSON),
                "aggregate": payload["delta_metrics"]["aggregate"],
                "gate4": payload["gate4"],
                "next_action": payload["next_evidence_needed"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)


def _write_manifest(payload: dict[str, Any]) -> None:
    files = [
        Path(__file__),
        OUT_JSON,
        BEFORE_JSON,
        AFTER_JSON,
        LOG_JSON,
        ARTIFACT_MD,
        CARD_MD,
        TICKET_JSON,
        MANIFEST_JSON,
    ]
    manifest = _json_load(MANIFEST_JSON, {})
    if not isinstance(manifest, dict):
        manifest = {}
    manifest.update(
        {
            "experiment_id": EXP_ID,
            "experiment_uid": payload.get("experiment_uid"),
            "status": payload["status"],
            "decision": payload["decision"],
            "updated_at": payload["timestamp"],
            "completed_at": payload["timestamp"],
            "files": {
                parent.base._repo_rel(path): {"exists": path.exists(), "sha256": _sha256(path)}
                for path in files
            },
            "result": {
                "aggregate": payload["delta_metrics"]["aggregate"],
                "gate4": payload["gate4"],
            },
        }
    )
    _write_json(MANIFEST_JSON, manifest)


def run(output: Path = OUT_JSON) -> dict[str, Any]:
    _configure()
    payload = _update_payload(parent._update_payload(parent.base._build_payload()))
    _write_json(output, payload)
    _write_json(BEFORE_JSON, _aggregate_for_close(payload["before_metrics"]))
    _write_json(AFTER_JSON, _aggregate_for_close(payload["after_metrics"]))
    _write_json(LOG_JSON, payload)
    report = _report(payload)
    _write_text(ARTIFACT_MD, report)
    _write_text(CARD_MD, report)
    _write_ticket(payload)
    _write_manifest(payload)
    parent.base._upsert_jsonl(EXPERIMENT_LOG, payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT_JSON)
    args = parser.parse_args()
    t0 = time.time()
    payload = run(args.output)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "runtime_seconds": round(time.time() - t0, 1),
                "aggregate": payload["delta_metrics"]["aggregate"],
                "gate4": payload["gate4"],
                "target_trade_summary": {
                    key: payload["target_trade_summary"][key]
                    for key in (
                        "total_trade_count",
                        "total_pnl",
                        "by_window_pnl",
                        "max_single_positive_pnl_share",
                        "positive_pnl_hhi",
                    )
                },
                "artifact": parent.base._repo_rel(args.output),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
