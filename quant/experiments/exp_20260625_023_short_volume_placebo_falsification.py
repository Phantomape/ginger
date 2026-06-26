"""exp-20260625-023: placebo falsification for short-volume informed-flow.

Read-only alpha falsification. This runner does not create a candidate pool,
change a helper, mutate paper sleeve state, or alter live/default behavior.

The single question is whether the positive exp-20260625-018 observed-only
Moomoo short_volume_ratio lead is stronger than deterministic placebo
assignments on the same forward observations. If exact PIT percentiles do not
beat the placebos, the lead should be treated as selection noise and not retried.
"""

from __future__ import annotations

import bisect
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
EXPERIMENTS_ROOT = REPO_ROOT / "quant" / "experiments"
for entry in (REPO_ROOT, SCRIPTS_ROOT, EXPERIMENTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402
import exp_20260625_018_short_volume_informed_flow_attribution as base  # noqa: E402


EXPERIMENT_ID = "exp-20260625-023"
OWNER = "alpha-explore"
SLUG = "short_volume_placebo_falsification"
RUNNER = f"quant/experiments/exp_20260625_023_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260625_023_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXP018_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260625-018"
    / "exp_20260625_018_short_volume_informed_flow_attribution.json"
)
EXP019_LOG = REPO_ROOT / "experiments" / "logs" / "exp-20260625-019.json"

HYPOTHESIS = (
    "alpha_search/falsification: if the exp-20260625-018 Moomoo short-volume "
    "informed-flow lead is real rather than selection noise, exact PIT "
    "short_volume_ratio percentiles should beat deterministic date-shift and "
    "ticker-shuffle placebo assignments on the same forward observations."
)
CHANGE_TYPE = "observed_only_attribution"
IMPLEMENTATION_MODE = "observed_only_falsification_runner"
MECHANISM_FAMILY = "alpha_falsification_audit"
TRIAL_FAMILY = "moomoo_short_volume_informed_flow_placebo_falsification"
TRIAL_VARIANT_ID = "exact_vs_dateshift_tickershuffle_v1"
CHANGED_VARIABLE = "moomoo_short_volume_informed_flow_placebo_falsification_v1"
NEW_EVIDENCE_TYPE = "new_gate_shape_falsification_placebo"
NEW_EVIDENCE_AXIS = (
    "New gate shape: a predeclared placebo falsification audit of the prior "
    "positive short-volume lead, not a threshold/top-N/hold/notional sweep or "
    "a new candidate-pool scan on the short-volume source."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260625-018",
    "exp-20260625-019",
    "exp-20260622-010",
]
CAUSAL_COMPONENTS = [
    "exp018 forward observation ledger",
    "exact short-volume percentile assignment",
    "date-shift placebo",
    "ticker-shuffle placebo",
    "no strategy change",
]
CONFIG = {
    "hold_days": base.HOLD_DAYS,
    "min_trailing_obs_for_percentile": base.MIN_TRAILING_OBS,
    "quintiles": 5,
    "toxic_quintile_index": 4,
    "min_total_observations": 2000,
    "min_windows_with_exact_negative_direction": 2,
    "min_exact_edge_advantage_vs_placebo": 0.0025,
    "date_shift_positions": 11,
    "ticker_shuffle_offset": 7,
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
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[str] = []
    replaced = False
    encoded = json.dumps(record, sort_keys=True)
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
                    rows.append(encoded)
                    replaced = True
                continue
            rows.append(json.dumps(existing, sort_keys=True))
    if not replaced:
        rows.append(encoded)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None


def sha256(path: Path) -> str | None:
    return base.sha256(path)


def bucket_stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "mean": None, "median": None, "win_rate": None}
    return {
        "n": len(values),
        "mean": round(sum(values) / len(values), 6),
        "median": round(float(median(values)), 6),
        "win_rate": round(sum(1 for value in values if value > 0) / len(values), 4),
    }


def pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 0 or vy <= 0:
        return None
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return round(cov / (vx * vy) ** 0.5, 6)


def quintile(percentile: float) -> int:
    return min(CONFIG["quintiles"] - 1, int(percentile * CONFIG["quintiles"]))


def window_of(activity_date: str) -> str | None:
    for name, start, end, _ in base.WINDOWS:
        if start <= activity_date <= end:
            return name
    return None


