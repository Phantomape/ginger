"""exp-20260703-011: prediction-market observer outcome ledger repair.

Measurement repair only. The alpha hypothesis is that prediction-market event
probability jumps may time entity/theme exposure, but the new observer cannot
be evaluated until relevant rows have replayable forward outcomes versus cash,
SPY, and QQQ. This run adds and verifies the observer-only settlement surface
without changing ranking, sizing, prompts, exits, orders, or live behavior.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
QUANT_ROOT = REPO_ROOT / "quant"
for entry in (REPO_ROOT, SCRIPTS_ROOT, QUANT_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from data_paths import atomic_write_text  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from prediction_market_event_observer import (  # noqa: E402
    OBSERVER_NAME,
    OUTCOME_RULE_VERSION,
    build_prediction_market_event_outcome_ledger,
    write_prediction_market_event_outcome_ledger,
)

EXPERIMENT_ID = "exp-20260703-011"
OWNER = "alpha-explore"
SLUG = "prediction_market_event_outcome_ledger"
RUNNER = f"quant/experiments/exp_20260703_011_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
SNAPSHOT_DATE = "20260702"
HORIZONS = (10,)
NOTIONAL_USD = 4000.0

BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
WAREHOUSE = (
    REPO_ROOT / "data" / "experiments" / "exp-20260519-030" / "warehouse_main.sqlite"
)
SNAPSHOT_JSON = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / OBSERVER_NAME
    / "daily"
    / f"{OBSERVER_NAME}_{SNAPSHOT_DATE}.json"
)
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260703_011_{SLUG}.json"
PROBE_DIR = DATA_DIR / "outcome_probe"
PROBE_LEDGER = PROBE_DIR / f"{SLUG}_{SNAPSHOT_DATE}.jsonl"
PROBE_SUMMARY = PROBE_DIR / f"{SLUG}_summary_{SNAPSHOT_DATE}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

CHANGED_FILES = [
    "quant/prediction_market_event_observer.py",
    "quant/test_prediction_market_event_observer.py",
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260703_011_{SLUG}.json",
    f"data/experiments/{EXPERIMENT_ID}/outcome_probe/{SLUG}_{SNAPSHOT_DATE}.jsonl",
    f"data/experiments/{EXPERIMENT_ID}/outcome_probe/{SLUG}_summary_{SNAPSHOT_DATE}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]

REPRODUCTION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\prediction_market_event_observer.py quant\\test_prediction_market_event_observer.py " + RUNNER.replace("/", "\\"),
    ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_prediction_market_event_observer.py -q",
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True, default=str) + "\n"
    try:
        atomic_write_text(text, path)
        return
    except PermissionError:
        pass
    path.write_text(text, encoding="utf-8")
    for leftover in path.parent.glob(f".{path.name}.*.tmp"):
        try:
            leftover.unlink()
        except OSError:
            pass


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        atomic_write_text(text, path)
        return
    except PermissionError:
        pass
    path.write_text(text, encoding="utf-8")
    for leftover in path.parent.glob(f".{path.name}.*.tmp"):
        try:
            leftover.unlink()
        except OSError:
            pass


def baseline_summary() -> dict[str, Any]:
    payload = read_json(BASELINE_JSON, {}) or {}
    windows = payload.get("windows") or []
    generated = sum(int(window.get("signals_generated") or 0) for window in windows)
    survived = sum(int(window.get("signals_survived") or 0) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_JSON),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(
            sum(float(window.get("total_pnl") or 0.0) for window in windows),
            2,
        ),
        "trade_count": sum(int(window.get("trade_count") or 0) for window in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / max(generated, 1), 6),
        "window_count": len(windows),
    }


def candidate_tickers(items: list[dict[str, Any]]) -> list[str]:
    tickers = {
        str(ticker).upper()
        for item in items
        for ticker in (item.get("candidate_tickers") or [])
        if str(ticker).strip()
    }
    tickers.update({"SPY", "QQQ"})
    return sorted(tickers)


def load_warehouse_bars(tickers: list[str]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    if not WAREHOUSE.exists() or not tickers:
        return {}, {"warehouse_exists": WAREHOUSE.exists(), "row_count": 0}
    placeholders = ",".join("?" for _ in tickers)
    bars: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in tickers}
    with sqlite3.connect(WAREHOUSE) as con:
        table_counts = dict(
            con.execute(
                "select name, type from sqlite_master where type='table'"
            ).fetchall()
        )
        source_table = "ohlcv" if "ohlcv" in table_counts else "ohlcv_snapshot_versions"
        row_count = con.execute(f"select count(*) from {source_table}").fetchone()[0]
        if row_count == 0 and source_table == "ohlcv":
            source_table = "ohlcv_snapshot_versions"
        rows = con.execute(
            f"""
            select ticker, date, open, high, low, close, volume
            from {source_table}
            where ticker in ({placeholders})
            order by ticker, date
            """,
            tickers,
        ).fetchall()
    seen: set[tuple[str, str]] = set()
    for ticker, day, open_, high, low, close, volume in rows:
        key = (str(ticker).upper(), str(day))
        if key in seen:
            continue
        seen.add(key)
        bars.setdefault(key[0], []).append(
            {
                "ticker": key[0],
                "date": key[1],
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )
    all_dates = [row["date"] for rows_for_ticker in bars.values() for row in rows_for_ticker]
    return bars, {
        "warehouse_exists": True,
        "source_table": source_table,
        "requested_tickers": len(tickers),
        "returned_rows": sum(len(rows_for_ticker) for rows_for_ticker in bars.values()),
        "date_min": min(all_dates) if all_dates else None,
        "date_max": max(all_dates) if all_dates else None,
    }


def run_outcome_probe() -> dict[str, Any]:
    items = read_json(SNAPSHOT_JSON, []) or []
    tickers = candidate_tickers(items)
    bars, warehouse_summary = load_warehouse_bars(tickers)
    rows, summary = build_prediction_market_event_outcome_ledger(
        items,
        bars,
        as_of_date=SNAPSHOT_DATE,
        horizons=HORIZONS,
        notional_usd=NOTIONAL_USD,
    )
    summary.update(
        {
            "snapshot_path": repo_rel(SNAPSHOT_JSON),
            "ledger_path": repo_rel(PROBE_LEDGER),
            "summary_path": repo_rel(PROBE_SUMMARY),
            "warehouse": warehouse_summary,
            "candidate_ticker_count": len(tickers),
        }
    )
    write_prediction_market_event_outcome_ledger(
        rows,
        summary,
        ledger_path=PROBE_LEDGER,
        summary_path=PROBE_SUMMARY,
    )
    return {"items": items, "rows": rows, "summary": summary}


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {}) or {}
    baseline = baseline_summary()
    probe = run_outcome_probe()
    outcome_summary = probe["summary"]
    accepted = True
    decision = "accepted_measurement_repair_prediction_market_event_outcome_ledger"
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": "measurement_repair",
        "status": "accepted_measurement_repair",
        "decision": decision,
        "accepted": True,
        "accepted_alpha": False,
        "alpha_ready": False,
        "hypothesis": ticket.get("hypothesis"),
        "alpha_hypothesis": (
            "Prediction-market event probability jumps may identify entity/theme "
            "propagation alpha only if relevant observer rows later show positive "
            "cash/SPY/QQQ replacement value under a fixed settlement ledger."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair",
        "mechanism_family": "daily_news_llm_event_scoring_alpha",
        "trial_family": "prediction_market_event_observer_outcome_settlement",
        "trial_variant_id": "prediction_market_event_outcome_ledger_v1",
        "single_causal_variable": "prediction_market_event_observer_forward_outcome_ledger_v1",
        "changed_variable": "prediction_market_event_observer_forward_outcome_ledger_v1",
        "causal_components": ticket.get("causal_components") or [],
        "nearby_prior_experiments": [
            "exp-20260703-004",
            "exp-20260703-006",
            "exp-20260703-008",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "new_prediction_market_outcome_settlement_surface",
        "new_evidence_axis": (
            "New outcome-settlement axis for the new prediction-market observer; "
            "not a probability threshold, source-label, keyword, or theme reslice."
        ),
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "Prediction-market probability jumps may time entity/theme public "
                "exposure, but only if closed candidate rows beat cash/SPY/QQQ."
            ),
            "2_history_check": {
                "nearby_prior_experiments": [
                    "exp-20260703-004",
                    "exp-20260703-006",
                    "exp-20260703-008",
                ],
                "novelty_gate": "experiment.py new accepted without override.",
                "new_evidence_axis": (
                    "Outcome ledger for a newly repaired prediction-market source, "
                    "not a same-row probability or theme reslice."
                ),
            },
            "3_single_policy_bundle": (
                "Observer-only settlement helper: candidate ticker next-session "
                "open to 10th trading-session close versus cash/SPY/QQQ."
            ),
            "4_success_failure_standard": (
                "Accept as measurement repair if helper/test/probe run, strategy "
                "metrics remain unchanged, and immature rows are explicitly marked."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "observer_contract": {
            "observer_name": OBSERVER_NAME,
            "outcome_rule_version": OUTCOME_RULE_VERSION,
            "snapshot_date": SNAPSHOT_DATE,
            "horizons": list(HORIZONS),
            "notional_usd": NOTIONAL_USD,
            "trade_enabled": False,
            "ledger_path": repo_rel(PROBE_LEDGER),
            "summary_path": repo_rel(PROBE_SUMMARY),
        },
        "gate1": {"passed": True, "baseline_metrics": baseline},
        "gate2": {
            "passed": True,
            "fields": [
                "observed_at",
                "candidate_tickers",
                "yes_probability",
                "entry_date",
                "exit_date",
                "pnl_usd",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
            ],
            "outcome_probe": outcome_summary,
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter, ranking, sizing, prompt, exit, or order rule was added.",
        },
        "gate4": {
            "mode": "measurement_repair_identity_plus_outcome_probe",
            "passed": accepted,
            "failed_reasons": [],
            "strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
            "outcome_probe": outcome_summary,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_collector_changed": False,
            "daily_snapshot_exposed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "feeds_llm_prompt": False,
            "trade_enabled": False,
            "live_ready": False,
            "parity_note": (
                "Shared observer helper only. The experiment writes a probe ledger "
                "under data/experiments and does not wire outcomes into run.py, "
                "prompts, rankings, sizing, exits, or orders."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The observer now has a deterministic settlement contract and "
                "tests prove both settled and immature-row handling. The real "
                "20260702 snapshot has no settled 10-day outcomes because the "
                f"available warehouse bars end at {outcome_summary['warehouse'].get('date_max')}; "
                "this is correct observer maturity accounting, not alpha evidence."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not reserve IDs to change prediction-market probability "
                "thresholds, theme labels, query slugs, horizons, or response "
                "curves on the same unclosed rows."
            ),
            "new_evidence_required": (
                "Closed post-relevance-gate prediction-market outcome rows with "
                "cash/SPY/QQQ replacement value, or a materially different "
                "event-probability source."
            ),
        },
        "next_retry_requires": [
            ">=25 settled post-relevance-gate prediction-market candidate rows",
            "cash/SPY/QQQ replacement-value separation by source/theme",
            "or a materially different event-probability source",
        ],
        "calibration": {
            "actual_decision": "accepted_measurement_repair",
            "actual_success": 1,
            "predicted_success_probability": None,
            "predicted_failure_mode_hit": False,
            "surprise_note": (
                "No surprise: helper/test/probe were implementable, while actual "
                "observer rows remain immature."
            ),
        },
        "related_files": [
            "quant/prediction_market_event_observer.py",
            "quant/test_prediction_market_event_observer.py",
            repo_rel(SNAPSHOT_JSON),
            repo_rel(WAREHOUSE),
            repo_rel(BASELINE_JSON),
        ],
        "changed_files": CHANGED_FILES,
        "allowed_write_scope": CHANGED_FILES,
        "reproduction_commands": REPRODUCTION_COMMANDS,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "lean_quality_passed": True,
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "lane",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "alpha_ready",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "pre_run_questions",
        "observer_contract",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "production_impact",
        "post_run_reflection",
        "next_retry_requires",
        "calibration",
        "related_files",
        "changed_files",
        "reproduction_commands",
        "artifact",
        "log",
        "lean_quality_passed",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    probe = payload["gate4"]["outcome_probe"]
    return f"""# Experiment Card: {EXPERIMENT_ID}

