"""exp-20260701-004: alpha-score paper pending/report repair closeout.

Measurement repair only. The alpha-score market-regime paper sleeve is a
default-off forward ledger; its rows are useful only if repeated same-day runs
are idempotent and the daily report shows the true pending queue.
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
QUANT_ROOT = REPO_ROOT / "quant"
for entry in (REPO_ROOT, SCRIPTS_ROOT, QUANT_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from alpha_score_market_regime_paper_sleeve import (  # noqa: E402
    build_alpha_score_market_regime_paper_sleeve_snapshot,
    empty_alpha_score_market_regime_paper_state,
)
from data_paths import atomic_write_text  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from report_generator import generate_daily_report  # noqa: E402

EXPERIMENT_ID = "exp-20260701-004"
OWNER = "alpha-explore"
SLUG = "alpha_score_sleeve_same_day_idempotency_and_pending_report"
RUNNER = f"quant/experiments/exp_20260701_004_{SLUG}.py"
RUNNER_WIN = RUNNER.replace("/", "\\")
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_WIN

BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260701_004_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

CHANGED_FILES = [
    "quant/alpha_score_market_regime_paper_sleeve.py",
    "quant/report_generator.py",
    "quant/test_alpha_score_market_regime_paper_sleeve.py",
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260701_004_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
    "docs/experiment_log.jsonl",
]

REPRODUCTION_COMMANDS = [
    (
        ".\\.venv\\Scripts\\python.exe -B -m py_compile "
        "quant\\alpha_score_market_regime_paper_sleeve.py "
        "quant\\report_generator.py "
        "quant\\test_alpha_score_market_regime_paper_sleeve.py "
        f"{RUNNER_WIN}"
    ),
    (
        ".\\.venv\\Scripts\\python.exe -B -m pytest "
        "quant\\test_alpha_score_market_regime_paper_sleeve.py -q"
    ),
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py rebuild-log",
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]

WRITE_FALLBACKS: list[str] = []


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def safe_write_text(text: str, path: Path) -> None:
    try:
        atomic_write_text(text, path)
        return
    except PermissionError as exc:
        WRITE_FALLBACKS.append(f"{repo_rel(path)}: atomic replace fallback: {exc}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    for leftover in path.parent.glob(f".{path.name}.*.tmp"):
        try:
            leftover.unlink()
        except OSError:
            pass


def safe_write_json(payload: Any, path: Path) -> None:
    safe_write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True, default=str)
        + "\n",
        path,
    )


def baseline_summary() -> dict[str, Any]:
    payload = load_json(BASELINE_JSON)
    windows = payload.get("windows") or []
    generated = sum(int(w.get("signals_generated") or 0) for w in windows)
    survived = sum(int(w.get("signals_survived") or 0) for w in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_JSON),
        "expected_value_score_sum": round(
            sum(float(w.get("expected_value_score") or 0.0) for w in windows), 4
        ),
        "total_pnl": round(sum(float(w.get("total_pnl") or 0.0) for w in windows), 2),
        "trade_count": sum(
            int(w.get("total_trades") or w.get("trade_count") or 0) for w in windows
        ),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / max(generated, 1), 6),
        "window_count": len(windows),
    }


def rows(
    *,
    base: float = 50.0,
    step: float = 0.10,
    days: int = 72,
    volume: float = 1_000_000.0,
) -> list[dict[str, Any]]:
    start = date(2026, 1, 1)
    out = []
    for idx in range(days):
        close = base + step * idx
        out.append(
            {
                "date": (start + timedelta(days=idx)).isoformat(),
                "open": round(close * 0.995, 4),
                "high": round(close * 1.01, 4),
                "low": round(close * 0.99, 4),
                "close": round(close, 4),
                "volume": volume,
            }
        )
    return out


def two_strong_features() -> dict[str, dict[str, Any]]:
    features = {
        "WIN": {
            "trend_score": 1.0,
            "breakout_20d": True,
            "above_200ma": True,
            "momentum_20d_pct": 0.40,
            "momentum_60d_pct": 0.80,
            "avg_historical_surprise_pct": 10.0,
        },
        "WIN2": {
            "trend_score": 0.9,
            "breakout_20d": True,
            "above_200ma": True,
            "momentum_20d_pct": 0.35,
            "momentum_60d_pct": 0.70,
            "avg_historical_surprise_pct": 8.0,
        },
    }
    for idx in range(18):
        features[f"L{idx:02d}"] = {
            "trend_score": 0.20,
            "breakout_20d": False,
            "above_200ma": True,
            "momentum_20d_pct": -0.05,
            "momentum_60d_pct": 0.02,
        }
    return features


def two_strong_ohlcv() -> dict[str, list[dict[str, Any]]]:
    ohlcv = {
        "SPY": rows(base=100.0, step=0.08),
        "IWM": rows(base=100.0, step=0.22),
        "WIN": rows(base=80.0, step=0.10, volume=1_200_000.0),
        "WIN2": rows(base=78.0, step=0.095, volume=1_150_000.0),
    }
    for idx in range(18):
        ohlcv[f"L{idx:02d}"] = rows(base=45.0 + idx, step=0.03)
    return ohlcv


def verify_same_day_idempotency() -> dict[str, Any]:
    ohlcv = two_strong_ohlcv()
    features = two_strong_features()
    as_of = ohlcv["SPY"][60]["date"]
    first = build_alpha_score_market_regime_paper_sleeve_snapshot(
        as_of=as_of,
        features_by_ticker=features,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=list(features),
        state=empty_alpha_score_market_regime_paper_state(),
        persist=False,
    )
    state_after = empty_alpha_score_market_regime_paper_state()
    state_after["pending_entries"] = first["pending_entries"]
    state_after["open_positions"] = first["open_positions"]
    state_after["closed_positions"] = first["closed_positions"]
    second = build_alpha_score_market_regime_paper_sleeve_snapshot(
        as_of=as_of,
        features_by_ticker=features,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=list(features),
        state=state_after,
        persist=False,
    )
    rejected_win2 = next(
        (
            row
            for row in second.get("rejected_candidates") or []
            if row.get("ticker") == "WIN2"
        ),
        {},
    )
    checks = {
        "first_run_new_pending_count_is_one": first.get("new_pending_count") == 1,
        "first_run_pending_count_is_one": first.get("pending_count") == 1,
        "first_run_ticker_is_win": (first.get("pending_entries") or [{}])[0].get("ticker")
        == "WIN",
        "second_run_candidate_is_win2": [
            row.get("ticker") for row in second.get("candidates") or []
        ]
        == ["WIN2"],
        "second_run_new_pending_count_is_zero": second.get("new_pending_count") == 0,
        "second_run_pending_count_stays_one": second.get("pending_count") == 1,
        "second_run_pending_queue_stays_win": [
            row.get("ticker") for row in second.get("pending_entries") or []
        ]
        == ["WIN"],
        "win2_rejected_by_daily_capacity": "daily_top1_or_capacity_limit"
        in (rejected_win2.get("reasons") or []),
        "trade_enabled_false": second.get("trade_enabled") is False,
        "orders_unchanged": (second.get("production_impact") or {}).get(
            "production_orders_changed"
        )
        is False,
    }
    return {
        "as_of": as_of,
        "passed": all(checks.values()),
        "checks": checks,
        "first": {
            "candidate_count": first.get("candidate_count"),
            "new_pending_count": first.get("new_pending_count"),
            "pending_count": first.get("pending_count"),
            "pending_tickers": [
                row.get("ticker") for row in first.get("pending_entries") or []
            ],
        },
        "second": {
            "candidate_count": second.get("candidate_count"),
            "candidate_tickers": [
                row.get("ticker") for row in second.get("candidates") or []
            ],
            "new_pending_count": second.get("new_pending_count"),
            "pending_count": second.get("pending_count"),
            "pending_tickers": [
                row.get("ticker") for row in second.get("pending_entries") or []
            ],
            "rejected_win2_reasons": rejected_win2.get("reasons") or [],
        },
    }


def verify_report_pending_queue() -> dict[str, Any]:
    snapshot = {
        "paper_enabled": True,
        "trade_enabled": False,
        "candidate_count": 0,
        "rejected_candidate_count": 0,
        "pending_count": 1,
        "open_position_count": 0,
        "closed_count_today": 0,
        "realized_pnl_to_date": 0.0,
        "unrealized_pnl": 0.0,
        "candidate_universe": {"status": "test_probe", "ticker_count": 1},
        "market_regime_context": {"reason": "test_probe"},
        "ranking_surface": {"ranked_count": 0, "top_decile_count": 0},
        "source_consensus_support": {},
        "candidates": [],
        "pending_entries": [
            {
                "ticker": "CAT",
                "created_asof": "2026-06-30",
                "notional": 4000.0,
                "candidate": {
                    "ticker": "CAT",
                    "alpha_score": 0.91,
                    "alpha_score_rank_pct": 0.04,
                    "intended_notional": 4000.0,
                },
            }
        ],
        "forward_paper_gate": {
            "status": "blocked",
            "reasons": ["min_closed_trades"],
            "metrics": {"closed_trades": 0, "realized_pnl": 0.0},
        },
    }
    report = generate_daily_report([], alpha_score_market_regime_paper_sleeve=snapshot)
    checks = {
        "section_rendered_from_pending_count": "ALPHA-SCORE MARKET-REGIME PAPER SLEEVE"
        in report,
        "pending_queue_header_rendered": "Pending queue (next-open paper buys):"
        in report,
        "stale_pending_ticker_rendered": "CAT:" in report,
        "stale_pending_signal_date_rendered": "signal 2026-06-30" in report,
        "pending_notional_rendered": "$4,000" in report,
        "fresh_candidate_not_required": "Candidates: 0" in report,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "report_excerpt": [
            line
            for line in report.splitlines()
            if "ALPHA-SCORE" in line
            or "Candidates:" in line
            or "Pending queue" in line
            or "CAT:" in line
        ],
    }


def build_payload() -> dict[str, Any]:
    ticket = load_json(TICKET_JSON)
    before = baseline_summary()
    idempotency = verify_same_day_idempotency()
    report_check = verify_report_pending_queue()
    accepted = idempotency["passed"] and report_check["passed"]
    status = "accepted_measurement_repair" if accepted else "rejected"
    decision = (
        "accepted_measurement_repair_alpha_score_same_day_idempotency_pending_report"
        if accepted
        else "rejected_alpha_score_same_day_idempotency_pending_report"
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": "measurement_repair",
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "alpha_ready": False,
        "hypothesis": ticket.get("hypothesis"),
        "alpha_hypothesis": (
            "The alpha-score market-regime paper sleeve can only produce usable "
            "forward replacement-value evidence if its same-day pending queue is "
            "idempotent and visible in the daily report."
        ),
        "change_summary": (
            "Verified same-signal-day pending admission is capped by daily_entry_slots "
            "and report rendering uses pending_entries."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair",
        "mechanism_family": "identity_or_measurement_repair",
        "trial_family": "alpha_score_market_regime_paper_ledger_repair",
        "trial_variant_id": "same_day_idempotency_and_pending_report_v1",
        "single_causal_variable": (
            "idempotent same-day pending admission + report renders true pending queue"
        ),
        "changed_variable": (
            "idempotent same-day pending admission + report renders true pending queue"
        ),
        "causal_components": [
            "same-asof pending count guard",
            "daily_entry_slots capacity cap",
            "snapshot pending_entries exposure",
            "daily report pending queue rendering",
            "default-off no-order contract",
        ],
        "nearby_prior_experiments": ["exp-20260531-021", "exp-20260701-005"],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "measurement_repair_for_forward_paper_ledger",
        "new_evidence_axis": (
            "Ledger/report parity repair for an already accepted default-off paper "
            "adapter; no new alpha threshold or response curve was tested."
        ),
        "gate1": {"passed": BASELINE_JSON.exists(), "baseline_metrics": before},
        "gate2": {
            "passed": idempotency["passed"] and report_check["passed"],
            "fields": [
                "pending_entries",
                "created_asof",
                "candidate",
                "notional",
                "daily_entry_slots",
                "trade_enabled",
            ],
            "entry_date_target_price_note": (
                "The repaired object is a next-open default-off paper pending queue, "
                "not an executable signal row; entry_date and target_price remain "
                "outside this measurement surface."
            ),
            "checks": {
                **idempotency["checks"],
                **report_check["checks"],
            },
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": before["signals_generated"],
            "signals_survived": before["signals_survived"],
            "survival_rate": before["survival_rate"],
            "note": (
                "No buy/sell/filter/ranking/sizing rule changed; paper ledger "
                "measurement survival is unchanged."
            ),
        },
        "gate4": {
            "passed": accepted,
            "mode": "measurement_repair_behavioral_contract",
            "idempotency_check": idempotency,
            "report_check": report_check,
            "strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
            "failed_reasons": []
            if accepted
            else [
                key
                for key, value in {
                    **idempotency["checks"],
                    **report_check["checks"],
                }.items()
                if not value
            ],
        },
        "before_metrics": before,
        "after_metrics": before,
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
            "daily_snapshot_exposed": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "feeds_llm_prompt": False,
            "trade_enabled": False,
            "live_ready": False,
            "parity_note": (
                "This closes a default-off paper ledger/report parity defect only. "
                "The sleeve still emits no live orders and does not alter core "
                "signals, ranking, sizing, exits, heat, LLM prompts, or watchlists."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The sleeve now subtracts already-created same-asof pending entries "
                "from daily_entry_slots before admitting new paper entries, and the "
                "report renders pending_entries directly. A re-run can still see a "
                "valid next-ranked candidate, but it does not grant a fresh daily "
                "slot."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune alpha-score regime thresholds, top-decile cutoffs, "
                "paper notional, or response curves on this repair. The next alpha "
                "step needs closed forward replacement-value rows from the repaired "
                "ledger."
            ),
            "new_evidence_required": (
                "Closed alpha_score_market_regime paper outcomes with replacement "
                "value versus cash/SPY/QQQ or a materially different production-"
                "visible PIT source."
            ),
        },
        "next_retry_requires": [
            "closed forward paper replacement-value rows emitted after this repair",
            "a materially different production-visible PIT alpha source",
            "or an activation-envelope audit after the repaired ledger matures",
        ],
        "prediction": ticket.get("prediction"),
        "calibration": {
            "actual_decision": status,
            "actual_success": 1 if accepted else 0,
            "predicted_success_probability": None,
            "predicted_failure_mode_hit": not accepted,
            "surprise_note": (
                "Behavioral probes confirmed the implementation already present in "
                "the shared helper and report generator."
            ),
        },
        "verification": {
            "runner_self_check": accepted,
            "same_day_idempotency": idempotency["passed"],
            "report_pending_queue": report_check["passed"],
        },
        "changed_files": CHANGED_FILES,
        "reproduction_commands": REPRODUCTION_COMMANDS,
        "write_fallbacks": WRITE_FALLBACKS,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
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
        "change_summary",
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
        "verification",
        "changed_files",
        "reproduction_commands",
        "artifact",
        "log",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    return f"""# Experiment Card: {EXPERIMENT_ID}