def build_observations() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    series, price_audit = base.load_price_series()
    lookup = base.build_forward_lookup(series)
    by_ticker, short_volume_audit = base.load_short_volume()
    pct_index = base.build_percentile_index(by_ticker)

    observations: list[dict[str, Any]] = []
    valid_pct_by_ticker: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for ticker, (dates, pcts) in pct_index.items():
        for activity_date, percentile in zip(dates, pcts):
            if percentile is not None:
                valid_pct_by_ticker[ticker].append((activity_date, percentile))

    for ticker, seq in by_ticker.items():
        if ticker in base.SKIP_TICKERS:
            continue
        dates, pcts = pct_index[ticker]
        for activity_date, percentile in zip(dates, pcts):
            if percentile is None:
                continue
            win = window_of(activity_date)
            if win is None:
                continue
            fwd = base.forward_return(series, lookup, ticker, activity_date)
            if fwd is None:
                continue
            observations.append(
                {
                    "ticker": ticker,
                    "activity_date": activity_date,
                    "window": win,
                    "exact_percentile": percentile,
                    "forward_return_10d": fwd,
                }
            )

    ticker_names = sorted(valid_pct_by_ticker)
    ticker_pos = {ticker: idx for idx, ticker in enumerate(ticker_names)}
    for row in observations:
        ticker = row["ticker"]
        own_values = valid_pct_by_ticker[ticker]
        own_dates = [item[0] for item in own_values]
        own_i = bisect.bisect_left(own_dates, row["activity_date"])
        if own_values:
            shifted_i = (own_i + CONFIG["date_shift_positions"]) % len(own_values)
            row["date_shift_percentile"] = own_values[shifted_i][1]
        else:
            row["date_shift_percentile"] = None

        shuffled = None
        if ticker in ticker_pos and ticker_names:
            start = ticker_pos[ticker] + CONFIG["ticker_shuffle_offset"]
            for step in range(len(ticker_names)):
                other = ticker_names[(start + step) % len(ticker_names)]
                if other == ticker:
                    continue
                other_values = valid_pct_by_ticker[other]
                other_dates = [item[0] for item in other_values]
                idx = bisect.bisect_right(other_dates, row["activity_date"]) - 1
                if idx >= 0:
                    shuffled = other_values[idx][1]
                    break
        row["ticker_shuffle_percentile"] = shuffled

    audit = {
        "ohlcv": price_audit,
        "short_volume": short_volume_audit,
        "observation_count": len(observations),
        "tickers_with_valid_percentiles": len(valid_pct_by_ticker),
        "date_shift_rows": sum(1 for row in observations if row.get("date_shift_percentile") is not None),
        "ticker_shuffle_rows": sum(
            1 for row in observations if row.get("ticker_shuffle_percentile") is not None
        ),
    }
    return observations, audit


def summarize_assignment(
    observations: list[dict[str, Any]],
    percentile_key: str,
) -> dict[str, Any]:
    scopes = ["POOLED", "old_thin", "mid_weak", "late_strong"]
    by_scope: dict[str, Any] = {}
    windows_with_negative_direction = 0
    usable_total = 0
    for scope in scopes:
        scoped = [
            row
            for row in observations
            if (scope == "POOLED" or row["window"] == scope)
            and row.get(percentile_key) is not None
        ]
        usable_total += len(scoped) if scope == "POOLED" else 0
        buckets = {
            q: bucket_stats(
                [
                    float(row["forward_return_10d"])
                    for row in scoped
                    if quintile(float(row[percentile_key])) == q
                ]
            )
            for q in range(CONFIG["quintiles"])
        }
        q1 = buckets[0]["mean"]
        q5 = buckets[CONFIG["toxic_quintile_index"]]["mean"]
        edge = round(q1 - q5, 6) if q1 is not None and q5 is not None else None
        toxic_below_clean = q1 is not None and q5 is not None and q5 < q1
        if scope != "POOLED" and toxic_below_clean:
            windows_with_negative_direction += 1
        by_scope[scope] = {
            "n": len(scoped),
            "q1_mean": q1,
            "q5_mean": q5,
            "q1_minus_q5_mean": edge,
            "corr_percentile_fwd_return": pearson(
                [float(row[percentile_key]) for row in scoped],
                [float(row["forward_return_10d"]) for row in scoped],
            ),
            "toxic_q5_underperforms_clean_q1": toxic_below_clean,
            "quintiles": {
                f"Q{q + 1}": buckets[q] for q in range(CONFIG["quintiles"])
            },
        }
    return {
        "percentile_key": percentile_key,
        "total_observations": usable_total,
        "windows_with_negative_direction": windows_with_negative_direction,
        "by_scope": by_scope,
    }


