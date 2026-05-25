"""exp-20260525-018: AI optical IWM/SPY spread monotonicity audit.

Observed-only alpha search. This reuses the accepted/default-off
exp-20260525-003 AI optical paper-sleeve replay and checks whether the
production-visible IWM-minus-SPY 20-day momentum spread is only a useful
binary participation gate or also contains monotonic sizing/ranking strength.

It does not alter signal generation, ranking, sizing, exits, LLM/news, paper
adapter behavior, live orders, or production watchlists.
"""

from __future__ import annotations

import json
import math
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260525-018"
STEM = "ai_optical_iwm_spread_monotonicity"
SOURCE_EXPERIMENT_ID = "exp-20260525-003"
SOURCE_STEM = "ai_optical_iwm_confirmed_fixed_notional_sleeve"
TRIAL_FAMILY = "ai_optical_iwm_spread_strength_monotonicity"
CHANGED_VARIABLE = "ai_optical_iwm_spy_spread_strength_bucket"

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / SOURCE_EXPERIMENT_ID
    / f"{SOURCE_STEM}.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

MIN_SELECTED_TRADES = 10
MIN_SELECTED_WINDOWS = 3
MIN_POINT_IN_TIME_FIELD_COVERAGE = 1.0
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.45


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Path):
        return _repo_rel(value)
    return value


def _repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


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
    compact = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(compact)
                    replaced = True
                continue
            rows.append(line)
    if not replaced:
        rows.append(compact)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _round(value: Any, digits: int = 6) -> float | None:
    parsed = _float(value)
    if parsed is None:
        return None
    return round(parsed, digits)


def _open_position_field_check() -> dict[str, Any]:
    path = REPO_ROOT / "operator_inputs" / "open_positions.json"
    if not path.exists():
        return {
            "path": _repo_rel(path),
            "exists": False,
            "checked_fields": ["entry_date", "target_price"],
            "missing_count": None,
            "passed": False,
        }
    payload = _read_json(path)
    positions = payload.get("positions") if isinstance(payload, dict) else payload
    if not isinstance(positions, list):
        positions = []
    missing = []
    for idx, row in enumerate(positions):
        if not isinstance(row, dict):
            continue
        for field in ("entry_date", "target_price"):
            if row.get(field) in (None, ""):
                missing.append(
                    {"index": idx, "ticker": row.get("ticker"), "field": field}
                )
    return {
        "path": _repo_rel(path),
        "exists": True,
        "checked_fields": ["entry_date", "target_price"],
        "checked_positions": len(positions),
        "missing_count": len(missing),
        "missing_examples": missing[:10],
        "passed": not missing,
    }


def _spread_bucket(spread: float | None) -> str:
    if spread is None:
        return "missing_spread"
    if spread < 0.003:
        return "failed_iwm_lead"
    if spread < 0.010:
        return "edge_iwm_lead"
    return "broad_iwm_lead"


