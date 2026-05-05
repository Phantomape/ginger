"""exp-20260504-012 SEC default-off forward queue policy.

This implements the next step after exp-20260504-011: the SEC negative-language
negative-reaction packet becomes production-visible as an observe-only queue.
It does not alter core entries, ranking, sizing, exits, or orders.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
DOCS_DIR = REPO_ROOT / "docs"

if str(REPO_ROOT / "quant") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "quant"))

from experiments.exp_20260504_008_sec_negative_reaction_absorption import BASELINE_METRICS, WINDOWS  # noqa: E402
from experiments.exp_20260504_010_sec_event_sleeve_backtest import TEXT_PATH, build_primary_candidates  # noqa: E402
from sec_event_queue import (  # noqa: E402
    QUEUE_NAME,
    RULE_VERSION,
    build_forward_queue_from_sec_filing_text,
    build_sec_event_queue,
    load_sec_filing_text_rows,
)


EXPERIMENT_ID = "exp-20260504-012"
OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "sec_forward_queue_policy.json"
LOG_JSON = DOCS_DIR / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = DOCS_DIR / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REPORT_MD = DOCS_DIR / "non_ohlcv_data_audit" / "sec_forward_queue_policy_20260504.md"
EXPERIMENT_LOG = DOCS_DIR / "experiment_log.jsonl"
CURRENT_ASOF = "2026-05-04"


def _safe(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: _safe(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_safe(value) for value in payload]
    if isinstance(payload, float) and not math.isfinite(payload):
        return None
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_safe(payload), indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def _historical_policy_parity() -> dict[str, Any]:
    expected, price_map = build_primary_candidates()
    text_rows = load_sec_filing_text_rows(TEXT_PATH)
    replayed: list[dict[str, Any]] = []
    by_asof: dict[str, int] = {}

    for as_of in sorted({row["usable_trade_date"] for row in expected}):
        queue = build_sec_event_queue(
            text_rows,
            as_of=as_of,
            ohlcv_by_ticker=price_map,
            spy_ohlcv=price_map["SPY"],
        )
        by_asof[as_of] = queue["candidate_count"]
        replayed.extend(queue["candidates"])

    expected_keys = {
        (row["ticker"], row["accession_number"], row["usable_trade_date"])
        for row in expected
    }
    replayed_keys = {
        (row["ticker"], row["accession_number"], row["usable_trade_date"])
        for row in replayed
    }
    return {
        "source_experiment": "exp-20260504-010",
        "expected_packet_count": len(expected),
        "shared_queue_replay_count": len(replayed),
        "matched_expected_count": len(expected_keys & replayed_keys),
        "missing_expected": sorted(list(expected_keys - replayed_keys)),
        "extra_replayed": sorted(list(replayed_keys - expected_keys)),
        "candidate_dates": len(by_asof),
        "candidate_count_by_asof": by_asof,
        "passed": replayed_keys == expected_keys,
    }


def build_payload() -> dict[str, Any]:
    parity = _historical_policy_parity()
    current_smoke = build_forward_queue_from_sec_filing_text(
        data_dir=DATA_DIR / "non_ohlcv",
        as_of=CURRENT_ASOF,
        ohlcv_by_ticker={},
        spy_ohlcv=[],
        core_signals=[],
    )
    status = "forward_queue_policy_ready_default_off" if parity["passed"] else "forward_queue_policy_blocked"
    decision_rationale = (
        "The shared SEC queue policy exactly replays the frozen exp-010 packet and is now safe to observe default-off."
        if parity["passed"]
        else "The shared SEC queue policy does not replay exp-010 exactly; do not expose it in production."
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "lane": "alpha_search",
        "status": status,
        "decision": status,
        "hypothesis": (
            "A production-visible, default-off SEC negative-reaction queue can accumulate forward replacement-value "
            "samples without changing orders or core strategy behavior."
        ),
        "alpha_hypothesis": {
            "category": "event_source_forward_queue",
            "entry_or_ranking": "entry_source_observation",
            "text": (
                "Recoverable-pressure SEC 8-K Item 2.02 events may become useful once forward replacement value is "
                "logged against frozen A/B alternatives."
            ),
        },
        "change_type": "default_off_forward_event_queue",
        "single_causal_variable": "production-visible observe-only SEC negative-reaction event queue",
        "historical_experiment_check": {
            "prior_same_family": {
                "exp-20260504-010": "standalone sleeve was positive but concentrated",
                "exp-20260504-011": "replacement value was inconclusive and blocked core promotion",
            },
            "why_this_is_not_repeat": (
                "This does not rerun replacement value or tune thresholds; it adds the observe-only forward queue "
                "needed to collect out-of-sample replacement attribution."
            ),
            "mechanism_insight_check": (
                "The playbook allows a default-off queue but forbids direct core-slot promotion, keyword tuning, "
                "and reaction-threshold sweeps."
            ),
        },
        "parameters": {
            "queue_name": QUEUE_NAME,
            "rule_version": RULE_VERSION,
            "packet_rule": "8-K Item 2.02 AND language_bucket == negative_language AND reaction_excess_return < 0",
            "enabled": False,
            "primary_horizon_trading_days": 10,
            "entry_timing": "next_trading_day_open_after_reaction_close",
            "locked_variables": [
                "keyword phrase list",
                "reaction threshold at < 0",
                "core A/B entries",
                "core A/B ranking",
                "core A/B sizing",
                "core exits",
                "LLM/news replay",
            ],
        },
        "date_range": {
            "primary": "2025-10-23 -> 2026-04-21",
            "secondary": ["2025-04-23 -> 2025-10-22", "2024-10-02 -> 2025-04-22"],
        },
        "market_regime_summary": {label: cfg["state_note"] for label, cfg in WINDOWS.items()},
        "before_metrics": BASELINE_METRICS,
        "after_metrics": BASELINE_METRICS,
        "expected_value_score_delta": 0.0,
        "production_impact": {
            "shared_policy_changed": True,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "replay_only": False,
            "parity_test_added": True,
            "production_signal_path_changed": False,
            "production_impact": "default_off_observe_only_event_queue_no_orders_changed",
        },
        "gate4": {
            "applicable": False,
            "core_strategy_changed": False,
            "result": "not_applicable_default_off_observe_only_queue",
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "policy_parity": parity,
        "production_smoke": {
            "as_of": CURRENT_ASOF,
            "enabled": current_smoke["enabled"],
            "candidate_count": current_smoke["candidate_count"],
            "data_source": current_smoke["data_source"],
            "production_impact": current_smoke["production_impact"],
        },
        "decision_rationale": decision_rationale,
        "next_retry_requires": [
            "Do not let this queue alter orders, sizing, or A/B ranking.",
            "Collect closed forward replacement-value outcomes with frozen alternatives.",
            "Only consider promotion after multiple out-of-sample queue candidates beat same-day alternatives.",
        ],
        "related_files": [
            _repo_rel("quant/sec_event_queue.py"),
            _repo_rel("quant/run.py"),
            _repo_rel("quant/report_generator.py"),
            _repo_rel("quant/test_sec_event_queue.py"),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(REPORT_MD),
        ],
    }
    return _safe(payload)


def build_report(payload: dict[str, Any]) -> str:
    parity = payload["policy_parity"]
    smoke = payload["production_smoke"]
    return "\n".join(
        [
            "# SEC Forward Queue Policy",
            "",
            f"Experiment: `{EXPERIMENT_ID}`",
            f"Status: `{payload['status']}`",
            "",
            "## Headline",
            "",
            payload["decision_rationale"],
            "",
            "## Policy Parity",
            "",
            f"- Expected exp-010 packets: `{parity['expected_packet_count']}`",
            f"- Shared queue replay packets: `{parity['shared_queue_replay_count']}`",
            f"- Matched packets: `{parity['matched_expected_count']}`",
            f"- Passed: `{parity['passed']}`",
            "",
            "## Production Smoke",
            "",
            f"- As of: `{smoke['as_of']}`",
            f"- Enabled: `{smoke['enabled']}`",
            f"- Candidates: `{smoke['candidate_count']}`",
            f"- Source status: `{smoke['data_source'].get('status')}`",
            "",
            "## Guardrail",
            "",
            "This queue is observe-only. It must not alter orders, sizing, A/B ranking, or core backtest metrics.",
            "",
        ]
    )


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "title": "SEC negative-reaction default-off forward queue",
        "summary": payload["decision_rationale"],
        "policy_parity": payload["policy_parity"],
        "production_impact": payload["production_impact"],
        "next_retry_requires": payload["next_retry_requires"],
    }
    _write_json(TICKET_JSON, ticket)
    _write_text(REPORT_MD, build_report(payload))

    compact = dict(payload)
    existing_lines = (
        EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        if EXPERIMENT_LOG.exists()
        else []
    )
    kept_lines = [
        line
        for line in existing_lines
        if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
        and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
    ]
    kept_lines.append(json.dumps(compact, ensure_ascii=False, separators=(",", ":")))
    EXPERIMENT_LOG.write_text("\n".join(kept_lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "policy_parity": payload["policy_parity"],
                "production_smoke": payload["production_smoke"],
                "production_impact": payload["production_impact"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    print(f"wrote: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
