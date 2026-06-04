"""exp-20260604-006: theme-density source-family consensus scout.

Replay-only alpha search. The accepted independent-source free-data consensus
is fixed, then the rejected standalone theme-density breakout paper rows from
exp-20260526-016 are added only as a new independent confirmation family. This
tests whether theme participation can improve the accepted adapter without
adding standalone noisy tickers.

No production code, live orders, ranking, sizing, exits, LLM, news, watchlists,
source thresholds, hold period, or candidate admission policy is changed. No
JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = REPO_ROOT / "quant" / "experiments"
QUANT_DIR = REPO_ROOT / "quant"
for import_path in (REPO_ROOT, EXPERIMENTS_DIR, QUANT_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260603_014_accepted_consensus_independent_source_family as consensus  # noqa: E402


EXPERIMENT_ID = "exp-20260604-006"
STEM = "theme_density_consensus_source_family"
TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_new_independent_theme_context_family"
CHANGED_VARIABLE = "theme_density_breakout_source_family_added_to_accepted_consensus_v1"
RULE_VERSION = CHANGED_VARIABLE
THEME_SOURCE_NAME = "THEME_DENSITY_BREAKOUT_PAPER"
THEME_SOURCE_FAMILY = "theme_density_breakout"
THEME_SOURCE_EXPERIMENT_ID = "exp-20260526-016"
THEME_SOURCE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / THEME_SOURCE_EXPERIMENT_ID
    / "theme_density_breakout_sleeve.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260604_006_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

ACCEPTED_COMPARATOR_ID = "exp-20260603-014"
ACCEPTED_COMPARATOR_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / ACCEPTED_COMPARATOR_ID
    / "accepted_consensus_independent_source_family.json"
)

PREDICTION = {
    "success_probability": 0.17,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "no_same_day_overlap",
        "accepted_comparator_not_beaten",
        "window_regression",
        "theme_concentration",
    ],
    "confidence_reason": (
        "Meta research favors default-off paper adapters; standalone theme-density "
        "failed, but using it only as confirmation could improve accepted consensus "
        "without adding raw ticker noise."
    ),
    "recorded_at": "2026-06-04T05:04:45+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_watchlist_changed": False,
    "production_orders_changed": False,
    "parity_note": (
        "This experiment changes no production code. A retained theme-density "
        "source family would need the shared free-data consensus paper adapter to "
        "load the same production-visible theme-density rows in daily production "
        "and historical replay, plus parity tests, before any report queue, "
        "notional, candidate priority, or order surface could change."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _configure_source_family() -> None:
    consensus._configure_prior_module()
    consensus.SOURCE_FAMILIES = {
        **consensus.SOURCE_FAMILIES,
        THEME_SOURCE_NAME: THEME_SOURCE_FAMILY,
    }
    consensus.SOURCE_EXPERIMENT_IDS = {
        **consensus.SOURCE_EXPERIMENT_IDS,
        THEME_SOURCE_NAME: THEME_SOURCE_EXPERIMENT_ID,
    }


def _theme_rows_by_window() -> tuple[
    dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
    dict[str, Any],
]:
    rows_by_window: dict[str, dict[tuple[str, str], list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    if not THEME_SOURCE_JSON.exists():
        return {}, {
            "source_status": "missing_theme_density_artifact",
            "path": _repo_rel(THEME_SOURCE_JSON),
        }

    artifact = _load_json(THEME_SOURCE_JSON)
    raw_by_window = artifact.get("target_trades_by_window") or {}
    for label, rows in raw_by_window.items():
        for row in rows or []:
            signal_date = str(row.get("signal_date") or row.get("date") or "")[:10]
            ticker = str(row.get("ticker") or "").upper()
            if not signal_date or not ticker:
                continue
            rows_by_window[label][(signal_date, ticker)].append(
                {
                    "source_name": THEME_SOURCE_NAME,
                    "source_experiment_id": THEME_SOURCE_EXPERIMENT_ID,
                    "date": signal_date,
                    "signal_date": signal_date,
                    "entry_date": row.get("entry_date"),
                    "ticker": ticker,
                    "selected_theme": row.get("selected_theme"),
                    "theme_density_score": row.get("theme_density_score"),
                    "theme_density_rule_version": row.get("theme_density_rule_version"),
                    "theme_density_context": row.get("theme_density_context"),
                    "candidate_day_rs_vs_spy": row.get("candidate_day_rs_vs_spy"),
                    "breakout_above_prior_20d_high_pct": row.get(
                        "breakout_above_prior_20d_high_pct"
                    ),
                    "volume_ratio_20": row.get("volume_ratio_20"),
                }
            )

    return rows_by_window, {
        "source_status": "loaded",
        "path": _repo_rel(THEME_SOURCE_JSON),
        "raw_selected_rows_by_window": {
            label: sum(len(rows) for rows in by_key.values())
            for label, by_key in sorted(rows_by_window.items())
        },
        "source_name": THEME_SOURCE_NAME,
        "source_family": THEME_SOURCE_FAMILY,
        "source_experiment_id": THEME_SOURCE_EXPERIMENT_ID,
        "source_decision": artifact.get("decision"),
        "standalone_gate4_passed": bool((artifact.get("gate4") or {}).get("passed")),
    }


def _merge_source_rows(
    base_rows: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
    theme_rows: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
) -> dict[str, dict[tuple[str, str], list[dict[str, Any]]]]:
    merged: dict[str, dict[tuple[str, str], list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for source in (base_rows, theme_rows):
        for label, rows_by_key in source.items():
            for key, rows in rows_by_key.items():
                merged[label][key].extend(rows)
    return merged


def _accepted_comparator(
    baselines: dict[str, dict[str, Any]],
    base_source_rows: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    results, trades = consensus._run_windows(baselines, base_source_rows)
    return results, trades, consensus.prior._aggregate_results(results)


def _aggregate_vs_comparator(
    after_results: list[dict[str, Any]],
    comparator_results: list[dict[str, Any]],
) -> dict[str, Any]:
    comparator_by_label = {row["label"]: row for row in comparator_results}
    rows = []
    for row in after_results:
        comparator = comparator_by_label[row["label"]]
        delta = consensus.prior.base.overlay_helper._delta(row["after"], comparator["after"])
        rows.append(
            {
                "label": row["label"],
                "expected_value_score_delta": delta["expected_value_score"],
                "strategy_total_pnl_delta": delta["total_pnl"],
                "total_pnl_delta": delta["total_pnl"],
                "max_drawdown_delta": delta["max_drawdown_pct"],
            }
        )
    after_ev = sum(_safe_float(row["after"].get("expected_value_score")) for row in after_results)
    comparator_ev = sum(
        _safe_float(row["after"].get("expected_value_score")) for row in comparator_results
    )
    after_pnl = sum(_safe_float(row["after"].get("total_pnl")) for row in after_results)
    comparator_pnl = sum(_safe_float(row["after"].get("total_pnl")) for row in comparator_results)
    return {
        "comparison": {
            "expected_value_score_delta": round(after_ev - comparator_ev, 6),
            "strategy_total_pnl_delta": round(after_pnl - comparator_pnl, 2),
            "total_pnl_delta": round(after_pnl - comparator_pnl, 2),
            "windows_ev_improved": sum(1 for row in rows if row["expected_value_score_delta"] > 0.0),
            "windows_ev_regressed": sum(1 for row in rows if row["expected_value_score_delta"] < 0.0),
            "windows_pnl_improved": sum(1 for row in rows if row["strategy_total_pnl_delta"] > 0.0),
            "windows_pnl_regressed": sum(1 for row in rows if row["strategy_total_pnl_delta"] < 0.0),
            "per_window": rows,
        }
    }


def _theme_selected_summary(target_trades_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rows = [row for trades in target_trades_by_window.values() for row in trades]
    theme_rows = [row for row in rows if THEME_SOURCE_NAME in (row.get("source_names") or [])]
    return {
        "theme_selected_trade_count": len(theme_rows),
        "theme_selected_trade_count_by_window": {
            label: sum(1 for row in trades if THEME_SOURCE_NAME in (row.get("source_names") or []))
            for label, trades in target_trades_by_window.items()
        },
        "theme_selected_trade_pnl_usd": round(sum(_safe_float(row.get("pnl")) for row in theme_rows), 2),
        "theme_selected_tickers": sorted({str(row.get("ticker") or "").upper() for row in theme_rows}),
        "theme_selected_combo_counts": dict(
            sorted(
                Counter("+".join(row.get("source_families") or []) for row in theme_rows).items()
            )
        ),
    }


def _gate4(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
    vs_comparator: dict[str, Any],
    source_family_summary: dict[str, Any],
    theme_selected: dict[str, Any],
) -> dict[str, Any]:
    base_gate = consensus.prior._gate4_decision(aggregate, results, target_summary)
    comp = vs_comparator["comparison"]
    comparator_passed = (
        comp["expected_value_score_delta"] > 0.0
        and comp["strategy_total_pnl_delta"] > 0.0
        and comp["windows_ev_improved"] == 3
        and comp["windows_pnl_improved"] == 3
    )
    theme_sample_passed = int(theme_selected["theme_selected_trade_count"]) > 0
    gates = {
        **base_gate["gates"],
        "beats_current_accepted_consensus_comparator": comparator_passed,
        "theme_selected_trade_count_positive": theme_sample_passed,
        "source_family_min_count_passed": source_family_summary[
            "all_selected_have_min_family_count"
        ],
    }
    passed = bool(base_gate["passed"] and comparator_passed and theme_sample_passed)
    if passed:
        decision = "positive_replay_lead_requires_shared_theme_density_consensus_adapter"
        rationale = (
            "Theme-density source-family consensus improved core and the current "
            "accepted consensus comparator in all three windows. Promotion would "
            "require a shared production/backtest adapter first."
        )
    elif not theme_sample_passed:
        decision = "rejected_no_theme_density_consensus_selected_rows"
        rationale = "Theme-density source rows produced no selected consensus trades."
    elif not comparator_passed:
        decision = "rejected_theme_density_source_family_did_not_beat_accepted_consensus"
        rationale = (
            "The variant did not beat the current accepted independent-source "
            "consensus comparator across all three windows."
        )
    else:
        decision = "rejected_theme_density_source_family_gate4_failed"
        rationale = base_gate["rationale"]
    return {
        "passed": passed,
        "decision": decision,
        "gates": gates,
        "rationale": rationale,
        "min_survival_rate": base_gate.get("min_survival_rate"),
        "max_drawdown_delta": base_gate.get("max_drawdown_delta"),
        "requires_parity_before_promotion": True,
        "accepted_comparator": ACCEPTED_COMPARATOR_ID,
    }


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comp = payload["aggregate"]["comparison"]
    accepted = payload["vs_accepted_comparator"]["comparison"]
    actual_success = 1 if payload["gate4"]["passed"] else 0
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["completed_at"],
        "lane": "alpha_search",
        "status": "accepted" if payload["gate4"]["passed"] else "rejected",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "theme_density_source_family_v1",
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "change_type": "default_off_paper_adapter_source_family_alpha",
        "mechanism_family": "default_off_paper_adapter_source_family_alpha",
        "prior_trial_count": 0,
        "nearby_prior_experiments": payload["preflight"]["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "production_visible_free_ohlcv_theme_density_source_family",
        "decision": payload["gate4"]["decision"],
        "accepted": bool(payload["gate4"]["passed"]),
        "rejection_reason": None if payload["gate4"]["passed"] else payload["gate4"]["rationale"],
        "prediction": PREDICTION,
        "calibration": {
            "actual_decision": payload["gate4"]["decision"],
            "actual_success": actual_success,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": round((PREDICTION["success_probability"] - actual_success) ** 2, 6),
            "realized_failure_mode": None if payload["gate4"]["passed"] else payload["gate4"]["decision"],
        },
        "production_impact": PRODUCTION_IMPACT,
        "requires_parity_before_promotion": True,
        "metrics": {
            "aggregate_expected_value_before": payload["aggregate"]["before"]["expected_value_score"],
            "aggregate_expected_value_after": payload["aggregate"]["after"]["expected_value_score"],
            "aggregate_expected_value_delta": comp["expected_value_score_delta"],
            "aggregate_strategy_total_pnl_before": payload["aggregate"]["before"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_after": payload["aggregate"]["after"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_delta": comp["strategy_total_pnl_delta"],
            "accepted_comparator_ev_delta": accepted["expected_value_score_delta"],
            "accepted_comparator_pnl_delta": accepted["strategy_total_pnl_delta"],
            "accepted_comparator_windows_ev_improved": accepted["windows_ev_improved"],
            "accepted_comparator_windows_pnl_improved": accepted["windows_pnl_improved"],
            "target_trade_count": payload["target_summary"]["target_trade_count"],
            "target_trade_pnl_usd": payload["target_summary"]["target_trade_pnl_usd"],
            "theme_selected_trade_count": payload["theme_selected_summary"][
                "theme_selected_trade_count"
            ],
            "theme_selected_trade_pnl_usd": payload["theme_selected_summary"][
                "theme_selected_trade_pnl_usd"
            ],
            "max_drawdown_delta": payload["gate4"]["max_drawdown_delta"],
            "max_single_positive_share": payload["target_summary"]["max_single_positive_share"],
            "positive_pnl_hhi": payload["target_summary"]["positive_pnl_hhi"],
        },
        "windows": [
            {
                "label": row["label"],
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["comparison"]["expected_value_score_delta"],
                "strategy_total_pnl_delta": row["comparison"]["strategy_total_pnl_delta"],
                "target_trade_count": row["target_trade_count"],
                "target_trade_pnl_usd": row["target_trade_pnl_usd"],
                "theme_selected_trade_count": payload["theme_selected_summary"][
                    "theme_selected_trade_count_by_window"
                ].get(row["label"], 0),
            }
            for row in payload["results"]
        ],
        "artifact_path": _repo_rel(OUT_JSON),
        "anti_js": "No JavaScript was used.",
    }


def _write_card(payload: dict[str, Any]) -> None:
    comp = payload["aggregate"]["comparison"]
    accepted = payload["vs_accepted_comparator"]["comparison"]
    lines = [
        f"# {EXPERIMENT_ID} Theme-density consensus source-family scout",
        "",
        "## Decision",
        "",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Rationale: {payload['gate4']['rationale']}",
        "",
        "## Three-window result",
        "",
        f"- Vs core: EV `{comp['expected_value_score_delta']:+.4f}`, PnL `${comp['strategy_total_pnl_delta']:+,.2f}`",
        f"- Vs accepted consensus comparator: EV `{accepted['expected_value_score_delta']:+.4f}`, PnL `${accepted['strategy_total_pnl_delta']:+,.2f}`",
        f"- Theme-density selected trades: `{payload['theme_selected_summary']['theme_selected_trade_count']}`",
        "",
        "## Production impact",
        "",
        "- Replay-only; no production code or live/default order behavior changed.",
        "- Positive retention would require a shared adapter/parity implementation first.",
        "",
        "No JavaScript was used.",
        "",
    ]
    _write_text(CARD_MD, "\n".join(lines))


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "id": EXPERIMENT_ID,
            "experiment_id": EXPERIMENT_ID,
            "status": "completed",
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "artifact": _repo_rel(OUT_JSON),
            "card": _repo_rel(CARD_MD),
            "log": _repo_rel(LOG_JSON),
            "production_impact": PRODUCTION_IMPACT,
            "gate4": payload["gate4"],
        }
    )
    _write_json(TICKET_JSON, ticket)


def _update_manifest(payload: dict[str, Any]) -> None:
    manifest = _load_json(MANIFEST_JSON) if MANIFEST_JSON.exists() else {}
    manifest.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "completed",
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "artifacts": [
                _repo_rel(OUT_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(CARD_MD),
                _repo_rel(TICKET_JSON),
            ],
        }
    )
    _write_json(MANIFEST_JSON, manifest)


def _upsert_registry(payload: dict[str, Any]) -> None:
    if not REGISTRY_JSON.exists():
        return
    registry = _load_json(REGISTRY_JSON)
    experiments = registry.get("experiments")
    if not isinstance(experiments, list):
        return
    for item in experiments:
        if isinstance(item, dict) and item.get("experiment_id") == EXPERIMENT_ID:
            item["status"] = "completed"
            item["decision"] = payload["gate4"]["decision"]
            item["completed_at"] = payload["completed_at"]
            item["artifact"] = _repo_rel(OUT_JSON)
            item["log"] = _repo_rel(LOG_JSON)
            item["aggregate_expected_value_delta"] = payload["aggregate"]["comparison"][
                "expected_value_score_delta"
            ]
            item["aggregate_strategy_total_pnl_delta"] = payload["aggregate"]["comparison"][
                "strategy_total_pnl_delta"
            ]
            item["updated_at"] = payload["completed_at"]
            break
    registry["updated_at"] = payload["completed_at"]
    _write_json(REGISTRY_JSON, registry)


def main() -> None:
    _configure_source_family()
    gate2 = consensus.prior.base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    base_source_rows = consensus.prior._source_rows_by_window()
    theme_source_rows, theme_diagnostics = _theme_rows_by_window()
    merged_source_rows = _merge_source_rows(base_source_rows, theme_source_rows)
    baselines = consensus.prior._load_baselines()

    accepted_results, accepted_trades, accepted_aggregate = _accepted_comparator(
        baselines,
        base_source_rows,
    )
    results, target_trades_by_window = consensus._run_windows(baselines, merged_source_rows)
    aggregate = consensus.prior._aggregate_results(results)
    target_summary = consensus.prior._target_summary(target_trades_by_window)
    source_family_summary = consensus._source_family_summary(target_trades_by_window)
    theme_selected = _theme_selected_summary(target_trades_by_window)
    vs_comparator = _aggregate_vs_comparator(results, accepted_results)
    gate4 = _gate4(
        aggregate,
        results,
        target_summary,
        vs_comparator,
        source_family_summary,
        theme_selected,
    )
    completed_at = _utc_now()

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "lane": "alpha_search",
        "preflight": {
            "alpha_hypothesis": (
                "Theme-density confirmed breakout rows may improve the accepted "
                "independent free-data consensus when used only as a new "
                "production-visible confirmation family, not as standalone noisy "
                "ticker expansion."
            ),
            "category": "entry/candidate_pool/default_off_paper_adapter",
            "playbook_alignment": (
                "Meta research ranks default-off paper adapters highest. This "
                "uses a materially different free-OHLCV theme-participation "
                "field instead of source-count, FINRA, VIX, Form4, SEC text, or "
                "post-earnings scalar retunes."
            ),
            "nearby_prior_experiments": [
                "exp-20260526-016",
                "exp-20260603-014",
                "exp-20260603-015",
                "exp-20260604-002",
                "exp-20260604-005",
            ],
            "prior_difference": (
                "exp-20260526-016 tested standalone theme-density paper trades "
                "and failed. This run does not trade raw theme-density rows; it "
                "only asks whether they can confirm already accepted consensus "
                "same-date same-ticker candidates."
            ),
            "single_causal_variable": CHANGED_VARIABLE,
            "acceptance_criteria": {
                "canonical_windows": list(consensus.prior.base.WINDOWS.keys()),
                "must_beat_current_accepted_consensus_comparator": True,
                "per_window_delta_vs_accepted_comparator": "3 of 3 windows > 0",
                "minimum_theme_density_selected_trades": 1,
                "max_drawdown_drift": consensus.prior.MAX_DRAWDOWN_WORSE,
                "survival_rate_floor": 0.05,
                "max_single_positive_share": consensus.prior.MAX_SINGLE_POSITIVE_SHARE,
                "positive_pnl_hhi_max": consensus.prior.MAX_POSITIVE_HHI,
            },
            "reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260604_006_theme_density_consensus_source_family.py"
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "entry/candidate_pool: theme-density participation may add an "
                "independent confirmation family to accepted free-data consensus."
            ),
            "2_history_check": {
                "exp-20260526-016": "Standalone theme-density paper sleeve rejected after late_strong/old_thin regressions.",
                "exp-20260603-014": "Accepted independent-source consensus comparator.",
                "exp-20260604-002": "Broad-market source-family addition had zero selected overlap.",
                "exp-20260604-005": "Form4 source-family addition had zero selected overlap.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Use docs/backtesting.md three fixed windows; accept only if the "
                "variant beats core and current accepted consensus in all windows."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260604_006_theme_density_consensus_source_family.py"
            ),
        },
        "source_files": {
            **{name: str(path).replace("\\", "/") for name, path in consensus.SOURCE_FILES.items()},
            THEME_SOURCE_NAME: _repo_rel(THEME_SOURCE_JSON),
        },
        "theme_diagnostics": theme_diagnostics,
        "rule": {
            "rule_version": RULE_VERSION,
            "theme_source_name": THEME_SOURCE_NAME,
            "theme_source_family": THEME_SOURCE_FAMILY,
            "theme_source_experiment_id": THEME_SOURCE_EXPERIMENT_ID,
            "min_source_family_count": consensus.MIN_SOURCE_FAMILY_COUNT,
            "source_families": consensus.SOURCE_FAMILIES,
            "base_notional_usd": consensus.prior.BASE_NOTIONAL_USD,
            "hold_days": consensus.prior.HOLD_DAYS,
            "max_paper_trades_per_day": consensus.prior.MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": consensus.prior.SAME_TICKER_COOLDOWN_DAYS,
        },
        "production_impact": PRODUCTION_IMPACT,
        "prediction": PREDICTION,
        "gate2": gate2,
        "gate3": {
            "survival_floor": 0.05,
            "new_core_filter_added": False,
            "candidate_pool_source_family_admission_only": True,
            "min_survival_rate": min(_safe_float(row["before"].get("survival_rate")) for row in results),
        },
        "aggregate": aggregate,
        "accepted_comparator": {
            "experiment_id": ACCEPTED_COMPARATOR_ID,
            "source_artifact": _repo_rel(ACCEPTED_COMPARATOR_JSON),
            "aggregate": accepted_aggregate,
            "target_summary": consensus.prior._target_summary(accepted_trades),
        },
        "vs_accepted_comparator": vs_comparator,
        "results": results,
        "target_summary": target_summary,
        "theme_selected_summary": theme_selected,
        "target_trades_by_window": target_trades_by_window,
        "source_family_summary": source_family_summary,
        "gate4": gate4,
        "anti_js": "No JavaScript was used.",
    }

    _write_json(OUT_JSON, payload)
    record = _experiment_log_record(payload)
    _write_json(LOG_JSON, record)
    _write_card(payload)
    _update_ticket(payload)
    _update_manifest(payload)
    _upsert_registry(payload)
    consensus.prior.base._upsert_jsonl(EXPERIMENT_LOG, record)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": gate4["decision"],
                "aggregate_vs_core": aggregate["comparison"],
                "aggregate_vs_accepted_consensus": vs_comparator["comparison"],
                "theme_selected_trade_count": theme_selected["theme_selected_trade_count"],
                "anti_js": "No JavaScript was used.",
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
