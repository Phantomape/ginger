"""exp-20260615-021: fixed PIT-regime soft chop down-tilt replay.

Alpha-search / replay lead test. The only policy bundle under test is a fixed
0.5x paper-notional down-tilt for trades whose entry/signal date is classified
as ``choppy_range`` by the frozen exp-20260615-019 PIT regime model. Non-chop
rows stay at 1.0x. No production helper, ranking, sizing, orders, exits,
watchlist, or LLM/news behavior changes.
"""

from __future__ import annotations

import json
import math
import sqlite3
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import experiment_registry  # noqa: E402
from quant.experiments.exp_20260615_019_pit_regime_state_attribution import (  # noqa: E402
    REGIME_LABELS,
    RegimeModel,
    WINDOWS,
)

EXPERIMENT_ID = "exp-20260615-021"
STEM = "pit_regime_soft_chop_down_tilt"
OWNER = "codex-alpha-explore"
CHANGED_VARIABLE = "fixed_choppy_range_soft_down_tilt_default_off_replay_v1"
RULE_VERSION = "pit_regime_soft_chop_down_tilt_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260615_021_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_ATTRIBUTION = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260615-019"
    / "exp_20260615_019_pit_regime_state_attribution.json"
)
PRIMARY_ACCEPTED_ALLOCATOR = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260611-005"
    / "exp_20260611_005_lagged_consensus_shared_allocator_source.json"
)
FGRS_ACCEPTED_SUPPORT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260528-017"
    / "fundamental_growth_rs_low_liability_support.json"
)
DEFERRED_REVENUE_REJECTED = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260615-017"
    / "exp_20260615_017_deferred_revenue_demand_acceleration.json"
)
PAPER_SLEEVES_DIR = REPO_ROOT / "data" / "paper_sleeves"
WAREHOUSE_DB = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"

