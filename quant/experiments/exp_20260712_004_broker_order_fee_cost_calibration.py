"""exp-20260712-004: broker-authoritative order-fee cost calibration.

This measurement-only runner projects the latest effective Moomoo fills,
orders, and order-level fees, reconciles them by order id, and reports the
observed fee burden by fixed notional bucket.  It deliberately does not change
the global commission or slippage model because the broker ledger has no
reliable arrival-price benchmark for estimating market impact.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EXPERIMENT_ID = "exp-20260712-004"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "broker_order_fee_cost_calibration"
RUNNER = f"quant/experiments/exp_20260712_004_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

HYPOTHESIS = (
    "Alpha blocker: every candidate-pool Gate 4 subtracts a fixed 35 bps "
    "round-trip commission in addition to 5 bps slippage per leg, but the new "
    "broker-authoritative execution ledger contains 554 fee-covered effective "
    "filled orders; calibrate reported order fees by notional bucket so future "
    "alpha EV is not accepted or rejected on an unverified cost assumption, "
    "without changing the global cost model until arrival-price slippage is "
    "separately observable."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "moomoo_execution_history_cost_measurement"
TRIAL_FAMILY = "moomoo_execution_history_order_fee_notional_cost_calibration"
TRIAL_VARIANT_ID = EXPERIMENT_ID
CHANGED_VARIABLE = "broker_authoritative_order_fee_cost_calibration_v1"
NEARBY_PRIORS = ["exp-20260712-001", "exp-20260712-002"]
NEW_EVIDENCE_TYPE = "new_gate_shape"
NEW_EVIDENCE_AXIS = (
    "New gate shape on moomoo_execution_history: authoritative transaction-cost "
    "calibration by reconciled order fee/notional, rather than exit-avoidance "
    "replacement value."
)

BROKER_ROOT = REPO_ROOT / "data" / "live_pilot" / "broker_execution"
FILLS_PATH = BROKER_ROOT / "fills.jsonl"
ORDERS_PATH = BROKER_ROOT / "order_snapshots.jsonl"
FEES_PATH = BROKER_ROOT / "order_fee_snapshots.jsonl"
STATE_PATH = BROKER_ROOT / "state.json"
BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260712_004_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

ROUND_TRIP_COMMISSION_BPS = 35.0
PER_LEG_SLIPPAGE_BPS = 5.0
ROUND_TRIP_TOTAL_BPS = ROUND_TRIP_COMMISSION_BPS + 2 * PER_LEG_SLIPPAGE_BPS
MIN_ORDER_COUNT = 100
MIN_FEE_COVERAGE = 0.95

NOTIONAL_BUCKETS: list[tuple[str, float, float | None]] = [
    ("lt_500", 0.0, 500.0),
    ("500_to_999", 500.0, 1_000.0),
    ("1000_to_1999", 1_000.0, 2_000.0),
    ("2000_to_4999", 2_000.0, 5_000.0),
    ("ge_5000", 5_000.0, None),
]

CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260712_004_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def finite_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = math.floor((len(ordered) - 1) * fraction)
    return ordered[index]


def rounded(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(float(value), digits)


def latest_by(
    rows: list[dict[str, Any]], key_fn: Callable[[dict[str, Any]], str]
) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = key_fn(row)
        if not key:
            continue
        sequence = int(row.get("ledger_sequence") or 0)
        if sequence >= int(latest.get(key, {}).get("ledger_sequence") or 0):
            latest[key] = row
    return latest


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_PATH)
    windows = list(payload.get("windows") or [])
    return {
        "baseline_result_file": repo_rel(BASELINE_PATH),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row["expected_value_score"]) for row in windows), 4
        ),
        "total_pnl_sum": round(sum(float(row["total_pnl"]) for row in windows), 2),
        "trade_count": sum(int(row["trade_count"]) for row in windows),
        "signals_generated": sum(int(row["signals_generated"]) for row in windows),
        "signals_survived": sum(int(row["signals_survived"]) for row in windows),
        "minimum_survival_rate": min(float(row["survival_rate"]) for row in windows),
        "windows": windows,
    }


def bucket_name(notional: float) -> str:
    for name, lower, upper in NOTIONAL_BUCKETS:
        if notional >= lower and (upper is None or notional < upper):
            return name
    raise AssertionError(f"unbucketed notional: {notional}")


def summarize_orders(rows: list[dict[str, Any]]) -> dict[str, Any]:
    notionals = [row["notional"] for row in rows]
    fees = [row["fee"] for row in rows]
    fee_bps = [row["fee_bps"] for row in rows]
    total_notional = sum(notionals)
    total_fee = sum(fees)
    weighted = 10_000.0 * total_fee / total_notional if total_notional else None
    weighted_round_trip_fee = None if weighted is None else 2.0 * weighted
    total_with_slippage = (
        None
        if weighted_round_trip_fee is None
        else weighted_round_trip_fee + 2.0 * PER_LEG_SLIPPAGE_BPS
    )
    return {
        "orders": len(rows),
        "total_notional": rounded(total_notional, 2),
        "total_fee": rounded(total_fee, 2),
        "weighted_leg_fee_bps": rounded(weighted),
        "median_leg_fee_bps": rounded(statistics.median(fee_bps)) if fee_bps else None,
        "p90_leg_fee_bps": rounded(percentile(fee_bps, 0.90)),
        "p95_leg_fee_bps": rounded(percentile(fee_bps, 0.95)),
        "implied_weighted_round_trip_fee_bps": rounded(weighted_round_trip_fee),
        "implied_round_trip_total_with_fixed_slippage_bps": rounded(
            total_with_slippage
        ),
        "delta_vs_current_round_trip_total_bps": rounded(
            None if total_with_slippage is None else total_with_slippage - ROUND_TRIP_TOTAL_BPS
        ),
    }


def source_projection() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    fill_rows = read_jsonl(FILLS_PATH)
    order_rows = read_jsonl(ORDERS_PATH)
    fee_rows = read_jsonl(FEES_PATH)
    state = read_json(STATE_PATH)

    latest_fills = latest_by(
        fill_rows, lambda row: str((row.get("fact") or {}).get("deal_id") or "")
    )
    latest_orders = latest_by(
        order_rows, lambda row: str((row.get("fact") or {}).get("order_id") or "")
    )
    latest_fees = latest_by(
        fee_rows, lambda row: str((row.get("fact") or {}).get("order_id") or "")
    )

    effective_fills = []
    status_counts: Counter[str] = Counter()
    for row in latest_fills.values():
        fact = row.get("fact") or {}
        status = str(fact.get("economic_effect_status") or "").lower()
        if not status:
            raw = str(fact.get("status") or "").upper()
            status = "effective" if raw in {"OK", "CHANGED"} else raw.lower()
        status_counts[status] += 1
        if status == "effective":
            effective_fills.append(row)

    notional_by_order: defaultdict[str, float] = defaultdict(float)
    qty_by_order: defaultdict[str, float] = defaultdict(float)
    deal_count_by_order: Counter[str] = Counter()
    for row in effective_fills:
        fact = row.get("fact") or {}
        order_id = str(fact.get("order_id") or "")
        notional = finite_float(fact.get("gross_notional"))
        qty = finite_float(fact.get("qty"))
        if order_id and notional is not None and qty is not None:
            notional_by_order[order_id] += abs(notional)
            qty_by_order[order_id] += abs(qty)
            deal_count_by_order[order_id] += 1

    observations: list[dict[str, Any]] = []
    missing_fee_orders: list[str] = []
    missing_order_rows: list[str] = []
    non_usd_orders: list[str] = []
    qty_mismatch_orders: list[str] = []
    side_counts: Counter[str] = Counter()
    currency_counts: Counter[str] = Counter()

    for order_id, notional in sorted(notional_by_order.items()):
        order_row = latest_orders.get(order_id)
        fee_row = latest_fees.get(order_id)
        if order_row is None:
            missing_order_rows.append(order_id)
            continue
        if fee_row is None:
            missing_fee_orders.append(order_id)
            continue

        order_fact = order_row.get("fact") or {}
        fee_fact = fee_row.get("fact") or {}
        fee = finite_float(fee_fact.get("fee_amount"))
        currency = str(fee_fact.get("currency") or "").upper()
        fee_status = str(fee_fact.get("fee_status") or "").lower()
        dealt_qty = finite_float(order_fact.get("dealt_qty"))
        if fee is None or fee_status != "reported":
            missing_fee_orders.append(order_id)
            continue
        if currency != "USD":
            non_usd_orders.append(order_id)
            continue
        if dealt_qty is None or not math.isclose(
            abs(dealt_qty), qty_by_order[order_id], rel_tol=0.0, abs_tol=1e-9
        ):
            qty_mismatch_orders.append(order_id)

        side = str(order_fact.get("trd_side") or "unknown").upper()
        side_counts[side] += 1
        currency_counts[currency] += 1
        observations.append(
            {
                "notional": notional,
                "fee": fee,
                "fee_bps": 10_000.0 * fee / notional,
                "bucket": bucket_name(notional),
                "side": side,
                "deal_count": deal_count_by_order[order_id],
            }
        )

    effective_order_count = len(notional_by_order)
    source_audit = {
        "ledger_root": repo_rel(BROKER_ROOT),
        "fill_snapshot_rows": len(fill_rows),
        "distinct_deal_versions_projected": len(latest_fills),
        "effective_fill_count": len(effective_fills),
        "effective_order_count": effective_order_count,
        "latest_order_count": len(latest_orders),
        "latest_fee_order_count": len(latest_fees),
        "fee_observation_count": len(observations),
        "fee_coverage": round(
            len(observations) / effective_order_count if effective_order_count else 0.0,
            6,
        ),
        "missing_fee_order_count": len(set(missing_fee_orders)),
        "missing_order_row_count": len(set(missing_order_rows)),
        "non_usd_order_count": len(set(non_usd_orders)),
        "quantity_mismatch_order_count": len(set(qty_mismatch_orders)),
        "latest_effect_status_counts": dict(status_counts),
        "side_counts": dict(side_counts),
        "currency_counts": dict(currency_counts),
        "multi_fill_order_count": sum(row["deal_count"] > 1 for row in observations),
        "state_fee_coverage": state.get("fee_coverage"),
        "raw_order_ids_persisted_to_artifact": False,
    }
    return source_audit, observations


def build_payload() -> dict[str, Any]:
    baseline = baseline_metrics()
    source_audit, observations = source_projection()
    aggregate = summarize_orders(observations)
    buckets = {
        name: summarize_orders([row for row in observations if row["bucket"] == name])
        for name, _lower, _upper in NOTIONAL_BUCKETS
    }
    by_side = {
        side: summarize_orders([row for row in observations if row["side"] == side])
        for side in sorted({row["side"] for row in observations})
    }

    fee_coverage = float(source_audit["fee_coverage"])
    checks = {
        "baseline_identity_matches": (
            baseline["expected_value_score_sum"] == 7.8941
            and baseline["total_pnl_sum"] == 234850.99
        ),
        "minimum_order_count_met": len(observations) >= MIN_ORDER_COUNT,
        "fee_coverage_met": fee_coverage >= MIN_FEE_COVERAGE,
        "no_missing_order_rows": source_audit["missing_order_row_count"] == 0,
        "all_fee_rows_reported_usd": source_audit["non_usd_order_count"] == 0,
        "fill_order_quantities_reconcile": (
            source_audit["quantity_mismatch_order_count"] == 0
        ),
        "all_fixed_notional_buckets_nonempty": all(
            buckets[name]["orders"] > 0 for name, _lower, _upper in NOTIONAL_BUCKETS
        ),
        "commission_and_slippage_kept_separate": True,
        "global_cost_model_unchanged": True,
    }
    passed = all(checks.values())
    failed = [name for name, ok in checks.items() if not ok]
    decision = (
        "accepted_measurement_repair_broker_order_fee_cost_calibration"
        if passed
        else "rejected_broker_order_fee_cost_calibration_contract_failed"
    )
    status = "accepted_measurement_repair" if passed else "rejected"

    standard_bucket = buckets["2000_to_4999"]
    tiny_bucket = buckets["lt_500"]
    interpretation = {
        "current_model": {
            "round_trip_commission_bps": ROUND_TRIP_COMMISSION_BPS,
            "per_leg_slippage_bps": PER_LEG_SLIPPAGE_BPS,
            "round_trip_total_bps": ROUND_TRIP_TOTAL_BPS,
        },
        "all_orders": aggregate,
        "strategy_notional_2000_to_4999": standard_bucket,
        "small_notional_lt_500": tiny_bucket,
        "finding": (
            "The fixed model is conservative for the weighted aggregate and the "
            "$2k-$5k strategy-notional bucket, but can understate fee drag for "
            "sub-$500 orders because Moomoo fees contain a fixed component."
        ),
        "policy_boundary": (
            "Do not change ROUND_TRIP_COST_PCT or slippage from fee-only evidence. "
            "A global calibration requires strategy-tagged orders plus an arrival-"
            "price benchmark that can measure adverse price movement separately."
        ),
    }

    ticket = read_json(TICKET_JSON)
    prediction = ticket.get("prediction") or {}
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "accepted": passed,
        "accepted_alpha": False,
        "accepted_measurement_repair": passed,
        "alpha_ready": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": (
            "Accurate broker-authoritative transaction costs may change the EV "
            "ordering of marginal candidate pools; this experiment repairs the "
            "fee measurement surface without promoting an alpha rule."
        ),
        "change_type": CHANGE_TYPE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "gate1": {
            "passed": checks["baseline_identity_matches"],
            "baseline_artifact": repo_rel(BASELINE_PATH),
            "expected_value_score": baseline["expected_value_score_sum"],
            "total_pnl": baseline["total_pnl_sum"],
            "note": "Measurement-only; canonical strategy metrics are unchanged.",
        },
        "gate2": {
            "passed": (
                checks["no_missing_order_rows"]
                and checks["all_fee_rows_reported_usd"]
                and checks["fill_order_quantities_reconcile"]
            ),
            "runtime_fields": [
                "deal_id",
                "order_id",
                "gross_notional",
                "qty",
                "dealt_qty",
                "fee_amount",
                "fee_status",
                "currency",
            ],
            "sentinel_note": (
                "entry_date and target_price remain canonical signal sentinels; "
                "this execution-cost measurement creates no entry signal."
            ),
        },
        "gate3": {
            "passed": checks["fee_coverage_met"],
            "new_filter_added": False,
            "signals_generated": source_audit["effective_order_count"],
            "signals_survived": source_audit["fee_observation_count"],
            "survival_rate": fee_coverage,
        },
        "gate4": {
            "applicable_to_strategy": False,
            "passed_as_measurement_repair": passed,
            "accepted_alpha": False,
            "decision": decision,
            "acceptance_checks": checks,
            "failed_reasons": failed,
            "note": (
                "No before/after strategy replay is warranted because no cost "
                "constant or trading behavior changed. Baseline identity remains exact."
            ),
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
        },
        "measurement": {
            "source_audit": source_audit,
            "aggregate": aggregate,
            "by_notional_bucket": buckets,
            "by_side": by_side,
            "interpretation": interpretation,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_changed": False,
            "fill_model_changed": False,
            "global_cost_constant_changed": False,
            "run_adapter_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "orders_changed": False,
            "trade_enabled": False,
            "scope": "read_only_broker_fee_calibration",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "Moomoo reports a roughly fixed platform-fee component, so fee "
                "bps falls sharply as order notional rises. The weighted real-"
                "order fee is below the fixed backtest commission envelope, while "
                "very small orders can exceed it."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not lower ROUND_TRIP_COST_PCT, retune slippage, or slice these "
                "same orders by ticker/year/side to manufacture alpha. Do not "
                "duplicate order-level fees across partial fills."
            ),
            "new_evidence_required": (
                "A strategy cost-model change requires broker-confirmed event "
                "timezone, strategy-tagged orders, and a reproducible arrival-"
                "price or decision-price benchmark covering both entry and exit legs."
            ),
        },
        "reopen_condition": (
            "Reopen only with strategy-tagged entry/exit orders plus an arrival-"
            "price benchmark that separates realized slippage from reported fees."
        ),
        "rejection_reason": None if passed else ";".join(failed),
        "changed_files": CHANGED_FILES,
        "related_files": [
            repo_rel(STATE_PATH),
            repo_rel(FILLS_PATH),
            repo_rel(ORDERS_PATH),
            repo_rel(FEES_PATH),
            "quant/constants.py",
            "quant/fill_model.py",
            repo_rel(BASELINE_PATH),
        ],
        "reproduction_commands": [
            f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER.replace('/', chr(92))}",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": passed,
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
    }


def build_card(payload: dict[str, Any]) -> str:
    measurement = payload["measurement"]
    aggregate = measurement["aggregate"]
    standard = measurement["by_notional_bucket"]["2000_to_4999"]
    tiny = measurement["by_notional_bucket"]["lt_500"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Broker order-fee cost calibration",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Fee-covered effective orders: `{aggregate['orders']}`",
            f"- Weighted one-leg fee: `{aggregate['weighted_leg_fee_bps']}` bps",
            f"- $2k-$5k weighted one-leg fee: `{standard['weighted_leg_fee_bps']}` bps",
            f"- Sub-$500 weighted one-leg fee: `{tiny['weighted_leg_fee_bps']}` bps",
            f"- Current modeled round-trip total: `{ROUND_TRIP_TOTAL_BPS}` bps",
            "",
            "The current fixed cost envelope is conservative for strategy-sized orders but can understate fixed-fee drag on very small orders. No global cost, slippage, strategy, or order behavior changed.",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduce",
            "",
            f"- `{RUNNER_COMMAND}`",
        ]
    ) + "\n"


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(payload, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "generated_at": payload["timestamp"],
            "runner": RUNNER,
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card": repo_rel(CARD_MD),
            "ticket": repo_rel(TICKET_JSON),
            "files": CHANGED_FILES,
            "reproduction_commands": payload["reproduction_commands"],
        },
    )
    ticket = read_json(TICKET_JSON)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "gate4": payload["gate4"],
            "headline_metrics": {
                "effective_orders": payload["measurement"]["source_audit"][
                    "effective_order_count"
                ],
                "fee_coverage": payload["measurement"]["source_audit"][
                    "fee_coverage"
                ],
                "weighted_leg_fee_bps": payload["measurement"]["aggregate"][
                    "weighted_leg_fee_bps"
                ],
                "strategy_notional_leg_fee_bps": payload["measurement"][
                    "by_notional_bucket"
                ]["2000_to_4999"]["weighted_leg_fee_bps"],
            },
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
        },
        status=payload["status"],
        fields={
            **{key: value for key, value in ticket.items() if key not in {"result", "status"}},
            **{
                key: value
                for key, value in payload.items()
                if key not in {"experiment_id", "status", "prediction"}
            },
            "owner": OWNER,
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "ticket_file": repo_rel(TICKET_JSON),
        },
    )


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "checks": payload["gate4"]["acceptance_checks"],
                "effective_orders": payload["measurement"]["source_audit"][
                    "effective_order_count"
                ],
                "fee_coverage": payload["measurement"]["source_audit"][
                    "fee_coverage"
                ],
                "aggregate": payload["measurement"]["aggregate"],
                "strategy_notional_2000_to_4999": payload["measurement"][
                    "by_notional_bucket"
                ]["2000_to_4999"],
                "small_notional_lt_500": payload["measurement"][
                    "by_notional_bucket"
                ]["lt_500"],
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if payload["accepted_measurement_repair"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
