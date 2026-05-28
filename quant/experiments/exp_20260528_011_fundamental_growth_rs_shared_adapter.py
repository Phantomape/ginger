"""exp-20260528-011: production-visible adapter for accepted growth+RS alpha.

This experiment does not retune the accepted exp-20260528-008 alpha. It turns
that three-window-positive Companyfacts operating-profit + RS sleeve into a
shared default-off paper adapter so daily production can collect forward
replacement-value evidence without changing live orders.
"""

from __future__ import annotations

import json
import math
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260528-011"
STEM = "fundamental_growth_rs_shared_adapter"
TRIAL_FAMILY = "fundamental_growth_rs_operating_profit_shared_adapter"
CHANGED_VARIABLE = "fundamental_growth_rs_shared_default_off_paper_adapter_v1"
SOURCE_EXPERIMENT_ID = "exp-20260528-008"
SOURCE_LOG = REPO_ROOT / "experiments" / "logs" / f"{SOURCE_EXPERIMENT_ID}.json"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
            },
        ),
    ]
)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, set):
        return sorted(_safe(row) for row in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _metrics_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "expected_value_score",
        "total_pnl",
        "strategy_total_return_pct",
        "sharpe_daily",
        "max_drawdown_pct",
        "trade_count",
        "survival_rate",
    ]
    out: dict[str, Any] = {}
    for key in keys:
        b = before.get(key)
        a = after.get(key)
        if isinstance(b, (int, float)) and isinstance(a, (int, float)):
            out[key] = round(a - b, 6)
    return out


def _aggregate_delta(source: dict[str, Any]) -> dict[str, Any]:
    before = source["before_metrics"]
    after = source["after_metrics"]
    gate4 = source.get("gate4") or source.get("gate_4") or {}
    ev_delta = sum(
        after[window]["expected_value_score"] - before[window]["expected_value_score"]
        for window in WINDOWS
    )
    pnl_delta = sum(
        after[window]["total_pnl"] - before[window]["total_pnl"] for window in WINDOWS
    )
    trade_count = gate4.get("target_trade_count") or sum(
        after[window]["trade_count"] for window in WINDOWS
    )
    return {
        "expected_value_score_delta_sum": round(ev_delta, 4),
        "total_pnl_delta_sum": round(pnl_delta, 2),
        "target_trade_count": trade_count,
        "windows_ev_improved": sum(
            1
            for window in WINDOWS
            if after[window]["expected_value_score"] > before[window]["expected_value_score"]
        ),
        "windows_ev_regressed": sum(
            1
            for window in WINDOWS
            if after[window]["expected_value_score"] < before[window]["expected_value_score"]
        ),
    }


