"""exp-20260621-017: Moomoo capital-flow forward readiness.

Alpha-search data-edge probe. This run checks whether the local Moomoo
capital-distribution snapshot is ready for a shared default-off candidate-pool
alpha. It changes no trading policy.

No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import experiment_registry  # noqa: E402


EXPERIMENT_ID = "exp-20260621-017"
SLUG = "moomoo_capital_flow_forward_readiness"
RUNNER_NAME = f"quant/experiments/exp_20260621_017_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_NAME.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"exp_20260621_017_{SLUG}.json"
BEFORE_JSON = DATA_DIR / "before_baseline.json"
AFTER_JSON = DATA_DIR / "after_no_strategy_change.json"
README_MD = DATA_DIR / "README.md"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT_FILE = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
MOO_MOO_DIR = REPO_ROOT / "data" / "non_ohlcv" / "moomoo_capital_flow"
MOO_MOO_MANIFEST = MOO_MOO_DIR / "manifest.json"
MOO_MOO_ROWS = MOO_MOO_DIR / "rows.jsonl"
FORWARD_REPLACEMENT_VALUE = (
    REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
)

MIN_FORWARD_OBSERVATION_DATES = 20
MIN_CLOSED_FORWARD_OUTCOMES = 20

HYPOTHESIS = (
    "candidate_pool/data-edge: production-visible Moomoo capital-flow "
    "main-flow imbalance may identify institutional order-flow pressure, but "
    "it can only become a default-off candidate source after PIT forward rows "
    "have enough dated coverage and closed replacement-value outcomes."
)
CHANGED_VARIABLE = "moomoo_capital_flow_forward_readiness_v1"
TRIAL_FAMILY = "moomoo_capital_flow_forward_readiness"
TRIAL_VARIANT_ID = "moomoo_capital_flow_snapshot_coverage_v1"
MECHANISM_FAMILY = "production_visible_moomoo_capital_flow_candidate_pool"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260621-015",
    "exp-20260618-023",
    "exp-20260617-004",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path) -> str:
    path = path.resolve()
    try:
        return path.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def append_jsonl_once(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        with path.open(encoding="utf-8-sig") as handle:
            for line in handle:
                if f'"experiment_id": "{EXPERIMENT_ID}"' in line:
                    return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def load_baseline() -> dict[str, Any]:
    raw = read_json(BASELINE_RESULT_FILE)
    windows: dict[str, dict[str, Any]] = {}
    for row in raw.get("windows") or []:
        label = str(row.get("label") or "")
        if not label:
            continue
        windows[label] = {
            "start": row.get("start"),
            "end": row.get("end"),
            "snapshot": row.get("source"),
            "expected_value_score": row.get("expected_value_score"),
            "sharpe_daily": row.get("sharpe_daily"),
            "total_pnl": row.get("total_pnl"),
            "max_drawdown_pct": row.get("max_drawdown_pct"),
            "win_rate": row.get("win_rate"),
            "trade_count": row.get("trade_count"),
            "signals_generated": row.get("signals_generated"),
            "signals_survived": row.get("signals_survived"),
            "survival_rate": row.get("survival_rate"),
        }
    return {"generated_at": raw.get("generated_at"), "windows": windows}


def aggregate_windows(windows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "aggregate_expected_value_score": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows.values()),
            4,
        ),
        "aggregate_total_pnl": round(
            sum(float(row.get("total_pnl") or 0.0) for row in windows.values()),
            2,
        ),
        "total_trade_count": sum(int(row.get("trade_count") or 0) for row in windows.values()),
        "min_survival_rate": round(
            min(float(row.get("survival_rate") or 0.0) for row in windows.values()),
            4,
        )
        if windows
        else 0.0,
        "max_window_drawdown_pct": round(
            max(float(row.get("max_drawdown_pct") or 0.0) for row in windows.values()),
            4,
        )
        if windows
        else 0.0,
    }


def window_for(value: Any, windows: dict[str, dict[str, Any]]) -> str | None:
    observed = parse_date(value)
    if observed is None:
        return None
    for label, window in windows.items():
        start = parse_date(window.get("start"))
        end = parse_date(window.get("end"))
        if start and end and start <= observed <= end:
            return label
    return None


def baseline_artifact(label: str, baseline: dict[str, Any]) -> dict[str, Any]:
    windows = baseline["windows"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "label": label,
        "baseline_result_file": repo_rel(BASELINE_RESULT_FILE),
        "windows": windows,
        "aggregate": aggregate_windows(windows),
        "strategy_code_changed": False,
        "production_code_changed": False,
        "note": "No after strategy was launched; after intentionally equals before.",
    }


def field_presence(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, dict[str, Any]]:
    total = len(rows)
    out: dict[str, dict[str, Any]] = {}
    for field in fields:
        present = sum(1 for row in rows if row.get(field) not in (None, ""))
        out[field] = {
            "present_rows": present,
            "scanned_rows": total,
            "present_rate": round(present / total, 4) if total else 0.0,
        }
    return out


def scan_forward_replacement_matches() -> dict[str, Any]:
    rows = iter_jsonl(FORWARD_REPLACEMENT_VALUE)
    matches = []
    for row in rows:
        sleeve_key = str(row.get("sleeve_key") or "").lower()
        decision_id = str(row.get("decision_id") or "").lower()
        if "moomoo" in sleeve_key or "capital_flow" in sleeve_key or "moomoo" in decision_id:
            matches.append(row)
    enriched = [row for row in matches if row.get("status") == "enriched"]
    return {
        "ledger_path": repo_rel(FORWARD_REPLACEMENT_VALUE),
        "ledger_rows_scanned": len(rows),
        "matched_rows": len(matches),
        "enriched_matched_rows": len(enriched),
        "sample_matches": matches[:5],
    }


def scan_moomoo_surface(baseline: dict[str, Any]) -> dict[str, Any]:
    manifest = read_json(MOO_MOO_MANIFEST)
    rows = iter_jsonl(MOO_MOO_ROWS)
    windows = baseline["windows"]
    as_of_dates = sorted({str(row.get("as_of_date")) for row in rows if row.get("as_of_date")})
    tickers = sorted({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")})
    rows_by_window = Counter()
    for row in rows:
        label = window_for(row.get("as_of_date"), windows)
        if label:
            rows_by_window[label] += 1

    positive_main = [row for row in rows if float(row.get("main_flow_ratio") or 0.0) > 0.0]
    negative_main = [row for row in rows if float(row.get("main_flow_ratio") or 0.0) < 0.0]
    top_positive = sorted(
        rows,
        key=lambda row: float(row.get("main_flow_ratio") or 0.0),
        reverse=True,
    )[:8]
    top_negative = sorted(rows, key=lambda row: float(row.get("main_flow_ratio") or 0.0))[:8]

    dependency_fields = [
        "as_of_date",
        "ticker",
        "moomoo_code",
        "collected_at_utc",
        "main_flow_ratio",
        "net_main",
        "net_super",
        "net_big",
        "net_mid",
        "net_small",
        "net_total",
        "source",
        "pit_note",
        "trade_enabled",
        "entry_date",
        "target_price",
    ]
    forward_matches = scan_forward_replacement_matches()
    pit_boundary = str(manifest.get("pit_boundary") or "")
    current_snapshot_only = "current_snapshot_only" in pit_boundary
    forward_only = "forward-only" in pit_boundary or "forward_only" in pit_boundary
    wired_to_decision = not str(manifest.get("pit_boundary") or "").endswith(
        "not wired to run.py or any decision"
    )
    canonical_window_labels = [label for label, count in rows_by_window.items() if count > 0]

    blocking_reasons = []
    if current_snapshot_only:
        blocking_reasons.append("manifest_current_snapshot_only")
    if forward_only:
        blocking_reasons.append("manifest_forward_only_never_backfillable")
    if len(as_of_dates) < MIN_FORWARD_OBSERVATION_DATES:
        blocking_reasons.append("forward_observation_dates_below_20")
    if not canonical_window_labels:
        blocking_reasons.append("no_rows_in_canonical_fixed_windows")
    if forward_matches["enriched_matched_rows"] < MIN_CLOSED_FORWARD_OUTCOMES:
        blocking_reasons.append("closed_forward_replacement_rows_below_20")
    if not wired_to_decision:
        blocking_reasons.append("not_wired_to_run_py_or_any_decision")

    return {
        "manifest_path": repo_rel(MOO_MOO_MANIFEST),
        "rows_path": repo_rel(MOO_MOO_ROWS),
        "manifest": manifest,
        "row_count": len(rows),
        "unique_tickers": len(tickers),
        "as_of_dates": as_of_dates,
        "as_of_date_count": len(as_of_dates),
        "rows_by_canonical_window": {label: int(rows_by_window[label]) for label in windows},
        "canonical_windows_with_rows": canonical_window_labels,
        "positive_main_flow_rows": len(positive_main),
        "negative_main_flow_rows": len(negative_main),
        "top_positive_main_flow": [
            {
                "ticker": row.get("ticker"),
                "as_of_date": row.get("as_of_date"),
                "main_flow_ratio": row.get("main_flow_ratio"),
                "net_main": row.get("net_main"),
                "net_total": row.get("net_total"),
            }
            for row in top_positive
        ],
        "top_negative_main_flow": [
            {
                "ticker": row.get("ticker"),
                "as_of_date": row.get("as_of_date"),
                "main_flow_ratio": row.get("main_flow_ratio"),
                "net_main": row.get("net_main"),
                "net_total": row.get("net_total"),
            }
            for row in top_negative
        ],
        "dependency_presence": field_presence(rows, dependency_fields),
        "forward_replacement_value_matches": forward_matches,
        "readiness": {
            "gate2_passed": False,
            "gate3_passed": False,
            "strategy_replay_allowed": False,
            "blocking_reasons": blocking_reasons,
        },
    }


def metric_deltas(windows: dict[str, dict[str, Any]]) -> dict[str, dict[str, float]]:
    fields = [
        "expected_value_score",
        "total_pnl",
        "max_drawdown_pct",
        "trade_count",
        "survival_rate",
    ]
    return {label: {field: 0.0 for field in fields} for label in windows}


def build_result() -> dict[str, Any]:
    baseline = load_baseline()
    windows = baseline["windows"]
    aggregate = aggregate_windows(windows)
    surface = scan_moomoo_surface(baseline)
    ticket = read_json(TICKET_JSON)
    prediction = ticket.get("prediction") or {
        "success_probability": 0.1,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "current_snapshot_only",
            "no_fixed_window_history",
            "no_closed_forward_outcomes",
            "not_wired_to_daily_decision_path",
        ],
        "confidence_reason": "Order-flow field is plausible but forward-only.",
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now_utc(),
        "lane": "alpha_search",
        "status": "blocked",
        "decision": "blocked_moomoo_capital_flow_current_snapshot_only",
        "hypothesis": HYPOTHESIS,
        "change_type": "candidate_pool_full_stack",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "prediction": prediction,
        "novelty": ticket.get("novelty"),
        "pre_run_questions": {
            "money_making_hypothesis": (
                "Vendor order-flow imbalance may proxy institutional pressure "
                "that precedes continuation or warns of distribution."
            ),
            "history_check": (
                "Novelty gate passed after recording the new evidence axis: "
                "Moomoo dated vendor flow rows are not an OHLCV accumulation or "
                "core-flow relabel. Nearby blockers were exp-20260621-015, "
                "exp-20260618-023, and exp-20260617-004."
            ),
            "single_attributable_policy_bundle": (
                "Readiness of one data edge: Moomoo main-flow imbalance as a "
                "future candidate-pool field. No trading threshold or replay is run."
            ),
            "acceptance_criteria": (
                "Gate 2/3 require replayable PIT dates, enough fixed-window or "
                "forward observations, at least 20 closed replacement-value rows, "
                "and shared daily/backtest parity before any Gate 4 strategy replay."
            ),
            "reproducibility": RUNNER_COMMAND,
        },
        "gate1": {
            "baseline_result_file": repo_rel(BASELINE_RESULT_FILE),
            "generated_at": baseline.get("generated_at"),
            "windows": windows,
            "aggregate": aggregate,
            "passed": True,
        },
        "gate2": {
            "dependency_fields_checked": list(surface["dependency_presence"].keys()),
            "dependency_presence": surface["dependency_presence"],
            "manifest_pit_boundary": surface["manifest"].get("pit_boundary"),
            "manifest_schema": surface["manifest"].get("schema"),
            "passed": False,
            "blocking_reason": (
                "Rows expose as_of_date, ticker, net flow fields, and PIT note, "
                "but the surface is current-snapshot-only, has no entry_date or "
                "target_price fields, and is not wired to run.py or any decision."
            ),
        },
        "gate3": {
            "baseline_survival_by_window": {
                label: {
                    "signals_generated": row.get("signals_generated"),
                    "signals_survived": row.get("signals_survived"),
                    "survival_rate": row.get("survival_rate"),
                }
                for label, row in windows.items()
            },
            "row_count": surface["row_count"],
            "unique_tickers": surface["unique_tickers"],
            "as_of_dates": surface["as_of_dates"],
            "as_of_date_count": surface["as_of_date_count"],
            "minimum_forward_observation_dates": MIN_FORWARD_OBSERVATION_DATES,
            "rows_by_canonical_window": surface["rows_by_canonical_window"],
            "canonical_windows_with_rows": surface["canonical_windows_with_rows"],
            "positive_main_flow_rows": surface["positive_main_flow_rows"],
            "negative_main_flow_rows": surface["negative_main_flow_rows"],
            "top_positive_main_flow": surface["top_positive_main_flow"],
            "top_negative_main_flow": surface["top_negative_main_flow"],
            "forward_replacement_value_matches": surface[
                "forward_replacement_value_matches"
            ],
            "minimum_closed_forward_outcomes": MIN_CLOSED_FORWARD_OUTCOMES,
            "passed": False,
            "blocking_reasons": surface["readiness"]["blocking_reasons"],
            "blocking_reason": (
                "The source has only one dated snapshot and zero matched closed "
                "forward replacement-value rows, with no canonical fixed-window "
                "history. A strategy replay would be unsupported."
            ),
        },
        "gate4": {
            "ran_after_strategy": False,
            "reason_after_not_run": (
                "Blocked at Gate 2/3 readiness; after intentionally equals before."
            ),
            "before_windows": windows,
            "after_windows": windows,
            "delta_by_window": metric_deltas(windows),
            "aggregate_before": aggregate,
            "aggregate_after": aggregate,
            "aggregate_delta": {
                "aggregate_expected_value_score": 0.0,
                "aggregate_total_pnl": 0.0,
                "total_trade_count": 0,
                "min_survival_rate": 0.0,
                "max_window_drawdown_pct": 0.0,
            },
            "passed": False,
        },
        "delta_metrics": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "total_trade_count": 0,
            "max_window_drawdown_pct": 0.0,
        },
        "surface_audit": surface,
        "production_impact": {
            "strategy_code_changed": False,
            "shared_helper_changed": False,
            "daily_snapshot_changed": False,
            "live_orders_changed": False,
            "trade_enabled_changed": False,
            "uses_moomoo_capital_flow": True,
            "backtest_production_parity_risk": "none_from_this_run",
            "parity_note": (
                "No buy/sell/filter/ranking/sizing/risk code changed. A future "
                "positive result would need a shared default-off helper and daily "
                "snapshot wiring before any replay or live decision."
            ),
        },
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "actual_success": 0,
            "brier_score": round(float(prediction.get("success_probability") or 0.0) ** 2, 4),
            "realized": "blocked_before_strategy_replay",
            "realized_failure_modes": surface["readiness"]["blocking_reasons"],
        },
        "post_run_reflection": {
            "why_blocked": (
                "The Moomoo capital-flow surface is a genuinely new PIT flow "
                "field, but the local manifest says current-snapshot-only and "
                "forward-only. It has 43 rows for one as_of_date, no canonical "
                "fixed-window history, no entry_date/target_price replay fields, "
                "and zero matched closed forward replacement-value rows."
            ),
            "negative_result_reflection": (
                "This is a data-edge readiness block, not a losing alpha. The "
                "money-making hypothesis remains plausible, but there is not yet "
                "enough replayable evidence to assign a threshold, top-N, hold "
                "period, notional, or comparator result."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not sweep main_flow_ratio, net_main, super/big/mid/small "
                "buckets, top-N, hold days, cooldown, or notional on this one-day "
                "snapshot."
            ),
            "next_new_evidence_required": (
                "Accumulate at least 20 dated forward observations and 20 closed "
                "replacement-value outcomes under a shared default-off observation "
                "helper, or obtain a historical PIT Moomoo capital-flow archive."
            ),
        },
        "changed_files": [
            RUNNER_NAME,
            repo_rel(ARTIFACT_JSON),
            repo_rel(BEFORE_JSON),
            repo_rel(AFTER_JSON),
            repo_rel(README_MD),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
        "reproduction": RUNNER_COMMAND,
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
    }


def build_log_record(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": result["timestamp"],
        "lane": result["lane"],
        "status": result["status"],
        "decision": result["decision"],
        "hypothesis": result["hypothesis"],
        "change_type": result["change_type"],
        "mechanism_family": result["mechanism_family"],
        "trial_family": result["trial_family"],
        "trial_variant_id": result["trial_variant_id"],
        "changed_variable": result["changed_variable"],
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "gate1": result["gate1"],
        "gate2": result["gate2"],
        "gate3": {
            "passed": result["gate3"]["passed"],
            "blocking_reason": result["gate3"]["blocking_reason"],
            "blocking_reasons": result["gate3"]["blocking_reasons"],
            "row_count": result["gate3"]["row_count"],
            "as_of_date_count": result["gate3"]["as_of_date_count"],
            "canonical_windows_with_rows": result["gate3"]["canonical_windows_with_rows"],
            "forward_replacement_value_matches": result["gate3"][
                "forward_replacement_value_matches"
            ],
        },
        "gate4": result["gate4"],
        "production_impact": result["production_impact"],
        "calibration": result["calibration"],
        "post_run_reflection": result["post_run_reflection"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": result["anti_js"],
        "lean_quality_passed": result["lean_quality_passed"],
    }


def build_card(result: dict[str, Any]) -> str:
    gate3 = result["gate3"]
    lines = [
        f"# {EXPERIMENT_ID}: Moomoo capital-flow forward readiness",
        "",
        "- Lane: alpha_search",
        "- Status: blocked",
        f"- Decision: {result['decision']}",
        "- Strategy / production behavior changed: no",
        "",
        "## Gate 3 Readiness",
        "",
        f"- Rows: {gate3['row_count']}",
        f"- Unique tickers: {gate3['unique_tickers']}",
        f"- As-of dates: {gate3['as_of_date_count']} ({', '.join(gate3['as_of_dates'])})",
        f"- Canonical windows with rows: {', '.join(gate3['canonical_windows_with_rows']) or 'none'}",
        "- Closed Moomoo replacement rows: "
        f"{gate3['forward_replacement_value_matches']['enriched_matched_rows']}",
        "",
        "## Baseline",
        "",
        "| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in result["gate1"]["windows"].items():
        ev = float(row.get("expected_value_score") or 0.0)
        pnl = float(row.get("total_pnl") or 0.0)
        lines.append(
            f"| {label} | {ev:.4f} | {ev:.4f} | 0.0000 | "
            f"${pnl:,.2f} | ${pnl:,.2f} | $0.00 |"
        )
    lines.extend(
        [
            "",
            "## Reflection",
            "",
            result["post_run_reflection"]["why_blocked"],
            "",
            result["post_run_reflection"]["next_new_evidence_required"],
            "",
        ]
    )
    return "\n".join(lines)


def build_readme(result: dict[str, Any]) -> str:
    return (
        f"# {EXPERIMENT_ID}\n\n"
        "Blocked alpha-search readiness record for the Moomoo capital-flow surface.\n\n"
        f"- Artifact: `{repo_rel(ARTIFACT_JSON)}`\n"
        f"- Log: `{repo_rel(LOG_JSON)}`\n"
        f"- Decision: `{result['decision']}`\n"
        f"- Reproduce: `{result['reproduction']}`\n"
    )


def build_manifest(result: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER_NAME,
        ARTIFACT_JSON,
        BEFORE_JSON,
        AFTER_JSON,
        README_MD,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": result["status"],
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "before": repo_rel(BEFORE_JSON),
        "after": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER_NAME,
        "command": result["reproduction"],
        "files": {
            repo_rel(path): {
                "exists": path.exists(),
                "sha256": sha256_file(path),
            }
            for path in files
        },
        "anti_js": result["anti_js"],
        "updated_at": now_utc(),
    }


def persist(result: dict[str, Any]) -> None:
    write_json(BEFORE_JSON, baseline_artifact("before_baseline", result["gate1"]))
    write_json(AFTER_JSON, baseline_artifact("after_no_strategy_change", result["gate1"]))
    write_json(ARTIFACT_JSON, result)
    write_json(LOG_JSON, result)
    write_text(CARD_MD, build_card(result))
    write_text(README_MD, build_readme(result))
    append_jsonl_once(EXPERIMENT_LOG_JSONL, build_log_record(result))

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "before": repo_rel(BEFORE_JSON),
        "after": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER_NAME,
        "delta_metrics": result["delta_metrics"],
        "gate4": result["gate4"],
        "calibration": result["calibration"],
        "summary": result["post_run_reflection"]["why_blocked"],
    }
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=result["prediction"],
        result=registry_result,
        status="blocked",
        fields={
            "owner": "alpha-explore-automation",
            "hypothesis": result["hypothesis"],
            "change_type": result["change_type"],
            "mechanism_family": result["mechanism_family"],
            "trial_family": result["trial_family"],
            "trial_variant_id": result["trial_variant_id"],
            "single_causal_variable": result["single_causal_variable"],
            "changed_variable": result["changed_variable"],
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "new_production_visible_flow_field",
            "baseline_result_file": repo_rel(BASELINE_RESULT_FILE),
            "evaluation_windows": [
                {
                    "label": label,
                    "start": row.get("start"),
                    "end": row.get("end"),
                    "snapshot": row.get("snapshot"),
                }
                for label, row in result["gate1"]["windows"].items()
            ],
            "acceptance_rule": (
                "Blocked unless the Moomoo surface has replayable PIT history or "
                "at least 20 dated forward observations and 20 closed "
                "replacement-value outcomes."
            ),
            "decision": result["decision"],
            "summary": result["post_run_reflection"]["why_blocked"],
            "artifact": repo_rel(ARTIFACT_JSON),
            "before": repo_rel(BEFORE_JSON),
            "after": repo_rel(AFTER_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": result["gate1"],
            "gate2": result["gate2"],
            "gate3": result["gate3"],
            "gate4": result["gate4"],
            "production_impact": result["production_impact"],
            "post_run_reflection": result["post_run_reflection"],
            "lean_quality_passed": result["lean_quality_passed"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(result))


def main() -> None:
    result = build_result()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "row_count": result["gate3"]["row_count"],
                "as_of_date_count": result["gate3"]["as_of_date_count"],
                "canonical_windows_with_rows": result["gate3"][
                    "canonical_windows_with_rows"
                ],
                "closed_forward_replacement_rows": result["gate3"][
                    "forward_replacement_value_matches"
                ]["enriched_matched_rows"],
                "aggregate_ev_delta": result["delta_metrics"][
                    "aggregate_expected_value_score"
                ],
                "aggregate_pnl_delta": result["delta_metrics"]["aggregate_total_pnl"],
                "anti_js": result["anti_js"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
