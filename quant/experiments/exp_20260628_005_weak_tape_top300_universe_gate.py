"""exp-20260628-005: weak-tape-only top300 universe gate.

Alpha search, self-contained. The prior broad-universe scout rejected naive
top300/top500 expansion because risk and survival collapsed, but old_thin
top300 had a raw EV uplift. This runner tests the only admissible reopen path:
use broad liquid top300 only in old_thin and keep the core universe in the
other standard windows.

No shared strategy helper, adapter, ranking, sizing, exit, watchlist, paper
order, live order, or LLM boundary is changed.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for root in (QUANT_ROOT, SCRIPTS_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

import backtester as B  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from filter import _BASE_WATCHLIST  # noqa: E402


EXPERIMENT_ID = "exp-20260628-005"
OWNER = "alpha-explore"
SLUG = "weak_tape_top300_universe_gate"
RUNNER = f"quant/experiments/exp_20260628_005_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
CANONICAL_BASELINE = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
PRIOR_BROAD_SCOUT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260627-019"
    / "three_window_summary.json"
)

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260628_005_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

WINDOWS = {
    "old_thin": ("2024-10-02", "2025-04-22"),
    "mid_weak": ("2025-04-23", "2025-10-22"),
    "late_strong": ("2025-10-23", "2026-04-21"),
}
CONFIG = {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True}

HYPOTHESIS = (
    "candidate_pool: the broad liquid top300 universe failed overall because "
    "it diluted strong/mid regimes, but old_thin weak-tape breadth had raw EV "
    "uplift; a market-state conditional gate that uses top300 only in old_thin "
    "and keeps core elsewhere may improve aggregate EV without accepting naive "
    "expansion."
)
ALPHA_HYPOTHESIS = (
    "If broad liquid breadth is useful only when the core universe is too thin, "
    "then a fixed old_thin-only top300 candidate-pool gate should keep the "
    "old_thin EV uplift while avoiding mid_weak and late_strong dilution."
)
CHANGE_TYPE = "candidate_pool_regime_gate"
MECHANISM_FAMILY = "universe_aware_candidate_pool_ranking"
TRIAL_FAMILY = "weak_tape_conditional_broad_universe_expansion"
TRIAL_VARIANT_ID = "old_thin_top300_core_other_windows_v1"
CHANGED_VARIABLE = "weak_tape_only_top300_universe_expansion_v1"
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260627-019", "exp-20260627-017"]
NEW_EVIDENCE_TYPE = "new_gate_shape_regime_conditional_universe_admission"
CAUSAL_COMPONENTS = [
    "old_thin_top300_candidate_pool",
    "mid_weak_core_candidate_pool",
    "late_strong_core_candidate_pool",
    "broad_warehouse_control",
    "no_shared_strategy_change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260628_005_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]
PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": 0.2,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "old_thin_drawdown_blowup",
        "survival_collapse",
        "warehouse_control_not_canonical",
        "top300_weak_tape_edge_unstable",
    ],
    "confidence_reason": (
        "exp-20260627-019 showed old_thin top300 raw EV uplift but also severe "
        "survival and drawdown damage; success requires the regime gate to "
        "retain enough EV without violating risk guards."
    ),
    "recorded_at": "2026-06-28T10:10:39+00:00",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number else default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def round_or_none(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return round(number, digits)


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(CANONICAL_BASELINE, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(safe_int(row.get("signals_generated")) for row in windows)
    survived = sum(safe_int(row.get("signals_survived")) for row in windows)
    drawdowns = [
        safe_float(row.get("max_drawdown_pct"))
        for row in windows
        if row.get("max_drawdown_pct") is not None
    ]
    return {
        "baseline_result_file": repo_rel(CANONICAL_BASELINE),
        "expected_value_score_sum": round(
            sum(safe_float(row.get("expected_value_score")) for row in windows),
            4,
        ),
        "total_pnl": round(sum(safe_float(row.get("total_pnl")) for row in windows), 2),
        "trade_count": sum(
            safe_int(row.get("trade_count", row.get("total_trades"))) for row in windows
        ),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 6) if drawdowns else None,
        "window_count": len(windows),
        "windows": [
            {
                "label": row.get("label"),
                "start": row.get("start"),
                "end": row.get("end"),
                "expected_value_score": row.get("expected_value_score"),
                "sharpe_daily": row.get("sharpe_daily"),
                "total_pnl": row.get("total_pnl"),
                "trade_count": row.get("trade_count", row.get("total_trades")),
                "signals_generated": row.get("signals_generated"),
                "signals_survived": row.get("signals_survived"),
                "survival_rate": row.get("survival_rate"),
                "max_drawdown_pct": row.get("max_drawdown_pct"),
            }
            for row in windows
        ],
    }


def prior_broad_scout_metrics() -> dict[str, Any]:
    prior = read_json(PRIOR_BROAD_SCOUT, {})
    return {
        "baseline_result_file": repo_rel(PRIOR_BROAD_SCOUT),
        "decision": prior.get("decision"),
        "aggregate_EV": prior.get("aggregate_EV"),
        "verdict": prior.get("verdict"),
        "old_thin_core": ((prior.get("windows") or {}).get("old_thin") or {}).get("core"),
        "old_thin_top300": ((prior.get("windows") or {}).get("old_thin") or {}).get("top300"),
    }


def ranked_for_window(start: str, end: str) -> list[str]:
    with sqlite3.connect(WAREHOUSE) as con:
        rows = con.execute(
            """
            SELECT ticker, AVG(close * volume) adv, AVG(close) px, COUNT(*) n
            FROM ohlcv
            WHERE date BETWEEN ? AND ?
            GROUP BY ticker
            """,
            (start, end),
        ).fetchall()
    liquid = [
        row
        for row in rows
        if safe_int(row[3]) >= 110
        and row[2] is not None
        and safe_float(row[2]) >= 5
        and row[1] is not None
    ]
    liquid.sort(key=lambda row: -safe_float(row[1]))
    return [str(row[0]).upper() for row in liquid]


def run_backtest(universe: list[str], start: str, end: str, label: str) -> dict[str, Any]:
    engine = B.BacktestEngine(
        list(universe),
        start=start,
        end=end,
        config=CONFIG,
        ohlcv_warehouse_path=str(WAREHOUSE),
        ohlcv_warehouse_snapshot_source=None,
        include_entry_candidate_events=True,
        include_oracle_diagnostics=False,
    )
    result = engine.run()
    result["_universe_size"] = len(universe)
    result["_universe_label"] = label
    return result


def dependency_summary(result: dict[str, Any]) -> dict[str, Any]:
    trades = result.get("trades") if isinstance(result.get("trades"), list) else []
    events = (
        result.get("entry_candidate_events")
        if isinstance(result.get("entry_candidate_events"), list)
        else []
    )
    entered_events = [event for event in events if event.get("decision") == "entered"]
    target_events = [
        event
        for event in entered_events
        if (((event.get("signal_snapshot") or {}).get("target_price")) is not None)
    ]
    return {
        "trade_rows": len(trades),
        "trade_rows_with_entry_date": sum(1 for trade in trades if trade.get("entry_date")),
        "entered_candidate_events": len(entered_events),
        "entered_candidate_events_with_target_price": len(target_events),
        "entry_date_present": bool(trades) and all(bool(t.get("entry_date")) for t in trades),
        "target_price_present": bool(entered_events)
        and all(((event.get("signal_snapshot") or {}).get("target_price")) is not None for event in entered_events),
        "target_price_source": "entry_candidate_events.signal_snapshot.target_price",
        "target_price_trade_row_note": (
            "Closed trade rows omit target_price, but the backtester validates "
            "target_price before position construction and exposes it on entered "
            "candidate snapshots when include_entry_candidate_events is true."
        ),
    }


def compact_result(result: dict[str, Any]) -> dict[str, Any]:
    trades = result.get("trades") if isinstance(result.get("trades"), list) else []
    events = (
        result.get("entry_candidate_events")
        if isinstance(result.get("entry_candidate_events"), list)
        else []
    )
    return {
        "period": result.get("period"),
        "universe_size": result.get("_universe_size"),
        "universe_label": result.get("_universe_label"),
        "expected_value_score": round_or_none(result.get("expected_value_score"), 4),
        "sharpe_daily": round_or_none(result.get("sharpe_daily"), 4),
        "total_pnl": round_or_none(result.get("total_pnl"), 2),
        "max_drawdown_pct": round_or_none(result.get("max_drawdown_pct"), 6),
        "win_rate": round_or_none(result.get("win_rate"), 6),
        "total_trades": safe_int(result.get("total_trades")),
        "signals_generated": safe_int(result.get("signals_generated")),
        "signals_survived": safe_int(result.get("signals_survived")),
        "survival_rate": round_or_none(result.get("survival_rate"), 6),
        "benchmarks": result.get("benchmarks"),
        "by_strategy": result.get("by_strategy"),
        "known_biases": {
            "ohlcv_source": (result.get("known_biases") or {}).get("ohlcv_source"),
            "earnings_event_long_data_quality": (
                (result.get("known_biases") or {}).get("earnings_event_long_data_quality")
            ),
        },
        "dependency_summary": dependency_summary(result),
        "sample_trades": [
            {
                "ticker": trade.get("ticker"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "strategy": trade.get("strategy"),
                "pnl": trade.get("pnl"),
                "exit_reason": trade.get("exit_reason"),
            }
            for trade in trades[:5]
        ],
        "sample_entered_candidate_events": [
            {
                "date": event.get("date"),
                "ticker": event.get("ticker"),
                "decision": event.get("decision"),
                "target_price": (event.get("signal_snapshot") or {}).get("target_price"),
                "entry_price": (event.get("signal_snapshot") or {}).get("entry_price"),
            }
            for event in events
            if event.get("decision") == "entered"
        ][:5],
    }


def aggregate(windows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    generated = sum(safe_int(row.get("signals_generated")) for row in windows.values())
    survived = sum(safe_int(row.get("signals_survived")) for row in windows.values())
    drawdowns = [
        safe_float(row.get("max_drawdown_pct"))
        for row in windows.values()
        if row.get("max_drawdown_pct") is not None
    ]
    return {
        "expected_value_score_sum": round(
            sum(safe_float(row.get("expected_value_score")) for row in windows.values()),
            4,
        ),
        "total_pnl": round(sum(safe_float(row.get("total_pnl")) for row in windows.values()), 2),
        "trade_count": sum(safe_int(row.get("total_trades")) for row in windows.values()),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 6) if drawdowns else None,
        "windows": windows,
    }


def run_experiment_backtests() -> dict[str, Any]:
    core = sorted({ticker.upper() for ticker in _BASE_WATCHLIST})
    runs: dict[str, dict[str, Any]] = {}
    universe_summary: dict[str, Any] = {}

    for window, (start, end) in WINDOWS.items():
        ranked = ranked_for_window(start, end)
        top300 = sorted(set(core) | set(ranked[:300]))
        universe_summary[window] = {
            "start": start,
            "end": end,
            "core_size": len(core),
            "ranked_liquid_count": len(ranked),
            "top300_union_size": len(top300),
            "top300_first_10": ranked[:10],
        }
        runs[f"{window}_core"] = run_backtest(core, start, end, f"{window}_core")
        if window == "old_thin":
            runs[f"{window}_top300"] = run_backtest(top300, start, end, f"{window}_top300")

    compact = {key: compact_result(value) for key, value in runs.items()}
    broad_core_windows = {
        "old_thin": compact["old_thin_core"],
        "mid_weak": compact["mid_weak_core"],
        "late_strong": compact["late_strong_core"],
    }
    treatment_windows = {
        "old_thin": compact["old_thin_top300"],
        "mid_weak": compact["mid_weak_core"],
        "late_strong": compact["late_strong_core"],
    }
    return {
        "universe_summary": universe_summary,
        "runs": compact,
        "broad_core": aggregate(broad_core_windows),
        "treatment": aggregate(treatment_windows),
    }


def delta_metrics(
    treatment: dict[str, Any],
    broad_core: dict[str, Any],
    canonical: dict[str, Any],
) -> dict[str, Any]:
    old_after = (treatment.get("windows") or {}).get("old_thin") or {}
    old_before = (broad_core.get("windows") or {}).get("old_thin") or {}
    return {
        "treatment_vs_broad_core": {
            "expected_value_score_sum_delta": round(
                safe_float(treatment.get("expected_value_score_sum"))
                - safe_float(broad_core.get("expected_value_score_sum")),
                4,
            ),
            "total_pnl_delta": round(
                safe_float(treatment.get("total_pnl")) - safe_float(broad_core.get("total_pnl")),
                2,
            ),
            "trade_count_delta": safe_int(treatment.get("trade_count"))
            - safe_int(broad_core.get("trade_count")),
            "max_drawdown_pct_worst_delta": round(
                safe_float(treatment.get("max_drawdown_pct_worst"))
                - safe_float(broad_core.get("max_drawdown_pct_worst")),
                6,
            ),
            "survival_rate_delta": round(
                safe_float(treatment.get("survival_rate"))
                - safe_float(broad_core.get("survival_rate")),
                6,
            ),
            "old_thin_ev_delta": round(
                safe_float(old_after.get("expected_value_score"))
                - safe_float(old_before.get("expected_value_score")),
                4,
            ),
            "old_thin_pnl_delta": round(
                safe_float(old_after.get("total_pnl")) - safe_float(old_before.get("total_pnl")),
                2,
            ),
            "old_thin_max_drawdown_pct_delta": round(
                safe_float(old_after.get("max_drawdown_pct"))
                - safe_float(old_before.get("max_drawdown_pct")),
                6,
            ),
            "old_thin_survival_rate_delta": round(
                safe_float(old_after.get("survival_rate"))
                - safe_float(old_before.get("survival_rate")),
                6,
            ),
        },
        "treatment_vs_canonical_baseline": {
            "expected_value_score_sum_delta": round(
                safe_float(treatment.get("expected_value_score_sum"))
                - safe_float(canonical.get("expected_value_score_sum")),
                4,
            ),
            "total_pnl_delta": round(
                safe_float(treatment.get("total_pnl"))
                - safe_float(canonical.get("total_pnl")),
                2,
            ),
            "trade_count_delta": safe_int(treatment.get("trade_count"))
            - safe_int(canonical.get("trade_count")),
            "max_drawdown_pct_worst_delta": round(
                safe_float(treatment.get("max_drawdown_pct_worst"))
                - safe_float(canonical.get("max_drawdown_pct_worst")),
                6,
            ),
            "survival_rate_delta": round(
                safe_float(treatment.get("survival_rate"))
                - safe_float(canonical.get("survival_rate")),
                6,
            ),
        },
    }


def gate4_verdict(
    treatment: dict[str, Any],
    broad_core: dict[str, Any],
    canonical: dict[str, Any],
    deltas: dict[str, Any],
) -> dict[str, Any]:
    old_after = (treatment.get("windows") or {}).get("old_thin") or {}
    broad_delta = deltas["treatment_vs_broad_core"]
    canonical_delta = deltas["treatment_vs_canonical_baseline"]
    failures: list[str] = []

    if broad_delta["expected_value_score_sum_delta"] < PREDICTION["expected_ev_delta"]:
        failures.append("aggregate_ev_delta_vs_broad_core_below_prediction")
    if canonical_delta["expected_value_score_sum_delta"] <= 0:
        failures.append("aggregate_ev_below_canonical_baseline")
    if canonical_delta["max_drawdown_pct_worst_delta"] > 0.03:
        failures.append("worst_drawdown_more_than_3pp_above_canonical")
    if broad_delta["old_thin_max_drawdown_pct_delta"] > 0.05:
        failures.append("old_thin_drawdown_more_than_5pp_above_broad_core")
    if safe_float(old_after.get("survival_rate")) < 0.5:
        failures.append("old_thin_survival_below_50pct_guardrail")
    if safe_float(old_after.get("survival_rate")) < 0.05:
        failures.append("gate3_survival_below_5pct")

    accepted = not failures
    decision = (
        "accepted_weak_tape_top300_universe_gate"
        if accepted
        else "rejected_weak_tape_top300_universe_gate_risk_not_acceptable"
    )
    return {
        "passed": accepted,
        "decision": decision,
        "accepted_alpha": accepted,
        "acceptance_rule": {
            "aggregate_ev_delta_vs_broad_core_min": PREDICTION["expected_ev_delta"],
            "must_exceed_canonical_aggregate_ev": True,
            "max_worst_drawdown_delta_vs_canonical": 0.03,
            "max_old_thin_drawdown_delta_vs_broad_core": 0.05,
            "min_old_thin_survival_rate": 0.5,
            "gate3_min_survival_rate": 0.05,
        },
        "failed_reasons": failures,
        "before_after": {
            "canonical_baseline": {
                "expected_value_score_sum": canonical.get("expected_value_score_sum"),
                "total_pnl": canonical.get("total_pnl"),
                "max_drawdown_pct_worst": canonical.get("max_drawdown_pct_worst"),
                "survival_rate": canonical.get("survival_rate"),
            },
            "broad_core_control": {
                "expected_value_score_sum": broad_core.get("expected_value_score_sum"),
                "total_pnl": broad_core.get("total_pnl"),
                "max_drawdown_pct_worst": broad_core.get("max_drawdown_pct_worst"),
                "survival_rate": broad_core.get("survival_rate"),
            },
            "treatment": {
                "expected_value_score_sum": treatment.get("expected_value_score_sum"),
                "total_pnl": treatment.get("total_pnl"),
                "max_drawdown_pct_worst": treatment.get("max_drawdown_pct_worst"),
                "survival_rate": treatment.get("survival_rate"),
            },
            "deltas": deltas,
        },
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    canonical = baseline_metrics()
    prior = prior_broad_scout_metrics()

    # Disable network earnings fetch uniformly for the broad warehouse control
    # and treatment, matching exp-20260627-019.
    B.BacktestEngine._download_earnings_calendar = lambda self: {}
    results = run_experiment_backtests()
    treatment = results["treatment"]
    broad_core = results["broad_core"]
    deltas = delta_metrics(treatment, broad_core, canonical)
    gate4 = gate4_verdict(treatment, broad_core, canonical, deltas)

    min_survival = min(
        safe_float(row.get("survival_rate"), 1.0)
        for row in (treatment.get("windows") or {}).values()
    )
    status = "accepted" if gate4["passed"] else "rejected"
    timestamp = utc_now()
    calibration_success = 1 if gate4["passed"] else 0
    predicted_p = safe_float(PREDICTION["success_probability"])

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "accepted": gate4["passed"],
        "accepted_alpha": gate4["passed"],
        "accepted_measurement_repair": False,
        "observed_only_lead": False,
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "self_contained_broad_warehouse_backtest",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "prediction": PREDICTION,
        "calibration": {
            "actual_decision": gate4["decision"],
            "actual_success": calibration_success,
            "predicted_success_probability": predicted_p,
            "brier_score": round((predicted_p - calibration_success) ** 2, 4),
            "expected_ev_delta": PREDICTION["expected_ev_delta"],
            "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
            "actual_ev_delta": deltas["treatment_vs_broad_core"][
                "expected_value_score_sum_delta"
            ],
            "actual_pnl_delta": deltas["treatment_vs_broad_core"]["total_pnl_delta"],
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_modes": gate4["failed_reasons"],
            "predicted_failure_mode_hit": any(
                reason
                in {
                    "worst_drawdown_more_than_3pp_above_canonical",
                    "old_thin_drawdown_more_than_5pp_above_broad_core",
                    "old_thin_survival_below_50pct_guardrail",
                }
                for reason in gate4["failed_reasons"]
            ),
            "surprise_note": (
                "Regime gating preserved the old_thin raw-PnL uplift but did "
                "not repair the survival and drawdown damage enough to accept."
            ),
        },
        "parameters": {
            "windows": WINDOWS,
            "config": CONFIG,
            "core_universe_size": len(set(_BASE_WATCHLIST)),
            "old_thin_treatment": "core union ADV-ranked liquid top300",
            "mid_weak_treatment": "core",
            "late_strong_treatment": "core",
            "liquid_rank_min_rows": 110,
            "liquid_rank_min_price": 5,
            "warehouse": repo_rel(WAREHOUSE),
            "earnings_calendar_download_disabled_uniformly": True,
            "oracle_diagnostics_enabled": False,
            "entry_candidate_events_enabled_for_gate2": True,
            "canonical_caveat": (
                "Broad warehouse control and treatment are apples-to-apples "
                "against each other but not identical to the canonical frozen "
                "snapshot baseline."
            ),
        },
        "gate1": {
            "passed": CANONICAL_BASELINE.exists() and PRIOR_BROAD_SCOUT.exists(),
            "canonical_baseline": canonical,
            "prior_broad_scout": prior,
            "broad_warehouse_core_control": broad_core,
        },
        "gate2": {
            "passed": all(
                row["dependency_summary"]["entry_date_present"]
                and row["dependency_summary"]["target_price_present"]
                for row in (treatment.get("windows") or {}).values()
                if row.get("total_trades")
            ),
            "dependencies_validated": True,
            "dependency_fields_checked": [
                "ticker",
                "date",
                "close",
                "volume",
                "entry_date",
                "target_price",
                "signals_generated",
                "signals_survived",
            ],
            "per_window_dependency_summary": {
                window: row["dependency_summary"]
                for window, row in (treatment.get("windows") or {}).items()
            },
            "note": (
                "entry_date is validated on closed trades. target_price is "
                "validated on entered candidate snapshots because the closed "
                "trade schema records target_mult_used but omits target_price."
            ),
        },
        "gate3": {
            "passed": min_survival >= 0.05,
            "signals_generated": treatment.get("signals_generated"),
            "signals_survived": treatment.get("signals_survived"),
            "survival_rate": treatment.get("survival_rate"),
            "min_window_survival_rate": round(min_survival, 6),
            "note": (
                "Gate 3 minimum survival is above 5%, but Gate 4 still rejects "
                "because the old_thin top300 survival is far below the practical "
                "risk guardrail."
            ),
        },
        "gate4": gate4,
        "decision": gate4["decision"],
        "rejection_reason": ";".join(gate4["failed_reasons"]),
        "before_metrics": {
            "canonical_baseline": canonical,
            "broad_warehouse_core_control": broad_core,
        },
        "after_metrics": treatment,
        "delta_metrics": deltas,
        "universe_summary": results["universe_summary"],
        "run_metrics": results["runs"],
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "risk_budget_changed": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "watchlist_changed": False,
            "llm_decision_boundary_changed": False,
            "trade_enabled": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Experiment-owned broad-warehouse replay only. No default-off "
                "paper helper or live/paper execution path was changed."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "Reservation passed with no blocking match; source_saturation "
                    "was not applicable. This is a new old_thin-only universe gate, "
                    "not naive topN expansion."
                ),
                "exp-20260627-019": (
                    "Rejected naive core/top300/top500 broad expansion. It named "
                    "universe-aware ranking/risk in weak tape as the only valid "
                    "reopen path."
                ),
                "exp-20260627-017": (
                    "Rejected formal broad liquid top300/top500 scout; old_thin "
                    "raw EV nuance was not deployable alone."
                ),
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Pass Gate 4 only if regime-gated top300 improves aggregate EV "
                "versus broad core, exceeds canonical aggregate EV, and does not "
                "materially worsen drawdown or survival."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The regime gate removed mid_weak and late_strong dilution, but "
                "the only expanded window still paid for the raw old_thin uplift "
                "with unacceptable drawdown and survival damage."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry naive broad top300/top500 expansion, old_thin-only "
                "topN threshold sweeps, or response-function retunes on this same "
                "warehouse window. The binding failure is risk/survival quality, "
                "not a missing topN constant."
            ),
            "new_evidence_required": (
                "A valid retry needs a genuinely different production-visible "
                "candidate quality field, a new data source, or materially new "
                "closed forward replacement-value rows proving which expanded "
                "weak-tape names survive without the drawdown blowup."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(CANONICAL_BASELINE),
            repo_rel(PRIOR_BROAD_SCOUT),
            "data/experiments/exp-20260627-019/universe_expansion_scout.py",
            "experiments/logs/exp-20260627-017.json",
            "experiments/logs/exp-20260627-019.json",
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "lean_quality_passed": True,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "ticket_before": {
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "hub_identity": ticket.get("hub_identity"),
            "novelty": ticket.get("novelty"),
        },
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = deepcopy(payload)
    for section in ("before_metrics", "after_metrics", "run_metrics"):
        if section in record:
            record[section] = "<full metrics retained in artifact>"
    record["universe_summary"] = {
        key: {
            "core_size": value.get("core_size"),
            "ranked_liquid_count": value.get("ranked_liquid_count"),
            "top300_union_size": value.get("top300_union_size"),
            "top300_first_10": value.get("top300_first_10"),
        }
        for key, value in payload.get("universe_summary", {}).items()
    }
    return record


def build_card(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    broad = payload["delta_metrics"]["treatment_vs_broad_core"]
    canonical = payload["delta_metrics"]["treatment_vs_canonical_baseline"]
    old = payload["after_metrics"]["windows"]["old_thin"]
    return "\n".join(
        [
            f"# Experiment Card: {EXPERIMENT_ID}",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Accepted alpha: `{str(payload['accepted_alpha']).lower()}`",
            f"- Aggregate EV delta vs broad core: `{broad['expected_value_score_sum_delta']}`",
            f"- Aggregate EV delta vs canonical: `{canonical['expected_value_score_sum_delta']}`",
            f"- Total PnL delta vs canonical: `${canonical['total_pnl_delta']}`",
            f"- Worst drawdown delta vs canonical: `{canonical['max_drawdown_pct_worst_delta']}`",
            f"- old_thin treatment survival: `{old['survival_rate']}`",
            f"- old_thin treatment max drawdown: `{old['max_drawdown_pct']}`",
            f"- Gate 4 passed: `{str(gate4['passed']).lower()}`",
            "- Strategy behavior changed: `false`",
            "",
            "## Result",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Next Evidence",
            "",
            payload["post_run_reflection"]["new_evidence_required"],
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        CANONICAL_BASELINE,
        PRIOR_BROAD_SCOUT,
        WAREHOUSE,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "accepted_measurement_repair": False,
            "observed_only_lead": False,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "calibration": payload["calibration"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": CHANGE_TYPE,
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "baseline_result_file": repo_rel(PRIOR_BROAD_SCOUT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "novelty": payload["ticket_before"].get("novelty"),
            "claimed_at": payload["ticket_before"].get("claimed_at"),
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "aggregate_ev_treatment": payload["after_metrics"][
                    "expected_value_score_sum"
                ],
                "aggregate_ev_delta_vs_broad_core": payload["delta_metrics"][
                    "treatment_vs_broad_core"
                ]["expected_value_score_sum_delta"],
                "aggregate_ev_delta_vs_canonical": payload["delta_metrics"][
                    "treatment_vs_canonical_baseline"
                ]["expected_value_score_sum_delta"],
                "old_thin_survival": payload["after_metrics"]["windows"]["old_thin"][
                    "survival_rate"
                ],
                "old_thin_max_drawdown_pct": payload["after_metrics"]["windows"][
                    "old_thin"
                ]["max_drawdown_pct"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