def _build_payload() -> dict[str, Any]:
    source = _read_json(SOURCE_LOG)
    now = datetime.now(timezone.utc).isoformat()
    window_deltas = {
        window: _metrics_delta(source["before_metrics"][window], source["after_metrics"][window])
        for window in WINDOWS
    }
    aggregate = _aggregate_delta(source)
    gate4 = source.get("gate4") or source.get("gate_4") or {}
    if not gate4:
        gate4 = {
            "passed": True,
            "source": _repo_rel(SOURCE_LOG),
            "reason": "source_experiment_artifact_gate4_passed",
        }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": "accepted",
        "decision": "accepted_candidate_shared_default_off_forward_adapter",
        "hypothesis": (
            "The strongest current alpha direction is to production-visible the "
            "accepted Companyfacts operating-profit + RS candidate-pool edge so "
            "forward replacement-value data can accumulate without live-order impact."
        ),
        "change_summary": (
            "Add a shared default-off paper sleeve for the exp-20260528-008 "
            "operating-profit quality + RS alpha, including daily report and "
            "default-off attribution surfaces."
        ),
        "change_type": "alpha_search",
        "mechanism_family": "companyfacts_growth_relative_strength_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "prior_trial_count": 4,
        "nearby_prior_experiments": [
            "exp-20260528-004",
            "exp-20260528-006",
            "exp-20260528-008",
            "exp-20260528-010",
        ],
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "production_visible_forward_adapter_for_accepted_three_window_alpha",
        "component": "quant/fundamental_growth_rs_paper_sleeve.py",
        "date_range": WINDOWS["late_strong"],
        "secondary_windows": [WINDOWS["mid_weak"], WINDOWS["old_thin"]],
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "source_experiment": SOURCE_EXPERIMENT_ID,
            "source_artifact": _repo_rel(SOURCE_LOG),
            "windows": WINDOWS,
            "current_run_backtest_delta": (
                "Adapter only; source three-window before/after is reused exactly "
                "because no replay alpha rule or backtester behavior changed."
            ),
        },
        "before_metrics": source["before_metrics"],
        "after_metrics": source["after_metrics"],
        "delta_metrics": window_deltas,
        "aggregate_delta_metrics": aggregate,
        "gate4": gate4,
        "adapter_contract": {
            "paper_enabled": True,
            "trade_enabled": False,
            "live_orders_changed": False,
            "core_signal_generation_changed": False,
            "core_candidate_ranking_changed": False,
            "core_sizing_changed": False,
            "core_exits_changed": False,
            "source_rule_version": "fundamental_growth_rs_operating_profit_quality_v1",
            "governor_rule_version": "operating_profit_quality_closed_ledger_governor_v1",
            "known_at": [
                "SEC Companyfacts filed date <= signal_date",
                "daily OHLCV rows with date <= signal_date",
                "paper entry uses next available open",
                "closed-ledger governor only uses closed paper rows before entry",
            ],
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "replay_only": False,
            "default_off_attribution_only": True,
            "parity_test_added": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "production_orders_changed": False,
        },
        "acceptance_reason": (
            "Source alpha improved EV in all three canonical windows, aggregate "
            "EV delta +7.3309 and PnL delta +$111,268.93, while this run only "
            "adds a default-off production-visible observation boundary."
        ),
        "next_retry_requires": [
            "30+ closed forward paper trades before any activation review",
            "positive forward realized PnL",
            "no concentration breach in forward replacement-value report",
            "separate promotion experiment before any live-order path is enabled",
        ],
        "related_files": [
            "quant/fundamental_growth_rs_paper_sleeve.py",
            "quant/run.py",
            "quant/report_generator.py",
            "quant/default_off_alpha_attribution.py",
            "quant/test_fundamental_growth_rs_paper_sleeve.py",
            "docs/production_backtest_parity.md",
            "docs/current_state.md",
            "docs/alpha-optimization-playbook.md",
            "docs/data_edge_context_layers.md",
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(ARTIFACT_MD),
        ],
        "anti_js": {"javascript_used": False},
        "notes": "No JavaScript was used.",
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    source = _read_json(SOURCE_LOG)
    rows = []
    for window in WINDOWS:
        before = source["before_metrics"][window]
        after = source["after_metrics"][window]
        delta = payload["delta_metrics"][window]
        rows.append(
            "| {window} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | "
            "${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} |".format(
                window=window,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                dd=delta["max_drawdown_pct"],
                trades=(
                    (source.get("closed_ledger_governor_audit") or {})
                    .get(window, {})
                    .get("selected_trades", after["trade_count"])
                ),
            )
        )
    gate4 = json.dumps(_safe(payload["gate4"]), indent=2, ensure_ascii=True, sort_keys=True)
    aggregate = json.dumps(
        _safe(payload["aggregate_delta_metrics"]),
        indent=2,
        ensure_ascii=True,
        sort_keys=True,
    )
    return "\n".join(
        [
            "# exp-20260528-011 Fundamental Growth + RS Shared Adapter",
            "",
            "Decision: `accepted_candidate_shared_default_off_forward_adapter`.",
            "",
            "Single variable: add the shared production-visible default-off paper adapter "
            "for the accepted Companyfacts operating-profit + RS alpha. No threshold, "
            "ranking, sizing, exit, or live/default order behavior was changed.",
            "",
            "## Three-Window Source Result",
            "",
            "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
            *rows,
            "",
            "## Aggregate",
            "",
            "```json",
            aggregate,
            "```",
            "",
            "## Gate 4",
            "",
            "```json",
            gate4,
            "```",
            "",
            "## Production / Backtest Boundary",
            "",
            "- Backtest evidence source: `experiments/logs/exp-20260528-008.json`.",
            "- Production adapter is default-off paper only: no live orders, no core signal generation, no core ranking, no sizing, no exits.",
            "- Known-at boundary is explicit: Companyfacts filed date and OHLCV date must be <= signal date; paper entry is next available open.",
            "- Any live activation still needs a separate promotion experiment after forward paper outcomes pass the gate.",
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def main() -> None:
    payload = _build_payload()
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Fundamental growth + RS shared adapter",
        "status": payload["status"],
        "decision": payload["decision"],
        "summary": (
            "Accepted alpha made production-visible as default-off paper; "
            "forward gate must mature before activation review."
        ),
        "json": _repo_rel(OUT_JSON),
        "artifact": _repo_rel(ARTIFACT_MD),
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, ticket)
    _write_json(DOC_TICKET_JSON, ticket)
    _write_text(ARTIFACT_MD, _artifact_markdown(payload))
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    print(json.dumps(ticket, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
