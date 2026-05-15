"""
exp-20260515-031: Space VSAT same-theme satcom trend pool.

Tests one candidate-pool variable on top of the accepted exp-20260515-024
Space stack: add only mature satcom extension tickers that pass the prior
all-positive 5d forward gate and also have positive 10d same-theme replacement
value. Added tickers remain trend_long only. This is meant to separate the
VSAT forward-quality row from the rejected exp-20260515-029 IRDM/VSAT bundle.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any


THIS = Path(__file__).resolve()
ROOT = THIS.parents[2]
EXPERIMENTS_DIR = THIS.parent
for path in (str(ROOT), str(EXPERIMENTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import exp_20260515_013_space_fast_5d_satcom_candidate_pool as exp013
import exp_20260515_021_space_defense_budget_same_theme_winner_trend_risk as exp021
import exp_20260515_024_space_source_diversity_peer_nonleader_trend_risk as exp024
import exp_20260515_029_space_current_stack_fast_5d_satcom_trend_pool as exp029


LOGGER = logging.getLogger(__name__)

EXPERIMENT_ID = "exp-20260515-031"
STEM = "space_vsat_same_theme_satcom_trend_pool"
BEFORE_EXPERIMENT_ID = "exp-20260515-024"
BEFORE_STEM = "space_source_diversity_peer_nonleader_trend_risk"

DATA_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
DOCS_DIR = ROOT / "docs" / "experiments"
LOG_DIR = DOCS_DIR / "logs"
TICKET_DIR = DOCS_DIR / "tickets"
ARTIFACT_DIR = DOCS_DIR / "artifacts"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

TARGET_STRATEGY = "trend_long"
FORWARD_5D_HORIZON = "5d"
CONFIRM_10D_HORIZON = "10d"


def _safe(value: Any) -> Any:
    return exp013._safe(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _append_jsonl_for_this_experiment(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                lines.append(line)
                continue
            if row.get("experiment_id") != EXPERIMENT_ID:
                lines.append(line)
    lines.append(json.dumps(_safe(payload), ensure_ascii=False, sort_keys=True))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _as_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _positive_values(row: dict[str, Any], keys: tuple[str, ...]) -> dict[str, float] | None:
    values: dict[str, float] = {}
    for key in keys:
        value = _as_float(row.get(key))
        if value is None or value <= 0.0:
            return None
        values[key] = value
    return values


def _satcom_fast_5d_same_theme_gate() -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    skipped: dict[str, int] = {}

    def skip(reason: str) -> None:
        skipped[reason] = skipped.get(reason, 0) + 1

    five_day_keys = (
        "cash_relative_pnl",
        "same_theme_replacement_value",
        "spy_relative_value",
        "qqq_relative_value",
        "ufo_relative_value",
        "arkx_relative_value",
    )
    ten_day_keys = ("cash_relative_pnl", "same_theme_replacement_value")

    for row in exp013._latest_event_rows(exp013.LEDGER_PATH):
        ticker = str(row.get("ticker") or "").upper()
        if ticker not in exp013.SATCOM_EXTENSION_CANDIDATES:
            skip("not_satcom_extension_candidate")
            continue
        if str(row.get("semantic_bucket") or "") == "attention_only":
            skip("attention_only")
            continue

        horizons = row.get("horizons") or {}
        five_day = horizons.get(FORWARD_5D_HORIZON)
        if not isinstance(five_day, dict) or five_day.get("status") != "mature":
            skip("missing_mature_5d")
            continue
        five_day_values = _positive_values(five_day, five_day_keys)
        if five_day_values is None:
            skip("not_all_5d_positive")
            continue

        ten_day = horizons.get(CONFIRM_10D_HORIZON)
        if not isinstance(ten_day, dict) or ten_day.get("status") != "mature":
            skip("missing_mature_10d")
            continue
        ten_day_values = _positive_values(ten_day, ten_day_keys)
        if ten_day_values is None:
            skip("not_10d_cash_and_same_theme_positive")
            continue

        grouped.setdefault(ticker, []).append(
            {
                "ticker": ticker,
                "event_id": row.get("event_id"),
                "event_date": row.get("event_date"),
                "asof_date": row.get("asof_date"),
                "logged_at": row.get("logged_at"),
                "closed_decision": row.get("closed_decision"),
                "source_type": row.get("source_type"),
                "semantic_bucket": row.get("semantic_bucket"),
                "theme_segment": row.get("theme_segment"),
                "event_fields": list(row.get("event_fields") or []),
                "5d_values": five_day_values,
                "10d_values": ten_day_values,
            }
        )

    profiles: dict[str, dict[str, Any]] = {}
    for ticker, rows in sorted(grouped.items()):
        profiles[ticker] = {
            "passed": True,
            "ticker": ticker,
            "closed_event_count": len(rows),
            "avg_5d_cash_relative_pnl": round(
                mean(float(row["5d_values"]["cash_relative_pnl"]) for row in rows), 6
            ),
            "avg_5d_same_theme_replacement_value": round(
                mean(
                    float(row["5d_values"]["same_theme_replacement_value"])
                    for row in rows
                ),
                6,
            ),
            "avg_10d_cash_relative_pnl": round(
                mean(float(row["10d_values"]["cash_relative_pnl"]) for row in rows),
                6,
            ),
            "avg_10d_same_theme_replacement_value": round(
                mean(
                    float(row["10d_values"]["same_theme_replacement_value"])
                    for row in rows
                ),
                6,
            ),
            "semantic_buckets": sorted({str(row["semantic_bucket"]) for row in rows}),
            "source_types": sorted({str(row["source_type"]) for row in rows}),
            "event_ids": sorted({str(row["event_id"]) for row in rows}),
            "rows": rows,
        }

    return {
        "passed": bool(profiles),
        "source_gate": "space_fast_5d_same_theme_satcom_candidate_profile",
        "path": str(exp013.LEDGER_PATH.relative_to(ROOT)),
        "candidate_universe": list(exp013.SATCOM_EXTENSION_CANDIDATES),
        "target_definition": (
            "satcom extension ticker with mature 5d profile positive versus cash, "
            "same-theme replacement, SPY, QQQ, UFO, and ARKX, plus mature 10d "
            "cash-relative PnL and same-theme replacement value both positive"
        ),
        "target_tickers": sorted(profiles),
        "target_profile_row_count": sum(len(item["rows"]) for item in profiles.values()),
        "profiles": profiles,
        "thresholds": {
            "min_5d_cash_relative_pnl": 0.0,
            "min_5d_same_theme_replacement_value": 0.0,
            "min_5d_spy_relative_value": 0.0,
            "min_5d_qqq_relative_value": 0.0,
            "min_5d_ufo_relative_value": 0.0,
            "min_5d_arkx_relative_value": 0.0,
            "min_10d_cash_relative_pnl": 0.0,
            "min_10d_same_theme_replacement_value": 0.0,
        },
        "skipped_counts": dict(sorted(skipped.items())),
    }


def _risk_distribution(variant: dict[str, Any]) -> dict[str, dict[str, Any]]:
    keys = ("worst_trade_pct", "max_consecutive_losses", "tail_loss_share")
    return {
        label: {key: row["metrics"].get(key) for key in keys}
        for label, row in variant["by_window"].items()
    }


def _experiment_record(payload: dict[str, Any]) -> dict[str, Any]:
    before = payload["before_variant"]
    after = payload["after_variant"]
    gate = payload["gate_results"]
    promoted = payload["decision"] == "accept"
    return {
        "experiment_id": EXPERIMENT_ID,
        "date": payload["completed_at"],
        "hypothesis": payload["hypothesis"],
        "change_type": "alpha_search",
        "changed_variable": "space_fast_5d_10d_same_theme_satcom_trend_pool_membership",
        "parameters": {
            "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
            "base_official_space_pool": payload["base_official_space_pool"],
            "extended_official_space_pool": payload["extended_official_space_pool"],
            "added_tickers": payload["added_tickers"],
            "candidate_universe": list(exp013.SATCOM_EXTENSION_CANDIDATES),
            "allowed_strategy_for_added_tickers": TARGET_STRATEGY,
            "forward_gate": payload["satcom_fast_5d_same_theme_gate"],
            "anti_js": "No JavaScript was used.",
        },
        "backtest_protocol": (
            "docs/backtesting.md fixed 3-window Space protocol using frozen "
            "Space augmented snapshots"
        ),
        "date_range": {
            label: spec
            for label, spec in exp024.exp041.source_diversity_exp.WINDOWS.items()
        },
        "before_metrics": before["aggregate"],
        "after_metrics": after["aggregate"],
        "by_window_before_metrics": {
            label: row["metrics"] for label, row in before["by_window"].items()
        },
        "by_window_after_metrics": {
            label: row["metrics"] for label, row in after["by_window"].items()
        },
        "by_window_delta": gate["by_window_delta_vs_before"],
        "expected_value_score_delta": gate["aggregate_delta_vs_before"][
            "expected_value_score_sum"
        ],
        "total_pnl_delta": gate["aggregate_delta_vs_before"]["total_pnl_sum"],
        "risk_distribution": {
            "before": _risk_distribution(before),
            "after": _risk_distribution(after),
        },
        "extension_trade_attribution": gate["extension_trade_attribution"],
        "gate_answers": {
            "1_alpha_hypothesis": (
                "Candidate-pool alpha: mature satcom tickers that pass both "
                "fast 5d all-benchmark validation and 10d same-theme replacement "
                "validation may add Space trend continuation value without the "
                "IRDM old-window displacement seen in exp-20260515-029."
            ),
            "2_prior_similar_experiments": [
                "exp-20260511-026 rejected broad mature-satcom breadth.",
                "exp-20260515-013 and exp-20260515-015 rejected fast-5d satcom admission on the earlier exp053 stack.",
                "exp-20260515-029 rejected current-stack IRDM/VSAT trend-only admission because old_thin regressed and drawdown worsened.",
                "This run changes the discriminator to require positive 10d same-theme replacement value, which keeps VSAT and excludes IRDM.",
            ],
            "3_single_causal_variable": (
                "Only the trend-only satcom extension membership changes from none to the 5d+10d same-theme-qualified ticker set."
            ),
            "4_success_criteria": (
                "Extension trades present, aggregate EV/PnL positive, at least "
                "two EV-improved windows, no EV-regressed windows, max drawdown "
                "drift <= 0.5 pp, survival >= 5%, and trade count >= 50."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260515_031_space_vsat_same_theme_satcom_trend_pool.py"
            ),
        },
        "gate_results": gate,
        "decision": payload["decision"],
        "rejection_reason": None
        if promoted
        else (
            "Gate 4 failed: the 5d+10d same-theme satcom trend-only admission "
            "did not improve the fixed three-window protocol without regression."
        ),
        "next_evidence_needed": None
        if promoted
        else (
            "Do not retry VSAT-only or nearby mature-satcom trend admission on "
            "these frozen windows without additional closed forward rows or a "
            "production-visible design that avoids old-window displacement."
        ),
        "production_impact": {
            "shared_policy_changed": promoted,
            "backtester_adapter_changed": promoted,
            "run_adapter_changed": promoted,
            "replay_only": not promoted,
            "parity_test_added": promoted,
            "live_slots": 0,
            "notes": (
                "If promoted, membership and trend-only scope must be expressed "
                "through shared space_catalyst_sleeve.py and observe-only reports; "
                "live Space slots remain zero."
                if promoted
                else "Experiment-only official-pool monkey patch; no live policy promoted."
            ),
        },
        "why_not_other_changes": (
            "LLM soft-ranking lacks attribution depth, ARKX/UFO theme-beta "
            "admission failed all windows, and adjacent source-diversity/defense "
            "trend scalars are sample-limited. This tests a materially stricter "
            "candidate-quality discriminator rather than a noisy ticker add."
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    before = payload["before_variant"]
    after = payload["after_variant"]
    gate = payload["gate_results"]
    promoted = payload["decision"] == "accept"
    lines = [
        f"# {EXPERIMENT_ID} Space VSAT same-theme satcom trend pool",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Single Changed Variable",
        (
            "`space_fast_5d_10d_same_theme_satcom_trend_pool_membership` on top "
            f"of accepted `{BEFORE_EXPERIMENT_ID}`."
        ),
        "",
        "## Gate 1 Baseline",
        f"- before experiment: `{BEFORE_EXPERIMENT_ID}` / `{BEFORE_STEM}`",
        f"- aggregate before EV: `{before['aggregate']['expected_value_score_sum']}`",
        f"- aggregate before PnL: `{before['aggregate']['total_pnl_sum']}`",
        f"- aggregate before max drawdown pct max: `{before['aggregate']['max_drawdown_pct_max']}`",
        "",
        "## Gate 2 Field Check",
        f"- open position field check passed: `{payload['field_check']['passed']}`",
        f"- 5d+10d same-theme satcom gate passed: `{payload['satcom_fast_5d_same_theme_gate']['passed']}`",
        f"- added tickers: `{payload['added_tickers']}`",
        f"- allowed strategy for added tickers: `{TARGET_STRATEGY}`",
        "",
        "## Gate 3 Survival Audit",
        f"- min survival before: `{before['aggregate']['min_survival_rate']}`",
        f"- min survival after: `{after['aggregate']['min_survival_rate']}`",
        "- no core filter was added; this is default-off Space candidate-scope membership.",
        "",
        "## Gate 4 Three-Window Result",
        "| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after | extension trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, delta in gate["by_window_delta_vs_before"].items():
        before_metrics = before["by_window"][label]["metrics"]
        after_metrics = after["by_window"][label]["metrics"]
        extension = gate["extension_trade_attribution"][label]["trade_count"]
        lines.append(
            "| {label} | {ev_before:.6f} | {ev_after:.6f} | {ev_delta:.6f} | {pnl_delta:.2f} | {dd_delta:.6f} | {trades_before} | {trades_after} | {extension} |".format(
                label=label,
                ev_before=before_metrics.get("expected_value_score", 0.0),
                ev_after=after_metrics.get("expected_value_score", 0.0),
                ev_delta=delta.get("expected_value_score", 0.0),
                pnl_delta=delta.get("total_pnl", 0.0),
                dd_delta=delta.get("max_drawdown_pct", 0.0),
                trades_before=before_metrics.get("trade_count", ""),
                trades_after=after_metrics.get("trade_count", ""),
                extension=extension,
            )
        )
    lines.extend(
        [
            "",
            "## Decision",
            f"- decision: `{payload['decision']}`",
            f"- Gate 4 passed: `{gate['passed']}`",
            f"- aggregate EV delta: `{gate['aggregate_delta_vs_before']['expected_value_score_sum']}`",
            f"- aggregate PnL delta: `{gate['aggregate_delta_vs_before']['total_pnl_sum']}`",
            f"- improved windows: `{gate['improved_windows']}`",
            f"- regressed windows: `{gate['regressed_windows']}`",
            f"- extension trades: `{gate['extension_trade_count']}`",
            f"- non-trend extension signals filtered: `{gate['non_trend_filtered_extension_signal_count']}`",
            "",
            "## Production Impact",
            "```text",
            "production_impact:",
            f"  shared_policy_changed: {str(promoted).lower()}",
            f"  backtester_adapter_changed: {str(promoted).lower()}",
            f"  run_adapter_changed: {str(promoted).lower()}",
            f"  replay_only: {str(not promoted).lower()}",
            f"  parity_test_added: {str(promoted).lower()}",
            "  live_slots: 0",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    gate = payload["gate_results"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["decision"],
        "summary": (
            "VSAT same-theme satcom trend pool "
            f"{payload['decision']} with EV delta "
            f"{gate['aggregate_delta_vs_before']['expected_value_score_sum']}."
        ),
        "artifact": str(ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.md"),
        "json": str(DATA_DIR / f"{STEM}.json"),
    }


def run() -> dict[str, Any]:
    LOGGER.info("Running %s", EXPERIMENT_ID)
    completed_at = datetime.now(timezone.utc).isoformat()
    base_pool = tuple(exp024.exp041.source_diversity_exp.OFFICIAL_SPACE_TICKERS)
    satcom_gate = _satcom_fast_5d_same_theme_gate()
    added = tuple(
        ticker for ticker in satcom_gate["target_tickers"] if ticker not in base_pool
    )
    extended_pool = tuple(sorted(set(base_pool) | set(added)))

    base_gates = exp029._collect_gates_with_pool(base_pool)
    extended_gates = exp029._collect_gates_with_pool(extended_pool)
    before = exp029._run_stack_with_pool(
        "accepted_exp024_base_pool",
        tickers=base_pool,
        gates=base_gates,
    )
    after = exp029._run_stack_with_pool(
        "current_stack_vsat_same_theme_satcom_trend_pool",
        tickers=extended_pool,
        gates=extended_gates,
        added_tickers=added,
    )
    gate = exp029._gate(after, before, added_tickers=added)
    field_check = exp021.exp051._open_position_field_check()
    decision = (
        "accept"
        if field_check["passed"] and satcom_gate["passed"] and gate["passed"]
        else "reject"
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "completed_at": completed_at,
        "hypothesis": (
            "VSAT has the mature satcom profile that the rejected IRDM/VSAT "
            "bundle lacked: all-positive 5d replacement evidence and positive "
            "10d same-theme replacement value. Adding only that ticker, trend "
            "only, may preserve the useful mid-window continuation while avoiding "
            "IRDM-driven breadth noise."
        ),
        "base_official_space_pool": list(base_pool),
        "extended_official_space_pool": list(extended_pool),
        "added_tickers": list(added),
        "base_gates": base_gates,
        "extended_gates": extended_gates,
        "satcom_fast_5d_same_theme_gate": satcom_gate,
        "field_check": field_check,
        "before_variant": before,
        "after_variant": after,
        "gate_results": gate,
        "decision": decision,
        "protocol": "docs/backtesting.md fixed 3-window Space protocol",
        "changed_variable": "space_fast_5d_10d_same_theme_satcom_trend_pool_membership",
    }
    payload["experiment_log_record"] = _experiment_record(payload)
    return payload


def persist(payload: dict[str, Any]) -> None:
    _write_json(DATA_DIR / f"{STEM}.json", payload)
    _write_json(LOG_DIR / f"{EXPERIMENT_ID}.json", payload["experiment_log_record"])
    _write_json(TICKET_DIR / f"{EXPERIMENT_ID}.json", _ticket(payload))
    artifact_path = ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.md"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_for_this_experiment(EXPERIMENT_LOG, payload["experiment_log_record"])


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    payload = run()
    persist(payload)
    gate = payload["gate_results"]
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "added_tickers": payload["added_tickers"],
                    "extension_trades": gate["extension_trade_count"],
                    "non_trend_filtered_extension_signals": gate[
                        "non_trend_filtered_extension_signal_count"
                    ],
                    "aggregate_ev_delta": gate["aggregate_delta_vs_before"][
                        "expected_value_score_sum"
                    ],
                    "aggregate_pnl_delta": gate["aggregate_delta_vs_before"][
                        "total_pnl_sum"
                    ],
                    "improved_windows": gate["improved_windows"],
                    "regressed_windows": gate["regressed_windows"],
                }
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
