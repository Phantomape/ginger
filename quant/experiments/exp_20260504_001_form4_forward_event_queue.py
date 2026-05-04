"""Record the Form 4 forward event queue alpha scout.

This experiment intentionally does not promote Form 4 events into entries,
ranking, sizing, or exits. It adds a production-visible, default-off queue so
future large insider-purchase events can be observed with frozen alternatives
before any strategy promotion.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
DOCS_DIR = REPO_ROOT / "docs"

if str(REPO_ROOT / "quant") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "quant"))

from form4_event_queue import (  # noqa: E402
    FORWARD_QUEUE_MIN_PURCHASE_VALUE,
    PRIMARY_HORIZON_TRADING_DAYS,
    QUEUE_NAME,
    RULE_VERSION,
    build_forward_queue_from_transactions,
)


EXP_ID = "exp-20260504-001"
OUT_DIR = DATA_DIR / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / "form4_forward_event_queue.json"
LOG_JSON = DOCS_DIR / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = DOCS_DIR / "experiments" / "tickets" / f"{EXP_ID}.json"
EXPERIMENT_LOG = DOCS_DIR / "experiment_log.jsonl"
AUDIT_MD = DOCS_DIR / "non_ohlcv_data_audit" / "form4_forward_event_queue_20260504.md"
SOURCE_SHADOW = DATA_DIR / "experiments" / "exp-20260503-052" / "form4_standalone_event_sleeve.json"

WINDOW_ORDER = ("late_strong", "mid_weak", "old_thin")
WINDOW_RANGES = {
    "late_strong": "2025-10-23 -> 2026-04-21",
    "mid_weak": "2025-04-23 -> 2025-10-22",
    "old_thin": "2024-10-02 -> 2025-04-22",
}
FIXED_WINDOW_METRICS = {
    "late_strong": {
        "expected_value_score": 3.4191,
        "sharpe_daily": 4.35,
        "total_pnl": 78600.33,
        "total_return_pct": 0.7860,
        "max_drawdown_pct": 0.0541,
        "win_rate": 0.7895,
        "trade_count": 19,
        "survival_rate": 0.8039,
    },
    "mid_weak": {
        "expected_value_score": 1.4415,
        "sharpe_daily": 2.62,
        "total_pnl": 55015.08,
        "total_return_pct": 0.5502,
        "max_drawdown_pct": 0.0879,
        "win_rate": 0.5238,
        "trade_count": 21,
        "survival_rate": 0.7925,
    },
    "old_thin": {
        "expected_value_score": 0.3179,
        "sharpe_daily": 1.29,
        "total_pnl": 24642.07,
        "total_return_pct": 0.2464,
        "max_drawdown_pct": 0.0805,
        "win_rate": 0.4091,
        "trade_count": 22,
        "survival_rate": 0.9167,
    },
}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def _append_experiment_log(row: dict[str, Any]) -> None:
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    compact = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = [
            line for line in lines
            if f'"experiment_id":"{EXP_ID}"' not in line and f'"experiment_id": "{EXP_ID}"' not in line
        ]
        lines.append(compact)
        EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    EXPERIMENT_LOG.write_text(compact + "\n", encoding="utf-8")


def _shadow_summary() -> dict[str, Any]:
    payload = _load_json(SOURCE_SHADOW, {})
    variant = ((payload.get("shadow_variants") or {}).get("meaningful_ge_500k") or {})
    return {
        "source_experiment": "exp-20260503-052",
        "source_decision": payload.get("decision"),
        "source_best_variant": payload.get("best_variant"),
        "variant": "meaningful_ge_500k",
        "aggregate": variant.get("aggregate"),
        "by_window": variant.get("by_window"),
    }


def _current_queue_smoke() -> dict[str, Any]:
    queue = build_forward_queue_from_transactions(
        data_dir=DATA_DIR / "non_ohlcv",
        as_of="2026-05-04",
        core_signals=[{"ticker": "NVDA", "strategy": "trend_long", "confidence_score": 0.91}],
    )
    return {
        "as_of": queue["asof_date"],
        "enabled": queue["enabled"],
        "candidate_count": queue["candidate_count"],
        "data_source_status": queue["data_source"]["status"],
        "data_source_path": queue["data_source"]["path"],
        "alters_orders": queue["production_impact"]["alters_orders"],
    }


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "status": "completed",
        "decision": "accepted_forward_observation_queue",
        "lane": "alpha_search",
        "mechanism_family": "form4_standalone_external_event_source",
        "change_type": "default_off_forward_event_queue",
        "hypothesis": (
            "Large PIT-safe meaningful Form 4 open-market purchase event-days can be "
            "a candidate-source alpha scout, but require forward replacement-value "
            "samples before trade promotion."
        ),
        "alpha_type": "external_event_candidate_source",
        "why_this_not_prior_rejected_paths": (
            "This is not a nearby role, SEC reaction, SPY-leader, or capacity threshold "
            "sweep. It implements the next step requested by the shadow-positive "
            "Form 4 result: observe default-off forward events with frozen alternatives."
        ),
        "parameters": {
            "queue_name": QUEUE_NAME,
            "rule_version": RULE_VERSION,
            "min_total_purchase_value": FORWARD_QUEUE_MIN_PURCHASE_VALUE,
            "primary_horizon_trading_days": PRIMARY_HORIZON_TRADING_DAYS,
            "default_enabled": False,
            "single_causal_variable": "production-visible Form 4 forward observation queue",
        },
        "date_range": {
            window: WINDOW_RANGES[window] for window in WINDOW_ORDER
        },
        "before_metrics": FIXED_WINDOW_METRICS,
        "after_metrics": FIXED_WINDOW_METRICS,
        "expected_value_score_delta": {
            window: 0.0 for window in WINDOW_ORDER
        },
        "gate4": {
            "core_strategy_changed": False,
            "result": "not_applicable_to_strategy_promotion",
            "reason": "queue is default-off and does not alter backtest entries, ranking, sizing, exits, or orders",
        },
        "shadow_alpha_evidence": _shadow_summary(),
        "production_impact": {
            "shared_policy_changed": True,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "replay_only": False,
            "parity_test_added": True,
            "production_impact": "observe_only_forward_queue_no_core_strategy_change",
        },
        "production_smoke": _current_queue_smoke(),
        "llm_change_scope": "none",
        "risk": (
            "If later promoted too early, sparse Form 4 events could displace strong "
            "A/B trend or breakout trades. This run deliberately keeps them observe-only."
        ),
        "next_action": (
            "Accumulate closed forward queue outcomes and replacement-value snapshots; "
            "do not promote to entries until sample stability improves beyond the old_thin "
            "one-event limitation."
        ),
    }


def _write_ticket(payload: dict[str, Any]) -> None:
    ticket = {
        "experiment_id": EXP_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "created_at": payload["timestamp"],
        "completed_at": payload["timestamp"],
        "hypothesis": payload["hypothesis"],
        "allowed_write_scope": [
            "quant/form4_event_queue.py",
            "quant/test_form4_event_queue.py",
            "quant/run.py",
            "quant/report_generator.py",
            "quant/experiments/exp_20260504_001_form4_forward_event_queue.py",
            "data/experiments/exp-20260504-001/form4_forward_event_queue.json",
            "docs/non_ohlcv_data_audit/form4_forward_event_queue_20260504.md",
            "docs/experiments/logs/exp-20260504-001.json",
            "docs/experiments/tickets/exp-20260504-001.json",
            "docs/experiment_log.jsonl",
            "docs/alpha-optimization-playbook.md",
        ],
        "result": {
            "artifact": _repo_rel(OUT_JSON),
            "audit_report": _repo_rel(AUDIT_MD),
            "log": _repo_rel(LOG_JSON),
            "production_impact": payload["production_impact"]["production_impact"],
            "next_action": payload["next_action"],
        },
    }
    _write_json(TICKET_JSON, ticket)


def _fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.2f}%"


def _fmt_raw_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}%"


def _write_report(payload: dict[str, Any]) -> None:
    lines = [
        "# Form 4 Forward Event Queue",
        "",
        f"- experiment_id: `{payload['experiment_id']}`",
        f"- timestamp: `{payload['timestamp']}`",
        f"- decision: `{payload['decision']}`",
        f"- production_impact: `{payload['production_impact']['production_impact']}`",
        "",
        "## Alpha Read",
        "",
        payload["hypothesis"],
        "",
        "This is an alpha-search scout, not a bug fix. The prior `$500k` Form 4 "
        "branch was shadow-promising but sample-limited, so the valid next step "
        "is production-visible forward observation with frozen alternatives.",
        "",
        "## Fixed-Window Metrics",
        "",
        "| Window | EV | Return | Sharpe daily | Max DD | Win rate | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for window in WINDOW_ORDER:
        row = payload["after_metrics"][window]
        lines.append(
            f"| {window} | {row['expected_value_score']:.4f} | "
            f"{_fmt_pct(row['total_return_pct'])} | {row['sharpe_daily']:.2f} | "
            f"{_fmt_pct(row['max_drawdown_pct'])} | {_fmt_pct(row['win_rate'])} | "
            f"{row['trade_count']} |"
        )
    shadow = payload["shadow_alpha_evidence"]
    aggregate = shadow.get("aggregate") or {}
    lines.extend([
        "",
        "## Shadow Evidence Carried Forward",
        "",
        f"- source_experiment: `{shadow.get('source_experiment')}`",
        f"- variant: `{shadow.get('variant')}`",
        f"- valid_events: `{aggregate.get('valid_event_count')}`",
        f"- avg_net_return: `{_fmt_raw_pct(aggregate.get('avg_net_return_pct'))}`",
        f"- avg_excess_vs_spy: `{_fmt_raw_pct(aggregate.get('avg_excess_vs_spy_pct'))}`",
        f"- positive_excess_windows: `{aggregate.get('positive_excess_windows')}/{len(WINDOW_ORDER)}`",
        "",
        "## Production Smoke",
        "",
        f"- as_of: `{payload['production_smoke']['as_of']}`",
        f"- enabled: `{payload['production_smoke']['enabled']}`",
        f"- candidate_count: `{payload['production_smoke']['candidate_count']}`",
        f"- alters_orders: `{payload['production_smoke']['alters_orders']}`",
        "",
        "## Decision",
        "",
        "Accepted as a default-off observation queue only. It does not pass as a "
        "strategy promotion because no core trades are added and the old_thin "
        "shadow sample remains too small.",
        "",
        "## Next Action",
        "",
        payload["next_action"],
        "",
    ])
    AUDIT_MD.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_MD.write_text("\n".join(lines), encoding="utf-8")


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_ticket(payload)
    _write_report(payload)
    _append_experiment_log(payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(json.dumps({
        "experiment_id": payload["experiment_id"],
        "decision": payload["decision"],
        "queue_name": payload["parameters"]["queue_name"],
        "production_smoke": payload["production_smoke"],
        "output": _repo_rel(OUT_JSON),
        "report": _repo_rel(AUDIT_MD),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