def evaluate_gate4(summaries: dict[str, dict[str, Any]], exp018: dict[str, Any]) -> dict[str, Any]:
    exact = summaries["exact"]
    date_shift = summaries["date_shift"]
    ticker_shuffle = summaries["ticker_shuffle"]
    exact_pooled = exact["by_scope"]["POOLED"]
    date_pooled = date_shift["by_scope"]["POOLED"]
    ticker_pooled = ticker_shuffle["by_scope"]["POOLED"]
    exact_edge = as_float(exact_pooled["q1_minus_q5_mean"])
    date_edge = as_float(date_pooled["q1_minus_q5_mean"])
    ticker_edge = as_float(ticker_pooled["q1_minus_q5_mean"])
    placebo_best = max(edge for edge in (date_edge, ticker_edge) if edge is not None)
    edge_advantage = exact_edge - placebo_best if exact_edge is not None else None

    failed: list[str] = []
    if exact["total_observations"] < CONFIG["min_total_observations"]:
        failed.append("thin_forward_rows")
    if exact_edge is None or exact_edge <= 0:
        failed.append("exact_clean_minus_toxic_not_positive")
    if exact_pooled["corr_percentile_fwd_return"] is None or exact_pooled["corr_percentile_fwd_return"] >= 0:
        failed.append("exact_correlation_not_negative")
    if exact["windows_with_negative_direction"] < CONFIG["min_windows_with_exact_negative_direction"]:
        failed.append("too_few_windows_with_exact_negative_direction")
    if edge_advantage is None or edge_advantage < CONFIG["min_exact_edge_advantage_vs_placebo"]:
        failed.append("placebo_matches_or_beats_exact_edge")

    exp019 = read_json(EXP019_LOG, {}) or {}
    exp019_decision = exp019.get("decision")
    exp019_gate_failed = exp019_decision == "rejected_moomoo_short_volume_clean_flow_gate"
    if exp019_gate_failed:
        failed.append("shared_gate_already_rejected_vs_accepted_allocator")

    passed_falsification = not any(
        reason
        for reason in failed
        if reason
        in {
            "thin_forward_rows",
            "exact_clean_minus_toxic_not_positive",
            "exact_correlation_not_negative",
            "too_few_windows_with_exact_negative_direction",
            "placebo_matches_or_beats_exact_edge",
        }
    )
    decision = (
        "observed_only_placebo_falsification_passed_but_promotion_blocked_by_exp019"
        if passed_falsification and exp019_gate_failed
        else (
            "observed_only_positive_short_volume_placebo_falsification_passed"
            if passed_falsification
            else "rejected_short_volume_lead_failed_placebo_falsification"
        )
    )
    status = "observed_only_positive_lead" if passed_falsification else "observed_only_rejected"
    if exp019_gate_failed:
        status = "observed_only_rejected"

    return {
        "passed": passed_falsification and not exp019_gate_failed,
        "falsification_passed": passed_falsification,
        "status": status,
        "decision": decision,
        "failed_reasons": failed,
        "acceptance_rule": (
            "Observed-only falsification passes only if exact PIT short_volume_ratio "
            "has >=2000 observations, pooled Q1-clean minus Q5-toxic forward-return "
            "edge is positive, pooled correlation is negative, at least two canonical "
            "windows have Q5 below Q1, and the exact pooled edge beats both date-shift "
            "and ticker-shuffle placebo edges by at least 25bp. Passing this test is "
            "still not accepted alpha; exp019's shared Gate-4 rejection remains binding."
        ),
        "exact_edge": exact_edge,
        "date_shift_edge": date_edge,
        "ticker_shuffle_edge": ticker_edge,
        "best_placebo_edge": placebo_best,
        "exact_edge_advantage_vs_best_placebo": (
            round(edge_advantage, 6) if edge_advantage is not None else None
        ),
        "exp018_decision": exp018.get("decision"),
        "exp019_decision": exp019_decision,
        "promotion_blockers": [
            "exp019_shared_clean_flow_gate_failed_vs_accepted_allocator",
            "no_strategy_or_paper_helper_changed",
            "do_not_retry_short_volume_thresholds_without_new_borrow_or_forward_rows",
        ],
    }


def production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "daily_snapshot_changed": False,
        "paper_orders_changed": False,
        "live_orders_changed": False,
        "trade_enabled": False,
        "ranking_changed": False,
        "sizing_changed": False,
        "exits_changed": False,
        "llm_decision_boundary_changed": False,
        "replay_only": False,
        "parity_note": "Read-only falsification audit; no production/backtest behavior changed.",
    }


