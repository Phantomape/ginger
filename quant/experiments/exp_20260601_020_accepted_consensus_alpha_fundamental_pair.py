"""exp-20260601-020: accepted consensus alpha+fundamental source pair.

Replay-only alpha scout. It keeps accepted free-data cross-source consensus
candidates only when the same ticker/date is supported by both the accepted
alpha-score market-regime paper source and the accepted Fundamental Growth +
RS paper source. It does not change production orders or shared adapters.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant.experiments import exp_20260531_030_accepted_free_data_cross_source_consensus as prev  # noqa: E402


EXPERIMENT_ID = "exp-20260601-020"
STEM = "accepted_consensus_alpha_fundamental_pair"
TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_source_composition"
CHANGED_VARIABLE = "accepted_free_data_consensus_alpha_fundamental_pair_v1"
RULE_VERSION = CHANGED_VARIABLE

REQUIRED_SOURCES = (
    "ALPHA_SCORE_MARKET_REGIME_PAPER",
    "FUNDAMENTAL_GROWTH_RS_PAPER",
)
SOURCE_EXPERIMENTS = {
    "exp-20260531-030": "Accepted free-data cross-source consensus candidate pool.",
    "exp-20260601-001": "Accepted shared default-off free-data consensus adapter.",
    "exp-20260601-015": "Positive no-core-entry capacity lead, not promotable due baseline drift.",
    "exp-20260601-018": "Positive core-capacity-available lead, not promotable due baseline drift.",
    "exp-20260601-017": "Rejected liquidity-efficiency gate; do not retry nearby liquidity/range filters.",
}

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30
CANONICAL_DOC_EV = 7.8941
CANONICAL_DOC_PNL = 234_850.99
DOC_BASELINE_TOLERANCE_EV = 0.001
DOC_BASELINE_TOLERANCE_PNL = 1.0

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = ROOT / "docs" / "experiment_registry.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    if isinstance(value, float):
        if math.isfinite(value):
            return round(value, 6)
        return None
    return value


def _round(value: Any, digits: int = 4) -> Any:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return value
    if not math.isfinite(numeric):
        return None
    return round(numeric, digits)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo_rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _configure_prev() -> None:
    prev.EXPERIMENT_ID = EXPERIMENT_ID
    prev.STEM = STEM
    prev.TRIAL_FAMILY = TRIAL_FAMILY
    prev.CHANGED_VARIABLE = CHANGED_VARIABLE
    prev.RULE_VERSION = RULE_VERSION
    prev.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    prev.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    prev.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    prev.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    prev.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    prev.OUT_DIR = OUT_DIR
    prev.OUT_JSON = OUT_JSON
    prev.BEFORE_JSON = BEFORE_JSON
    prev.AFTER_JSON = AFTER_JSON
    prev.LOG_JSON = LOG_JSON
    prev.TICKET_JSON = TICKET_JSON
    prev.CARD_MD = CARD_MD
    prev.EXPERIMENT_LOG = EXPERIMENT_LOG
    prev.REGISTRY_JSON = REGISTRY_JSON


def _baseline_caveat(aggregate: dict[str, Any]) -> dict[str, Any]:
    ev_delta = float(aggregate["before"]["expected_value_score"]) - CANONICAL_DOC_EV
    pnl_delta = float(aggregate["before"]["total_pnl"]) - CANONICAL_DOC_PNL
    matches = (
        abs(ev_delta) <= DOC_BASELINE_TOLERANCE_EV
        and abs(pnl_delta) <= DOC_BASELINE_TOLERANCE_PNL
    )
    return {
        "baseline_matches_docs": matches,
        "canonical_docs_ev": CANONICAL_DOC_EV,
        "canonical_docs_pnl": CANONICAL_DOC_PNL,
        "current_replay_ev": aggregate["before"]["expected_value_score"],
        "current_replay_pnl": aggregate["before"]["total_pnl"],
        "ev_delta_vs_docs": _round(ev_delta, 6),
        "pnl_delta_vs_docs": _round(pnl_delta, 2),
        "note": (
            "Current replay baseline differs from docs/backtesting.md accepted baseline. "
            "Positive replay results are observation-only until the clean baseline/parity "
            "decision is resolved."
        )
        if not matches
        else "Current replay aggregate baseline matches docs/backtesting.md within tolerance.",
    }


def _filter_candidates(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    rejected: Counter[str] = Counter()
    for candidate in candidates:
        source_names = set(candidate.get("source_names") or [])
        if not set(REQUIRED_SOURCES).issubset(source_names):
            rejected["missing_required_alpha_fundamental_pair"] += 1
            continue
        updated = dict(candidate)
        updated.update(
            {
                "required_source_pair": list(REQUIRED_SOURCES),
                "source_composition_rule": "requires_alpha_score_market_regime_and_fundamental_growth_rs",
                "rule_version": RULE_VERSION,
                "strategy": "accepted_consensus_alpha_fundamental_pair",
                "trade_enabled": False,
                "alters_orders": False,
            }
        )
        filtered.append(updated)
    diagnostics = {
        "raw_consensus_candidates": len(candidates),
        "source_pair_candidate_count": len(filtered),
        "rejection_counts": dict(sorted(rejected.items())),
        "raw_source_combo_counts": dict(
            sorted(
                Counter("+".join(row.get("source_names") or []) for row in candidates).items(),
                key=lambda item: (-item[1], item[0]),
            )
        ),
    }
    return filtered, diagnostics


def _run_windows(
    baselines: dict[str, dict[str, Any]],
    source_rows_by_window: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    results: list[dict[str, Any]] = []
    target_trades_by_window: dict[str, list[dict[str, Any]]] = {}
    for label, cfg in prev.base.WINDOWS.items():
        snapshot = prev.base.shadow._load_snapshot(cfg["snapshot"])
        raw_candidates = prev._consensus_candidates_for_window(label, source_rows_by_window)
        candidates, source_pair_diagnostics = _filter_candidates(raw_candidates)
        target_trades, target_diagnostics = prev._select_target_trades(snapshot, candidates)
        for trade in target_trades:
            trade["rule_version"] = RULE_VERSION
            trade["strategy"] = "accepted_consensus_alpha_fundamental_pair"
            trade["required_source_pair"] = list(REQUIRED_SOURCES)
            trade["source_composition_rule"] = "requires_alpha_score_market_regime_and_fundamental_growth_rs"
            trade["trade_enabled"] = False
            trade["alters_orders"] = False

        before_result = baselines[label]["result"]
        before = baselines[label]["metrics"]
        overlay = prev.base._overlay_from_paper_trades(before_result, target_trades)
        after = prev.base.overlay_helper._metrics_with_overlay(before_result, overlay)
        raw_delta = prev.base.overlay_helper._delta(after, before)
        comparison = {
            "expected_value_score_delta": raw_delta["expected_value_score"],
            "strategy_total_pnl_delta": raw_delta["total_pnl"],
            "total_pnl_delta": raw_delta["total_pnl"],
            "max_drawdown_delta": raw_delta["max_drawdown_pct"],
            "raw_delta": raw_delta,
        }
        results.append(
            {
                "label": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "before": before,
                "after": after,
                "comparison": comparison,
                "target_trade_count": len(target_trades),
                "target_trade_pnl_usd": sum(float(row.get("pnl", 0.0)) for row in target_trades),
                "raw_consensus_candidate_count": len(raw_candidates),
                "source_pair_candidate_count": len(candidates),
                "target_diagnostics": {
                    **target_diagnostics,
                    "source_pair_filter": source_pair_diagnostics,
                },
            }
        )
        target_trades_by_window[label] = target_trades
    return results, target_trades_by_window


def _gate4(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
    baseline_caveat: dict[str, Any],
) -> dict[str, Any]:
    comparison = aggregate["comparison"]
    ev_delta = float(comparison.get("expected_value_score_delta") or 0.0)
    pnl_delta = float(comparison.get("strategy_total_pnl_delta") or 0.0)
    ev_windows = [
        row["label"]
        for row in results
        if float(row["comparison"].get("expected_value_score_delta") or 0.0) > 0.0
    ]
    pnl_windows = [
        row["label"]
        for row in results
        if float(row["comparison"].get("strategy_total_pnl_delta") or 0.0) > 0.0
    ]
    max_drawdown_delta = max(float(row["comparison"].get("max_drawdown_delta") or 0.0) for row in results)
    min_survival_rate = min(float(row["after"].get("survival_rate") or 0.0) for row in results)
    target_trade_count = int(target_summary["target_trade_count"])
    target_window_count = sum(1 for row in results if int(row["target_trade_count"]) > 0)
    alpha_gates = {
        "aggregate_expected_value_positive": ev_delta > 0.0,
        "aggregate_pnl_positive": pnl_delta > 0.0,
        "all_windows_expected_value_improved": len(ev_windows) == len(results),
        "all_windows_pnl_improved": len(pnl_windows) == len(results),
        "target_trade_count_passed": target_trade_count >= MIN_TARGET_TRADES,
        "target_window_count_passed": target_window_count >= MIN_TARGET_WINDOWS,
        "drawdown_drift_passed": max_drawdown_delta <= MAX_DRAWDOWN_WORSE,
        "survival_floor_passed": min_survival_rate >= 0.05,
        "concentration_guard_passed": (
            float(target_summary["max_single_positive_share"]) <= MAX_SINGLE_POSITIVE_SHARE
            and float(target_summary["positive_pnl_hhi"]) <= MAX_POSITIVE_HHI
        ),
    }
    gates = dict(alpha_gates)
    gates["baseline_matches_docs_for_retention"] = bool(baseline_caveat["baseline_matches_docs"])
    alpha_failed = [key for key, passed in alpha_gates.items() if not passed]
    failed = [key for key, passed in gates.items() if not passed]
    alpha_passed = not alpha_failed
    promotable_now = alpha_passed and bool(baseline_caveat["baseline_matches_docs"])
    if alpha_passed and not baseline_caveat["baseline_matches_docs"]:
        decision = "positive_replay_lead_not_promoted_baseline_mismatch"
        rationale = (
            "The alpha+fundamental source pair cleared alpha gates, but current replay "
            "baseline does not match docs/backtesting.md, so no strategy change is retained."
        )
    elif alpha_passed:
        decision = "positive_replay_lead_not_promoted_requires_shared_source_pair_adapter"
        rationale = (
            "The source pair cleared alpha gates on a matching baseline, but this run did "
            "not add a shared live/backtest adapter; no production orders changed."
        )
    else:
        decision = "rejected_accepted_consensus_alpha_fundamental_pair"
        rationale = "One or more Gate 4 alpha checks failed, so no strategy change is retained."
    return {
        "decision": decision,
        "passed": promotable_now,
        "alpha_passed": alpha_passed,
        "promotable_now": promotable_now,
        "rationale": rationale,
        "gates": gates,
        "alpha_failed_gates": alpha_failed,
        "failed_gates": failed,
        "ev_windows_improved": ev_windows,
        "pnl_windows_improved": pnl_windows,
        "max_drawdown_delta": _round(max_drawdown_delta, 6),
        "min_survival_rate": _round(min_survival_rate, 6),
        "requires_parity_before_promotion": alpha_passed,
        "requires_clean_baseline_before_promotion": alpha_passed and not baseline_caveat["baseline_matches_docs"],
    }


def _preflight() -> dict[str, Any]:
    return {
        "alpha_hypothesis": (
            "entry / candidate_pool: accepted free-data consensus candidates backed by both "
            "alpha-score market-regime and Fundamental Growth + RS may provide cleaner "
            "replacement value than the full consensus queue."
        ),
        "category": "entry / candidate_pool",
        "playbook_alignment": (
            "Uses a production-visible default-off paper adapter family and free data; avoids "
            "LLM soft-ranking, state-surface scalar retunes, broad alpha_score retunes, and "
            "Companyfacts FCF threshold retries."
        ),
        "history_check": SOURCE_EXPERIMENTS,
        "single_causal_variable": CHANGED_VARIABLE,
        "acceptance_criteria": {
            "source": "docs/backtesting.md canonical three-window replay",
            "aggregate_expected_value_delta": "> 0",
            "aggregate_pnl_delta": "> 0",
            "per_window_expected_value_delta": "3 of 3 windows > 0",
            "per_window_pnl_delta": "3 of 3 windows > 0",
            "minimum_target_trades": MIN_TARGET_TRADES,
            "minimum_target_windows": MIN_TARGET_WINDOWS,
            "max_drawdown_drift": MAX_DRAWDOWN_WORSE,
            "survival_rate_floor": 0.05,
            "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi_max": MAX_POSITIVE_HHI,
            "baseline_matches_docs_for_retention": True,
        },
        "reproducibility": (
            "Run .venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260601_020_accepted_consensus_alpha_fundamental_pair.py"
        ),
    }


def _artifact(payload: dict[str, Any]) -> str:
    aggregate = payload["aggregate"]
    comparison = aggregate["comparison"]
    lines = [
        f"# {EXPERIMENT_ID}: Accepted Consensus Alpha + Fundamental Pair",
        "",
        f"- decision: `{payload['decision']}`",
        f"- aggregate EV: `{aggregate['before']['expected_value_score']}` -> `{aggregate['after']['expected_value_score']}` "
        f"({comparison['expected_value_score_delta']:+.4f})",
        f"- aggregate PnL: `${aggregate['before']['total_pnl']:,.2f}` -> `${aggregate['after']['total_pnl']:,.2f}` "
        f"({comparison['strategy_total_pnl_delta']:+,.2f})",
        f"- target trades: `{payload['target_summary']['target_trade_count']}`",
        f"- max single positive share: `{payload['target_summary']['max_single_positive_share']}`",
        f"- positive PnL HHI: `{payload['target_summary']['positive_pnl_hhi']}`",
        f"- alpha failed gates: `{', '.join(payload['gate4']['alpha_failed_gates']) or 'none'}`",
        f"- retention failed gates: `{', '.join(payload['gate4']['failed_gates']) or 'none'}`",
        "",
        "## Three-Window Result",
        "",
        "| window | EV before | EV after | EV delta | PnL delta | target trades | source-pair candidates |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["results"]:
        lines.append(
            f"| {row['label']} | {float(row['before']['expected_value_score']):.4f} | "
            f"{float(row['after']['expected_value_score']):.4f} | "
            f"{float(row['comparison']['expected_value_score_delta']):+.4f} | "
            f"${float(row['comparison']['strategy_total_pnl_delta']):+,.2f} | "
            f"{row['target_trade_count']} | {row['source_pair_candidate_count']} |"
        )
    lines.extend(
        [
            "",
            "## Production / Backtest Consistency",
            "",
            "Replay-only. No production order generation, shared ranking, sizing, exits, LLM, "
            "or live adapter changed. Any positive lead must be rebuilt as a shared "
            "live/backtest default-off adapter before promotion.",
            "",
            "## Baseline Caveat",
            "",
            payload["baseline_caveat"]["note"],
            "",
            "## Conclusion",
            "",
            payload["gate4"]["rationale"],
            "",
        ]
    )
    return "\n".join(lines)


def _card(payload: dict[str, Any]) -> str:
    aggregate = payload["aggregate"]
    comparison = aggregate["comparison"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} accepted consensus alpha+fundamental pair",
            "",
            f"- Trial family: `{TRIAL_FAMILY}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            f"- Decision: `{payload['decision']}`",
            f"- Aggregate EV delta: {float(comparison['expected_value_score_delta']):+.4f}",
            f"- Aggregate PnL delta: ${float(comparison['strategy_total_pnl_delta']):+,.2f}",
            f"- Target trades: {payload['target_summary']['target_trade_count']}",
            f"- Baseline matches docs: {payload['baseline_caveat']['baseline_matches_docs']}",
            f"- Before/after: `{aggregate['before']['expected_value_score']}` -> `{aggregate['after']['expected_value_score']}`",
            "",
            "See artifact for the three-window table and production/backtest caveat.",
            "",
        ]
    )


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["completed_at"],
        "lane": "alpha_search",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "change_type": "default_off_candidate_pool_source_composition",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "decision": payload["decision"],
        "accepted": bool(payload["gate4"]["promotable_now"]),
        "baseline_caveat": payload["baseline_caveat"],
        "production_impact": payload["production_impact"],
        "requires_parity_before_promotion": bool(payload["gate4"]["requires_parity_before_promotion"]),
        "metrics": {
            "aggregate_expected_value_before": payload["aggregate"]["before"]["expected_value_score"],
            "aggregate_expected_value_after": payload["aggregate"]["after"]["expected_value_score"],
            "aggregate_expected_value_delta": comparison["expected_value_score_delta"],
            "aggregate_strategy_total_pnl_before": payload["aggregate"]["before"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_after": payload["aggregate"]["after"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_delta": comparison["strategy_total_pnl_delta"],
            "target_trade_count": payload["target_summary"]["target_trade_count"],
            "target_trade_pnl_usd": payload["target_summary"]["target_trade_pnl_usd"],
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
            }
            for row in payload["results"]
        ],
        "artifact_path": _repo_rel(OUT_JSON),
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket: dict[str, Any] = {}
    if TICKET_JSON.exists():
        ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
    ticket.update(
        {
            "id": EXPERIMENT_ID,
            "experiment_id": EXPERIMENT_ID,
            "status": "completed",
            "decision": payload["decision"],
            "completed_at": payload["completed_at"],
            "artifact": _repo_rel(OUT_JSON),
            "report_file": _repo_rel(ARTIFACT_MD),
            "log": _repo_rel(LOG_JSON),
            "gate4": payload["gate4"],
            "baseline_caveat": payload["baseline_caveat"],
            "production_impact": payload["production_impact"],
        }
    )
    _write_json(TICKET_JSON, ticket)


def _update_registry(payload: dict[str, Any]) -> None:
    if not REGISTRY_JSON.exists():
        return
    registry = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    experiments = registry.get("experiments")
    if not isinstance(experiments, list):
        return
    for item in experiments:
        if isinstance(item, dict) and item.get("experiment_id") == EXPERIMENT_ID:
            item["status"] = "completed"
            item["decision"] = payload["decision"]
            item["completed_at"] = payload["completed_at"]
            item["artifact"] = _repo_rel(OUT_JSON)
            item["report_file"] = _repo_rel(ARTIFACT_MD)
            item["log"] = _repo_rel(LOG_JSON)
            item["aggregate_expected_value_delta"] = payload["aggregate"]["comparison"][
                "expected_value_score_delta"
            ]
            item["aggregate_strategy_total_pnl_delta"] = payload["aggregate"]["comparison"][
                "strategy_total_pnl_delta"
            ]
            break
    _write_json(REGISTRY_JSON, registry)


def main() -> None:
    _configure_prev()
    gate2 = prev.base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    source_rows = prev._source_rows_by_window()
    baselines = prev._load_baselines()
    results, target_trades_by_window = _run_windows(baselines, source_rows)
    aggregate = prev._aggregate_results(results)
    target_summary = prev._target_summary(target_trades_by_window)
    baseline_caveat = _baseline_caveat(aggregate)
    gate4 = _gate4(aggregate, results, target_summary, baseline_caveat)
    completed_at = _utc_now()
    production_impact = {
        "replay_only": True,
        "default_off_paper_only": True,
        "shared_policy_changed": False,
        "run_adapter_changed": False,
        "backtester_adapter_changed": False,
        "parity_test_added": False,
        "trade_enabled": False,
        "alters_orders": False,
        "production_orders_changed": False,
        "production_signal_path_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "llm_used": False,
    }

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "lane": "alpha_search",
        "status": gate4["decision"],
        "decision": gate4["decision"],
        "accepted": bool(gate4["promotable_now"]),
        "preflight": _preflight(),
        "source_files": {name: path.as_posix() for name, path in prev.SOURCE_FILES.items()},
        "required_sources": list(REQUIRED_SOURCES),
        "rule": {
            "rule_version": RULE_VERSION,
            "base_consensus_min_source_count": prev.MIN_SOURCE_COUNT,
            "required_sources": list(REQUIRED_SOURCES),
            "base_notional_usd": prev.BASE_NOTIONAL_USD,
            "hold_days": prev.HOLD_DAYS,
            "max_paper_trades_per_day": prev.MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": prev.SAME_TICKER_COOLDOWN_DAYS,
        },
        "production_impact": production_impact,
        "gate1": {
            "passed": True,
            "baseline_artifact": _repo_rel(BEFORE_JSON),
            "baseline_caveat": baseline_caveat,
        },
        "gate2": gate2,
        "gate3": {
            "passed": min(float(row["after"].get("survival_rate") or 0.0) for row in results) >= 0.05,
            "note": "No production filter was added; survival is inherited from canonical core replay plus paper overlay.",
            "signals_generated_survived_by_window": {
                row["label"]: {
                    "signals_generated": row["after"].get("signals_generated"),
                    "signals_survived": row["after"].get("signals_survived"),
                    "survival_rate": row["after"].get("survival_rate"),
                }
                for row in results
            },
        },
        "aggregate": aggregate,
        "results": results,
        "target_summary": target_summary,
        "target_trades_by_window": target_trades_by_window,
        "baseline_caveat": baseline_caveat,
        "gate4": gate4,
        "interpretation": gate4["rationale"],
        "next_retry_requires": [
            "clean current-vs-docs baseline/parity decision before any positive replay promotion",
            "shared live/backtest source-pair adapter before order impact",
            "new forward replacement rows before nearby consensus filter/cap retries",
        ],
        "anti_js": "No JavaScript was used.",
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(CARD_MD),
            _repo_rel(TICKET_JSON),
        ],
    }

    _write_json(OUT_JSON, payload)
    _write_json(
        BEFORE_JSON,
        {
            **aggregate["before"],
            "experiment_id": EXPERIMENT_ID,
            "artifact_role": "before_aggregate",
            "baseline_caveat": baseline_caveat,
        },
    )
    _write_json(
        AFTER_JSON,
        {
            **aggregate["after"],
            "experiment_id": EXPERIMENT_ID,
            "artifact_role": "after_aggregate",
            "baseline_caveat": baseline_caveat,
        },
    )
    _write_json(LOG_JSON, _experiment_log_record(payload))
    _write_text(CARD_MD, _card(payload))
    _write_text(ARTIFACT_MD, _artifact(payload))
    _update_ticket(payload)
    _update_registry(payload)
    prev.base._upsert_jsonl(EXPERIMENT_LOG, _experiment_log_record(payload))

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": gate4["decision"],
                "aggregate": aggregate["comparison"],
                "alpha_failed_gates": gate4["alpha_failed_gates"],
                "failed_gates": gate4["failed_gates"],
                "baseline_caveat": baseline_caveat,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
