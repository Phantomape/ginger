"""Audit fixed-window backtest result artifacts for experiment comparability.

This is a read-only measurement artifact. It does not run the backtester or
change strategy behavior; it reports whether existing result files are ready to
serve as reproducible baselines for fixed-window alpha experiments.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FIXED_WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
    },
}

REQUIRED_METRICS = [
    "period",
    "trading_days",
    "total_trades",
    "win_rate",
    "total_pnl",
    "sharpe_daily",
    "max_drawdown_pct",
    "signals_generated",
    "signals_survived",
    "survival_rate",
    "expected_value_score",
    "by_strategy",
    "benchmarks",
    "known_biases",
    "capital_efficiency",
    "single_window_quality",
    "trades",
]


@dataclass(frozen=True)
class ResultArtifact:
    path: Path
    data: dict[str, Any]

    @property
    def period(self) -> str:
        return str(self.data.get("period", ""))

    @property
    def mtime(self) -> float:
        return self.path.stat().st_mtime


def normalize_period(period: str) -> str:
    return re.sub(r"\s+", " ", period.replace("->", "→")).strip()


def expected_period(start: str, end: str) -> str:
    return f"{start} → {end}"


def window_label_for_period(period: str) -> str | None:
    normalized = normalize_period(period)
    for label, spec in FIXED_WINDOWS.items():
        if normalized == expected_period(spec["start"], spec["end"]):
            return label
    return None


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def has_snapshot_provenance(data: dict[str, Any]) -> bool:
    haystack = json.dumps(
        {
            "diagnostics": data.get("diagnostics"),
            "known_biases": data.get("known_biases"),
            "caveats": data.get("caveats"),
            "period": data.get("period"),
        },
        ensure_ascii=False,
        sort_keys=True,
    ).lower()
    return "ohlcv_snapshot" in haystack or "snapshot" in haystack


def summarize_result(artifact: ResultArtifact) -> dict[str, Any]:
    data = artifact.data
    missing_metrics = [field for field in REQUIRED_METRICS if field not in data]
    trades = data.get("trades")
    trade_count_matches = (
        isinstance(trades, list)
        and isinstance(data.get("total_trades"), int)
        and len(trades) == data.get("total_trades")
    )
    return {
        "path": artifact.path.as_posix(),
        "period": artifact.period,
        "window_label": window_label_for_period(artifact.period),
        "modified_utc": datetime.fromtimestamp(
            artifact.mtime, timezone.utc
        ).isoformat(),
        "missing_required_metrics": missing_metrics,
        "trade_count_matches_trades_len": trade_count_matches,
        "has_snapshot_provenance": has_snapshot_provenance(data),
        "metrics": {
            "expected_value_score": data.get("expected_value_score"),
            "sharpe_daily": data.get("sharpe_daily"),
            "max_drawdown_pct": data.get("max_drawdown_pct"),
            "total_pnl": data.get("total_pnl"),
            "win_rate": data.get("win_rate"),
            "total_trades": data.get("total_trades"),
            "survival_rate": data.get("survival_rate"),
        },
    }


def parse_backtesting_doc(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    commands = [
        line.strip()
        for line in text.splitlines()
        if "quant\\backtester.py" in line or "quant/backtester.py" in line
    ]
    snapshots = {
        spec["snapshot"]: Path(spec["snapshot"]).exists()
        for spec in FIXED_WINDOWS.values()
    }
    return {
        "path": path.as_posix(),
        "exists": path.exists(),
        "fixed_window_command_count": sum(
            "--ohlcv-snapshot" in command for command in commands
        ),
        "snapshot_files_exist": snapshots,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-glob", default="data/backtest_results_*.json")
    parser.add_argument("--ticket", default="docs/experiments/tickets/exp-20260428-015.json")
    parser.add_argument("--backtesting-doc", default="docs/backtesting.md")
    parser.add_argument("--output", default="data/exp_baseline_reproducibility_audit.json")
    args = parser.parse_args()

    result_artifacts = []
    unreadable = []
    for path in sorted(Path().glob(args.results_glob)):
        data = load_json(path)
        if data is None:
            unreadable.append(path.as_posix())
            continue
        result_artifacts.append(ResultArtifact(path=path, data=data))

    by_window: dict[str, list[dict[str, Any]]] = {label: [] for label in FIXED_WINDOWS}
    non_fixed = []
    for artifact in result_artifacts:
        summary = summarize_result(artifact)
        label = summary["window_label"]
        if label:
            by_window[label].append(summary)
        else:
            non_fixed.append(summary)

    latest_by_window = {}
    for label, summaries in by_window.items():
        latest_by_window[label] = max(
            summaries,
            key=lambda row: row["modified_utc"],
            default=None,
        )

    ticket_data = load_json(Path(args.ticket)) or {}
    ticket_baseline = ticket_data.get("baseline_result_file")
    ticket_baseline_path = Path(ticket_baseline) if ticket_baseline else None
    ticket_baseline_data = load_json(ticket_baseline_path) if ticket_baseline_path else None
    ticket_baseline_label = (
        window_label_for_period(str(ticket_baseline_data.get("period", "")))
        if ticket_baseline_data
        else None
    )

    issues = []
    for label, latest in latest_by_window.items():
        if latest is None:
            issues.append(f"missing_fixed_window_result:{label}")
        elif latest["missing_required_metrics"]:
            issues.append(f"missing_required_metrics:{label}")
        if latest is not None and not latest["has_snapshot_provenance"]:
            issues.append(f"missing_snapshot_provenance:{label}")
    if ticket_baseline_label and len(FIXED_WINDOWS) > 1:
        issues.append(
            "ticket_baseline_is_single_window:"
            f"{ticket_baseline_label};multi_window_comparison_needs_all_windows"
        )
    if not ticket_baseline_label:
        issues.append("ticket_baseline_not_fixed_window_or_unreadable")

    output = {
        "experiment_id": "exp-20260428-015",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "lane": "measurement_repair",
        "change_type": "measurement_instrumentation",
        "single_causal_variable": "fixed-window baseline result artifact consistency",
        "alpha_hypothesis_released": (
            "multi-window alpha promotion tests can use a preflight baseline "
            "manifest to avoid comparing against missing, stale, or single-window "
            "result artifacts"
        ),
        "strategy_behavior_changed": False,
        "backtesting_doc": parse_backtesting_doc(Path(args.backtesting_doc)),
        "fixed_windows": FIXED_WINDOWS,
        "required_metrics": REQUIRED_METRICS,
        "result_file_count": len(result_artifacts),
        "unreadable_result_files": unreadable,
        "latest_fixed_window_results": latest_by_window,
        "fixed_window_result_counts": {
            label: len(rows) for label, rows in by_window.items()
        },
        "non_fixed_window_result_count": len(non_fixed),
        "ticket_baseline": {
            "ticket_path": Path(args.ticket).as_posix(),
            "baseline_result_file": ticket_baseline,
            "baseline_window_label": ticket_baseline_label,
        },
        "issues": issues,
        "measurement_status": "ready_with_warnings" if issues else "ready",
        "next_alpha_experiment_less_blocked": (
            "any fixed-window alpha_discovery promotion or production wiring "
            "test that needs judge-ready before/after artifacts"
        ),
    }

    out_path = Path(args.output)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(out_path.as_posix())
    print(json.dumps({"measurement_status": output["measurement_status"], "issues": issues}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