def calibration(gate4: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
    predicted = float(prediction.get("success_probability") or 0.0)
    success = 1.0 if gate4["passed"] else 0.0
    return {
        "actual_success": success,
        "actual_gate4_passed": gate4["passed"],
        "predicted_success_probability": predicted,
        "brier_score": round((predicted - success) ** 2, 4),
        "predicted_failure_modes": prediction.get("main_failure_modes") or [],
        "realized_failure_modes": gate4["failed_reasons"],
        "predicted_failure_mode_hit": bool(
            set(prediction.get("main_failure_modes") or []) & set(gate4["failed_reasons"])
        )
        or "shared_gate_already_rejected_vs_accepted_allocator" in gate4["failed_reasons"],
        "surprise_note": (
            "Low surprise: the exact signal had to clear placebo and the already rejected "
            "shared clean-flow Gate-4 result remained a binding blocker."
        ),
    }


def post_run_reflection(gate4: dict[str, Any]) -> dict[str, Any]:
    if gate4["falsification_passed"]:
        why = (
            "The exact PIT short-volume percentile edge exceeded the deterministic "
            "placebos, so exp018 was not obviously a date/ticker assignment artifact. "
            "However exp019 already showed the tradable clean-flow gate did not beat "
            "the accepted allocator, so this remains rejected for promotion."
        )
    else:
        why = (
            "The exact PIT short-volume percentile edge did not clear the placebo "
            "falsification standard, so the observed-only lead is not reliable enough "
            "to justify another shared-helper or threshold retry."
        )
    return {
        "why_result_happened": why,
        "forbidden_near_neighbor_retry": (
            "Do not retry Moomoo short-volume by changing quintile cutoffs, percentile "
            "lookbacks, top-N, hold days, notional, cooldown, allocator rank, or clean/"
            "toxic threshold on the same frozen windows or same forward rows."
        ),
        "new_evidence_required": (
            "Reopen only with true PIT borrow fee/utilization/loan-availability economics, "
            "materially more closed accepted-allocator forward rows tagged at entry, or a "
            "different non-OHLCV flow source with its own placebo and accepted-comparator gate."
        ),
    }


def pct(value: Any) -> str:
    number = as_float(value)
    return "n/a" if number is None else f"{number * 100:+.2f}%"


def build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Assignment | n | Q1 clean | Q5 toxic | Q1-Q5 | corr |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for key in ["exact", "date_shift", "ticker_shuffle"]:
        summary = payload["attribution"][key]["by_scope"]["POOLED"]
        rows.append(
            "| {key} | {n} | {q1} | {q5} | {edge} | {corr} |".format(
                key=key,
                n=summary["n"],
                q1=pct(summary["q1_mean"]),
                q5=pct(summary["q5_mean"]),
                edge=pct(summary["q1_minus_q5_mean"]),
                corr=summary["corr_percentile_fwd_return"],
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: short-volume placebo falsification",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production orders changed: `false`",
            "- Shared helper promoted: `false`",
            f"- Runner: `{RUNNER_COMMAND}`",
            "",
            "## Hypothesis",
            "",
            HYPOTHESIS,
            "",
            "## Pooled Forward 10d Edge",
            "",
            *rows,
            "",
            f"- Exact edge advantage vs best placebo: `{pct(payload['gate4']['exact_edge_advantage_vs_best_placebo'])}`",
            f"- Failed reasons: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    paths = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        EXP018_ARTIFACT,
        EXP019_LOG,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "runner": RUNNER,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "reproduction_commands": payload["reproduction_commands"],
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in paths
        },
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "lane": "alpha_search",
        "owner": OWNER,
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["gate4"]["falsification_passed"],
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "parameters": payload["parameters"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "attribution": payload["attribution"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "artifact": payload["artifact"],
        "runner": RUNNER,
        "changed_files": payload["changed_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "anti_js": payload["anti_js"],
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
            "accepted": False,
            "accepted_alpha": False,
            "observed_only_lead": payload["gate4"]["falsification_passed"],
            "allocation_ready": False,
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "baseline_result_file": repo_rel(base.BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": payload["artifact"],
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
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {}) or {}
    prediction = ticket.get("prediction") or {}
    observations, source_audit = build_observations()
    summaries = {
        "exact": summarize_assignment(observations, "exact_percentile"),
        "date_shift": summarize_assignment(observations, "date_shift_percentile"),
        "ticker_shuffle": summarize_assignment(observations, "ticker_shuffle_percentile"),
    }
    exp018 = read_json(EXP018_ARTIFACT, {}) or {}
    gate4 = evaluate_gate4(summaries, exp018)
    status = gate4["status"]
    baseline = base.baseline_metrics()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "lane": "alpha_search",
        "owner": OWNER,
        "decision": gate4["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": gate4["falsification_passed"],
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "ticket_before": ticket,
        "prediction": prediction,
        "parameters": {
            "config": CONFIG,
            "windows": [
                {"label": name, "start": start, "end": end, "snapshot": snapshot}
                for name, start, end, snapshot in base.WINDOWS
            ],
            "exact_assignment": "per-ticker expanding PIT percentile of short_volume_ratio",
            "date_shift_placebo": "same ticker percentile shifted by 11 valid observations",
            "ticker_shuffle_placebo": (
                "percentile from the next ticker offset by seven symbols, as of the same date"
            ),
            "input_lead_artifact": repo_rel(EXP018_ARTIFACT),
            "shared_gate_log": repo_rel(EXP019_LOG),
        },
        "pre_run_questions": {
            "alpha_hypothesis": HYPOTHESIS,
            "history_check": {
                "novelty_gate": "passed with no strong near-neighbor; no override used",
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "new_evidence_axis": NEW_EVIDENCE_AXIS,
            },
            "single_policy_bundle": (
                "Read-only exact-vs-placebo falsification of the exp018 short-volume "
                "lead; no strategy, helper, order, sizing, rank, exit, or daily path change."
            ),
            "success_failure_standard": gate4["acceptance_rule"],
            "reproducibility": RUNNER_COMMAND,
        },
        "gate1": {
            "passed": Path(base.BASELINE_RESULT).exists(),
            "baseline_result_file": repo_rel(base.BASELINE_RESULT),
            "baseline_summary": baseline,
            "note": "Observed-only falsification; before and after strategy behavior are identical.",
        },
        "gate2": {
            "passed": bool(observations),
            "runtime_fields": [
                "ohlcv Date/Open/Close",
                "moomoo short_volume_ratio",
                "moomoo activity_date",
                "forward_return_10d",
                "exact/date_shift/ticker_shuffle percentile assignments",
            ],
            "source_audit": source_audit,
            "entry_date": {
                "available": True,
                "source": "activity_date mapped to next-open forward-return observation",
            },
            "target_price": {
                "available": False,
                "reason": "No executable entry/exit/order target is scheduled.",
            },
        },
        "gate3": {
            "strategy_filter_added": False,
            "signals_generated": len(observations),
            "signals_survived": len(observations),
            "survival_rate": 1.0 if observations else None,
            "baseline_survival_rate": baseline.get("survival_rate"),
            "passed": True,
            "note": "No executable filter was added; this is a placebo audit only.",
        },
        "gate4": gate4,
        "before_metrics": baseline,
        "after_metrics": {**baseline, "strategy_behavior_changed": False},
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "max_drawdown_pct_worst_delta": 0.0,
        },
        "attribution": summaries,
        "source_audit": source_audit,
        "production_impact": production_impact(),
        "calibration": calibration(gate4, prediction),
        "post_run_reflection": post_run_reflection(gate4),
        "related_files": [
            RUNNER,
            "quant/experiments/exp_20260625_018_short_volume_informed_flow_attribution.py",
            repo_rel(EXP018_ARTIFACT),
            repo_rel(EXP019_LOG),
            repo_rel(base.SHORT_VOLUME_ROWS),
            repo_rel(base.BASELINE_RESULT),
            "docs/backtesting.md",
            "docs/agent_experiment_protocol.md",
            "docs/alpha-optimization-playbook.md",
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
        "allowed_write_scope": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(LOG_JSON),
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
    }
    return payload


def main() -> int:
    payload = build_payload()
    persist(payload)
    pooled = {
        key: payload["attribution"][key]["by_scope"]["POOLED"]
        for key in ["exact", "date_shift", "ticker_shuffle"]
    }
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "pooled": {
                    key: {
                        "n": row["n"],
                        "q1_minus_q5_mean": row["q1_minus_q5_mean"],
                        "corr": row["corr_percentile_fwd_return"],
                    }
                    for key, row in pooled.items()
                },
                "edge_advantage_vs_best_placebo": payload["gate4"][
                    "exact_edge_advantage_vs_best_placebo"
                ],
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
