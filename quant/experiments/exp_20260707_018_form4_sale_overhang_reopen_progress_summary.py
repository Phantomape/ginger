"""exp-20260707-018: Form4 sale-overhang reopen progress summary.

This measurement repair verifies that the accepted default-off Form4
sale-overhang context helper reports settled forward-row progress separately
from raw context-row counts. It does not change strategy policy, rankings,
sizing, exits, or live order behavior.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from form4_sale_overhang_context import FORWARD_REOPEN_GATE, summarize_forward_reopen_progress


EXPERIMENT_ID = "exp-20260707-018"
SLUG = "form4_sale_overhang_reopen_progress_summary"
NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_BEFORE = OUT_DIR / f"before_{SLUG}.json"
OUT_AFTER = OUT_DIR / f"after_{SLUG}.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def zero_backtest_metrics() -> dict[str, Any]:
    return {
        "benchmarks": {"strategy_total_return_pct": 0.0},
        "expected_value_score": 0.0,
        "sharpe_daily": 0.0,
        "sharpe": 0.0,
        "max_drawdown_pct": 0.0,
        "win_rate": 0.0,
        "total_trades": 0,
        "survival_rate": None,
        "total_pnl": 0.0,
    }


def latest_context_tag() -> str:
    paths = sorted(NON_OHLCV_DIR.glob("form4_sale_overhang_context_*.jsonl"))
    if not paths:
        raise FileNotFoundError("no form4_sale_overhang_context_*.jsonl files found")
    return paths[-1].stem.rsplit("_", 1)[-1]


def main() -> int:
    tag = latest_context_tag()
    context_path = NON_OHLCV_DIR / f"form4_sale_overhang_context_{tag}.jsonl"
    summary_path = NON_OHLCV_DIR / f"form4_sale_overhang_context_summary_{tag}.json"
    rows = read_jsonl(context_path)
    before_summary = read_json(summary_path, {})
    before_has_progress = (
        isinstance(before_summary, dict)
        and isinstance(before_summary.get("forward_reopen_progress"), dict)
    )
    progress = summarize_forward_reopen_progress(rows)
    accepted = (
        progress.get("context_rows_current") == len(rows)
        and "closed_forward_rows_current" in progress
        and "replacement_value_complete_closed_rows_current" in progress
    )

    common = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "lane": "measurement_repair",
        "alpha_hypothesis": (
            "Risk allocation: PIT Form4 sale, 10b5-1, and officer-sale overhang "
            "may flag loss-tail risk, but the alpha response remains parked until "
            "settled forward replacement rows satisfy the shared helper reopen gate."
        ),
        "single_causal_variable": "form4_sale_overhang_reopen_progress_summary_v1",
        "changed_variable": "form4_sale_overhang_reopen_progress_summary_v1",
        "latest_context_tag": tag,
        "context_path": repo_rel(context_path),
        "summary_path": repo_rel(summary_path),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "trade_enabled": False,
            "scope": "default_off_form4_sale_overhang_context_summary_only",
        },
        "gate4": {
            "required": False,
            "reason": (
                "Measurement repair only: the change adds machine-checkable "
                "summary fields and does not alter entries, exits, ranking, "
                "sizing, risk budgets, or orders."
            ),
        },
    }

    before_payload = {
        **zero_backtest_metrics(),
        **common,
        "phase": "before",
        "summary_had_forward_reopen_progress": before_has_progress,
        "rows_written": before_summary.get("rows_written") if isinstance(before_summary, dict) else None,
        "rows_with_high_sale_overhang": (
            before_summary.get("rows_with_high_sale_overhang")
            if isinstance(before_summary, dict)
            else None
        ),
        "measurement_gap": (
            "summary lacks settled forward-row progress"
            if not before_has_progress
            else "summary already has settled forward-row progress"
        ),
    }
    after_payload = {
        **zero_backtest_metrics(),
        **common,
        "phase": "after",
        "decision": (
            "accepted_measurement_repair_form4_sale_overhang_reopen_progress_summary"
            if accepted
            else "blocked_form4_sale_overhang_reopen_progress_summary"
        ),
        "forward_reopen_gate": FORWARD_REOPEN_GATE,
        "forward_reopen_progress": progress,
        "changed_files": [
            repo_rel(REPO_ROOT / "quant" / "form4_sale_overhang_context.py"),
            repo_rel(REPO_ROOT / "quant" / "test_form4_sale_overhang_context.py"),
            repo_rel(Path(__file__)),
            repo_rel(OUT_BEFORE),
            repo_rel(OUT_AFTER),
        ],
        "verification_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_form4_sale_overhang_context.py -q",
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260707_018_form4_sale_overhang_reopen_progress_summary.py",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "post_run_reflection": (
            "Do not reopen or retune the Form4 sale-overhang alpha on context-row "
            "counts alone. A valid alpha retry still needs at least 25 closed "
            "forward rows, at least 8 high-sale-overhang closed rows, complete "
            "cash/SPY/QQQ replacement values, and max single-ticker closed-row "
            "share <= 40%, or a distinct new data source/gate shape."
        ),
    }
    write_json(OUT_BEFORE, before_payload)
    write_json(OUT_AFTER, after_payload)
    print(
        json.dumps(
            {
                "accepted": accepted,
                "before": repo_rel(OUT_BEFORE),
                "after": repo_rel(OUT_AFTER),
                "forward_reopen_progress": progress,
            },
            indent=2,
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0 if accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
