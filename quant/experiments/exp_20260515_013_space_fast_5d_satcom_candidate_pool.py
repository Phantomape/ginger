"""exp-20260515-013: Space fast-5d satcom candidate pool.

Tests one candidate-pool variable on top of the accepted exp-20260514-053
Space stack: add only mature satcom tickers whose shadow ledger has all-positive
5d confirmation versus cash, same-theme replacement, SPY, QQQ, UFO, and ARKX.

This is not a broad ticker expansion. It follows the rejected satcom-breadth
retry condition by requiring new forward-ledger evidence before retesting IRDM,
VSAT, or SATS.
"""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from copy import deepcopy
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

import exp_20260515_012_space_fast_5d_benchmark_trend_risk as exp012


EXPERIMENT_ID = "exp-20260515-013"
STEM = "space_fast_5d_satcom_candidate_pool"
BEFORE_EXPERIMENT_ID = "exp-20260514-053"
BEFORE_STEM = "space_benchmark_breadth_iwm_leader_trend_risk"

DATA_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
DOCS_DIR = ROOT / "docs" / "experiments"
LOG_DIR = DOCS_DIR / "logs"
TICKET_DIR = DOCS_DIR / "tickets"
ARTIFACT_DIR = DOCS_DIR / "artifacts"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"
LEDGER_PATH = ROOT / "data" / "space_catalyst_event_state_shadow_ledger.jsonl"

SATCOM_EXTENSION_CANDIDATES = ("IRDM", "VSAT", "SATS")
FORWARD_HORIZON = "5d"
MIN_SURVIVAL_RATE = 0.05
MIN_TRADE_COUNT = 50
MAX_DRAWDOWN_DAMAGE_VS_BEFORE = 0.005


