"""Compute an auditable Deflated Sharpe report from an explicit trial panel.

Input JSON schema::

    {
      "selected_config_id": "winner-v3",
      "expected_attempt_count": 12,
      "selection_pool_complete": true,
      "expected_return_dates": ["2026-01-05", "2026-01-06"],
      "periods_per_year": 252,
      "trials": [ ... complete aligned trial rows ... ]
    }

Trial-row requirements are enforced by ``quant.sharpe_inference``.  An
incomplete panel produces ``not_computable`` and no numeric DSR.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant.sharpe_inference import evaluate_deflated_sharpe_trial_panel  # noqa: E402


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _gate5_report(panel_result: dict[str, Any]) -> dict[str, Any]:
    if panel_result.get("status") != "computable":
        return {
            "status": "not_computable",
            "selection_pool_complete": False,
            "selection_scope_id": None,
            "panel_hash": None,
            "dsr_probability": None,
            "reason_codes": list(panel_result.get("reason_codes") or []),
        }

    context = panel_result.get("context") or {}
    dsr = panel_result.get("dsr") or {}
    probability = dsr.get("probability") if dsr.get("status") == "computable" else None
    if probability is None:
        return {
            "status": "not_computable",
            "selection_pool_complete": False,
            "selection_scope_id": context.get("selection_scope"),
            "panel_hash": panel_result.get("panel_sha256"),
            "dsr_probability": None,
            "reason_codes": list(dsr.get("reason_codes") or ["dsr_probability_missing"]),
        }
    return {
        "status": "computed",
        "selection_pool_complete": True,
        "selection_scope_id": context.get("selection_scope"),
        "panel_hash": panel_result.get("panel_sha256"),
        "dsr_probability": probability,
        "threshold": 0.95,
        "passes_live_threshold": probability >= 0.95,
    }


def build_report(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        panel_result = {
            "status": "not_computable",
            "reason_codes": ["input_payload_not_an_object"],
            "dsr": {
                "status": "not_computable",
                "reason_codes": ["input_payload_not_an_object"],
            },
        }
    else:
        panel_result = evaluate_deflated_sharpe_trial_panel(
            payload.get("trials"),
            selected_config_id=payload.get("selected_config_id"),
            expected_attempt_count=payload.get("expected_attempt_count"),
            selection_pool_complete=payload.get("selection_pool_complete"),
            expected_return_dates=payload.get("expected_return_dates"),
            periods_per_year=payload.get("periods_per_year", 252),
        )
    return {
        "schema_version": 1,
        "status": panel_result.get("status"),
        "panel_input": payload if isinstance(payload, dict) else None,
        "panel_result": panel_result,
        "gate5_dsr_report": _gate5_report(panel_result),
        "interpretation": (
            "DSR is a selection-bias-adjusted probability statistic, not a Sharpe "
            "value, future-profit probability, PBO estimate, or benchmark outperformance test."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Complete trial-panel JSON")
    parser.add_argument("--output", type=Path, help="Optional report JSON path")
    args = parser.parse_args(argv)

    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        report = build_report(None)
        report["input_error"] = str(exc)
    else:
        report = build_report(payload)

    if args.output:
        _atomic_write_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if report["status"] == "computable" else 2


if __name__ == "__main__":
    raise SystemExit(main())
