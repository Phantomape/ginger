"""Offline measurement proof for reserved exp-20260906-001; never trades.

The source contract is frozen before outcomes are read. Only this experiment's
directory is written; broker facts and historical daily reports remain intact.
"""

from __future__ import annotations

import ast
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "quant"))
from broker_performance import compute_broker_performance
from report_generator import generate_daily_report

EXPERIMENT_ID = "exp-20260906-001"
OUTPUT = ROOT / "data" / "experiments" / EXPERIMENT_ID
CONTRACT = OUTPUT / "source_contract.json"


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True,
                               allow_nan=False) + "\n", encoding="utf-8")


def actual_daily_output_statements(summary):
    """Execute the production output statements with no strategy/network work."""
    tree = ast.parse((ROOT / "quant/run.py").read_text(encoding="utf-8"))
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    names = {"broker_performance", "report", "quant_signals_payload"}
    nodes = [node for node in main.body if isinstance(node, ast.Assign)
             and any(isinstance(target, ast.Name) and target.id in names for target in node.targets)]
    loads = {node.id for statement in nodes for node in ast.walk(statement)
             if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}
    scope = dict.fromkeys(loads)
    signals = [{"ticker": "SYNTHETIC", "strategy": "proof", "action": "WAIT", "risk": 0}]
    original_signals = deepcopy(signals)
    scope.update({
        "_build_broker_performance_snapshot": lambda: summary,
        "generate_daily_report": generate_daily_report,
        "signals": signals, "entry_cash_admission": {"observations": []},
        "datetime": datetime, "timezone": timezone,
    })
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "frozen_daily_outputs", "exec"), scope)
    payload, report = scope["quant_signals_payload"], scope["report"]
    net = summary["pnl_by_currency"]["USD"]["net_trading_pnl_after_order_fees"]
    expected = (f"Net trading P&L after order fees: ${net:,.2f}" if net is not None
                else "Net trading P&L: unavailable (not zero)")
    checks = {
        "quant_signals_broker_measurement_present": payload["broker_performance"] is summary,
        "daily_report_broker_measurement_present": "BROKER TRADING P&L" in report and expected in report,
        "signals_unchanged": signals == original_signals and payload["signals"] is signals,
        "strategy_attribution_unavailable_visible": "strategy attribution unavailable" in report,
    }
    return payload, report, checks


def main():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    for relative, expected in contract["code_file_sha256"].items():
        if file_hash(ROOT / relative) != expected:
            raise SystemExit(f"Frozen code changed: {relative}")
    source_before = {relative: file_hash(ROOT / relative)
                     for relative in contract["source_file_sha256"]}
    if source_before != contract["source_file_sha256"]:
        raise SystemExit("Frozen broker source changed; do not silently re-freeze or reuse this proof.")
    first = compute_broker_performance(ROOT / "data/live_pilot/broker_execution")
    second = compute_broker_performance(ROOT / "data/live_pilot/broker_execution")
    source_after = {relative: file_hash(ROOT / relative) for relative in source_before}
    payload, report, checks = actual_daily_output_statements(first)
    usd = first["pnl_by_currency"]["USD"]
    net = usd["net_trading_pnl_after_order_fees"]
    arithmetic = (abs(Decimal(str(usd["gross_trading_pnl_before_order_fees"]))
                      - Decimal(str(usd["order_fee_total"])) - Decimal(str(net))) <= Decimal("0.00000001")
                  if net is not None else None)
    checks.update({
        "two_summary_calls_identical": first == second,
        "raw_source_bytes_unchanged": source_before == source_after,
        "same_cohort_gross_less_fees_equals_net": arithmetic,
        "missing_pnl_is_null_not_zero": net is not None or all(
            usd[key] is None for key in ("gross_trading_pnl_before_order_fees", "order_fee_total")),
        "trade_enabled_false": first["trade_enabled"] is False,
    })
    result = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "measurement_only": True,
        "source_contract_sha256": file_hash(CONTRACT),
        "runner_sha256": file_hash(Path(__file__)),
        "broker_performance": first,
        "source_hashes_before": source_before,
        "source_hashes_after": source_after,
        "downstream_checks": checks,
        "engineering_measurement_accepted": all(value is not False for value in checks.values()),
        "economic_progress": False,
        "alpha_changed": False,
        "trade_enabled": False,
        "production_proof_boundary": "Actual output statements executed offline with synthetic signals and real read-only aggregate; next ordinary daily run publishes it. No historical daily output rewritten.",
        "backtest_metrics": "not_applicable_measurement_repair",
    }
    write_json(OUTPUT / "after.json", result)
    write_json(OUTPUT / "quant_signals_preview.json", {
        "proof_scope": "offline actual production payload assignment; all signals synthetic",
        "broker_performance": payload["broker_performance"], "signals": payload["signals"],
    })
    (OUTPUT / "report_preview.txt").write_text(report, encoding="utf-8")
    print(json.dumps({"status": first["status"], "counts": first["counts"],
                      "USD": usd, "coverage_reasons": first["coverage_reasons"],
                      "checks": checks}, ensure_ascii=False, allow_nan=False))
    if not result["engineering_measurement_accepted"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