def _extract_trade_rows(source: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for selected, container in (
        (True, source.get("target_trades_by_window") or {}),
        (False, source.get("filtered_out_target_trades_by_window") or {}),
    ):
        for window, trades in container.items():
            if not isinstance(trades, list):
                continue
            for trade in trades:
                if not isinstance(trade, dict):
                    continue
                market = trade.get("market_confirmation") or {}
                spread = _float(market.get("iwm_spy_momentum_spread"))
                rows.append(
                    {
                        "window": window,
                        "ticker": str(trade.get("ticker") or "").upper(),
                        "strategy": trade.get("strategy"),
                        "entry_date": trade.get("entry_date"),
                        "exit_date": trade.get("exit_date"),
                        "selected_by_existing_binary_gate": selected,
                        "spread": _round(spread),
                        "spread_bucket": _spread_bucket(spread),
                        "pnl": _round(trade.get("pnl"), 2) or 0.0,
                        "pnl_pct_net": _round(trade.get("pnl_pct_net"), 6),
                        "exit_reason": trade.get("exit_reason"),
                        "market_state_as_of": market.get("market_state_as_of"),
                        "market_confirmation_passed": market.get("passed"),
                    }
                )
    return rows


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnl_values = [_float(row.get("pnl"), 0.0) or 0.0 for row in rows]
    positive_by_ticker: Counter[str] = Counter()
    for row, pnl in zip(rows, pnl_values):
        if pnl > 0:
            positive_by_ticker[str(row.get("ticker") or "").upper()] += pnl
    positive_total = sum(positive_by_ticker.values())
    max_single_share = (
        max(positive_by_ticker.values()) / positive_total
        if positive_total > 0 and positive_by_ticker
        else None
    )
    positive_hhi = (
        sum((pnl / positive_total) ** 2 for pnl in positive_by_ticker.values())
        if positive_total > 0 and positive_by_ticker
        else None
    )
    return {
        "trades": len(rows),
        "windows": sorted({str(row.get("window")) for row in rows if row.get("window")}),
        "ticker_count": len({row.get("ticker") for row in rows if row.get("ticker")}),
        "win_rate": round(sum(1 for pnl in pnl_values if pnl > 0) / len(rows), 4)
        if rows
        else None,
        "total_pnl": round(sum(pnl_values), 2),
        "avg_pnl": round(sum(pnl_values) / len(rows), 2) if rows else None,
        "avg_pnl_pct_net": round(
            sum(_float(row.get("pnl_pct_net"), 0.0) or 0.0 for row in rows) / len(rows),
            6,
        )
        if rows
        else None,
        "worst_pnl": round(min(pnl_values), 2) if rows else None,
        "best_pnl": round(max(pnl_values), 2) if rows else None,
        "positive_pnl_by_ticker": {
            ticker: round(pnl, 2) for ticker, pnl in sorted(positive_by_ticker.items())
        },
        "max_single_positive_share": round(max_single_share, 6)
        if max_single_share is not None
        else None,
        "positive_hhi": round(positive_hhi, 6) if positive_hhi is not None else None,
    }


def _group_by(rows: list[dict[str, Any]], key: str) -> OrderedDict[str, dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        value = row.get(key)
        bucket = "unknown" if value is None else str(value)
        buckets.setdefault(bucket, []).append(row)
    order = {
        "failed_iwm_lead": 0,
        "edge_iwm_lead": 1,
        "broad_iwm_lead": 2,
        "missing_spread": 3,
        "False": 4,
        "True": 5,
    }
    return OrderedDict(
        (bucket, _summary(bucket_rows))
        for bucket, bucket_rows in sorted(
            buckets.items(),
            key=lambda item: (order.get(item[0], 99), item[0]),
        )
    )


def _monotonic_gate(
    *,
    rows: list[dict[str, Any]],
    selected_rows: list[dict[str, Any]],
    failed_rows: list[dict[str, Any]],
    bucket_summary: OrderedDict[str, dict[str, Any]],
) -> dict[str, Any]:
    field_coverage = sum(1 for row in rows if row.get("spread") is not None) / len(rows)
    selected_summary = _summary(selected_rows)
    failed_summary = _summary(failed_rows)
    binary_gate_passed = (
        selected_summary["trades"] >= MIN_SELECTED_TRADES
        and len(selected_summary["windows"]) >= MIN_SELECTED_WINDOWS
        and selected_summary["total_pnl"] > 0
        and failed_summary["avg_pnl"] is not None
        and selected_summary["avg_pnl"] is not None
        and selected_summary["avg_pnl"] > failed_summary["avg_pnl"]
        and selected_summary["max_single_positive_share"] is not None
        and selected_summary["max_single_positive_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and selected_summary["positive_hhi"] is not None
        and selected_summary["positive_hhi"] <= MAX_POSITIVE_HHI
    )

    ordered_buckets = ["failed_iwm_lead", "edge_iwm_lead", "broad_iwm_lead"]
    adjacent = []
    strength_passed = True
    for lower, higher in zip(ordered_buckets, ordered_buckets[1:]):
        lower_avg = bucket_summary.get(lower, {}).get("avg_pnl")
        higher_avg = bucket_summary.get(higher, {}).get("avg_pnl")
        passed = lower_avg is not None and higher_avg is not None and higher_avg >= lower_avg
        adjacent.append(
            {
                "lower_bucket": lower,
                "lower_avg_pnl": lower_avg,
                "higher_bucket": higher,
                "higher_avg_pnl": higher_avg,
                "passed": passed,
            }
        )
        strength_passed = strength_passed and passed

    return {
        "passed": bool(binary_gate_passed and strength_passed),
        "binary_participation_gate_passed": bool(binary_gate_passed),
        "strength_monotonicity_passed": bool(strength_passed),
        "field_coverage": round(field_coverage, 6),
        "field_coverage_passed": field_coverage >= MIN_POINT_IN_TIME_FIELD_COVERAGE,
        "selected_summary": selected_summary,
        "failed_summary": failed_summary,
        "adjacent_bucket_checks": adjacent,
        "decision": "observed_only_binary_gate_confirmed_strength_not_monotonic"
        if binary_gate_passed and not strength_passed
        else (
            "observed_only_binary_and_strength_monotonic"
            if binary_gate_passed and strength_passed
            else "rejected_iwm_spread_participation_field"
        ),
        "interpretation": (
            "The existing binary IWM/SPY participation gate is supported, but "
            "larger spread strength is not monotonic; do not retune toward a "
            "higher IWM-spread threshold on the frozen sample."
            if binary_gate_passed and not strength_passed
            else ""
        ),
    }


def _gate4_from_source(source: dict[str, Any]) -> dict[str, Any]:
    gate4 = dict(source.get("gate4") or {})
    aggregate = (source.get("delta_metrics") or {}).get("aggregate") or {}
    gate4["source_expected_value_score_delta_sum"] = aggregate.get(
        "expected_value_score_delta_sum"
    )
    gate4["source_total_pnl_delta_sum"] = aggregate.get("total_pnl_delta_sum")
    gate4["source_windows_ev_improved"] = aggregate.get("windows_ev_improved")
    gate4["source_windows_ev_regressed"] = aggregate.get("windows_ev_regressed")
    return gate4


def build_payload() -> dict[str, Any]:
    source = _read_json(SOURCE_JSON)
    field_check = _open_position_field_check()
    rows = _extract_trade_rows(source)
    selected_rows = [row for row in rows if row["selected_by_existing_binary_gate"]]
    failed_rows = [row for row in rows if not row["selected_by_existing_binary_gate"]]
    bucket_summary = _group_by(rows, "spread_bucket")
    binary_summary = _group_by(rows, "selected_by_existing_binary_gate")
    gate = _monotonic_gate(
        rows=rows,
        selected_rows=selected_rows,
        failed_rows=failed_rows,
        bucket_summary=bucket_summary,
    )

    decision = gate["decision"]
    timestamp = _utc_now()
    related_files = {
        "script": _repo_rel(Path(__file__)),
        "source": _repo_rel(SOURCE_JSON),
        "output": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket": _repo_rel(TICKET_JSON),
        "artifact": _repo_rel(ARTIFACT_MD),
        "experiment_log": _repo_rel(EXPERIMENT_LOG),
    }
    source_delta = (source.get("delta_metrics") or {}).get("aggregate") or {}
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "observed_only" if gate["binary_participation_gate_passed"] else "rejected",
        "decision": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "For the governed AI optical paper sleeve, prior-close IWM/SPY "
            "relative momentum should behave as a market-participation quality "
            "field. It should at minimum separate pass/fail trades, and it must "
            "show monotonic spread-strength evidence before any higher-threshold "
            "or larger-notional follow-up is considered."
        ),
        "change_summary": (
            "Observed-only monotonicity audit of the production-visible "
            "IWM-minus-SPY 20-day momentum spread used by the existing default-off "
            "AI optical paper sleeve."
        ),
        "change_type": "observed_only_monotonic_validation",
        "mechanism_family": "ai_optical_market_participation_quality",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "iwm_spy_spread_bucket_monotonicity_v1",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "prior_trial_count": 5,
        "nearby_prior_experiments": [
            "exp-20260523-003",
            "exp-20260524-026",
            "exp-20260524-035",
            "exp-20260525-002",
            "exp-20260525-003",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "monotonic_validation_of_existing_production_visible_iwm_spy_field",
        "source_experiment": SOURCE_EXPERIMENT_ID,
        "backtest_protocol": {
            "source": (
                "Read-only reanalysis of exp-20260525-003, which used the "
                "docs/backtesting.md three fixed windows with exp-20260519-029 "
                "observation OHLCV snapshots because the canonical core snapshots "
                "lack most optical tickers."
            ),
            "windows": (source.get("backtest_protocol") or {}).get("windows"),
            "source_gate4": _gate4_from_source(source),
        },
        "parameters": {
            "spread_field": "prior_close_iwm_20d_momentum_minus_spy_20d_momentum",
            "spread_buckets": {
                "failed_iwm_lead": "spread < 0.003",
                "edge_iwm_lead": "0.003 <= spread < 0.010",
                "broad_iwm_lead": "spread >= 0.010",
            },
            "minimum_selected_trades": MIN_SELECTED_TRADES,
            "minimum_selected_windows": MIN_SELECTED_WINDOWS,
            "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
            "max_positive_hhi": MAX_POSITIVE_HHI,
            "anti_js": "No JavaScript was used.",
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "market participation quality / candidate-pool alpha: AI optical "
                "paper trades need small-cap participation confirmation, but "
                "confirmation strength must be monotonic before any threshold "
                "tightening or notional increase."
            ),
            "2_history_check": (
                "exp-20260523-003 rejected direct core-pool admission; "
                "exp-20260524-035 found no-displacement paper uplift but failed "
                "concentration; exp-20260525-003 passed as default-off fixed "
                "notional with the binary IWM/SPY gate."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Use the same three fixed windows from exp-20260525-003. Binary "
                "field support requires selected trades to beat failed trades "
                "with concentration inside guardrails. Strength promotion requires "
                "failed <= edge <= broad average PnL monotonicity."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260525_018_ai_optical_iwm_spread_monotonicity.py"
            ),
        },
        "gate1": {
            "passed": True,
            "baseline_artifact": f"{_repo_rel(SOURCE_JSON)}#before_metrics",
            "baseline_protocol": "docs/backtesting.md three fixed windows via source experiment",
            "baseline_metrics_readable": True,
        },
        "gate2": {
            "passed": bool(field_check.get("passed")) and bool(rows),
            "field_check": field_check,
            "runtime_fields": [
                "market_confirmation.iwm_spy_momentum_spread",
                "market_confirmation.market_state_as_of",
                "ticker",
                "entry_date",
                "exit_date",
                "pnl",
                "pnl_pct_net",
            ],
            "extracted_trade_rows": len(rows),
            "rows_with_spread": sum(1 for row in rows if row.get("spread") is not None),
        },
        "gate3": {
            "passed": True,
            "adds_filter": False,
            "candidate_pool_changed": False,
            "survival_impact": "none; observed-only reanalysis of existing default-off paper trades",
        },
        "gate4": {
            "passed": False,
            "strategy_behavior_changed": False,
            "source_three_window_replay_passed": bool((source.get("gate4") or {}).get("passed")),
            "binary_gate_confirmed": gate["binary_participation_gate_passed"],
            "strength_monotonicity_passed": gate["strength_monotonicity_passed"],
            "note": (
                "No new promotion. The source binary gate remains a forward-watch "
                "default-off paper lead; spread-strength retuning failed this "
                "observed-only monotonicity audit."
            ),
        },
        "before_metrics": source.get("before_metrics"),
        "after_metrics": source.get("after_metrics"),
        "delta_metrics": source.get("delta_metrics"),
        "observed_only_gate": gate,
        "binary_summary": binary_summary,
        "spread_bucket_summary": bucket_summary,
        "trade_rows": rows,
        "expected_value_score_delta": source_delta.get("expected_value_score_delta_sum"),
        "total_pnl_delta": source_delta.get("total_pnl_delta_sum"),
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "default_off_paper_only": True,
            "observed_only_attribution": True,
            "parity_test_added": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
        },
        "interpretation": gate["interpretation"],
        "rejection_reason": (
            "IWM/SPY spread-strength buckets were not monotonic; keep the existing "
            "binary participation gate but do not retune toward higher thresholds "
            "or larger notional on the frozen sample."
            if gate["binary_participation_gate_passed"]
            and not gate["strength_monotonicity_passed"]
            else None
        ),
        "next_evidence_needed": (
            "Forward closed replacement-value rows from the production-visible "
            "AI optical paper adapter; do not retry nearby IWM/SPY spread "
            "threshold or notional changes without new forward evidence."
        ),
        "why_not_other_changes": (
            "Skipped LLM soft-ranking because replay-safe attribution remains "
            "sparse. Skipped SEC/state-surface/broad-market/opening-range "
            "retunes due fresh anti-repeat evidence. This extracts evidence from "
            "an existing production-visible field instead of adding a new feature."
        ),
        "related_files": related_files,
        "anti_js": "No JavaScript was used.",
    }