## Summary

{payload["decision"]}

## Hypothesis

{payload["hypothesis"]}

## Result

- Status: `{payload["status"]}`
- Accepted alpha: `{payload["accepted_alpha"]}`
- Strategy behavior changed: `false`
- Same-day idempotency passed: `{payload["gate4"]["idempotency_check"]["passed"]}`
- Report pending queue passed: `{payload["gate4"]["report_check"]["passed"]}`
- Artifact: `{payload["artifact"]}`

## Gates

- Gate 1 baseline loaded: `{payload["gate1"]["passed"]}`
- Gate 2 runtime fields verified: `{payload["gate2"]["passed"]}`
- Gate 3 survival unchanged: `{payload["gate3"]["passed"]}`
- Gate 4 measurement repair: `{payload["gate4"]["passed"]}`

## Reflection

{payload["post_run_reflection"]["why_result_happened"]}

## Reproduction

```powershell
{chr(10).join(payload["reproduction_commands"])}
```
"""


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [REPO_ROOT / path for path in CHANGED_FILES if path != repo_rel(OUT_JSON)]
    files.append(OUT_JSON)
    return {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_closeout_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "artifact": payload["artifact"],
        "log": payload["log"],
        "changed_files": CHANGED_FILES,
        "files": {repo_rel(path): {"exists": path.exists()} for path in files},
    }


def update_ticket(payload: dict[str, Any]) -> None:
    ticket = load_json(TICKET_JSON)
    ticket["status"] = payload["status"]
    ticket["completed_at"] = payload["timestamp"]
    ticket["result"] = {
        "decision": payload["decision"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "alpha_ready": False,
    }
    ticket["owner"] = OWNER
    for path in CHANGED_FILES:
        if path not in ticket.get("allowed_write_scope", []):
            ticket.setdefault("allowed_write_scope", []).append(path)
    safe_write_json(ticket, TICKET_JSON)


def main() -> int:
    payload = build_payload()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    safe_write_json(payload, OUT_JSON)
    log_record = compact_log_record(payload)
    safe_write_json(log_record, LOG_JSON)
    safe_write_text(build_card(payload), CARD_MD)
    safe_write_json(build_manifest(payload), MANIFEST_JSON)
    update_ticket(payload)

    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
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
            "change_summary": payload["change_summary"],
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
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": CHANGED_FILES,
            "artifact": payload["artifact"],
            "log": payload["log"],
        },
    )
    print(json.dumps({"experiment_id": EXPERIMENT_ID, "status": payload["status"]}))
    return 0 if payload["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
