"""exp-20260705-011: Form4 sale-overhang daily pipeline wiring.

This measurement repair verifies that the accepted Form4 sale-overhang
data-only observer is wired into the production daily non-OHLCV path. It does
not run a backtest or materialize today's non-OHLCV files; the behavioral
contract is that the production run path now requests default-off context rows.
"""

from __future__ import annotations

import ast
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "exp-20260705-011"
SLUG = "form4_sale_overhang_daily_pipeline_wiring"

RUN_PY = REPO_ROOT / "quant" / "run.py"
TEST_RUN_DAILY_WIRING = REPO_ROOT / "quant" / "test_run_daily_wiring.py"
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260705_011_{SLUG}.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return rows
    for line in lines:
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def baseline_metrics() -> dict[str, Any]:
    raw = read_json(BASELINE_RESULT, {})
    if not isinstance(raw, dict):
        return {"loaded": False, "baseline_result_file": repo_rel(BASELINE_RESULT)}
    windows = raw.get("windows") or []
    if not isinstance(windows, list):
        windows = []
    signals_generated = sum(int(row.get("signals_generated") or 0) for row in windows if isinstance(row, dict))
    signals_survived = sum(int(row.get("signals_survived") or 0) for row in windows if isinstance(row, dict))
    return {
        "loaded": True,
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows if isinstance(row, dict)),
            6,
        ),
        "total_pnl": round(
            sum(float(row.get("total_pnl") or 0.0) for row in windows if isinstance(row, dict)),
            2,
        ),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows if isinstance(row, dict)),
        "signals_generated": signals_generated,
        "signals_survived": signals_survived,
        "survival_rate": round(signals_survived / signals_generated, 6) if signals_generated else None,
    }


def call_has_true_keyword(call: ast.Call, keyword: str) -> bool:
    for item in call.keywords:
        if item.arg != keyword:
            continue
        return isinstance(item.value, ast.Constant) and item.value.value is True
    return False


def daily_wiring_checks() -> dict[str, Any]:
    source = RUN_PY.read_text(encoding="utf-8")
    tree = ast.parse(source)
    in_daily_builder = False
    ensure_calls = []
    fallback_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_build_daily_non_ohlcv_snapshot":
            in_daily_builder = True
            for child in ast.walk(node):
                if not isinstance(child, ast.Call):
                    continue
                func_name = getattr(child.func, "id", None)
                if func_name == "ensure_non_ohlcv_coverage":
                    ensure_calls.append(child)
                elif func_name == "persist_daily_non_ohlcv_snapshots":
                    fallback_calls.append(child)
            break

    ensure_refresh = [call_has_true_keyword(call, "refresh_form4_context") for call in ensure_calls]
    fallback_refresh = [call_has_true_keyword(call, "refresh_form4_context") for call in fallback_calls]
    return {
        "daily_builder_found": in_daily_builder,
        "ensure_call_count": len(ensure_calls),
        "fallback_call_count": len(fallback_calls),
        "ensure_refresh_form4_context_true": bool(ensure_refresh) and all(ensure_refresh),
        "fallback_refresh_form4_context_true": bool(fallback_refresh) and all(fallback_refresh),
        "all_checks_passed": (
            in_daily_builder
            and bool(ensure_refresh)
            and all(ensure_refresh)
            and bool(fallback_refresh)
            and all(fallback_refresh)
        ),
    }


def current_gap_snapshot(tag: str = "20260704") -> dict[str, Any]:
    daily_snapshot = read_json(NON_OHLCV_DIR / f"daily_non_ohlcv_snapshot_{tag}.json", {})
    form4_rows = read_jsonl(NON_OHLCV_DIR / f"form4_transactions_{tag}.jsonl")
    form4_context_path = NON_OHLCV_DIR / f"form4_sale_overhang_context_{tag}.jsonl"
    form4_context = daily_snapshot.get("form4_sale_overhang_context") if isinstance(daily_snapshot, dict) else {}
    return {
        "date_tag": tag,
        "daily_snapshot_path": repo_rel(NON_OHLCV_DIR / f"daily_non_ohlcv_snapshot_{tag}.json"),
        "daily_snapshot_status": daily_snapshot.get("status") if isinstance(daily_snapshot, dict) else None,
        "form4_transactions_rows": len(form4_rows),
        "form4_sale_overhang_context_status": form4_context.get("status") if isinstance(form4_context, dict) else None,
        "form4_sale_overhang_context_reason": form4_context.get("reason") if isinstance(form4_context, dict) else None,
        "form4_sale_overhang_context_path_exists": form4_context_path.exists(),
    }


def main() -> int:
    wiring = daily_wiring_checks()
    accepted = wiring["all_checks_passed"]
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "lane": "measurement_repair",
        "decision": (
            "accepted_measurement_repair_form4_sale_overhang_daily_pipeline_wiring"
            if accepted
            else "blocked_form4_sale_overhang_daily_pipeline_wiring"
        ),
        "alpha_hypothesis": (
            "Risk allocation: PIT Form4 sale, 10b5-1, and officer-sale "
            "overhang may flag loss-tail risk, but alpha response remains "
            "parked until enough prospective context rows close with cash/SPY/QQQ RV."
        ),
        "single_causal_variable": "form4_sale_overhang_daily_pipeline_context_wiring_v1",
        "changed_variable": "form4_sale_overhang_daily_pipeline_context_wiring_v1",
        "baseline": baseline_metrics(),
        "wiring_checks": wiring,
        "before_gap_snapshot": current_gap_snapshot(),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "replay_only": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "trade_enabled": False,
            "scope": "default_off_form4_sale_overhang_context_daily_collection_only",
        },
        "gate4": {
            "required": False,
            "reason": (
                "Measurement repair only: the change requests data-only context "
                "rows in run.py daily non-OHLCV coverage and does not change "
                "entries, exits, ranking, sizing, risk budget, or orders."
            ),
        },
        "changed_files": [
            repo_rel(RUN_PY),
            repo_rel(TEST_RUN_DAILY_WIRING),
            repo_rel(Path(__file__)),
            repo_rel(OUT_JSON),
        ],
        "verification_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_run_daily_wiring.py -q",
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_daily_non_ohlcv_snapshot.py quant\\test_run_daily_wiring.py -q",
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260705_011_form4_sale_overhang_daily_pipeline_wiring.py",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "post_run_reflection": (
            "Do not retune Form4 alpha responses on the current row set. The "
            "next valid Form4 alpha step still requires the shared helper's "
            "reopen gate: at least 25 closed rows, at least 8 high-sale-overhang "
            "rows, cash/SPY/QQQ replacement values, and max single-ticker share <=40%."
        ),
    }
    write_json(OUT_JSON, payload)
    print(json.dumps({"artifact": repo_rel(OUT_JSON), "accepted": accepted}, indent=2))
    return 0 if accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