def _safe(value: Any) -> Any:
    return exp012._safe(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    exp012._write_json(path, payload)


def _append_jsonl_for_this_experiment(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                lines.append(line)
                continue
            if row.get("experiment_id") != EXPERIMENT_ID:
                lines.append(line)
    lines.append(json.dumps(_safe(payload), ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _as_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _latest_event_rows(path: Path) -> list[dict[str, Any]]:
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    if not path.exists():
        return []
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        ticker = str(row.get("ticker") or "").upper()
        event_id = str(row.get("event_id") or "")
        if not ticker or not event_id:
            continue
        key = (ticker, event_id)
        stamp = str(row.get("logged_at") or row.get("asof_date") or "")
        previous = latest.get(key)
        previous_stamp = str(
            (previous or {}).get("logged_at") or (previous or {}).get("asof_date") or ""
        )
        if previous is None or stamp >= previous_stamp:
            latest[key] = row
    return list(latest.values())


def _satcom_fast_5d_gate() -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    skipped: dict[str, int] = {}

    def skip(reason: str) -> None:
        skipped[reason] = skipped.get(reason, 0) + 1

    for row in _latest_event_rows(LEDGER_PATH):
        ticker = str(row.get("ticker") or "").upper()
        if ticker not in SATCOM_EXTENSION_CANDIDATES:
            skip("not_satcom_extension_candidate")
            continue
        if str(row.get("semantic_bucket") or "") == "attention_only":
            skip("attention_only")
            continue
        horizon = (row.get("horizons") or {}).get(FORWARD_HORIZON)
        if not isinstance(horizon, dict) or horizon.get("status") != "mature":
            skip("missing_mature_5d")
            continue
        values = {
            "cash_relative_pnl": _as_float(horizon.get("cash_relative_pnl")),
            "same_theme_replacement_value": _as_float(
                horizon.get("same_theme_replacement_value")
            ),
            "spy_relative_value": _as_float(horizon.get("spy_relative_value")),
            "qqq_relative_value": _as_float(horizon.get("qqq_relative_value")),
            "ufo_relative_value": _as_float(horizon.get("ufo_relative_value")),
            "arkx_relative_value": _as_float(horizon.get("arkx_relative_value")),
        }
        if any(value is None for value in values.values()):
            skip("missing_5d_values")
            continue
        if not all(float(value) > 0.0 for value in values.values()):
            skip("not_all_5d_positive")
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
                "horizon": FORWARD_HORIZON,
                **values,
            }
        )

    profiles: dict[str, dict[str, Any]] = {}
    for ticker, rows in sorted(grouped.items()):
        profiles[ticker] = {
            "passed": True,
            "ticker": ticker,
            "horizon": FORWARD_HORIZON,
            "closed_event_count": len(rows),
            "avg_5d_cash_relative_pnl": round(
                mean(float(row["cash_relative_pnl"]) for row in rows), 6
            ),
            "avg_5d_same_theme_replacement_value": round(
                mean(float(row["same_theme_replacement_value"]) for row in rows), 6
            ),
            "avg_5d_spy_relative_value": round(
                mean(float(row["spy_relative_value"]) for row in rows), 6
            ),
            "avg_5d_qqq_relative_value": round(
                mean(float(row["qqq_relative_value"]) for row in rows), 6
            ),
            "avg_5d_ufo_relative_value": round(
                mean(float(row["ufo_relative_value"]) for row in rows), 6
            ),
            "avg_5d_arkx_relative_value": round(
                mean(float(row["arkx_relative_value"]) for row in rows), 6
            ),
            "semantic_buckets": sorted({str(row["semantic_bucket"]) for row in rows}),
            "source_types": sorted({str(row["source_type"]) for row in rows}),
            "event_ids": sorted({str(row["event_id"]) for row in rows}),
            "rows": rows,
        }

    return {
        "passed": bool(profiles),
        "source_gate": "space_fast_5d_satcom_candidate_profile",
        "path": str(LEDGER_PATH.relative_to(ROOT)),
        "candidate_universe": list(SATCOM_EXTENSION_CANDIDATES),
        "target_definition": (
            "satcom extension ticker with mature 5d profile positive versus "
            "cash, same-theme replacement, SPY, QQQ, UFO, and ARKX"
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
        },
        "skipped_counts": dict(sorted(skipped.items())),
    }


def _modules_with_official_space_tickers() -> list[Any]:
    modules = []
    for module in list(sys.modules.values()):
        if module is None:
            continue
        name = str(getattr(module, "__name__", ""))
        if not name.startswith("exp_202605"):
            continue
        if hasattr(module, "OFFICIAL_SPACE_TICKERS"):
            modules.append(module)
    return modules


@contextmanager
def _official_space_pool(tickers: tuple[str, ...]):
    originals: list[tuple[Any, tuple[str, ...]]] = []
    for module in _modules_with_official_space_tickers():
        current = tuple(getattr(module, "OFFICIAL_SPACE_TICKERS"))
        originals.append((module, current))
        setattr(module, "OFFICIAL_SPACE_TICKERS", tickers)
    try:
        yield
    finally:
        for module, current in originals:
            setattr(module, "OFFICIAL_SPACE_TICKERS", current)


def _collect_gates_with_pool(tickers: tuple[str, ...]) -> dict[str, Any]:
    with _official_space_pool(tickers):
        gates = exp012._collect_gates()
    gates["official_space_pool"] = list(tickers)
    gates["satcom_fast_5d_candidate_gate"] = _satcom_fast_5d_gate()
    return gates


def _run_with_pool(label: str, tickers: tuple[str, ...], gates: dict[str, Any]) -> dict[str, Any]:
    with _official_space_pool(tickers):
        variant = exp012._run_exp053_stack_variant(
            label,
            fast_5d_scalar=1.0,
            gates=gates,
        )
    variant["parameters"] = {
        **variant["parameters"],
        "official_space_pool": list(tickers),
        "satcom_fast_5d_added_tickers": [
            ticker
            for ticker in tickers
            if ticker
            not in exp012.exp041.source_diversity_exp.OFFICIAL_SPACE_TICKERS
        ],
        "space_fast_5d_satcom_candidate_pool_rule": (
            "add mature satcom tickers with all-positive 5d cash, same-theme, "
            "SPY, QQQ, UFO, and ARKX confirmation"
        ),
    }
    return variant


def _aggregate_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    return exp012.exp041.source_diversity_exp._aggregate_delta(
        after["aggregate"],
        before["aggregate"],
    )


def _by_window_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    return {
        label: exp012.exp041.source_diversity_exp._delta(
            row["metrics"],
            before["by_window"][label]["metrics"],
        )
        for label, row in after["by_window"].items()
    }


def _space_trades_by_extension(variant: dict[str, Any]) -> dict[str, Any]:
    targets = set(variant["parameters"].get("satcom_fast_5d_added_tickers") or [])
    by_window: dict[str, Any] = {}
    for label, row in variant["by_window"].items():
        attribution = row.get("official_space_trade_attribution") or row.get(
            "space_trade_attribution"
        ) or {}
        trades = [
            trade
            for trade in attribution.get("trades") or []
            if str(trade.get("ticker") or "").upper() in targets
        ]
        by_window[label] = {
            "trade_count": len(trades),
            "total_pnl": round(sum(float(trade.get("pnl") or 0.0) for trade in trades), 2),
            "wins": sum(1 for trade in trades if float(trade.get("pnl") or 0.0) > 0.0),
            "losses": sum(1 for trade in trades if float(trade.get("pnl") or 0.0) < 0.0),
            "trades": trades,
        }
    return by_window


def _gate(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = _aggregate_delta(after, before)
    by_window_delta = _by_window_delta(after, before)
    ev_improved = {
        label: row["expected_value_score"]
        for label, row in by_window_delta.items()
        if row["expected_value_score"] > 1e-9
    }
    ev_regressed = {
        label: row["expected_value_score"]
        for label, row in by_window_delta.items()
        if row["expected_value_score"] < -1e-9
    }
    extension_trade_count = sum(
        row["trade_count"] for row in _space_trades_by_extension(after).values()
    )
    passed = bool(
        extension_trade_count > 0
        and aggregate_delta["expected_value_score_sum"] > 0.0
        and aggregate_delta["total_pnl_sum"] > 0.0
        and len(ev_improved) >= 2
        and not ev_regressed
        and aggregate_delta["max_drawdown_pct_max"] <= MAX_DRAWDOWN_DAMAGE_VS_BEFORE
        and after["aggregate"].get("min_survival_rate", 0.0) >= MIN_SURVIVAL_RATE
        and after["aggregate"].get("trade_count_sum", 0) >= MIN_TRADE_COUNT
    )
    return {
        "aggregate_delta_vs_before": aggregate_delta,
        "by_window_delta_vs_before": by_window_delta,
        "passed": passed,
        "improved_windows": ev_improved,
        "regressed_windows": ev_regressed,
        "extension_trade_count": extension_trade_count,
        "reasons": {
            "extension_trades_present": extension_trade_count > 0,
            "aggregate_ev_delta_positive": aggregate_delta["expected_value_score_sum"]
            > 0.0,
            "aggregate_pnl_delta_positive": aggregate_delta["total_pnl_sum"] > 0.0,
            "at_least_two_windows_improved": len(ev_improved) >= 2,
            "no_window_regressed": not ev_regressed,
            "drawdown_delta_within_limit": (
                aggregate_delta["max_drawdown_pct_max"]
                <= MAX_DRAWDOWN_DAMAGE_VS_BEFORE
            ),
            "survival_rate_ok": after["aggregate"].get("min_survival_rate", 0.0)
            >= MIN_SURVIVAL_RATE,
            "trade_count_ok": after["aggregate"].get("trade_count_sum", 0)
            >= MIN_TRADE_COUNT,
        },
    }


def _risk_distribution(variant: dict[str, Any]) -> dict[str, dict[str, Any]]:
    keys = ("worst_trade_pct", "max_consecutive_losses", "tail_loss_share")
    return {
        label: {key: row["metrics"].get(key) for key in keys}
        for label, row in variant["by_window"].items()
    }


def _experiment_record(payload: dict[str, Any]) -> dict[str, Any]:
    promoted = payload["decision"] == "accept"
    before = payload["before_variant"]
    after = payload["after_variant"]
    gate = payload["gate_results"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "date": payload["completed_at"],
        "hypothesis": payload["hypothesis"],
        "change_type": "alpha_search",
        "changed_variable": "space_fast_5d_satcom_candidate_pool_membership",
        "parameters": {
            "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
            "base_official_space_pool": payload["base_official_space_pool"],
            "added_tickers": payload["added_tickers"],
            "candidate_universe": list(SATCOM_EXTENSION_CANDIDATES),
            "forward_horizon": FORWARD_HORIZON,
            "satcom_fast_5d_gate": payload["satcom_fast_5d_gate"],
            "anti_js": "No JavaScript was used.",
        },
        "backtest_protocol": (
            "docs/backtesting.md fixed 3-window Space protocol using frozen "
            "Space augmented snapshots"
        ),
        "date_range": {
            label: spec
            for label, spec in exp012.exp041.source_diversity_exp.WINDOWS.items()
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
        "extension_trade_attribution": payload["extension_trade_attribution"],
        "gate_results": gate,
        "decision": payload["decision"],
        "rejection_reason": None
        if promoted
        else (
            "Gate 4 failed: forward-qualified satcom pool extension did not "
            "improve enough fixed windows without regression."
        ),
        "next_evidence_needed": None
        if promoted
        else (
            "Do not retry IRDM/VSAT/SATS candidate admission without new closed "
            "forward rows or a tighter ex-ante event-quality discriminator."
        ),
        "production_impact": {
            "shared_policy_changed": promoted,
            "backtester_adapter_changed": False,
            "run_adapter_changed": promoted,
            "replay_only": True,
            "parity_test_added": promoted,
            "live_slots": 0,
            "notes": (
                "If promoted, official Space candidate membership must be "
                "represented in shared space_catalyst_sleeve.py and surfaced "
                "through the daily observe-only path; live slots remain zero."
                if promoted
                else "Experiment-only official-pool monkey patch; no live policy promoted."
            ),
        },
        "why_not_other_changes": (
            "LLM soft-ranking remains data-limited, nearby Space scalars have "
            "been exhausted, and broad satcom admission was previously rejected. "
            "This tests only the new fast-5d forward evidence gate requested by "
            "the prior satcom rejection."
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    before = payload["before_variant"]
    after = payload["after_variant"]
    gate = payload["gate_results"]
    lines = [
        f"# {EXPERIMENT_ID} Space fast-5d satcom candidate pool",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Single Changed Variable",
        "`space_fast_5d_satcom_candidate_pool_membership` on top of accepted "
        f"`{BEFORE_EXPERIMENT_ID}`. Entries, exits, ranking, stops, LLM/news, "
        "and live Space slots stay fixed.",
        "",
        "## Gate 1 Baseline",
        f"- before experiment: `{BEFORE_EXPERIMENT_ID}` / `{BEFORE_STEM}`",
        f"- aggregate before EV: `{before['aggregate']['expected_value_score_sum']}`",
        f"- aggregate before PnL: `{before['aggregate']['total_pnl_sum']}`",
        f"- aggregate before max drawdown pct max: `{before['aggregate']['max_drawdown_pct_max']}`",
        "",
        "## Gate 2 Field Check",
        f"- open position field check passed: `{payload['field_check']['passed']}`",
        f"- satcom fast-5d gate passed: `{payload['satcom_fast_5d_gate']['passed']}`",
        f"- added tickers: `{payload['added_tickers']}`",
        "",
        "## Gate 3 Survival Audit",
        f"- min survival before: `{before['aggregate']['min_survival_rate']}`",
        f"- min survival after: `{after['aggregate']['min_survival_rate']}`",
        "- no new filter was added; this is candidate membership under a forward-evidence gate.",
        "",
        "## Gate 4 Three-Window Result",
        "| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after | extension trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, delta in gate["by_window_delta_vs_before"].items():
        before_metrics = before["by_window"][label]["metrics"]
        after_metrics = after["by_window"][label]["metrics"]
        extension = payload["extension_trade_attribution"][label]["trade_count"]
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
            "",
            "## Production Impact",
            "```text",
            "production_impact:",
            f"  shared_policy_changed: {str(payload['decision'] == 'accept').lower()}",
            "  backtester_adapter_changed: false",
            f"  run_adapter_changed: {str(payload['decision'] == 'accept').lower()}",
            "  replay_only: true",
            f"  parity_test_added: {str(payload['decision'] == 'accept').lower()}",
            "  live_slots: 0",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["decision"],
        "summary": (
            "Fast-5d satcom candidate pool "
            f"{payload['decision']} with EV delta "
            f"{payload['gate_results']['aggregate_delta_vs_before']['expected_value_score_sum']}."
        ),
        "artifact": str(ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.md"),
        "json": str(DATA_DIR / f"{STEM}.json"),
    }


def run() -> dict[str, Any]:
    completed_at = datetime.now(timezone.utc).isoformat()
    base_pool = tuple(exp012.exp041.source_diversity_exp.OFFICIAL_SPACE_TICKERS)
    satcom_gate = _satcom_fast_5d_gate()
    added = tuple(
        ticker for ticker in satcom_gate["target_tickers"] if ticker not in base_pool
    )
    extended_pool = tuple(sorted(set(base_pool) | set(added)))

    base_gates = _collect_gates_with_pool(base_pool)
    extended_gates = _collect_gates_with_pool(extended_pool)
    before = _run_with_pool("accepted_exp053_base_pool", base_pool, base_gates)
    after = _run_with_pool(
        "fast_5d_satcom_extended_pool",
        extended_pool,
        extended_gates,
    )
    gate = _gate(after, before)
    field_check = exp012.exp051._open_position_field_check()
    decision = (
        "accept"
        if field_check["passed"] and satcom_gate["passed"] and gate["passed"]
        else "reject"
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "completed_at": completed_at,
        "hypothesis": (
            "Mature satcom tickers with all-positive 5d forward confirmation "
            "may be a cleaner Space candidate-pool extension than the rejected "
            "broad IRDM/VSAT/SATS satcom breadth test."
        ),
        "base_official_space_pool": list(base_pool),
        "extended_official_space_pool": list(extended_pool),
        "added_tickers": list(added),
        "satcom_fast_5d_gate": satcom_gate,
        "field_check": field_check,
        "base_gates": base_gates,
        "extended_gates": extended_gates,
        "before_variant": before,
        "after_variant": after,
        "extension_trade_attribution": _space_trades_by_extension(after),
        "gate_results": gate,
        "decision": decision,
        "protocol": "docs/backtesting.md fixed 3-window Space protocol",
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate pool: forward-confirmed mature satcom names may add "
                "Space replacement value without broad ticker noise."
            ),
            "2_history_check": {
                "exp-20260511-026": (
                    "Rejected broad IRDM/VSAT/SATS low-risk extension and asked "
                    "for PIT official event-state or forward-ledger evidence; "
                    "this run adds only all-positive mature 5d ledger names."
                ),
                "exp-20260514-015": (
                    "Rejected VSAT-only 10d candidate risk; this run is a binary "
                    "forward-qualified membership rule, not a VSAT scalar."
                ),
                "exp-20260514-021": (
                    "Rejected IRDM trend-only scalar; this run requires the new "
                    "all-benchmark 5d gate and evaluates the pool rule."
                ),
            },
            "3_single_causal_variable": (
                "space_fast_5d_satcom_candidate_pool_membership. Accepted Space "
                "risk stack, entries, exits, ranking, LLM/news, and live slots "
                "stay fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed Space windows; require positive "
                "aggregate EV and PnL, at least two EV-improved windows, no "
                "EV-regressed window, max drawdown drift <= 0.5 pp, survival >= "
                "5%, >=50 trades, and nonzero extension trades."
            ),
            "5_reproducibility": (
                f".venv\\Scripts\\python.exe quant\\experiments\\{Path(__file__).name}"
            ),
        },
    }
    payload["experiment_log_record"] = _experiment_record(payload)
    return payload


def persist(payload: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    TICKET_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    artifact = _artifact_markdown(payload)
    payload["artifact_markdown"] = artifact
    _write_json(DATA_DIR / f"{STEM}.json", payload)
    _write_json(LOG_DIR / f"{EXPERIMENT_ID}.json", payload["experiment_log_record"])
    _write_json(TICKET_DIR / f"{EXPERIMENT_ID}.json", _ticket(payload))
    (ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.md").write_text(
        artifact,
        encoding="utf-8",
    )
    _append_jsonl_for_this_experiment(EXPERIMENT_LOG, payload["experiment_log_record"])


def main() -> None:
    payload = run()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "added_tickers": payload["added_tickers"],
                    "extension_trade_count": payload["gate_results"][
                        "extension_trade_count"
                    ],
                    "aggregate_ev_delta": payload["gate_results"][
                        "aggregate_delta_vs_before"
                    ]["expected_value_score_sum"],
                    "aggregate_pnl_delta": payload["gate_results"][
                        "aggregate_delta_vs_before"
                    ]["total_pnl_sum"],
                    "improved_windows": payload["gate_results"]["improved_windows"],
                    "regressed_windows": payload["gate_results"]["regressed_windows"],
                }
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
