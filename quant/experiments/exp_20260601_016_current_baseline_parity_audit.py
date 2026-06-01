"""exp-20260601-016: current baseline parity audit.

Lane: measurement_repair.

This records the blocker that prevents retaining the positive
exp-20260601-015 accepted-consensus capacity alpha lead: the current code's
canonical three-window baseline no longer matches docs/backtesting.md's
accepted exp-20260517-009 baseline.

No JavaScript was used.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "quant") not in sys.path:
    sys.path.insert(0, str(ROOT / "quant"))

from backtester import BacktestEngine  # noqa: E402
from convergence import compute_expected_value_score  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260601-016"
STEM = "exp_20260601_016_current_baseline_parity_audit"

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
    },
}

DOCS_ACCEPTED_BASELINE = {
    "late_strong": {
        "expected_value_score": 5.1628,
        "total_pnl": 117_072.92,
        "total_trades": 18,
        "survival_rate": 0.8039,
        "max_drawdown_pct": 0.0665,
    },
    "mid_weak": {
        "expected_value_score": 2.1402,
        "total_pnl": 78_110.11,
        "total_trades": 21,
        "survival_rate": 0.7925,
        "max_drawdown_pct": 0.1119,
    },
    "old_thin": {
        "expected_value_score": 0.5911,
        "total_pnl": 39_667.96,
        "total_trades": 22,
        "survival_rate": 0.8667,
        "max_drawdown_pct": 0.1001,
    },
}

PRODUCTION_IMPACT = {
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "parity_test_added": False,
    "replay_only": False,
    "trade_enabled": False,
    "production_orders_changed": False,
    "alters_orders": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = ROOT / value
    return str(value.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _git_output(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    return (proc.stdout or proc.stderr or "").strip()


def _metric_row(result: dict[str, Any]) -> dict[str, Any]:
    result["expected_value_score"] = compute_expected_value_score(result)
    return {
        "expected_value_score": round(float(result.get("expected_value_score") or 0.0), 4),
        "total_pnl": round(float(result.get("total_pnl") or 0.0), 2),
        "strategy_total_return_pct": round(
            float((result.get("benchmarks") or {}).get("strategy_total_return_pct") or 0.0),
            4,
        ),
        "sharpe_daily": round(float(result.get("sharpe_daily") or 0.0), 4),
        "max_drawdown_pct": round(float(result.get("max_drawdown_pct") or 0.0), 4),
        "total_trades": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": round(float(result.get("survival_rate") or 0.0), 4),
    }


def _run_current_baseline() -> dict[str, dict[str, Any]]:
    universe = get_universe()
    config = {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True}
    rows: dict[str, dict[str, Any]] = {}
    for label, spec in WINDOWS.items():
        engine = BacktestEngine(
            universe=universe,
            start=spec["start"],
            end=spec["end"],
            config=config,
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=spec["snapshot"],
            include_oracle_diagnostics=False,
        )
        result = engine.run()
        if "error" in result:
            rows[label] = {"error": result["error"]}
        else:
            rows[label] = _metric_row(result)
    return rows


def _compare(current: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows: dict[str, dict[str, Any]] = {}
    for label, expected in DOCS_ACCEPTED_BASELINE.items():
        actual = current.get(label) or {}
        ev_delta = round(
            float(actual.get("expected_value_score") or 0.0)
            - float(expected["expected_value_score"]),
            6,
        )
        pnl_delta = round(
            float(actual.get("total_pnl") or 0.0) - float(expected["total_pnl"]),
            2,
        )
        trade_delta = (
            int(actual.get("total_trades") or 0) - int(expected["total_trades"])
        )
        rows[label] = {
            "docs": expected,
            "current": actual,
            "expected_value_score_delta": ev_delta,
            "total_pnl_delta": pnl_delta,
            "trade_count_delta": trade_delta,
            "matches_docs_baseline": abs(ev_delta) <= 0.01 and abs(pnl_delta) <= 100.0,
        }
    docs_ev = sum(row["expected_value_score"] for row in DOCS_ACCEPTED_BASELINE.values())
    docs_pnl = sum(row["total_pnl"] for row in DOCS_ACCEPTED_BASELINE.values())
    current_ev = sum(float((current.get(label) or {}).get("expected_value_score") or 0.0) for label in WINDOWS)
    current_pnl = sum(float((current.get(label) or {}).get("total_pnl") or 0.0) for label in WINDOWS)
    return {
        "rows": rows,
        "aggregate": {
            "docs_expected_value_score": round(docs_ev, 4),
            "current_expected_value_score": round(current_ev, 4),
            "expected_value_score_delta": round(current_ev - docs_ev, 6),
            "docs_total_pnl": round(docs_pnl, 2),
            "current_total_pnl": round(current_pnl, 2),
            "total_pnl_delta": round(current_pnl - docs_pnl, 2),
        },
        "matches_all_windows": all(row["matches_docs_baseline"] for row in rows.values()),
    }


def _audit_open_positions() -> dict[str, Any]:
    path = ROOT / "operator_inputs" / "open_positions.json"
    if not path.exists():
        return {"passed": False, "path": _repo_rel(path), "reason": "missing_file"}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        return {"passed": False, "path": _repo_rel(path), "reason": str(exc)}
    positions = data.get("positions") if isinstance(data, dict) else data
    if not isinstance(positions, list):
        return {"passed": False, "path": _repo_rel(path), "reason": "positions_not_list"}
    missing = []
    for idx, position in enumerate(positions):
        if not isinstance(position, dict):
            missing.append({"index": idx, "field": "position_not_dict"})
            continue
        for field in ("entry_date", "target_price"):
            if position.get(field) in (None, ""):
                missing.append(
                    {
                        "index": idx,
                        "ticker": position.get("ticker"),
                        "field": field,
                    }
                )
    return {
        "passed": not missing,
        "path": _repo_rel(path),
        "position_count": len(positions),
        "missing_required_fields": missing,
    }


def _write_card(payload: dict[str, Any]) -> None:
    comp = payload["baseline_comparison"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} current baseline parity audit",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Docs accepted aggregate EV/PnL: `{comp['docs_expected_value_score']:.4f}` / `${comp['docs_total_pnl']:,.2f}`",
        f"- Current aggregate EV/PnL: `{comp['current_expected_value_score']:.4f}` / `${comp['current_total_pnl']:,.2f}`",
        f"- Aggregate drift: `{comp['expected_value_score_delta']:+.4f}` EV / `${comp['total_pnl_delta']:+,.2f}`",
        f"- Blocks alpha retention: `{payload['blocks_alpha_retention']}`",
        "",
        "## Window Drift",
        "",
        "| window | docs EV | current EV | EV delta | docs PnL | current PnL | PnL delta | trade delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["baseline_comparison"]["rows"].items():
        docs = row["docs"]
        current = row["current"]
        lines.append(
            f"| {label} | {docs['expected_value_score']:.4f} | "
            f"{current.get('expected_value_score', 0):.4f} | "
            f"{row['expected_value_score_delta']:+.4f} | "
            f"${docs['total_pnl']:,.2f} | ${current.get('total_pnl', 0):,.2f} | "
            f"${row['total_pnl_delta']:+,.2f} | {row['trade_count_delta']:+d} |"
        )
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            payload["conclusion"],
            "",
            "This is a measurement repair artifact only. It changed no entries, exits, ranking, sizing, LLM/news path, watchlist, or live/default orders.",
            "",
        ]
    )
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.write_text("\n".join(lines), encoding="utf-8")


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket: dict[str, Any] = {}
    if TICKET_JSON.exists():
        ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
    ticket.update(
        {
            "status": "accepted",
            "decision": payload["decision"],
            "completed_at": payload["completed_at"],
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "production_impact": PRODUCTION_IMPACT,
            "result": payload["baseline_comparison"]["aggregate"],
            "blocks_alpha_retention": payload["blocks_alpha_retention"],
        }
    )
    _write_json(TICKET_JSON, ticket)


def run() -> dict[str, Any]:
    completed_at = _utc_now()
    current = _run_current_baseline()
    comparison = _compare(current)
    gate2 = _audit_open_positions()
    blocks_alpha = not comparison["matches_all_windows"]
    conclusion = (
        "Current-code canonical three-window baseline does not match the "
        "docs/backtesting.md accepted exp-20260517-009 baseline. Positive "
        "alpha leads such as exp-20260601-015 must stay observed-only until "
        "the baseline drift is explained or the accepted baseline is updated "
        "through a dedicated parity decision."
        if blocks_alpha
        else "Current-code canonical baseline matches the accepted docs baseline."
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "lane": "measurement_repair",
        "created_at": completed_at,
        "completed_at": completed_at,
        "hypothesis": (
            "Current-code canonical three-window baseline mismatches "
            "docs/backtesting.md accepted baseline, blocking retention of "
            "positive accepted-consensus capacity alpha leads."
        ),
        "changed_variable": "current-code canonical three-window baseline parity audit",
        "single_causal_variable": "current-code canonical three-window baseline parity audit",
        "alpha_hypothesis_blocked": {
            "candidate_alpha": "exp-20260601-015 accepted free-data consensus no-core-entry-day capacity gate",
            "candidate_alpha_result": {
                "aggregate_ev_delta": 0.89,
                "aggregate_pnl_delta": 20_028.83,
                "windows_improved": 3,
                "target_trade_count": 38,
            },
            "blocking_item": "baseline_matches_docs=false",
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical command semantics",
            "windows": WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "regime_aware_exit": True,
            "replay_partial_reduces": True,
            "oracle_diagnostics": False,
            "writes_backtest_results_file": False,
        },
        "gate1": {
            "passed": comparison["matches_all_windows"],
            "current_baseline": current,
            "accepted_baseline": DOCS_ACCEPTED_BASELINE,
        },
        "gate2": gate2,
        "gate3": {
            "passed": min(float(row.get("survival_rate") or 0.0) for row in current.values()) >= 0.05,
            "survival_by_window": {
                label: row.get("survival_rate") for label, row in current.items()
            },
        },
        "baseline_comparison": comparison,
        "blocks_alpha_retention": blocks_alpha,
        "decision": "accepted_measurement_repair_baseline_blocker_recorded",
        "conclusion": conclusion,
        "production_impact": PRODUCTION_IMPACT,
        "dirty_context": {
            "git_head": _git_output(["rev-parse", "--short", "HEAD"]),
            "git_status_short": _git_output(["status", "--short"]).splitlines(),
        },
        "next_alpha_step": (
            "Resolve or explicitly accept the current-code baseline drift, then "
            "rerun/promote exp-20260601-015 only through a shared adapter if the "
            "same no-core capacity gate reproduces on the clean accepted baseline."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(TICKET_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_card(payload)
    _update_ticket(payload)
    return payload


def main() -> None:
    payload = run()
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "blocks_alpha_retention": payload["blocks_alpha_retention"],
                "aggregate": payload["baseline_comparison"]["aggregate"],
                "artifact": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
