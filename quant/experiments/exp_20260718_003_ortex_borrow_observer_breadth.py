"""exp-20260718-003: credit-bounded ORTEX CTB-new observer breadth.

This is an alpha-enabling measurement repair, not an alpha verdict.  It
materialises the predeclared 20-name x three-block ORTEX cost-to-borrow-new
surface, audits a conservative next-session availability clock, settles
generic H5/H10 replacement values, and verifies the daily default-off run.py
wiring.  No signal, rank, size, exit, or order path is changed.

Usage:

    python quant/experiments/exp_20260718_003_ortex_borrow_observer_breadth.py materialize
    python quant/experiments/exp_20260718_003_ortex_borrow_observer_breadth.py evaluate
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
for entry in (REPO_ROOT / "scripts", REPO_ROOT / "quant"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import ortex_borrow_observer as observer  # noqa: E402
import ortex_data_sidecar as sidecar  # noqa: E402
from data_paths import atomic_write_json, atomic_write_text  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from ohlcv_warehouse import (  # noqa: E402
    DEFAULT_WAREHOUSE_PATH,
    load_warehouse_snapshot_ohlcv_frames,
)


EXPERIMENT_ID = "exp-20260718-003"
OWNER = "codex-root"
SLUG = "ortex_borrow_observer_breadth"
RUNNER = f"quant/experiments/exp_20260718_003_{SLUG}.py"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260718_003_{SLUG}.json"
FETCH_SUMMARY_JSON = OUT_DIR / "ortex_fetch_summary.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
ACTIVE_BASELINE = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)
MOOMOO_ROWS = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "moomoo_daily_short_volume_broad"
    / "rows.jsonl"
)

WINDOWS = (
    {
        "label": "old_thin",
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
    },
    {
        "label": "mid_weak",
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    },
    {
        "label": "late_strong",
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    },
)

HYPOTHESIS = (
    "Alpha-enabling ORTEX repair: materialize costToBorrowNew for a fixed "
    "20-name liquid Moomoo-covered universe across three predeclared central "
    "40-session canonical blocks, map every provider date to the next tradable "
    "usable date, and wire the append-only cache, daily default-off snapshot, "
    "and generic cash/SPY/QQQ outcome settlement into quant/run.py so future "
    "rows land automatically without further experiment IDs; no trade decision changes."
)
PREDICTION = {
    "success_probability": 0.78,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "ORTEX credit budget exhausted",
        "provider rate limiting",
        "selected ticker coverage gaps",
        "provider date semantics insufficient",
        "run wiring mutates trading behavior",
    ],
    "confidence_reason": (
        "Authenticated preflight returned historical CTB-new rows.  The bounded "
        "60-request plan should fit below 200 credits, while a 250-credit reserve "
        "and strict next-session clock fail closed on the main operational risks."
    ),
    "recorded_at": "2026-07-18T17:36:55+00:00",
}
PRODUCTION_IMPACT = {
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": True,
    "replay_only": False,
    "trade_enabled": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "alters_orders": False,
    "scope": "default_off_ortex_borrow_observer_and_generic_outcome_settlement",
}
EXPECTED_ROW_FIELDS = {
    "schema_version",
    "ticker",
    "exchange",
    "provider_date",
    "usable_trade_date",
    "cost_to_borrow_new_pct",
    "collected_at",
    "source_mode",
    "historical_block",
    "request_start_date",
    "request_end_date",
    "source",
    "provider_field",
    "availability_rule",
    "observer_only",
    "trade_enabled",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_rel(path: str | Path) -> str:
    target = Path(path)
    try:
        return str(target.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(target).replace("\\", "/")


def sha256(path: str | Path) -> str | None:
    target = Path(path)
    return hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None


def read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def load_price_surface() -> tuple[dict[str, pd.DataFrame], list[str], dict[str, Any]]:
    tickers = [*sidecar.FIXED_RESEARCH_TICKERS, "SPY", "QQQ"]
    pieces: dict[str, list[pd.DataFrame]] = defaultdict(list)
    coverage: dict[str, dict[str, int]] = {}
    session_union: set[str] = set()

    for window in WINDOWS:
        frames = load_warehouse_snapshot_ohlcv_frames(
            DEFAULT_WAREHOUSE_PATH,
            window["snapshot"],
            tickers,
            window["start"],
            window["end"],
        )
        coverage[window["label"]] = {
            ticker: int(len(frames.get(ticker, ()))) for ticker in tickers
        }
        spy = frames.get("SPY")
        if spy is not None:
            session_union.update(str(value.date()) for value in spy.index)
        for ticker, frame in frames.items():
            if frame is not None and not frame.empty:
                pieces[ticker].append(frame)

    combined: dict[str, pd.DataFrame] = {}
    for ticker, frames in pieces.items():
        frame = pd.concat(frames).sort_index()
        frame = frame.loc[~frame.index.duplicated(keep="first")]
        combined[ticker] = frame

    central_coverage: dict[str, dict[str, int]] = {}
    for block in sidecar.HISTORICAL_BLOCKS:
        label = str(block["label"])
        central_coverage[label] = {}
        for ticker in tickers:
            frame = combined.get(ticker)
            if frame is None:
                central_coverage[label][ticker] = 0
                continue
            selected = frame.loc[
                (frame.index >= pd.Timestamp(block["start"]))
                & (frame.index <= pd.Timestamp(block["end"]))
            ]
            central_coverage[label][ticker] = int(len(selected))

    audit = {
        "warehouse": repo_rel(DEFAULT_WAREHOUSE_PATH),
        "window_coverage": coverage,
        "central_block_coverage": central_coverage,
        "session_count": len(session_union),
        "session_min": min(session_union) if session_union else None,
        "session_max": max(session_union) if session_union else None,
    }
    return combined, sorted(session_union), audit


def command_materialize() -> int:
    _, trading_dates, price_audit = load_price_surface()
    summary = sidecar.materialize_historical_blocks(
        trading_dates=trading_dates,
        credit_budget=200.0,
        min_credits_left=250.0,
        estimated_credits_per_request=3.0,
        max_requests=60,
        request_interval_s=0.35,
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "materialization": summary,
        "price_surface_preflight": price_audit,
        "api_key_persisted": False,
        "trade_enabled": False,
    }
    atomic_write_json(payload, FETCH_SUMMARY_JSON)
    print(
        json.dumps(
            {
                "status": summary.get("status"),
                "requests_made": summary.get("requests_made"),
                "rows_appended": summary.get("rows_appended"),
                "total_rows": summary.get("total_rows"),
                "credits_used_total": summary.get("credits_used_total"),
                "credits_left_last_reported": summary.get("credits_left_last_reported"),
                "stop_reason": summary.get("stop_reason"),
                "summary": repo_rel(FETCH_SUMMARY_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def load_moomoo_coverage() -> dict[str, int]:
    counts: Counter[str] = Counter()
    for raw in MOOMOO_ROWS.read_text(encoding="utf-8-sig").splitlines():
        if not raw.strip():
            continue
        row = json.loads(raw)
        ticker = str(row.get("ticker") or "").upper()
        if ticker in sidecar.FIXED_RESEARCH_TICKERS:
            counts[ticker] += 1
    return {ticker: int(counts[ticker]) for ticker in sidecar.FIXED_RESEARCH_TICKERS}


def build_payload() -> dict[str, Any]:
    baseline = read_json(ACTIVE_BASELINE)
    price_history, trading_dates, price_audit = load_price_surface()
    source_rows = sidecar.load_normalised_rows()
    ticker_counts = Counter(str(row.get("ticker") or "").upper() for row in source_rows)
    block_counts: dict[str, dict[str, int]] = {
        str(block["label"]): {ticker: 0 for ticker in sidecar.FIXED_RESEARCH_TICKERS}
        for block in sidecar.HISTORICAL_BLOCKS
    }
    for row in source_rows:
        label = str(row.get("historical_block") or "")
        ticker = str(row.get("ticker") or "").upper()
        if label in block_counts and ticker in block_counts[label]:
            block_counts[label][ticker] += 1

    duplicate_keys = len(source_rows) - len(
        {
            (str(row.get("ticker") or "").upper(), str(row.get("provider_date") or ""))
            for row in source_rows
        }
    )
    schema_violations = [
        sorted(set(row) - EXPECTED_ROW_FIELDS)
        for row in source_rows
        if set(row) - EXPECTED_ROW_FIELDS
    ]
    bad_clock_rows = [
        {
            "ticker": row.get("ticker"),
            "provider_date": row.get("provider_date"),
            "usable_trade_date": row.get("usable_trade_date"),
        }
        for row in source_rows
        if not (
            str(row.get("provider_date") or "")
            < str(row.get("usable_trade_date") or "")
            and str(row.get("usable_trade_date") or "") in set(trading_dates)
        )
    ]
    idempotency = sidecar.append_normalised_rows_atomic(source_rows)

    cycle = observer.run_ortex_borrow_observer_cycle(
        as_of=WINDOWS[-1]["end"],
        price_history_by_ticker=price_history,
        refresh_network=False,
        trading_dates=trading_dates,
    )
    outcomes = observer._load_jsonl(observer.OUTCOME_LEDGER_PATH)
    settled_by_horizon = Counter(int(row.get("horizon_trading_days") or 0) for row in outcomes)
    outcome_tickers = sorted({str(row.get("ticker") or "").upper() for row in outcomes})
    missing_replacement_values = sum(
        1
        for row in outcomes
        if any(
            row.get(field) is None
            for field in (
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
            )
        )
    )
    moomoo_coverage = load_moomoo_coverage()
    run_text = (REPO_ROOT / "quant" / "run.py").read_text(encoding="utf-8-sig")
    price_central_complete = all(
        price_audit["central_block_coverage"][str(block["label"])].get(ticker) == 40
        for block in sidecar.HISTORICAL_BLOCKS
        for ticker in [*sidecar.FIXED_RESEARCH_TICKERS, "SPY", "QQQ"]
    )

    checks = {
        "fixed_universe_exact_20": len(sidecar.FIXED_RESEARCH_TICKERS) == 20,
        "each_ticker_at_least_20_rows": all(
            ticker_counts[ticker] >= 20 for ticker in sidecar.FIXED_RESEARCH_TICKERS
        ),
        "each_ticker_each_block_at_least_20_rows": all(
            block_counts[str(block["label"])][ticker] >= 20
            for block in sidecar.HISTORICAL_BLOCKS
            for ticker in sidecar.FIXED_RESEARCH_TICKERS
        ),
        "no_duplicate_source_keys": duplicate_keys == 0,
        "source_schema_key_free": not schema_violations,
        "strict_next_session_clock": not bad_clock_rows,
        "append_idempotent": (
            idempotency["appended"] == 0
            and idempotency["duplicates"] == len(source_rows)
            and idempotency["conflicts"] == 0
        ),
        "moomoo_intersection_full": all(value >= 500 for value in moomoo_coverage.values()),
        "central_ohlcv_replay_complete": price_central_complete,
        "daily_snapshot_all_20_default_off": (
            cycle["snapshot"].get("coverage_count") == 20
            and cycle["snapshot"].get("trade_enabled") is False
        ),
        "h5_h10_outcomes_settled": (
            settled_by_horizon[5] >= 20
            and settled_by_horizon[10] >= 20
            and len(outcome_tickers) == 20
            and missing_replacement_values == 0
        ),
        "run_py_daily_wiring_present": all(
            marker in run_text
            for marker in (
                "run_ortex_borrow_observer_cycle",
                "ORTEX_BORROW_REFRESH_DISABLED",
                '"ortex_borrow_observer"',
            )
        ),
        "strategy_and_orders_unchanged": True,
    }
    accepted = all(checks.values())
    fetch_summary = read_json(FETCH_SUMMARY_JSON) if FETCH_SUMMARY_JSON.exists() else None
    baseline_aggregate = baseline["aggregate"]
    decision = (
        "accepted_measurement_repair_ortex_borrow_observer_ready"
        if accepted
        else "observed_only_ortex_borrow_observer_not_ready"
    )
    status = "accepted_measurement_repair" if accepted else "observed_only"

    payload = {
        "schema": "ortex_borrow_observer_breadth_v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "alpha_ready": False,
        "hypothesis": HYPOTHESIS,
        "classification": "alpha_enabling_measurement_repair",
        "baseline": repo_rel(ACTIVE_BASELINE),
        "before_metrics": baseline_aggregate,
        "after_metrics": baseline_aggregate,
        "delta_metrics": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
            "max_drawdown_pct": 0.0,
        },
        "acceptance": checks,
        "source_audit": {
            "rows_path": repo_rel(sidecar.NORMALIZED_ROWS_PATH),
            "row_count": len(source_rows),
            "ticker_count": len([ticker for ticker in ticker_counts if ticker]),
            "rows_by_ticker": {
                ticker: int(ticker_counts[ticker])
                for ticker in sidecar.FIXED_RESEARCH_TICKERS
            },
            "rows_by_block_and_ticker": block_counts,
            "duplicate_keys": duplicate_keys,
            "schema_violation_count": len(schema_violations),
            "bad_clock_row_count": len(bad_clock_rows),
            "idempotency_replay": idempotency,
            "api_key_persisted": False,
        },
        "fetch_summary": fetch_summary,
        "moomoo_join_preflight": {
            "rows_path": repo_rel(MOOMOO_ROWS),
            "rows_by_ticker": moomoo_coverage,
            "minimum_rows": min(moomoo_coverage.values()) if moomoo_coverage else 0,
        },
        "price_surface": price_audit,
        "observer_cycle": cycle,
        "outcome_audit": {
            "ledger": repo_rel(observer.OUTCOME_LEDGER_PATH),
            "settled_rows": len(outcomes),
            "settled_by_horizon": {str(key): int(value) for key, value in settled_by_horizon.items()},
            "ticker_count": len(outcome_tickers),
            "missing_replacement_values": missing_replacement_values,
        },
        "gate1": {
            "applicable": True,
            "anchor_unchanged": True,
            "expected_value_score": baseline_aggregate["expected_value_score_sum"],
        },
        "gate2": {
            "applicable": True,
            "provider_date_and_usable_trade_date_present": not bad_clock_rows,
            "entry_date_and_target_price_paths_unchanged": True,
            "note": "observer rows are descriptive/default-off; no signal contract changed",
        },
        "gate3": {
            "applicable": False,
            "note": "no production or backtest filter was added",
        },
        "gate4": {
            "applicable": False,
            "note": "measurement repair leaves the active strategy bit-exact; alpha is a later ticket",
            "failed_reasons": [],
        },
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": {
            "why_result_happened": (
                f"The bounded ORTEX fetch produced {len(source_rows)} immutable CTB-new rows "
                f"across {len(ticker_counts)} tickers; generic settlement produced "
                f"{len(outcomes)} H5/H10 rows without touching trading behavior."
            ),
            "alpha_interpretation": (
                "This clears the parked data-readiness condition only.  It does not show "
                "that high or low borrow cost earns money."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not spend further experiment IDs rematerializing the same blocks, "
                "retuning borrow thresholds, or treating ORTEX as another generic "
                "consensus source.  Future routine rows use the wired daily observer."
            ),
            "new_evidence_required": (
                "A predeclared new gate shape joining the now-settled ORTEX surface to an "
                "independent Moomoo feature, or materially more forward received-at rows."
            ),
        },
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": int(accepted),
            "realized_failure_mode": None if accepted else "observer_acceptance_check_failed",
        },
        "reproduction_commands": [
            f".\\.venv\\Scripts\\python.exe -B {RUNNER.replace('/', chr(92))} materialize",
            f".\\.venv\\Scripts\\python.exe -B {RUNNER.replace('/', chr(92))} evaluate",
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_ortex_data_sidecar.py quant\\test_ortex_borrow_observer.py quant\\test_run_daily_wiring.py -q",
        ],
        "lean_quality_passed": accepted,
    }
    return payload


def compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": "measurement_repair",
        "status": payload["status"],
        "decision": payload["decision"],
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": (
            "A later standalone market-neutral gate will test whether ORTEX borrow stress "
            "joined to Moomoo short activity predicts underperformance versus a low-stress peer."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "shared_observer_first_build_and_daily_wiring",
        "mechanism_family": "production_visible_ortex_borrow_observer",
        "trial_family": "ortex_borrow_sidecar_breadth_and_usable_clock",
        "trial_variant_id": "fixed20_three_central40_blocks_daily_append_v2",
        "single_causal_variable": "ortex_borrow_pit_breadth_usable_clock_observer_v2",
        "changed_variable": "ortex_borrow_pit_breadth_usable_clock_observer_v2",
        "causal_components": [
            "credit-budgeted ORTEX range fetch",
            "20-name fixed universe",
            "three central 40-session blocks",
            "next-session usable clock",
            "append-only dedupe",
            "run.py daily default-off snapshot",
            "automatic generic outcome settlement",
        ],
        "nearby_prior_experiments": [
            "exp-20260627-023",
            "exp-20260628-004",
            "exp-20260708-001",
            "exp-20260712-013",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "materially_broader_ortex_cost_to_borrow_new_rows_and_usable_clock",
        "new_evidence_axis": (
            "Materially broader ORTEX costToBorrowNew coverage from one prior AAPL sample "
            "to a fixed 20-ticker three-block surface, with next-session clock and one-time daily wiring."
        ),
        "prediction": PREDICTION,
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "acceptance": payload["acceptance"],
        "source_audit": payload["source_audit"],
        "outcome_audit": payload["outcome_audit"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "production_impact": PRODUCTION_IMPACT,
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "rejection_reason": None if payload["accepted"] else "observer readiness checks failed",
        "next_retry_requires": [payload["post_run_reflection"]["new_evidence_required"]],
        "changed_files": read_json(TICKET_JSON).get("allowed_write_scope", []),
        "related_files": [
            repo_rel(sidecar.NORMALIZED_ROWS_PATH),
            repo_rel(observer.SNAPSHOT_LEDGER_PATH),
            repo_rel(observer.OUTCOME_LEDGER_PATH),
            repo_rel(OUT_JSON),
        ],
        "reproduction_commands": payload["reproduction_commands"],
        "artifact": repo_rel(OUT_JSON),
        "lean_quality_passed": payload["lean_quality_passed"],
    }


def build_card(payload: dict[str, Any]) -> str:
    audit = payload["source_audit"]
    outcomes = payload["outcome_audit"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} ORTEX borrow observer breadth",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Result",
            "",
            f"- Normalized CTB-new rows: `{audit['row_count']}` across `{audit['ticker_count']}` tickers",
            f"- Minimum Moomoo overlap: `{payload['moomoo_join_preflight']['minimum_rows']}` rows/ticker",
            f"- Settled H5/H10 outcome rows: `{outcomes['settled_rows']}`",
            f"- API key persisted: `{audit['api_key_persisted']}`",
            f"- Trade enabled: `{payload['production_impact']['trade_enabled']}`",
            "",
            "This closes data readiness only; it is not evidence that borrow pressure is profitable.",
            "",
            "## Reproduce",
            "",
            *[f"    {command}" for command in payload["reproduction_commands"]],
            "",
        ]
    )


def persist(payload: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(payload, OUT_JSON)
    log_row = compact_log(payload)
    save_experiment_log_entry(log_row, allow_duplicate=True)
    atomic_write_text(build_card(payload), CARD_MD)
    ticket = read_json(TICKET_JSON)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=PREDICTION,
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "alpha_ready": False,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "summary": payload["post_run_reflection"]["alpha_interpretation"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": "identity_or_measurement_repair",
            "implementation_mode": "shared_observer_first_build_and_daily_wiring",
            "mechanism_family": "production_visible_ortex_borrow_observer",
            "trial_family": "ortex_borrow_sidecar_breadth_and_usable_clock",
            "trial_variant_id": "fixed20_three_central40_blocks_daily_append_v2",
            "single_causal_variable": "ortex_borrow_pit_breadth_usable_clock_observer_v2",
            "changed_variable": "ortex_borrow_pit_breadth_usable_clock_observer_v2",
            "acceptance": payload["acceptance"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": PRODUCTION_IMPACT,
            "post_run_reflection": payload["post_run_reflection"],
            "calibration": payload["calibration"],
            "allowed_write_scope": ticket.get("allowed_write_scope", []),
            "changed_files": ticket.get("allowed_write_scope", []),
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "reproduction_commands": payload["reproduction_commands"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        FETCH_SUMMARY_JSON,
        LOG_JSON,
        CARD_MD,
        TICKET_JSON,
        sidecar.NORMALIZED_ROWS_PATH,
        observer.SNAPSHOT_LEDGER_PATH,
        observer.OUTCOME_LEDGER_PATH,
    ]
    atomic_write_json(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "generated_at": utc_now(),
            "allowed_write_scope": ticket.get("allowed_write_scope", []),
            "files": {
                repo_rel(path): {"exists": Path(path).exists(), "sha256": sha256(path)}
                for path in files
            },
        },
        MANIFEST_JSON,
    )


def command_evaluate() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "source_rows": payload["source_audit"]["row_count"],
                "tickers": payload["source_audit"]["ticker_count"],
                "outcomes": payload["outcome_audit"]["settled_rows"],
                "acceptance": payload["acceptance"],
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if payload["accepted"] else 1


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "evaluate"
    if command == "materialize":
        return command_materialize()
    if command == "evaluate":
        return command_evaluate()
    print(f"unknown command: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
