"""Closeout artifact for exp-20260527-001 Kova data sidecar."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "exp-20260527-001"
STEM = "kova_free_data_sidecar"


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl_once(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        needle = f'"experiment_id": "{EXPERIMENT_ID}"'
        compact = f'"experiment_id":"{EXPERIMENT_ID}"'
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if needle in line or compact in line:
                return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _build_payload() -> dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    sample_path = REPO_ROOT / "data" / "kova" / "snapshots" / "kova_data_snapshot_20260421.json"
    sample = _load_json(sample_path)
    artifacts = {
        "json": f"data/experiments/{EXPERIMENT_ID}/{STEM}.json",
        "log": f"experiments/logs/{EXPERIMENT_ID}.json",
        "ticket": f"experiments/tickets/{EXPERIMENT_ID}.json",
        "docs_ticket": f"docs/experiments/tickets/{EXPERIMENT_ID}.json",
        "markdown": f"experiments/artifacts/{EXPERIMENT_ID}_{STEM}.md",
        "sample_snapshot": _repo_rel(sample_path),
    }
    related_files = [
        "quant/kova_data_sidecar.py",
        "quant/test_kova_data_sidecar.py",
        "scripts/run_kova_data_refresh.py",
        "docs/data_edge_context_layers.md",
        "docs/current_state.md",
        "docs/alpha-optimization-playbook.md",
        "data/kova/snapshots/kova_data_snapshot_20260421.json",
        "data/kova/fundamentals/companyfacts_growth_20260421.jsonl",
        "data/kova/rs_proxy/rs_proxy_20260421.jsonl",
        "data/kova/intraday/intraday_ohlcv_20260421.jsonl",
        "data/kova/institutional/sec13f_ownership_20260421.jsonl",
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": "accepted_measurement_repair",
        "decision": "accepted_default_off_kova_free_data_sidecar",
        "created_at": now,
        "lane": "measurement_repair",
        "registry_lane": "measurement_repair",
        "change_type": "measurement_repair_for_alpha_search",
        "trial_family": "kova_free_data_backfill_and_forward_snapshot",
        "trial_variant_id": "intraday_fundamental_13f_rs_sidecar_v1",
        "changed_variable": "kova_free_data_sidecar_available_v1",
        "single_causal_variable": "kova_free_data_sidecar_available_v1",
        "alpha_hypothesis": (
            "Kova intraday, fundamental-growth, institutional-ownership, and RS "
            "surfaces should become PIT sidecars before any new VCP alpha gate or "
            "lifecycle replay is attempted."
        ),
        "history_check": {
            "nearby_prior_experiments": [
                "exp-20260526-022",
                "exp-20260526-023",
                "exp-20260526-024",
                "exp-20260526-025",
                "exp-20260526-037",
            ],
            "result": (
                "Prior Kova daily-OHLCV attributions were not actionable; "
                "remaining ideas needed data surfaces."
            ),
        },
        "gate1": {
            "baseline": "data/experiments/exp-20260526-037/kova_unavailable_feature_readiness_audit.json",
            "core_logic_changed": False,
        },
        "gate2": {
            "fields_added": [
                "intraday_ohlcv",
                "sec_companyfacts_growth",
                "sec13f_institutional_ownership",
                "ginger_rs_proxy",
            ],
            "pit_join_key": "ticker + asof_date <= signal_date",
            "sample_snapshot": sample,
        },
        "gate3": {
            "survival_impact": "none",
            "reason": "No filter is added.",
        },
        "gate4": {
            "promotion_allowed": False,
            "reason": "Data sidecar only; future alpha use requires separate Gate 1-4 replay.",
        },
        "sample_run": {
            "command": (
                ".\\.venv\\Scripts\\python.exe -B scripts\\run_kova_data_refresh.py "
                "--as-of 2026-04-21 --tickers AAPL MSFT NVDA "
                "--ohlcv-snapshot data\\ohlcv\\ohlcv_snapshot_20251023_20260421.json"
            ),
            "snapshot": sample,
        },
        "test_results": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_kova_data_sidecar.py -> 6 passed",
            ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\kova_data_sidecar.py scripts\\run_kova_data_refresh.py -> passed",
        ],
        "production_impact": {
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "default_off_data_only": True,
        },
        "artifacts": artifacts,
        "related_files": related_files,
        "summary": (
            "Added a default-off Kova data sidecar with Alpha Vantage intraday "
            "support, SEC Companyfacts growth derivation, SEC 13F zip ingestion "
            "with optional CUSIP map, OHLCV RS proxy, as-of loader, CLI runner, "
            "tests, and a local sample snapshot."
        ),
    }


def _build_ticket(payload: dict[str, Any]) -> dict[str, Any]:
    artifacts = payload["artifacts"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "owner": "codex-kova",
        "hypothesis": payload["alpha_hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": "kova_data_sidecar",
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": payload["single_causal_variable"],
        "changed_variable": payload["changed_variable"],
        "baseline_result_file": payload["gate1"]["baseline"],
        "allowed_write_scope": payload["related_files"]
        + [
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
            artifacts["markdown"],
            artifacts["json"],
            artifacts["log"],
            artifacts["ticket"],
            artifacts["docs_ticket"],
        ],
        "must_not_touch": [
            "quant/run.py",
            "quant/backtester.py",
            "quant/volatility_contraction_paper_sleeve.py",
        ],
        "locked_variables": [
            "core entries",
            "ranking",
            "sizing",
            "exits",
            "LLM/news",
            "universe",
            "live/default orders",
            "VCP rules",
        ],
        "evaluation_windows": [
            {"start": "2025-10-23", "end": "2026-04-21"},
            {"start": "2025-04-23", "end": "2025-10-22"},
            {"start": "2024-10-02", "end": "2025-04-22"},
        ],
        "acceptance_rule": (
            "Sidecar collectors/loaders are tested, default-off, PIT-as-of tagged, "
            "and do not alter orders; alpha promotion requires later Gate 1-4 experiments."
        ),
        "created_at": payload["created_at"],
        "completed_at": payload["created_at"],
        "result": {
            "decision": payload["decision"],
            "summary": payload["summary"],
            "artifact": artifacts["markdown"],
            "json": artifacts["json"],
        },
        "summary": payload["summary"],
        "artifacts": artifacts,
        "repro_command": (
            ".\\.venv\\Scripts\\python.exe -B scripts\\run_kova_data_refresh.py "
            "--as-of YYYY-MM-DD --tickers AAPL MSFT NVDA "
            "--ohlcv-snapshot data\\ohlcv\\ohlcv_snapshot_YYYYMMDD_YYYYMMDD.json"
        ),
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    sample = payload["sample_run"]["snapshot"]
    return "\n".join(
        [
            "# exp-20260527-001 Kova Free Data Sidecar",
            "",
            "## Decision",
            "",
            "`accepted_default_off_kova_free_data_sidecar`. This is measurement repair only: no strategy, ranking, sizing, exit, LLM/news, universe, or order path consumes the fields.",
            "",
            "## What Was Added",
            "",
            "- `quant/kova_data_sidecar.py`: Alpha Vantage intraday parser/fetcher, SEC Companyfacts growth derivation, SEC 13F zip parser, Ginger RS proxy, and as-of loader.",
            "- `scripts/run_kova_data_refresh.py`: forward/backfill refresh entry point.",
            "- `quant/test_kova_data_sidecar.py`: PIT and parser tests.",
            "",
            "## Sample Run",
            "",
            f"`2026-04-21` sample for `AAPL/MSFT/NVDA`: fundamentals rows `{sample['fundamental_growth']['rows_written']}`, RS rows `{sample['rs_proxy']['rows_written']}`, intraday skipped rows `{sample['intraday_ohlcv']['rows_written']}`, 13F skipped rows `{sample['institutional_ownership']['rows_written']}`.",
            "",
            "Intraday needs `ALPHA_VANTAGE_API_KEY`; 13F needs a supplied/downloaded SEC 13F zip and CUSIP map for ticker joins.",
            "",
            "## Verification",
            "",
            "- `pytest quant\\test_kova_data_sidecar.py`: 6 passed.",
            "- `py_compile quant\\kova_data_sidecar.py scripts\\run_kova_data_refresh.py`: passed.",
            "",
            "## Next Use",
            "",
            "Future experiments may join these rows with `ticker` and `asof_date <= signal_date`. Any use as a VCP gate, stop/R policy, or pyramid/add-on rule needs a separate Gate 1-4 replay.",
            "",
        ]
    )


def _update_registry(payload: dict[str, Any]) -> None:
    registry_path = REPO_ROOT / "docs" / "experiment_registry.json"
    registry = _load_json(registry_path)
    experiments = registry.setdefault("experiments", [])
    result = {
        "decision": payload["decision"],
        "artifact": payload["artifacts"]["markdown"],
        "json": payload["artifacts"]["json"],
        "summary": payload["summary"],
    }
    updated = False
    for entry in experiments:
        if entry.get("experiment_id") == EXPERIMENT_ID:
            entry.update(
                {
                    "status": payload["status"],
                    "lane": payload["registry_lane"],
                    "owner": "codex-kova",
                    "hypothesis": payload["alpha_hypothesis"],
                    "ticket_file": payload["artifacts"]["ticket"],
                    "updated_at": payload["created_at"],
                    "completed_at": payload["created_at"],
                    "result": result,
                }
            )
            updated = True
            break
    if not updated:
        experiments.append(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "lane": payload["registry_lane"],
                "owner": "codex-kova",
                "hypothesis": payload["alpha_hypothesis"],
                "ticket_file": payload["artifacts"]["ticket"],
                "updated_at": payload["created_at"],
                "completed_at": payload["created_at"],
                "result": result,
            }
        )
    registry["updated_at"] = payload["created_at"]
    _write_json(registry_path, registry)


def main() -> None:
    payload = _build_payload()
    ticket = _build_ticket(payload)
    artifacts = payload["artifacts"]
    _write_json(REPO_ROOT / artifacts["json"], payload)
    _write_json(REPO_ROOT / artifacts["log"], payload)
    _write_json(REPO_ROOT / artifacts["ticket"], ticket)
    _write_json(REPO_ROOT / artifacts["docs_ticket"], ticket)
    md_path = REPO_ROOT / artifacts["markdown"]
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_build_markdown(payload), encoding="utf-8")
    _append_jsonl_once(REPO_ROOT / "docs" / "experiment_log.jsonl", payload)
    _update_registry(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "artifact": artifacts["markdown"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