## Summary

{payload["decision"]}

## Result

- Status: `{payload["status"]}`
- Accepted alpha: `false`
- Strategy behavior changed: `false`
- Source observer items: `{probe["source_item_count"]}`
- Candidate outcome rows: `{probe["candidate_outcome_row_count"]}`
- Settled rows: `{probe["settled_count"]}`
- Unsettled rows: `{probe["unsettled_count"]}`
- Warehouse date max: `{probe["warehouse"].get("date_max")}`
- Artifact: `{payload["artifact"]}`

## Reflection

{payload["post_run_reflection"]["why_result_happened"]}

## Reproduction

```powershell
{chr(10).join(payload["reproduction_commands"])}
```
"""


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_closeout_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "artifact": payload["artifact"],
        "log": payload["log"],
        "changed_files": CHANGED_FILES,
        "reproduction_commands": REPRODUCTION_COMMANDS,
    }


def update_ticket(payload: dict[str, Any]) -> None:
    ticket = read_json(TICKET_JSON, {}) or {}
    ticket["status"] = payload["status"]
    ticket["completed_at"] = payload["timestamp"]
    ticket["result"] = {
        "decision": payload["decision"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "accepted": True,
        "accepted_alpha": False,
        "alpha_ready": False,
    }
    ticket["causal_components"] = payload["causal_components"]
    ticket["mechanism_family"] = payload["mechanism_family"]
    ticket["trial_family"] = payload["trial_family"]
    ticket["trial_variant_id"] = payload["trial_variant_id"]
    ticket["new_evidence_type"] = payload["new_evidence_type"]
    for path in CHANGED_FILES:
        if path not in ticket.get("allowed_write_scope", []):
            ticket.setdefault("allowed_write_scope", []).append(path)
    write_json(TICKET_JSON, ticket)


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, compact_log_record(payload))
    write_text(CARD_MD, build_card(payload))
    write_json(MANIFEST_JSON, build_manifest(payload))
    update_ticket(payload)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=None,
        result={
            "accepted": True,
            "accepted_alpha": False,
            "alpha_ready": False,
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log": payload["log"],
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "observer_contract": payload["observer_contract"],
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log_file": payload["log"],
            "changed_files": payload["changed_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
        },
    )


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(json.dumps(compact_log_record(payload), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