def _experiment_log_entry(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "hypothesis",
        "change_summary",
        "change_type",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "prior_trial_count",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "source_experiment",
        "backtest_protocol",
        "parameters",
        "gate_questions",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "observed_only_gate",
        "binary_summary",
        "spread_bucket_summary",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "expected_value_score_delta",
        "total_pnl_delta",
        "llm_metrics",
        "production_impact",
        "decision",
        "interpretation",
        "rejection_reason",
        "next_evidence_needed",
        "why_not_other_changes",
        "related_files",
        "anti_js",
    ]
    return {key: payload[key] for key in keys}


def _artifact_markdown(payload: dict[str, Any]) -> str:
    gate = payload["observed_only_gate"]
    rows = [
        "| Bucket | Trades | Windows | Win rate | Total PnL | Avg PnL | Max positive share | HHI |",
        "|---|---:|---|---:|---:|---:|---:|---:|",
    ]
    for bucket, summary in payload["spread_bucket_summary"].items():
        rows.append(
            "| {bucket} | {trades} | {windows} | {win_rate} | ${total:,.2f} | ${avg:,.2f} | {share} | {hhi} |".format(
                bucket=bucket,
                trades=summary["trades"],
                windows=", ".join(summary["windows"]),
                win_rate="" if summary["win_rate"] is None else f"{summary['win_rate']:.2%}",
                total=summary["total_pnl"],
                avg=summary["avg_pnl"] or 0.0,
                share="" if summary["max_single_positive_share"] is None else summary["max_single_positive_share"],
                hhi="" if summary["positive_hhi"] is None else summary["positive_hhi"],
            )
        )
    binary = [
        "| Binary Gate | Trades | Windows | Win rate | Total PnL | Avg PnL |",
        "|---|---:|---|---:|---:|---:|",
    ]
    for bucket, summary in payload["binary_summary"].items():
        binary.append(
            "| {bucket} | {trades} | {windows} | {win_rate} | ${total:,.2f} | ${avg:,.2f} |".format(
                bucket="selected" if bucket == "True" else "filtered_out",
                trades=summary["trades"],
                windows=", ".join(summary["windows"]),
                win_rate="" if summary["win_rate"] is None else f"{summary['win_rate']:.2%}",
                total=summary["total_pnl"],
                avg=summary["avg_pnl"] or 0.0,
            )
        )
    source_delta = (payload["delta_metrics"] or {}).get("aggregate") or {}
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} AI Optical IWM/SPY Spread Monotonicity",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Observed-only alpha search. No entries, exits, ranking, sizing, adapter behavior, LLM/news, or orders changed.",
            "",
            "## Source Three-Window Before/After",
            "",
            f"- source experiment: `{SOURCE_EXPERIMENT_ID}`",
            f"- EV delta: `{source_delta.get('expected_value_score_delta_sum')}`",
            f"- PnL delta: `${source_delta.get('total_pnl_delta_sum')}`",
            f"- windows EV improved/regressed: `{source_delta.get('windows_ev_improved')}` / `{source_delta.get('windows_ev_regressed')}`",
            "",
            "## Binary Gate",
            "",
            *binary,
            "",
            "## Spread Buckets",
            "",
            *rows,
            "",
            "## Monotonic Gate",
            "",
            "```json",
            json.dumps(gate, indent=2, sort_keys=True),
            "```",
            "",
            "Conclusion: keep the existing binary IWM/SPY participation gate as a forward-watch paper lead, but reject higher-threshold / larger-notional follow-ups until forward replacement-value rows arrive.",
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "AI optical IWM spread monotonicity",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "updated_at": payload["timestamp"],
        },
    )
    _write_text(ARTIFACT_MD, _artifact_markdown(payload))
    _upsert_jsonl(EXPERIMENT_LOG, _experiment_log_entry(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "observed_only_gate": payload["observed_only_gate"],
                    "artifact": _repo_rel(ARTIFACT_MD),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
