"""exp-20260515-037: Space GSAT connectivity candidate pool.

Alpha search. Tests one candidate-pool variable on top of accepted
exp-20260515-024: whether the registry-defined GSAT satellite-connectivity
shadow record has enough replacement value to join the default-off official
Space pool.

This is not a broad satcom retry, ETF admission, LLM soft-ranking, or live-slot
change. It isolates the only non-mature-satcom satellite-connectivity shadow
candidate with full frozen Space OHLCV coverage and a production-visible
registry/event profile.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
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


EXPERIMENT_ID = "exp-20260515-037"
STEM = "space_gsat_connectivity_candidate_pool"
BEFORE_EXPERIMENT_ID = "exp-20260515-024"
BEFORE_STEM = "space_source_diversity_peer_nonleader_trend_risk"

DATA_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
DOCS_DIR = ROOT / "docs" / "experiments"
LOG_DIR = DOCS_DIR / "logs"
TICKET_DIR = DOCS_DIR / "tickets"
ARTIFACT_DIR = DOCS_DIR / "artifacts"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_PATH = ROOT / "data" / "universe_registry.json"
LEDGER_PATH = ROOT / "data" / "space_catalyst_event_state_shadow_ledger.jsonl"
SPACE_SNAPSHOT_DIR = (
    ROOT / "data" / "experiments" / "exp-20260510-028" / "ohlcv"
)

ADDED_TICKER = "GSAT"
ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_SCALAR = 1.025
MIN_SURVIVAL_RATE = 0.05
MIN_TRADE_COUNT = 50
MAX_DRAWDOWN_DAMAGE_VS_BEFORE = 0.005


def _safe(value: Any) -> Any:
    return exp024._safe(value)


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


def _load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8-sig"))


def _window_snapshot_path(label: str) -> Path:
    return SPACE_SNAPSHOT_DIR / f"exp-20260510-028_{label}_with_space_catalyst.json"


def _ohlcv_coverage(ticker: str) -> dict[str, Any]:
    windows: dict[str, Any] = {}
    for label, spec in exp024.exp041.source_diversity_exp.WINDOWS.items():
        path = _window_snapshot_path(label)
        if not path.exists():
            windows[label] = {
                "passed": False,
                "reason": "missing_space_augmented_snapshot",
                "path": str(path.relative_to(ROOT)),
            }
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = (data.get("ohlcv") or {}).get(ticker)
        if not isinstance(rows, list) or not rows:
            windows[label] = {
                "passed": False,
                "reason": "missing_ticker_ohlcv",
                "path": str(path.relative_to(ROOT)),
            }
            continue
        in_window = [
            row
            for row in rows
            if spec["start"] <= str(row.get("Date") or "")[:10] <= spec["end"]
        ]
        nonzero_volume = [
            row for row in in_window if float(row.get("Volume") or 0.0) > 0.0
        ]
        windows[label] = {
            "passed": bool(in_window and nonzero_volume),
            "path": str(path.relative_to(ROOT)),
            "row_count": len(rows),
            "in_window_row_count": len(in_window),
            "nonzero_volume_row_count": len(nonzero_volume),
            "first_date": str(rows[0].get("Date") or ""),
            "last_date": str(rows[-1].get("Date") or ""),
            "window_start": spec["start"],
            "window_end": spec["end"],
        }
    return {"passed": all(row["passed"] for row in windows.values()), "windows": windows}


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


def _horizon_values(row: dict[str, Any], horizon_name: str) -> dict[str, Any]:
    horizon = (row.get("horizons") or {}).get(horizon_name)
    if not isinstance(horizon, dict):
        return {"status": "missing"}
    return {
        "status": horizon.get("status"),
        "cash_relative_pnl": _as_float(horizon.get("cash_relative_pnl")),
        "same_theme_replacement_value": _as_float(
            horizon.get("same_theme_replacement_value")
        ),
        "spy_relative_value": _as_float(horizon.get("spy_relative_value")),
        "qqq_relative_value": _as_float(horizon.get("qqq_relative_value")),
        "ufo_relative_value": _as_float(horizon.get("ufo_relative_value")),
        "arkx_relative_value": _as_float(horizon.get("arkx_relative_value")),
        "event_return": _as_float(horizon.get("event_return")),
    }


def _gsat_candidate_gate() -> dict[str, Any]:
    registry = _load_registry()
    record = (registry.get("tickers") or {}).get(ADDED_TICKER) or {}
    coverage = _ohlcv_coverage(ADDED_TICKER)
    checks = {
        "registry_record_present": bool(record),
        "status_is_research": record.get("status") == "research",
        "pilot_sleeve_is_space_shadow": (
            record.get("pilot_sleeve") == "SPACE_CATALYST_SHADOW"
        ),
        "theme_is_satellite_connectivity": (
            record.get("theme") == "space_satellite_connectivity"
        ),
        "theme_segment_is_satellite_connectivity": (
            record.get("theme_segment") == "satellite_connectivity"
        ),
        "not_mature_satcom_theme": record.get("theme") != "space_mature_satcom",
        "not_theme_beta_benchmark": record.get("theme_segment") != "theme_beta_benchmark",
        "requires_event_guard": record.get("requires_event_guard") is True,
        "connectivity_partner_profile": (
            "connectivity_partner"
            in str(record.get("event_guard_profile") or "").lower()
        ),
        "max_capital_scalar_zero_before_experiment": (
            float(record.get("max_capital_scalar") or 0.0) == 0.0
        ),
        "non_live_candidate_before_experiment": (
            record.get("first_trade_allowed_as_of") is None
        ),
        "ohlcv_all_windows_present": coverage["passed"],
    }

    event_rows = [
        row
        for row in _latest_event_rows(LEDGER_PATH)
        if str(row.get("ticker") or "").upper() == ADDED_TICKER
        and str(row.get("semantic_bucket") or "") == "defense_budget_theme"
        and str(row.get("source_type") or "") == "official_government_release"
        and "government_space_contract" in {str(item) for item in row.get("event_fields") or []}
    ]
    latest_row = event_rows[0] if event_rows else {}
    h10 = _horizon_values(latest_row, "10d") if latest_row else {"status": "missing"}
    checks["official_government_contract_event_present"] = bool(event_rows)
    checks["mature_10d_cash_positive"] = (
        h10.get("status") == "mature"
        and _as_float(h10.get("cash_relative_pnl")) is not None
        and float(h10["cash_relative_pnl"]) > 0.0
    )

    failed_checks = sorted(key for key, value in checks.items() if not value)
    passed = not failed_checks
    return {
        "passed": passed,
        "source_gate": "space_gsat_connectivity_registry_event_profile",
        "registry_path": str(REGISTRY_PATH.relative_to(ROOT)),
        "ledger_path": str(LEDGER_PATH.relative_to(ROOT)),
        "candidate_universe": [ADDED_TICKER],
        "target_definition": (
            "GSAT registry-defined satellite_connectivity Space shadow record "
            "with full frozen Space OHLCV coverage, official Golden Dome "
            "government-contract event evidence, and mature 10d cash-positive "
            "event return; excludes mature_satcom and theme-beta ETF records."
        ),
        "target_tickers": [ADDED_TICKER] if passed else [],
        "profiles": {
            ADDED_TICKER: {
                "passed": passed,
                "failed_checks": failed_checks,
                "registry": {
                    key: record.get(key)
                    for key in (
                        "status",
                        "theme",
                        "pilot_sleeve",
                        "theme_segment",
                        "history_class",
                        "liquidity_tier",
                        "max_capital_scalar",
                        "max_risk_scalar",
                        "requires_event_guard",
                        "event_guard_profile",
                        "first_trade_allowed_as_of",
                        "notes",
                    )
                },
                "checks": checks,
                "ohlcv_coverage": coverage,
                "event_profile": {
                    "event_row_count": len(event_rows),
                    "sample_event": {
                        key: latest_row.get(key)
                        for key in (
                            "event_id",
                            "event_date",
                            "semantic_bucket",
                            "source_type",
                            "event_fields",
                            "closed_decision",
                            "outcome_status",
                        )
                    }
                    if latest_row
                    else None,
                    "horizons": {
                        name: _horizon_values(latest_row, name)
                        for name in ("1d", "5d", "10d", "20d")
                    }
                    if latest_row
                    else {},
                },
            }
        },
        "failed_checks": failed_checks,
    }


def _collect_gates_with_pool(tickers: tuple[str, ...]) -> dict[str, Any]:
    with exp013._official_space_pool(tickers):
        gates = exp021._collect_gates()
    gates["official_space_pool"] = list(tickers)
    gates["gsat_candidate_gate"] = _gsat_candidate_gate()
    return gates


def _run_with_pool(
    label: str,
    tickers: tuple[str, ...],
    gates: dict[str, Any],
    added_tickers: tuple[str, ...],
) -> dict[str, Any]:
    with exp013._official_space_pool(tickers):
        variant = exp024._run_exp021_stack_variant(
            label,
            peer_nonleader_scalar=ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_SCALAR,
            gates=gates,
        )
    variant["parameters"] = {
        **variant["parameters"],
        "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
        "official_space_pool": list(tickers),
        "gsat_connectivity_added_tickers": list(added_tickers),
        "space_gsat_connectivity_candidate_pool_rule": (
            "add only the registry-defined GSAT satellite-connectivity shadow "
            "candidate after the production-visible registry/event/coverage gate"
        ),
        "accepted_source_diversity_peer_nonleader_trend_scalar": (
            ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_SCALAR
        ),
    }
    return variant


def _aggregate_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    return exp024.exp041.source_diversity_exp._aggregate_delta(
        after["aggregate"],
        before["aggregate"],
    )


def _by_window_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    return {
        label: exp024.exp041.source_diversity_exp._delta(
            row["metrics"],
            before["by_window"][label]["metrics"],
        )
        for label, row in after["by_window"].items()
    }


def _space_trades_by_extension(variant: dict[str, Any]) -> dict[str, Any]:
    targets = set(variant["parameters"].get("gsat_connectivity_added_tickers") or [])
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
        "changed_variable": "space_gsat_connectivity_candidate_pool_membership",
        "parameters": {
            "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
            "base_official_space_pool": payload["base_official_space_pool"],
            "added_tickers": payload["added_tickers"],
            "candidate_gate": payload["gsat_candidate_gate"],
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
        "extension_trade_attribution": payload["extension_trade_attribution"],
        "gate_results": gate,
        "decision": payload["decision"],
        "rejection_reason": None
        if promoted
        else (
            "Gate 4 failed: GSAT candidate-pool admission did not improve the "
            "fixed Space three-window replay without regression."
        ),
        "next_evidence_needed": None
        if promoted
        else (
            "Do not add GSAT or adjacent satellite-connectivity candidates to "
            "the Space pool without new closed forward rows or a stronger "
            "production-visible catalyst-quality discriminator."
        ),
        "production_impact": {
            "shared_policy_changed": promoted,
            "backtester_adapter_changed": False,
            "run_adapter_changed": promoted,
            "replay_only": True,
            "parity_test_added": promoted,
            "live_slots": 0,
            "notes": (
                "If promoted, Space candidate membership must be represented in "
                "shared space_catalyst_sleeve.py and production observation "
                "metadata before any trade-enabled adapter; live slots remain zero."
                if promoted
                else "Experiment-only official-pool monkey patch; no live policy promoted."
            ),
        },
        "gate_answers": {
            "1_alpha_hypothesis": (
                "Candidate-pool extension: GSAT may be a cleaner satellite-"
                "connectivity candidate than rejected mature-satcom/ETF "
                "expansions because it is a registry-defined Space shadow record "
                "with official event evidence and full frozen OHLCV coverage."
            ),
            "2_prior_similar_experiments": [
                "exp-20260515-019 rejected ARKX/UFO theme-beta ETF admission.",
                "exp-20260515-031 and exp-20260515-035 rejected VSAT mature-satcom admission even with stricter fallback design.",
                "No prior experiment found that isolates GSAT satellite-connectivity candidate-pool membership on top of exp-20260515-024.",
            ],
            "3_single_causal_variable": (
                "Only GSAT membership in the default-off official Space pool changes."
            ),
            "4_success_criteria": (
                "Extension trades present, aggregate EV/PnL positive, at least "
                "two EV-improved windows, no EV-regressed windows, max drawdown "
                "drift <= 0.5 pp, survival >= 5%, and trade count >= 50."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260515_037_space_gsat_connectivity_candidate_pool.py"
            ),
        },
        "why_not_other_changes": (
            "LLM soft-ranking remains data-limited, contract/profile mining has "
            "already failed or become adjacent, and mature-satcom plus theme-ETF "
            "pool expansion were rejected. This run tests one distinct registry "
            "Space candidate instead of adding a noisy ticker basket."
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    before = payload["before_variant"]
    after = payload["after_variant"]
    gate = payload["gate_results"]
    promoted = payload["decision"] == "accept"
    lines = [
        f"# {EXPERIMENT_ID} Space GSAT connectivity candidate pool",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Single Changed Variable",
        "`space_gsat_connectivity_candidate_pool_membership` on top of accepted "
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
        f"- GSAT candidate gate passed: `{payload['gsat_candidate_gate']['passed']}`",
        f"- added tickers: `{payload['added_tickers']}`",
        f"- failed candidate checks: `{payload['gsat_candidate_gate']['failed_checks']}`",
        "",
        "## Gate 3 Survival Audit",
        f"- min survival before: `{before['aggregate']['min_survival_rate']}`",
        f"- min survival after: `{after['aggregate']['min_survival_rate']}`",
        "- no new filter was added; this is candidate membership under a registry/event/coverage gate.",
        "",
        "## Gate 4 Three-Window Result",
        "| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after | GSAT trades |",
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
            f"- GSAT trades: `{gate['extension_trade_count']}`",
            "",
            "## Production Impact",
            "```text",
            "production_impact:",
            f"  shared_policy_changed: {str(promoted).lower()}",
            "  backtester_adapter_changed: false",
            f"  run_adapter_changed: {str(promoted).lower()}",
            "  replay_only: true",
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
            f"GSAT connectivity candidate pool {payload['decision']} with EV "
            f"delta {gate['aggregate_delta_vs_before']['expected_value_score_sum']}."
        ),
        "artifact": str(ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.md"),
        "json": str(DATA_DIR / f"{STEM}.json"),
    }


def run() -> dict[str, Any]:
    completed_at = datetime.now(timezone.utc).isoformat()
    base_pool = tuple(exp024.exp041.source_diversity_exp.OFFICIAL_SPACE_TICKERS)
    candidate_gate = _gsat_candidate_gate()
    added = (ADDED_TICKER,) if candidate_gate["passed"] and ADDED_TICKER not in base_pool else ()
    extended_pool = tuple(sorted(set(base_pool) | set(added)))

    base_gates = _collect_gates_with_pool(base_pool)
    extended_gates = _collect_gates_with_pool(extended_pool)
    before = _run_with_pool("accepted_exp024_base_pool", base_pool, base_gates, ())
    after = _run_with_pool(
        "gsat_connectivity_extended_pool",
        extended_pool,
        extended_gates,
        added,
    )
    gate = _gate(after, before)
    field_check = exp024.exp051._open_position_field_check()
    decision = (
        "accept"
        if field_check["passed"] and candidate_gate["passed"] and gate["passed"]
        else "reject"
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "completed_at": completed_at,
        "hypothesis": (
            "GSAT may be a cleaner Space satellite-connectivity candidate-pool "
            "extension than rejected mature-satcom or theme-ETF admissions "
            "because it is registry-defined, event-guarded, non-live, has full "
            "frozen OHLCV coverage, and has official Golden Dome event evidence."
        ),
        "base_official_space_pool": list(base_pool),
        "extended_official_space_pool": list(extended_pool),
        "added_tickers": list(added),
        "gsat_candidate_gate": candidate_gate,
        "field_check": field_check,
        "base_gates": base_gates,
        "extended_gates": extended_gates,
        "before_variant": before,
        "after_variant": after,
        "extension_trade_attribution": _space_trades_by_extension(after),
        "gate_results": gate,
        "decision": decision,
        "protocol": "docs/backtesting.md fixed 3-window Space protocol",
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
                    "candidate_gate_passed": payload["gsat_candidate_gate"]["passed"],
                    "extension_trades": gate["extension_trade_count"],
                    "aggregate_ev_delta": gate["aggregate_delta_vs_before"][
                        "expected_value_score_sum"
                    ],
                    "aggregate_pnl_delta": gate["aggregate_delta_vs_before"][
                        "total_pnl_sum"
                    ],
                    "improved_windows": gate["improved_windows"],
                    "regressed_windows": gate["regressed_windows"],
                    "anti_js": "No JavaScript was used.",
                }
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