CHOPPY_WEIGHT = 0.5
NON_CHOP_WEIGHT = 1.0
MIN_FORWARD_CHOPPY_ROWS = 20
MIN_HISTORICAL_CHOPPY_ROWS = 20


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _round(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return round(out, digits) if math.isfinite(out) else None


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_historical_models() -> dict[str, RegimeModel]:
    models: dict[str, RegimeModel] = {}
    for label, (_start, _end, rel_path) in WINDOWS.items():
        payload = _load_json(REPO_ROOT / rel_path)
        models[label] = RegimeModel(payload.get("ohlcv") or {})
    return models


def _build_warehouse_model() -> RegimeModel | None:
    if not WAREHOUSE_DB.exists() or WAREHOUSE_DB.stat().st_size <= 0:
        return None
    ohlcv: dict[str, list[dict[str, Any]]] = defaultdict(list)
    con = sqlite3.connect(str(WAREHOUSE_DB))
    try:
        rows = con.execute(
            """
            select ticker, date, open, high, low, close, volume
            from ohlcv
            where date >= '2025-01-01'
            order by ticker, date
            """
        )
        for ticker, date, open_, high, low, close, volume in rows:
            ohlcv[str(ticker)].append(
                {
                    "Date": str(date)[:10],
                    "Open": open_,
                    "High": high,
                    "Low": low,
                    "Close": close,
                    "Volume": volume,
                }
            )
    finally:
        con.close()
    return RegimeModel(dict(ohlcv))


def _load_target_trades(path: Path, pnl_keys: tuple[str, ...]) -> dict[str, list[dict[str, Any]]]:
    data = _load_json(path)
    by_window = data.get("target_trades_by_window") or {}
    out: dict[str, list[dict[str, Any]]] = {}
    for label in WINDOWS:
        clean: list[dict[str, Any]] = []
        for row in by_window.get(label) or []:
            signal_date = str(row.get("signal_date") or row.get("date") or "")[:10]
            pnl = None
            for key in pnl_keys:
                if row.get(key) is None:
                    continue
                try:
                    pnl = float(row[key])
                    break
                except (TypeError, ValueError):
                    continue
            if not signal_date or pnl is None:
                continue
            clean.append(
                {
                    "signal_date": signal_date,
                    "entry_date": str(row.get("entry_date") or signal_date)[:10],
                    "ticker": row.get("ticker"),
                    "pnl": pnl,
                    "source_family": row.get("source_family") or row.get("source") or row.get("strategy"),
                    "notional_usd": row.get("paper_notional_usd") or row.get("notional_usd"),
                }
            )
        out[label] = clean
    return out


def _weight_for_regime(regime_label: str) -> float:
    return CHOPPY_WEIGHT if regime_label == "choppy_range" else NON_CHOP_WEIGHT


def _summarize_pnls(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "total_pnl": 0.0, "mean_pnl": None, "win_rate": None}
    return {
        "count": len(values),
        "total_pnl": _round(sum(values), 2),
        "mean_pnl": _round(sum(values) / len(values), 2),
        "win_rate": _round(sum(1 for v in values if v > 0) / len(values), 4),
    }


def _evaluate_trade_set(
    name: str,
    artifact: Path,
    trades_by_window: dict[str, list[dict[str, Any]]],
    models: dict[str, RegimeModel],
    primary: bool,
) -> dict[str, Any]:
    by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    by_regime: dict[str, list[float]] = defaultdict(list)
    source_counts: Counter[str] = Counter()
    total_base = 0.0
    total_after = 0.0
    total_delta = 0.0
    total_trades = 0
    choppy_trades = 0
    unknown_trades = 0
    deltas: list[float] = []

    for label, trades in trades_by_window.items():
        base = 0.0
        after = 0.0
        choppy_base = 0.0
        choppy_count = 0
        unknown_count = 0
        regime_counts: Counter[str] = Counter()
        for trade in trades:
            total_trades += 1
            base += trade["pnl"]
            regime = models[label].classify(trade["signal_date"])
            regime_label = regime.get("regime_label", "unknown")
            if regime_label == "unknown":
                unknown_count += 1
                unknown_trades += 1
            weight = _weight_for_regime(regime_label)
            adjusted = trade["pnl"] * weight
            after += adjusted
            by_regime[regime_label].append(trade["pnl"])
            regime_counts[regime_label] += 1
            if regime_label == "choppy_range":
                choppy_count += 1
                choppy_trades += 1
                choppy_base += trade["pnl"]
            if trade.get("source_family"):
                source_counts[str(trade["source_family"])] += 1
        delta = after - base
        deltas.append(delta)
        by_window[label] = {
            "trade_count": len(trades),
            "base_pnl": _round(base, 2),
            "after_pnl": _round(after, 2),
            "delta_pnl": _round(delta, 2),
            "choppy_trade_count": choppy_count,
            "choppy_base_pnl": _round(choppy_base, 2),
            "unknown_regime_trade_count": unknown_count,
            "regime_counts": dict(regime_counts),
        }
        total_base += base
        total_after += after
        total_delta += delta

    windows_improved = sum(1 for delta in deltas if delta > 0.000001)
    windows_regressed = sum(1 for delta in deltas if delta < -0.000001)
    historical_passed = (
        primary
        and total_delta > 0
        and windows_improved == len(WINDOWS)
        and windows_regressed == 0
        and choppy_trades >= MIN_HISTORICAL_CHOPPY_ROWS
        and unknown_trades == 0
    )
    return {
        "name": name,
        "artifact": _repo_rel(artifact),
        "primary_acceptance_set": primary,
        "base_total_pnl": _round(total_base, 2),
        "after_total_pnl": _round(total_after, 2),
        "delta_total_pnl": _round(total_delta, 2),
        "trade_count": total_trades,
        "choppy_trade_count": choppy_trades,
        "unknown_regime_trade_count": unknown_trades,
        "windows_improved": windows_improved,
        "windows_regressed": windows_regressed,
        "historical_replay_passed": historical_passed,
        "by_window": by_window,
        "by_regime_base_pnl": {label: _summarize_pnls(vals) for label, vals in sorted(by_regime.items())},
        "source_counts_top10": dict(source_counts.most_common(10)),
    }


def _load_forward_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for state_path in sorted(PAPER_SLEEVES_DIR.glob("*/state.json")):
        try:
            state = _load_json(state_path)
        except Exception:
            continue
        sleeve = state.get("sleeve") or state_path.parent.name
        closed = state.get("closed_positions") or state.get("closed_outcomes") or []
        for row in closed:
            entry = str(row.get("entry_date") or row.get("signal_date") or "")[:10]
            if not entry:
                continue
            rows.append(
                {
                    "sleeve": sleeve,
                    "entry_date": entry,
                    "ticker": row.get("ticker"),
                    "pnl": row.get("pnl"),
                    "replacement_value_vs_cash_usd": row.get("replacement_value_vs_cash_usd"),
                    "replacement_value_vs_spy_usd": row.get("replacement_value_vs_spy_usd"),
                    "replacement_value_vs_qqq_usd": row.get("replacement_value_vs_qqq_usd"),
                }
            )
    return rows


def _evaluate_forward_rows(current_model: RegimeModel | None) -> dict[str, Any]:
    rows = _load_forward_rows()
    if current_model is None:
        return {
            "forward_rows_total": len(rows),
            "tagged_rows": 0,
            "choppy_rows_with_replacement_value_vs_spy": 0,
            "ready_for_acceptance": False,
            "blocker": "warehouse_model_unavailable",
        }
    by_regime_values: dict[str, list[float]] = defaultdict(list)
    by_regime_counts: Counter[str] = Counter()
    by_sleeve_counts: Counter[str] = Counter()
    tagged = 0
    for row in rows:
        regime = current_model.classify(row["entry_date"])
        regime_label = regime.get("regime_label", "unknown")
        if regime_label == "unknown":
            continue
        tagged += 1
        by_regime_counts[regime_label] += 1
        by_sleeve_counts[str(row["sleeve"])] += 1
        rv = row.get("replacement_value_vs_spy_usd")
        if rv is None:
            continue
        try:
            by_regime_values[regime_label].append(float(rv))
        except (TypeError, ValueError):
            continue
    choppy_rv_count = len(by_regime_values.get("choppy_range", []))
    return {
        "forward_rows_total": len(rows),
        "tagged_rows": tagged,
        "regime_counts": dict(by_regime_counts),
        "sleeve_counts": dict(by_sleeve_counts),
        "replacement_value_vs_spy_by_regime": {
            label: _summarize_pnls(vals) for label, vals in sorted(by_regime_values.items())
        },
        "choppy_rows_with_replacement_value_vs_spy": choppy_rv_count,
        "min_forward_choppy_rows": MIN_FORWARD_CHOPPY_ROWS,
        "ready_for_acceptance": choppy_rv_count >= MIN_FORWARD_CHOPPY_ROWS,
        "warehouse_source": _repo_rel(WAREHOUSE_DB),
    }


def _build_payload() -> dict[str, Any]:
    historical_models = _build_historical_models()
    current_model = _build_warehouse_model()

    primary = _evaluate_trade_set(
        "accepted_helper_source_priority_allocator_exp20260611005",
        PRIMARY_ACCEPTED_ALLOCATOR,
        _load_target_trades(PRIMARY_ACCEPTED_ALLOCATOR, ("pnl", "paper_pnl")),
        historical_models,
        primary=True,
    )
    secondary_fgrs = _evaluate_trade_set(
        "accepted_fundamental_growth_rs_low_liability_support_diagnostic",
        FGRS_ACCEPTED_SUPPORT,
        _load_target_trades(FGRS_ACCEPTED_SUPPORT, ("pnl", "pnl_without_low_liability_support")),
        historical_models,
        primary=False,
    )
    secondary_deferred = _evaluate_trade_set(
        "rejected_deferred_revenue_candidate_pool_diagnostic_only",
        DEFERRED_REVENUE_REJECTED,
        _load_target_trades(DEFERRED_REVENUE_REJECTED, ("pnl", "paper_pnl")),
        historical_models,
        primary=False,
    )
    forward = _evaluate_forward_rows(current_model)

    failed_reasons: list[str] = []
    if not primary["historical_replay_passed"]:
        if primary["windows_improved"] < len(WINDOWS):
            failed_reasons.append("not_all_canonical_windows_improved")
        if primary["windows_regressed"] > 0:
            failed_reasons.append("canonical_window_regression")
        if primary["choppy_trade_count"] < MIN_HISTORICAL_CHOPPY_ROWS:
            failed_reasons.append("historical_choppy_sample_too_small")
        if primary["delta_total_pnl"] <= 0:
            failed_reasons.append("aggregate_pnl_delta_not_positive")
    if not forward["ready_for_acceptance"]:
        failed_reasons.append("forward_choppy_replacement_rows_too_thin")
    failed_reasons.append("replay_only_no_shared_daily_regime_artifact")

    historical_positive_lead = (
        primary["delta_total_pnl"] > 0
        and primary["windows_regressed"] == 0
        and primary["choppy_trade_count"] >= MIN_HISTORICAL_CHOPPY_ROWS
    )
    if historical_positive_lead and forward["ready_for_acceptance"]:
        decision = "positive_replay_lead_not_promoted_shared_regime_artifact_missing"
        status = "positive_replay_lead_not_promoted"
    else:
        decision = "rejected_soft_chop_down_tilt_not_promotable"
        status = "rejected"

    actual_success = 1 if status == "accepted" else 0
    success_probability = 0.18
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": _utc_now(),
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "change_type": "risk_allocation_replay_lead",
        "mechanism_family": "tail_state_classifier_for_momentum_candidate_pools",
        "trial_family": "pit_regime_soft_chop_down_tilt",
        "trial_variant_id": "choppy_range_weight_0p50_nonchop_1p00_v1",
        "changed_variable": CHANGED_VARIABLE,
        "rule_version": RULE_VERSION,
        "hypothesis": (
            "Risk allocation alpha: a fixed soft 0.5x notional down-tilt for "
            "default-off paper trades whose entry date is classified as "
            "choppy_range by the frozen exp-20260615-019 PIT regime model may "
            "cut directionless-chop losses while preserving risk_on and "
            "risk_off winners."
        ),
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "risk allocation / capital allocation: fixed choppy_range soft "
                "down-tilt for default-off paper rows, aligned with the tail-state "
                "classifier queue."
            ),
            "2_history_check": {
                "exp-20260615-019": "Built the PIT regime diagnostic and found choppy_range losses, but forward rows were too thin.",
                "exp-20260614-010": "Rejected a hard accepted-allocator market-breadth tail filter after all three windows regressed.",
                "exp-20260613-005": "Accepted a narrow state-conditioned sleeve tilt, capped at paper-pending-forward.",
            },
            "3_single_policy_bundle": (
                "0.5x multiplier on choppy_range rows, 1.0x on all other rows, "
                "using frozen exp019 regime constants; all implementation is "
                "read-only measurement needed to test this one bundle."
            ),
            "4_acceptance_standard": (
                "Primary accepted allocator replay must improve all three fixed "
                "windows with no regression and adequate choppy sample; forward "
                "closed rows must include at least 20 choppy_range replacement-value "
                "rows before promotion can be considered."
            ),
            "5_reproducibility": f".venv\\Scripts\\python.exe -B {_repo_rel(Path(__file__))}",
        },
        "parameters": {
            "choppy_weight": CHOPPY_WEIGHT,
            "non_chop_weight": NON_CHOP_WEIGHT,
            "min_forward_choppy_rows": MIN_FORWARD_CHOPPY_ROWS,
            "min_historical_choppy_rows": MIN_HISTORICAL_CHOPPY_ROWS,
            "regime_rule_source": _repo_rel(BASELINE_ATTRIBUTION),
        },
        "primary_result": primary,
        "secondary_diagnostics": {
            "accepted_fundamental_growth_rs_low_liability_support": secondary_fgrs,
            "rejected_deferred_revenue_candidate_pool": secondary_deferred,
        },
        "forward_readiness": forward,
        "gate4": {
            "passed": False,
            "decision": decision,
            "failed_reasons": failed_reasons,
            "primary_artifact": _repo_rel(PRIMARY_ACCEPTED_ALLOCATOR),
            "primary_aggregate_pnl_delta": primary["delta_total_pnl"],
            "primary_windows_improved": primary["windows_improved"],
            "primary_windows_regressed": primary["windows_regressed"],
            "primary_choppy_trade_count": primary["choppy_trade_count"],
            "forward_choppy_replacement_rows": forward.get("choppy_rows_with_replacement_value_vs_spy", 0),
            "note": (
                "This runner does not recompute canonical core EV because it is a "
                "read-only notional overlay on default-off paper rows. It can only "
                "create a lead; acceptance requires a shared daily regime artifact, "
                "parity test, and full Gate 1-4 replay."
            ),
        },
        "before_metrics": {
            "primary_total_pnl": primary["base_total_pnl"],
            "primary_trade_count": primary["trade_count"],
        },
        "after_metrics": {
            "primary_total_pnl": primary["after_total_pnl"],
            "primary_trade_count": primary["trade_count"],
        },
        "delta_metrics": {
            "primary_total_pnl": primary["delta_total_pnl"],
            "primary_choppy_trade_count": primary["choppy_trade_count"],
        },
        "prediction": {
            "success_probability": success_probability,
            "expected_ev_delta": 0.05,
            "expected_pnl_delta": 1200.0,
            "main_failure_modes": [
                "forward_rows_too_thin",
                "mid_weak_no_chop_coverage",
                "window_regression",
                "replay_only_not_promotable",
            ],
            "confidence_reason": (
                "exp019 found choppy_range losses in FGRS and deferred-revenue "
                "attribution, but forward rows had no choppy coverage and exp20260614-010 "
                "rejected a harder breadth tail filter, so this is a low-probability "
                "replay-lead test."
            ),
        },
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual_success,
            "predicted_success_probability": success_probability,
            "brier_score": _round((success_probability - actual_success) ** 2, 4),
            "actual_pnl_delta": primary["delta_total_pnl"],
            "expected_pnl_delta": 1200.0,
            "predicted_failure_modes": [
                "forward_rows_too_thin",
                "mid_weak_no_chop_coverage",
                "window_regression",
                "replay_only_not_promotable",
            ],
            "realized_failure_mode": ",".join(failed_reasons),
            "predicted_failure_mode_hit": any(
                reason in failed_reasons
                for reason in [
                    "forward_choppy_replacement_rows_too_thin",
                    "not_all_canonical_windows_improved",
                    "canonical_window_regression",
                    "replay_only_no_shared_daily_regime_artifact",
                ]
            ),
        },
        "production_impact": {
            "replay_only": True,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "parity_test_added": False,
            "trade_enabled": False,
            "daily_snapshot_exposed": False,
            "live_realism_evaluated": False,
            "live_ready": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "uses_llm": False,
            "parity_note": (
                "No production path changed. A retry/promotion would require a shared "
                "daily PIT regime artifact, adapter parity test, and enough closed "
                "forward replacement-value rows tagged as choppy_range."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The chop signal remains a plausible loss attribution axis, but the "
                "fixed soft tilt is not promotable because the accepted allocator "
                "does not deliver the required three-window replay improvement and "
                "current closed forward rows still do not provide enough choppy_range "
                "replacement-value evidence."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not sweep choppy weights, regime constants, risk_off/bull thresholds, "
                "hard on/off gates, per-window labels, top-N, hold days, or allocator "
                "rank on the frozen windows."
            ),
            "new_evidence_required": (
                "Retry only after a shared daily regime artifact has accumulated enough "
                "closed forward replacement-value rows in choppy_range, or after a "
                "materially different PIT chop discriminator is available."
            ),
        },
        "next_retry_requires": [
            "shared_daily_pit_regime_artifact",
            ">=20 closed forward choppy_range rows with replacement_value_vs_spy_usd",
            "full Gate 1-4 replay through shared policy if the forward evidence matures",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    primary = payload["primary_result"]
    lines = [
        f"# {EXPERIMENT_ID} PIT Regime Soft Chop Down-Tilt",
        "",
        f"Status: `{payload['status']}`",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Primary Accepted Allocator Result",
        "",
        "| window | trades | choppy | base PnL | after PnL | delta |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, row in primary["by_window"].items():
        lines.append(
            f"| {label} | {row['trade_count']} | {row['choppy_trade_count']} | "
            f"{row['base_pnl']} | {row['after_pnl']} | {row['delta_pnl']} |"
        )
    lines += [
        "",
        f"Aggregate primary PnL delta: `{primary['delta_total_pnl']}`",
        f"Windows improved/regressed: `{primary['windows_improved']}` / `{primary['windows_regressed']}`",
        "",
        "## Forward Readiness",
        "",
        "```json",
        json.dumps(payload["forward_readiness"], indent=2, sort_keys=True),
        "```",
        "",
        "## Verdict",
        "",
        ", ".join(payload["gate4"]["failed_reasons"]),
        "",
        "No JavaScript was used.",
    ]
    return "\n".join(lines) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "parameters": payload["parameters"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "gate4": payload["gate4"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
        "artifact": _repo_rel(OUT_JSON),
        "anti_js": "No JavaScript was used.",
    }


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }
    _write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _build_card(payload))
    experiment_registry.append_log_entry(EXPERIMENT_LOG, _build_log_record(payload))
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "decision": payload["decision"],
        "summary": payload["decision"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
    }
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result=result,
        status=payload["status"],
        fields=fields,
    )
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    _persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "primary_delta_total_pnl": payload["primary_result"]["delta_total_pnl"],
                "primary_windows": payload["primary_result"]["by_window"],
                "forward_readiness": payload["forward_readiness"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
